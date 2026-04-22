"""
main.py  –  FastAPI backend for IoT Healthcare Patient Monitor v5.2.
"""

import asyncio
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from jose import JWTError, ExpiredSignatureError, jwt

import auth
import crud
import data_sources
import models
import schemas
import whatsapp_notifier
from database import engine, Base, SessionLocal, require_redis_on_startup, get_redis_client, is_redis_available
from json_logger import setup_logging, request_id_var, generate_request_id
from rate_limiter import limiter, setup_rate_limiter, LOGIN_LIMIT
from exception_handlers import setup_exception_handlers
from logger import log_security_event, request_ip, sanitize_headers
from security_utils import (
    FAILED_LOGIN_BLOCK_SECONDS,
    bind_refresh_session,
    can_access_patient_abac,
    clear_refresh_session,
    detect_suspicious_refresh_activity,
    is_ip_blocked,
    register_failed_login,
    reset_failed_login,
    validate_refresh_request,
)

# ── Setup structured logging ─────────────────────────────────────────────────
setup_logging()

# ── Redis startup check ───────────────────────────────────────────────────────
require_redis_on_startup()

# ── Create tables ─────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)


def _ensure_source_partition_columns() -> None:
    """Backfill schema on existing deployments without requiring manual migration."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE vitals ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'fake'"))
        conn.execute(text("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'fake'"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vitals_source ON vitals (source)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts (source)"))
        conn.execute(text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'ck_vitals_source'
                ) THEN
                    ALTER TABLE vitals
                    ADD CONSTRAINT ck_vitals_source CHECK (source IN ('fake','thingspeak'));
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'ck_alerts_source'
                ) THEN
                    ALTER TABLE alerts
                    ADD CONSTRAINT ck_alerts_source CHECK (source IN ('fake','thingspeak'));
                END IF;
            END
            $$;
            """
        ))


_ensure_source_partition_columns()

logger = logging.getLogger(__name__)

# ── WebSocket config ──────────────────────────────────────────────────────────
WS_CONNECTION_LIMIT = int(os.getenv("WS_CONNECTION_LIMIT", "50"))
WS_USER_CONNECTION_LIMIT = int(os.getenv("WS_USER_CONNECTION_LIMIT", "5"))
WS_MESSAGES_PER_MINUTE = int(os.getenv("WS_MESSAGES_PER_MINUTE", "120"))
WS_MESSAGES_PER_SECOND = int(os.getenv("WS_MESSAGES_PER_SECOND", "10"))
WS_BROADCAST_MODE = os.getenv("WS_BROADCAST_MODE", "event")  # "event" (incremental) or "full"
WS_REDIS_CHANNEL = "iot:vitals"
ALLOW_ADMIN_ALERT_ACK = os.getenv("ALLOW_ADMIN_ALERT_ACK", "false").lower() in ("1", "true", "yes")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
FORGOT_PASSWORD_CODE_TTL_MINUTES = int(os.getenv("FORGOT_PASSWORD_CODE_TTL_MINUTES", "10"))
FAKE_VITALS_ENABLED_SETTING_KEY = "fake_vitals_generation_enabled"

# ── Basic Prometheus-compatible metrics (no external dependency) ─────────────
APP_STARTED_AT = time.time()
HTTP_REQUESTS_TOTAL = 0
HTTP_REQUEST_ERRORS_TOTAL = 0
HTTP_REQUEST_DURATION_SECONDS_SUM = 0.0
_redis_subscriber_started = False
_redis_subscriber_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """Manage background subscriber lifecycle without deprecated startup hooks."""
    global _redis_subscriber_started, _redis_subscriber_task
    if not _redis_subscriber_started and is_redis_available():
        _redis_subscriber_task = asyncio.create_task(_redis_vitals_subscriber())
        _redis_subscriber_started = True
        logger.info("Redis pub/sub WebSocket subscriber started (v5.2 event-driven)")
    try:
        yield
    finally:
        if _redis_subscriber_task and not _redis_subscriber_task.done():
            _redis_subscriber_task.cancel()
            try:
                await _redis_subscriber_task
            except asyncio.CancelledError:
                pass

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="IoT Healthcare Patient Monitor",
    description="Real-time patient vital-sign monitoring with WhatsApp alerts, "
                "Redis pub/sub WebSocket, and role-based access control.",
    lifespan=app_lifespan,
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
setup_rate_limiter(app)

# ── Exception Handlers ────────────────────────────────────────────────────────
setup_exception_handlers(app)

# ── CORS ──────────────────────────────────────────────────────────────────────
origins = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID middleware ─────────────────────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    global HTTP_REQUESTS_TOTAL, HTTP_REQUEST_ERRORS_TOTAL, HTTP_REQUEST_DURATION_SECONDS_SUM
    started = time.perf_counter()
    req_id = request.headers.get("X-Request-ID", generate_request_id())
    request_id_var.set(req_id)
    try:
        response = await call_next(request)
    except Exception:
        HTTP_REQUESTS_TOTAL += 1
        HTTP_REQUEST_ERRORS_TOTAL += 1
        HTTP_REQUEST_DURATION_SECONDS_SUM += max(0.0, time.perf_counter() - started)
        raise
    HTTP_REQUESTS_TOTAL += 1
    if response.status_code >= 500:
        HTTP_REQUEST_ERRORS_TOTAL += 1
    HTTP_REQUEST_DURATION_SECONDS_SUM += max(0.0, time.perf_counter() - started)
    response.headers["X-Request-ID"] = req_id
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "REQUEST_LOG",
        extra={
            "action": "request_log",
            "extra_data": {
                "event": "REQUEST_LOG",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "response_time_ms": duration_ms,
                "ip": request_ip(request),
                "headers": sanitize_headers({"Authorization": request.headers.get("authorization", "")}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self';"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── DB Dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _set_refresh_cookie(response: Response, refresh_token: str):
    response.set_cookie(
        key=auth.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=auth.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
    )


def _clear_refresh_cookie(response: Response):
    response.delete_cookie(key=auth.REFRESH_COOKIE_NAME, path="/")


def _setting_bool(db: Session, key: str, default: bool = False) -> bool:
    row = db.query(models.AppSetting).filter(models.AppSetting.setting_key == key).first()
    if not row or row.setting_value is None:
        return default
    return str(row.setting_value).strip().lower() in {"1", "true", "yes", "on"}


def _set_setting_bool(db: Session, key: str, value: bool) -> bool:
    row = db.query(models.AppSetting).filter(models.AppSetting.setting_key == key).first()
    text_value = "true" if value else "false"
    if row:
        row.setting_value = text_value
    else:
        row = models.AppSetting(setting_key=key, setting_value=text_value)
        db.add(row)
    db.commit()
    return value


def filter_response_by_role(current_user: models.User, data):
    """Hide internal metadata from non-admin patient and vitals responses."""
    if current_user.role == "ADMIN":
        return data

    def _filter_patient(item):
        d = {
            "patient_id": item.patient_id,
            "name": item.name,
            "age": item.age,
            "room_number": item.room_number,
            "doctor_name": getattr(item, "doctor_name", None),
            "nurse_name": getattr(item, "nurse_name", None),
            "hospital_name": getattr(item, "hospital_name", None),
            "hospital_id": None,
            "assigned_doctor": None,
            "assigned_nurse": None,
        }
        return d

    def _filter_vital(item):
        return {
            "vital_id": None,
            "patient_id": item.patient_id,
            "heart_rate": item.heart_rate,
            "spo2": item.spo2,
            "temperature": item.temperature,
            "timestamp": item.timestamp,
        }

    if isinstance(data, list):
        if not data:
            return data
        sample = data[0]
        if hasattr(sample, "heart_rate") and hasattr(sample, "spo2"):
            return [_filter_vital(v) for v in data]
        if hasattr(sample, "room_number") and hasattr(sample, "age"):
            return [_filter_patient(p) for p in data]
        return data

    if hasattr(data, "heart_rate") and hasattr(data, "spo2"):
        return _filter_vital(data)
    if hasattr(data, "room_number") and hasattr(data, "age"):
        return _filter_patient(data)
    return data


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/register", response_model=schemas.UserOut, tags=["Auth"])
def register(
    body: schemas.RegisterRequest,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    """Admin-only staff user registration."""
    if body.role == "ADMIN":
        raise HTTPException(status_code=403, detail="Admin accounts cannot be created via registration")
    if auth.get_user_by_username(db, body.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    user = auth.create_user(
        db, body.username, body.password, body.role,
        doctor_id=body.doctor_id, nurse_id=body.nurse_id,
    )
    crud.write_audit(db, "REGISTER", "user", entity_id=user.user_id, user_id=current_user.user_id)
    return user


@app.post("/auth/register/doctor", response_model=schemas.TokenResponse, tags=["Auth"])
def register_doctor(body: schemas.DoctorSelfRegister, response: Response, request: Request, db: Session = Depends(get_db)):
    """
    Self-registration for freelancer doctors.
    Creates a Doctor record + User account, then returns a JWT.
    """
    if auth.get_user_by_username(db, body.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    # Create Doctor record
    doctor = models.Doctor(
        name=body.name,
        specialization=body.specialization,
        hospital_id=body.hospital_id,
        phone=body.phone,
        email=body.email,
        is_freelancer=body.is_freelancer,
        is_available=True,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    # Create User linked to this doctor
    user = auth.create_user(db, body.username, body.password, "DOCTOR", doctor_id=doctor.doctor_id)
    crud.write_audit(db, "SELF_REGISTER", "doctor", entity_id=doctor.doctor_id, user_id=user.user_id)

    token, refresh_token = auth.issue_token_pair(user)
    access_payload = auth.decode_token(token, expected_type="access")
    refresh_payload = auth.decode_token(refresh_token, expected_type="refresh")
    revoked = bind_refresh_session(
        user.user_id,
        refresh_jti=refresh_payload["jti"],
        access_jti=access_payload["jti"],
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        expires_at=refresh_payload["exp"],
    )
    for jti in revoked:
        auth.revoke_token_jti(jti, refresh_payload["exp"])
    _set_refresh_cookie(response, refresh_token)
    return schemas.TokenResponse(
        access_token=token, role=user.role, username=user.username,
        doctor_id=doctor.doctor_id,
    )


@app.post("/auth/register/nurse", response_model=schemas.TokenResponse, tags=["Auth"])
def register_nurse(body: schemas.NurseSelfRegister, response: Response, request: Request, db: Session = Depends(get_db)):
    """
    Self-registration for nurses.
    Creates a Nurse record + User account, then returns a JWT.
    """
    if auth.get_user_by_username(db, body.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    # Create Nurse record
    nurse = models.Nurse(
        name=body.name,
        department=body.department,
        hospital_id=body.hospital_id,
        phone=body.phone,
        email=body.email,
    )
    db.add(nurse)
    db.commit()
    db.refresh(nurse)

    # Create User linked to this nurse
    user = auth.create_user(db, body.username, body.password, "NURSE", nurse_id=nurse.nurse_id)
    crud.write_audit(db, "SELF_REGISTER", "nurse", entity_id=nurse.nurse_id, user_id=user.user_id)

    token, refresh_token = auth.issue_token_pair(user)
    access_payload = auth.decode_token(token, expected_type="access")
    refresh_payload = auth.decode_token(refresh_token, expected_type="refresh")
    revoked = bind_refresh_session(
        user.user_id,
        refresh_jti=refresh_payload["jti"],
        access_jti=access_payload["jti"],
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        expires_at=refresh_payload["exp"],
    )
    for jti in revoked:
        auth.revoke_token_jti(jti, refresh_payload["exp"])
    _set_refresh_cookie(response, refresh_token)
    return schemas.TokenResponse(
        access_token=token, role=user.role, username=user.username,
        nurse_id=nurse.nurse_id,
    )


@app.post("/auth/login", response_model=schemas.TokenResponse, tags=["Auth"])
@limiter.limit(LOGIN_LIMIT)
def login(body: schemas.LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    stage_marks = {"start": t0}

    def _mark(label: str) -> None:
        stage_marks[label] = time.perf_counter()

    client_ip = request_ip(request)
    _mark("client_ip")
    if is_ip_blocked(client_ip):
        log_security_event(
            "BRUTE_FORCE_BLOCKED",
            request=request,
            user=body.username,
            block_seconds=FAILED_LOGIN_BLOCK_SECONDS,
        )
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Try again later.")
    _mark("ip_block_check")

    user = auth.get_user_by_username(db, body.username)
    _mark("user_lookup")
    if not user or not auth.verify_password(body.password, user.password_hash):
        attempts = register_failed_login(client_ip)
        log_security_event(
            "FAILED_LOGIN",
            request=request,
            user=body.username,
            attempts=attempts,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _mark("password_verify")

    reset_failed_login(client_ip)
    _mark("failed_login_reset")
    token, refresh_token = auth.issue_token_pair(user)
    _mark("issue_token_pair")
    access_payload = auth.decode_token(token, expected_type="access")
    refresh_payload = auth.decode_token(refresh_token, expected_type="refresh")
    _mark("decode_tokens")
    revoked = bind_refresh_session(
        user.user_id,
        refresh_jti=refresh_payload["jti"],
        access_jti=access_payload["jti"],
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        expires_at=refresh_payload["exp"],
    )
    _mark("bind_refresh")
    for jti in revoked:
        auth.revoke_token_jti(jti, refresh_payload["exp"])
    _mark("revoke_old_tokens")
    _set_refresh_cookie(response, refresh_token)
    crud.write_audit(db, "LOGIN", "user", entity_id=user.user_id, user_id=user.user_id)
    _mark("audit_write")
    logger.info("User logged in: %s (role: %s)", user.username, user.role,
                extra={"action": "login_success"})

    total = stage_marks["audit_write"] - t0
    if total >= 1.5:
        logger.warning(
            "Slow login detected for user=%s ip=%s total=%.3fs timings=%s",
            body.username,
            client_ip,
            total,
            {
                "ip_check": round(stage_marks["ip_block_check"] - stage_marks["client_ip"], 3),
                "user_lookup": round(stage_marks["user_lookup"] - stage_marks["ip_block_check"], 3),
                "password_verify": round(stage_marks["password_verify"] - stage_marks["user_lookup"], 3),
                "failed_reset": round(stage_marks["failed_login_reset"] - stage_marks["password_verify"], 3),
                "issue_tokens": round(stage_marks["issue_token_pair"] - stage_marks["failed_login_reset"], 3),
                "decode_tokens": round(stage_marks["decode_tokens"] - stage_marks["issue_token_pair"], 3),
                "bind_refresh": round(stage_marks["bind_refresh"] - stage_marks["decode_tokens"], 3),
                "revoke_old": round(stage_marks["revoke_old_tokens"] - stage_marks["bind_refresh"], 3),
                "audit_write": round(stage_marks["audit_write"] - stage_marks["revoke_old_tokens"], 3),
            },
        )

    return schemas.TokenResponse(
        access_token=token, role=user.role, username=user.username,
        doctor_id=user.doctor_id, nurse_id=user.nurse_id,
    )


@app.get("/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def me(current_user: models.User = Depends(auth.require_auth)):
    return current_user


@app.post("/auth/reset-password", tags=["Auth"])
def reset_password(
    body: schemas.ResetPasswordRequest,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    user = auth.get_user_by_username(db, body.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = auth.hash_password(body.new_password)
    db.commit()
    crud.write_audit(db, "RESET_PASSWORD", "user", entity_id=user.user_id, user_id=current_user.user_id)
    return {"detail": f"Password reset successful for '{user.username}'"}


def _password_reset_phone_for_user(db: Session, user: models.User) -> Optional[str]:
    phone = None
    if user.doctor_id:
        doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == user.doctor_id).first()
        if doctor and doctor.phone:
            phone = doctor.phone
    elif user.nurse_id:
        nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == user.nurse_id).first()
        if nurse and nurse.phone:
            phone = nurse.phone
    if not phone:
        return None
    return phone.strip().lstrip("+")


@app.post("/auth/forgot-password/request", tags=["Auth"])
def forgot_password_request(
    body: schemas.ForgotPasswordStartRequest,
    db: Session = Depends(get_db),
):
    """Request a one-time password reset code delivered via configured channel."""
    response_payload = {
        "detail": "If the account exists, a verification code has been sent.",
        "delivery": "unavailable",
    }
    user = auth.get_user_by_username(db, body.username)
    if not user:
        return response_payload

    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.user_id,
        models.PasswordResetToken.used == False,
    ).update({"used": True})

    verification_code = f"{secrets.randbelow(1000000):06d}"
    reset_token = models.PasswordResetToken(
        user_id=user.user_id,
        code_hash=auth.hash_password(verification_code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=FORGOT_PASSWORD_CODE_TTL_MINUTES),
        used=False,
    )
    db.add(reset_token)
    db.commit()

    target_phone = _password_reset_phone_for_user(db, user)
    if target_phone and whatsapp_notifier.WHATSAPP_ENABLED:
        sent = whatsapp_notifier.send_whatsapp_message(
            target_phone,
            (
                "🔐 *Password Reset Code*\n"
                f"Your verification code is: *{verification_code}*\n"
                f"It expires in {FORGOT_PASSWORD_CODE_TTL_MINUTES} minutes."
            ),
            retries=2,
            event_type="RESET",
        )
        if sent:
            response_payload["delivery"] = "whatsapp"

    if os.getenv("ENVIRONMENT", "development").lower() != "production":
        response_payload["verification_code"] = verification_code

    return response_payload


@app.post("/auth/forgot-password/confirm", tags=["Auth"])
@app.post("/auth/forgot-password", tags=["Auth"])
def forgot_password_confirm(
    body: schemas.ForgotPasswordConfirmRequest,
    db: Session = Depends(get_db),
):
    user = auth.get_user_by_username(db, body.username)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    now = datetime.now(timezone.utc)
    token_row = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.user_id == user.user_id,
            models.PasswordResetToken.used == False,
            models.PasswordResetToken.expires_at > now,
        )
        .order_by(models.PasswordResetToken.created_at.desc())
        .first()
    )
    if not token_row or not auth.verify_password(body.verification_code, token_row.code_hash):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    token_row.used = True
    user.password_hash = auth.hash_password(body.new_password)
    db.commit()
    crud.write_audit(db, "FORGOT_PASSWORD_RESET", "user", entity_id=user.user_id, user_id=user.user_id)
    return {"detail": f"Password reset successful for '{user.username}'"}


@app.post("/auth/refresh", response_model=schemas.TokenResponse, tags=["Auth"])
def refresh_auth_token(response: Response, request: Request, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get(auth.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = auth.decode_token(refresh_token, expected_type="refresh")
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if not payload or auth.is_token_revoked(payload.get("jti")):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = auth.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    client_ip = request_ip(request)
    allowed, status_code, reason = validate_refresh_request(
        user.user_id,
        refresh_jti=payload.get("jti"),
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", ""),
    )
    if not allowed:
        if reason.startswith("token_theft_"):
            log_security_event(
                "TOKEN_THEFT_SUSPECTED",
                request=request,
                user=user.username,
                reason=reason,
            )
            raise HTTPException(status_code=403, detail="Refresh token binding mismatch")
        raise HTTPException(status_code=status_code, detail="Invalid refresh token")

    anomaly_reasons = detect_suspicious_refresh_activity(user.user_id, client_ip)
    if anomaly_reasons:
        log_security_event(
            "SUSPICIOUS_ACTIVITY",
            request=request,
            user=user.username,
            reasons=",".join(anomaly_reasons),
        )

    auth.revoke_token_jti(payload.get("jti"), payload.get("exp"))
    access_token, new_refresh = auth.issue_token_pair(user)
    new_access_payload = auth.decode_token(access_token, expected_type="access")
    new_payload = auth.decode_token(new_refresh, expected_type="refresh")
    revoked = bind_refresh_session(
        user.user_id,
        refresh_jti=new_payload["jti"],
        access_jti=new_access_payload["jti"],
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        expires_at=new_payload["exp"],
    )
    for jti in revoked:
        auth.revoke_token_jti(jti, new_payload["exp"])
    _set_refresh_cookie(response, new_refresh)

    return schemas.TokenResponse(
        access_token=access_token,
        role=user.role,
        username=user.username,
        doctor_id=user.doctor_id,
        nurse_id=user.nurse_id,
    )


@app.post("/auth/logout", tags=["Auth"])
def logout(
    response: Response,
    request: Request,
    token: str = Depends(auth.require_token),
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    try:
        payload = auth.decode_token(token, expected_type="access")
        if payload:
            auth.revoke_token_jti(payload.get("jti"), payload.get("exp"))
    except JWTError:
        pass

    refresh_token = request.cookies.get(auth.REFRESH_COOKIE_NAME)
    if refresh_token:
        try:
            refresh_payload = auth.decode_token(refresh_token, expected_type="refresh", verify_exp=False)
            if refresh_payload:
                auth.revoke_token_jti(refresh_payload.get("jti"), refresh_payload.get("exp"))
                clear_refresh_session(current_user.user_id, refresh_payload.get("jti"))
        except JWTError:
            pass
    _clear_refresh_cookie(response)
    crud.write_audit(db, "LOGOUT", "user", entity_id=current_user.user_id, user_id=current_user.user_id)
    return {"detail": "Logged out"}


# ═══════════════════════════════════════════════════════════════════════════════
#  HOSPITAL ENDPOINTS  (ADMIN only for create)
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/hospitals", response_model=List[schemas.HospitalOut], tags=["Hospitals"])
def list_hospitals(
    db: Session = Depends(get_db),
):
    return crud.get_hospitals(db)


@app.post("/hospitals", response_model=schemas.HospitalOut, tags=["Hospitals"])
def create_hospital(
    hospital: schemas.HospitalCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    return crud.create_hospital(db, hospital)


# ═══════════════════════════════════════════════════════════════════════════════
#  DOCTOR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/doctors", response_model=List[schemas.DoctorOut], tags=["Doctors"])
def list_doctors(
    hospital_id: Optional[int] = None,
    specialization: Optional[str] = None,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_doctors(db, hospital_id=hospital_id, specialization=specialization)


@app.post("/doctors", response_model=schemas.DoctorOut, tags=["Doctors"])
def create_doctor(
    doctor: schemas.DoctorCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    # If admin provided credentials, create a linked login account
    if doctor.username:
        if not doctor.password or len(doctor.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        if auth.get_user_by_username(db, doctor.username):
            raise HTTPException(status_code=400, detail="Username already taken")
    return crud.create_doctor(db, doctor, user_id=current_user.user_id)


@app.get("/doctors/{doctor_id}", response_model=schemas.DoctorOut, tags=["Doctors"])
def get_doctor(
    doctor_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    d = crud.get_doctor(db, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return d


@app.put("/doctors/{doctor_id}", response_model=schemas.DoctorOut, tags=["Doctors"])
def update_doctor(
    doctor_id: int,
    payload: schemas.DoctorUpdate,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"ADMIN", "DOCTOR"}:
        raise HTTPException(status_code=403, detail="Not authorized to update doctor")
    if current_user.role == "DOCTOR" and current_user.doctor_id != doctor_id:
        raise HTTPException(status_code=403, detail="Not authorized to update doctor")
    d = crud.update_doctor(db, doctor_id, payload, user_id=current_user.user_id)
    if not d:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return d


@app.delete("/doctors/{doctor_id}", tags=["Doctors"],
            summary="Delete doctor",
            description="Hard delete: permanently removes the doctor record from the database.")
def delete_doctor(
    doctor_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    d = crud.delete_doctor(db, doctor_id, user_id=current_user.user_id)
    if not d:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"detail": "Doctor deleted successfully"}


@app.get("/doctors/{doctor_id}/patients", response_model=List[schemas.PatientOut], tags=["Doctors"])
def list_doctor_patients(
    doctor_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    if current_user.role == "DOCTOR" and current_user.doctor_id != doctor_id:
        raise HTTPException(status_code=403, detail="Not authorized to access these patients")
    if current_user.role == "NURSE":
        raise HTTPException(status_code=403, detail="Not authorized to access these patients")
    patients = crud.get_patients(db, doctor_id=doctor_id)
    return filter_response_by_role(current_user, patients)


# ═══════════════════════════════════════════════════════════════════════════════
#  NURSE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/nurses", response_model=List[schemas.NurseOut], tags=["Nurses"])
def list_nurses(
    hospital_id: Optional[int] = None,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_nurses(db, hospital_id=hospital_id)


@app.post("/nurses", response_model=schemas.NurseOut, tags=["Nurses"])
def create_nurse(
    nurse: schemas.NurseCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    if nurse.username:
        if not nurse.password or len(nurse.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        if auth.get_user_by_username(db, nurse.username):
            raise HTTPException(status_code=400, detail="Username already taken")
    return crud.create_nurse(db, nurse, user_id=current_user.user_id)


@app.get("/nurses/{nurse_id}", response_model=schemas.NurseOut, tags=["Nurses"])
def get_nurse(
    nurse_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    n = crud.get_nurse(db, nurse_id)
    if not n:
        raise HTTPException(status_code=404, detail="Nurse not found")
    return n


@app.put("/nurses/{nurse_id}", response_model=schemas.NurseOut, tags=["Nurses"])
def update_nurse(
    nurse_id: int,
    payload: schemas.NurseUpdate,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    if current_user.role not in {"ADMIN", "DOCTOR", "NURSE"}:
        raise HTTPException(status_code=403, detail="Not authorized to update nurse")
    if current_user.role == "NURSE" and current_user.nurse_id != nurse_id:
        raise HTTPException(status_code=403, detail="Not authorized to update nurse")
    n = crud.update_nurse(db, nurse_id, payload, user_id=current_user.user_id)
    if not n:
        raise HTTPException(status_code=404, detail="Nurse not found")
    return n


@app.delete("/nurses/{nurse_id}", tags=["Nurses"],
            summary="Delete nurse",
            description="Hard delete: permanently removes the nurse record from the database.")
def delete_nurse(
    nurse_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    n = crud.delete_nurse(db, nurse_id, user_id=current_user.user_id)
    if not n:
        raise HTTPException(status_code=404, detail="Nurse not found")
    return {"detail": "Nurse deleted successfully"}


@app.get("/nurses/{nurse_id}/patients", response_model=List[schemas.PatientOut], tags=["Nurses"])
def list_nurse_patients(
    nurse_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    if current_user.role == "NURSE" and current_user.nurse_id != nurse_id:
        raise HTTPException(status_code=403, detail="Not authorized to access these patients")
    if current_user.role == "DOCTOR":
        raise HTTPException(status_code=403, detail="Not authorized to access these patients")
    patients = crud.get_patients(db, nurse_id=nurse_id)
    return filter_response_by_role(current_user, patients)


# ═══════════════════════════════════════════════════════════════════════════════
#  PATIENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/patients", response_model=List[schemas.PatientOut], tags=["Patients"])
def list_patients(
    doctor_id: Optional[int] = None,
    nurse_id: Optional[int] = None,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    if current_user.role == "DOCTOR":
        if not current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these patients")
        if doctor_id and doctor_id != current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these patients")
        if doctor_id == current_user.doctor_id:
            patients = crud.get_patients(db, doctor_id=current_user.doctor_id)
        else:
            allowed_ids = _allowed_patient_ids_for_user(db, current_user)
            patients = crud.get_patients(db, patient_ids=list(allowed_ids or []))
        return filter_response_by_role(current_user, patients)
    elif current_user.role == "NURSE":
        if not current_user.nurse_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these patients")
        if nurse_id and nurse_id != current_user.nurse_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these patients")
        if doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these patients")
        if nurse_id == current_user.nurse_id:
            patients = crud.get_patients(db, nurse_id=current_user.nurse_id)
        else:
            allowed_ids = _allowed_patient_ids_for_user(db, current_user)
            patients = crud.get_patients(db, patient_ids=list(allowed_ids or []))
        return filter_response_by_role(current_user, patients)
    patients = crud.get_patients(db, doctor_id=doctor_id, nurse_id=nurse_id)
    return filter_response_by_role(current_user, patients)


@app.put("/patients/{patient_id}", response_model=schemas.PatientOut, tags=["Patients"])
def update_patient(
    patient_id: int,
    payload: schemas.PatientUpdate,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR", "NURSE")),
    db: Session = Depends(get_db),
):
    existing = crud.get_patient(db, patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, existing)
    updated = crud.update_patient(db, patient_id, payload, user_id=current_user.user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Patient not found")
    return updated


@app.post("/patients", response_model=schemas.PatientOut, tags=["Patients"])
def create_patient(
    patient: schemas.PatientCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    try:
        return crud.create_patient(db, patient, user_id=current_user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/patients/{patient_id}", response_model=schemas.PatientOut, tags=["Patients"])
def get_patient(
    patient_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    p = crud.get_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, p)
    return filter_response_by_role(current_user, p)


@app.delete("/patients/{patient_id}", tags=["Patients"],
            summary="Delete patient",
            description="Hard delete: permanently removes the patient and all their vitals from the database.")
def delete_patient(
    patient_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    p = crud.get_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, p)
    p = crud.delete_patient(db, patient_id, user_id=current_user.user_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"detail": "Patient deleted successfully"}


@app.patch("/patients/{patient_id}/assign_doctor", response_model=schemas.PatientOut, tags=["Patients"])
def assign_doctor(
    patient_id: int,
    body: schemas.AssignDoctor,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    existing = crud.get_patient(db, patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, existing)
    try:
        p = crud.assign_doctor(db, patient_id, body.doctor_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not p:
        raise HTTPException(status_code=404, detail="Patient or Doctor not found")
    return p


@app.patch("/patients/{patient_id}/assign_nurse", response_model=schemas.PatientOut, tags=["Patients"])
def assign_nurse(
    patient_id: int,
    body: schemas.AssignNurse,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR", "NURSE")),
    db: Session = Depends(get_db),
):
    existing = crud.get_patient(db, patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, existing)
    try:
        p = crud.assign_nurse(db, patient_id, body.nurse_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not p:
        raise HTTPException(status_code=404, detail="Patient or Nurse not found")
    return p


# ═══════════════════════════════════════════════════════════════════════════════
#  VITALS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/vitals", response_model=schemas.VitalsOut, tags=["Vitals"])
def create_vitals(
    vital: schemas.VitalsCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR", "NURSE")),
    db: Session = Depends(get_db),
):
    db_vital = crud.create_vitals(db=db, vital=vital)
    crud.sync_alerts_for_vital(db=db, vital_record=db_vital)
    return db_vital


@app.get("/vitals", response_model=List[schemas.VitalsOut], tags=["Vitals"])
def get_vitals(
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    if patient_id is not None:
        p = crud.get_patient(db, patient_id)
        if not p:
            raise HTTPException(status_code=404, detail="Patient not found")
        check_patient_access(db, current_user, p)
        vitals = crud.get_vitals(db, patient_id=patient_id, limit=limit, offset=offset)
        return filter_response_by_role(current_user, vitals)

    if current_user.role == "ADMIN":
        return crud.get_vitals(db, doctor_id=doctor_id, limit=limit, offset=offset)
    if current_user.role == "DOCTOR":
        if not current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these vitals")
        if doctor_id and doctor_id != current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these vitals")
        allowed_ids = _allowed_patient_ids_for_user(db, current_user)
        vitals = crud.get_vitals(db, patient_ids=list(allowed_ids or []), limit=limit, offset=offset)
        return filter_response_by_role(current_user, vitals)
    if current_user.role == "NURSE":
        if not current_user.nurse_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these vitals")
        if doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these vitals")
        allowed_ids = _allowed_patient_ids_for_user(db, current_user)
        vitals = crud.get_vitals(db, patient_ids=list(allowed_ids or []), limit=limit, offset=offset)
        return filter_response_by_role(current_user, vitals)
    raise HTTPException(status_code=403, detail="Not authorized to access these vitals")


@app.get("/vitals/latest/{patient_id}", response_model=schemas.VitalsOut, tags=["Vitals"])
def get_latest_vital(
    patient_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    p = crud.get_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, p)
    v = crud.get_latest_vital(db, patient_id)
    if not v:
        raise HTTPException(status_code=404, detail="No vitals found for this patient")
    return filter_response_by_role(current_user, v)


# ═══════════════════════════════════════════════════════════════════════════════
#  ALERT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/alerts", response_model=List[schemas.AlertOut], tags=["Alerts"])
def get_alerts(
    status: Optional[str] = None,
    doctor_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    if current_user.role == "ADMIN":
        return crud.get_alerts(db, status=status, doctor_id=doctor_id, limit=limit, offset=offset)

    if current_user.role == "DOCTOR":
        if not current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these alerts")
        if doctor_id and doctor_id != current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these alerts")
        allowed_ids = _allowed_patient_ids_for_user(db, current_user)
        return crud.get_alerts(db, status=status, patient_ids=list(allowed_ids or []), limit=limit, offset=offset)

    if current_user.role == "NURSE":
        if not current_user.nurse_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these alerts")
        if doctor_id:
            raise HTTPException(status_code=403, detail="Not authorized to access these alerts")
        allowed_ids = _allowed_patient_ids_for_user(db, current_user)
        return crud.get_alerts(db, status=status, patient_ids=list(allowed_ids or []), limit=limit, offset=offset)

    raise HTTPException(status_code=403, detail="Not authorized to access these alerts")


@app.patch("/alerts/{alert_id}/acknowledge", response_model=schemas.AlertOut, tags=["Alerts"])
def acknowledge_alert(
    alert_id: int,
    body: schemas.AlertAcknowledge,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    _ = body
    check_alert_ownership(db, alert_id, current_user)
    alert = crud.acknowledge_alert(
        db=db,
        alert_id=alert_id,
        current_user=current_user,
        allow_admin_override=ALLOW_ADMIN_ALERT_ACK,
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


# ═══════════════════════════════════════════════════════════════════════════════
#  ESCALATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/escalations", response_model=List[schemas.EscalationOut], tags=["Escalations"])
def list_escalations(
    alert_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_escalations(db, alert_id=alert_id, doctor_id=doctor_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  NOTIFICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/notifications/my", response_model=List[schemas.AlertNotificationOut], tags=["Notifications"])
def my_notifications(
    unread_only: bool = False,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_notifications(db, current_user.user_id, unread_only=unread_only)


@app.patch("/notifications/{notification_id}/read", response_model=schemas.AlertNotificationOut, tags=["Notifications"])
def read_notification(
    notification_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    notif = crud.mark_notification_read(db, notification_id, current_user.user_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif


@app.post("/notifications/read-all", tags=["Notifications"])
def read_all_notifications(
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    crud.mark_all_notifications_read(db, current_user.user_id)
    return {"detail": "All notifications marked as read"}


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/dashboard/stats", response_model=schemas.DashboardStats, tags=["Dashboard"])
def dashboard_stats(
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_dashboard_stats(db, current_user=current_user)


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT ENDPOINTS  (per-patient treatment chat — v5.2: authorization check)
# ═══════════════════════════════════════════════════════════════════════════════

def check_patient_access(db: Session, current_user: models.User, patient: models.Patient):
    """ABAC: ADMIN full; DOCTOR assigned or same hospital; NURSE assigned only."""
    if can_access_patient_abac(db, current_user, patient):
        return
    raise HTTPException(
        status_code=403,
        detail="Not authorized to access this patient",
    )


def check_alert_ownership(db: Session, alert_id: int, current_user: models.User):
    """Only the assigned doctor can acknowledge alerts (admin only if explicitly enabled)."""
    alert = db.query(models.Alert).filter(models.Alert.alert_id == alert_id).first()
    if not alert:
        return

    patient = db.query(models.Patient).filter(models.Patient.patient_id == alert.patient_id).first()
    if not patient:
        return

    if current_user.role == "DOCTOR":
        if not current_user.doctor_id or patient.assigned_doctor != current_user.doctor_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to acknowledge this alert",
            )
        return

    if current_user.role == "ADMIN" and ALLOW_ADMIN_ALERT_ACK:
        return

    raise HTTPException(
        status_code=403,
        detail="Not authorized to acknowledge this alert",
    )


def _allowed_patient_ids_for_user(db: Session, user: models.User) -> Optional[set[int]]:
    """
    Return patient IDs visible to the user for real-time streams.
    None means full access.
    """
    if user.role == "ADMIN":
        return None

    if user.role == "DOCTOR":
        if not user.doctor_id:
            return set()
        ids = {
            row[0] for row in db.query(models.Patient.patient_id).filter(
                models.Patient.assigned_doctor == user.doctor_id
            ).all()
        }
        doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == user.doctor_id).first()
        if doctor and doctor.hospital_id:
            ids.update(
                row[0] for row in db.query(models.Patient.patient_id).filter(
                    models.Patient.hospital_id == doctor.hospital_id
                ).all()
            )
        return ids

    if user.role == "NURSE":
        if not user.nurse_id:
            return set()
        ids = {
            row[0] for row in db.query(models.Patient.patient_id).filter(
                models.Patient.assigned_nurse == user.nurse_id
            ).all()
        }
        nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == user.nurse_id).first()
        if nurse and nurse.hospital_id:
            ids.update(
                row[0] for row in db.query(models.Patient.patient_id).filter(
                    models.Patient.hospital_id == nurse.hospital_id
                ).all()
            )
        return ids

    return set()


def _filter_ws_payload_for_user(payload: list[dict], allowed_ids: Optional[set[int]]) -> list[dict]:
    if allowed_ids is None:
        return payload
    return [row for row in payload if row.get("patient_id") in allowed_ids]


@app.get("/patients/{patient_id}/chat", response_model=List[schemas.ChatMessageOut], tags=["Chat"])
def get_patient_chat(
    patient_id: int,
    limit: int = 100,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    p = crud.get_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, p)
    return crud.get_chat_messages(db, patient_id, limit=limit)


@app.post("/patients/{patient_id}/chat", response_model=schemas.ChatMessageOut, tags=["Chat"])
def post_patient_chat(
    patient_id: int,
    body: schemas.ChatMessageCreate,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    p = crud.get_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    check_patient_access(db, current_user, p)
    msg = crud.create_chat_message(
        db,
        patient_id=patient_id,
        sender_username=current_user.username,
        sender_role=current_user.role,
        message=body.message,
    )
    return msg


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/audit-logs", response_model=List[schemas.AuditLogOut], tags=["Audit"])
def list_audit_logs(
    entity: Optional[str] = None,
    limit: int = 200,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    return crud.get_audit_logs(db, entity=entity, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET – event-driven vitals push with Redis pub/sub (v5.2)
# ═══════════════════════════════════════════════════════════════════════════════
class ConnectionManager:
    """WebSocket manager with per-IP rate limiting and Redis pub/sub support."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._ip_counts: dict[str, int] = {}
        self._user_counts: dict[str, int] = {}
        self._msg_counts: dict[str, int] = {}
        self._msg_reset_time: dict[str, float] = {}
        self._conn_msg_times: dict[int, list[float]] = {}
        self._conn_user: dict[int, dict] = {}

    async def connect(
        self,
        ws: WebSocket,
        user: models.User,
        client_ip: str = "unknown",
        user_key: str = "unknown",
    ):
        current = self._ip_counts.get(client_ip, 0)
        if current >= WS_CONNECTION_LIMIT:
            await ws.close(code=1008, reason="Too many WebSocket connections from this IP")
            return False
        user_current = self._user_counts.get(user_key, 0)
        if user_current >= WS_USER_CONNECTION_LIMIT:
            await ws.close(code=1008, reason="Too many WebSocket connections for this user")
            return False
        await ws.accept()
        self.active_connections.append(ws)
        self._ip_counts[client_ip] = current + 1
        self._user_counts[user_key] = user_current + 1
        self._conn_msg_times[id(ws)] = []
        self._conn_user[id(ws)] = {
            "user_id": user.user_id,
            "role": user.role,
            "doctor_id": user.doctor_id,
            "nurse_id": user.nurse_id,
            "username": user.username,
        }
        return True

    def disconnect(self, ws: WebSocket, client_ip: str = "unknown", user_key: str = "unknown"):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        current = self._ip_counts.get(client_ip, 1)
        self._ip_counts[client_ip] = max(0, current - 1)
        user_current = self._user_counts.get(user_key, 1)
        self._user_counts[user_key] = max(0, user_current - 1)
        self._conn_msg_times.pop(id(ws), None)
        self._conn_user.pop(id(ws), None)

    def check_connection_message_rate(self, ws: WebSocket) -> bool:
        now = time.time()
        key = id(ws)
        times = self._conn_msg_times.get(key, [])
        times = [t for t in times if now - t <= 1.0]
        if len(times) >= WS_MESSAGES_PER_SECOND:
            self._conn_msg_times[key] = times
            return False
        times.append(now)
        self._conn_msg_times[key] = times
        return True

    def check_message_rate(self, client_ip: str) -> bool:
        """Return True if message can be sent, False if rate limited."""
        import time
        now = time.time()
        reset = self._msg_reset_time.get(client_ip, 0)
        if now - reset > 60:
            self._msg_counts[client_ip] = 0
            self._msg_reset_time[client_ip] = now
        count = self._msg_counts.get(client_ip, 0)
        if count >= WS_MESSAGES_PER_MINUTE:
            return False
        self._msg_counts[client_ip] = count + 1
        return True

    async def broadcast_vitals(self, message: str):
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            payload = []
        if not isinstance(payload, list):
            payload = []

        db = SessionLocal()
        try:
            allowed_cache: dict[int, Optional[set[int]]] = {}
            for conn in list(self.active_connections):
                try:
                    user_meta = self._conn_user.get(id(conn))
                    if not user_meta:
                        await conn.send_text("[]")
                        continue
                    user_id = int(user_meta["user_id"])
                    allowed_ids = allowed_cache.get(user_id)
                    if user_id not in allowed_cache:
                        db_user = db.query(models.User).filter(models.User.user_id == user_id).first()
                        allowed_ids = _allowed_patient_ids_for_user(db, db_user) if db_user else set()
                        allowed_cache[user_id] = allowed_ids
                    filtered_payload = _filter_ws_payload_for_user(payload, allowed_ids)
                    await conn.send_text(json.dumps(filtered_payload))
                except Exception:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)
                    self._conn_msg_times.pop(id(conn), None)
                    self._conn_user.pop(id(conn), None)
        finally:
            db.close()

    async def broadcast(self, message: str):
        for conn in list(self.active_connections):
            try:
                await conn.send_text(message)
            except Exception:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

    def get_stats(self) -> dict:
        return {
            "active_connections": len(self.active_connections),
            "unique_ips": len([v for v in self._ip_counts.values() if v > 0]),
        }


manager = ConnectionManager()


async def _redis_vitals_subscriber():
    """Subscribe to Redis pub/sub channel and broadcast to all WebSocket clients.
    Event-driven: scheduler publishes → Redis channel → backend subscribes → broadcast.
    Uses redis.asyncio for non-blocking pub/sub.
    """
    import redis.asyncio as aioredis
    from database import REDIS_URL
    logger.info("Starting Redis pub/sub subscriber on channel: %s", WS_REDIS_CHANNEL)
    while True:
        r = None
        pubsub = None
        try:
            r = aioredis.from_url(REDIS_URL, socket_connect_timeout=5)
            pubsub = r.pubsub()
            await pubsub.subscribe(WS_REDIS_CHANNEL)
            async for raw_message in pubsub.listen():
                if raw_message["type"] == "message":
                    data = raw_message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await manager.broadcast_vitals(data)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Redis subscriber error (reconnecting in 3s): %s", e)
            await asyncio.sleep(3)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.aclose()
                except Exception:
                    pass
            if r is not None:
                try:
                    await r.aclose()
                except Exception:
                    pass


def _get_ws_user(token: str, db: Session) -> tuple[Optional[models.User], Optional[str]]:
    """Resolve a WebSocket user from a JWT token."""
    try:
        payload = auth.decode_token(token, expected_type="access")
        if payload is None:
            return None, "invalid"
        if auth.is_token_revoked(payload.get("jti")):
            return None, "revoked"
        username = payload.get("sub")
        if not username:
            return None, "invalid"
    except ExpiredSignatureError:
        return None, "expired"
    except JWTError:
        return None, "invalid"
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None, "invalid"
    return user, None


@app.websocket("/ws/vitals")
async def ws_vitals(websocket: WebSocket):
    """v5.2: Event-driven WebSocket. Clients connect and receive updates pushed
    from Redis pub/sub. No DB polling in the WebSocket handler.
    Falls back to periodic polling if Redis is unavailable.
    """
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        log_security_event("WEBSOCKET_AUTH_FAILURE", request=None, ip=request_ip(None), reason="missing_token")
        await websocket.accept()
        await websocket.close(code=1008, reason="Missing auth token")
        return

    db = SessionLocal()
    try:
        user, token_error = _get_ws_user(token, db)
    finally:
        db.close()

    if not user:
        log_security_event("WEBSOCKET_AUTH_FAILURE", request=None, ip=websocket.client.host if websocket.client else "unknown", reason=token_error or "invalid")
        await websocket.accept()
        if token_error == "expired":
            await websocket.close(code=1008, reason="Expired auth token")
        else:
            await websocket.close(code=1008, reason="Invalid auth token")
        return

    client_ip = websocket.client.host if websocket.client else "unknown"
    user_key = str(user.user_id)
    accepted = await manager.connect(websocket, user=user, client_ip=client_ip, user_key=user_key)
    if not accepted:
        return

    try:
        if is_redis_available():
            # Event-driven mode: just keep the connection alive.
            # Broadcasts are handled by _redis_vitals_subscriber.
            while True:
                # Wait for client messages (ping/pong keepalive)
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    if not manager.check_connection_message_rate(websocket):
                        log_security_event(
                            "WEBSOCKET_RATE_LIMIT_HIT",
                            request=None,
                            ip=client_ip,
                            user=user.username,
                        )
                        await websocket.close(code=1008, reason="WebSocket message rate limit exceeded")
                        break
                except asyncio.TimeoutError:
                    # Send a ping to keep alive
                    try:
                        await websocket.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        break
        else:
            # Fallback: periodic DB polling (degraded mode without Redis)
            db = SessionLocal()
            try:
                while True:
                    allowed_ids = _allowed_patient_ids_for_user(db, user)
                    patients = crud.get_patients(db)
                    if allowed_ids is not None:
                        patients = [p for p in patients if p.patient_id in allowed_ids]
                    payload = []
                    for p in patients:
                        v = crud.get_latest_vital(db, p.patient_id)
                        if v:
                            payload.append({
                                "patient_id": p.patient_id,
                                "name": p.name,
                                "room": p.room_number,
                                "heart_rate": v.heart_rate,
                                "spo2": v.spo2,
                                "temperature": v.temperature,
                                "timestamp": str(v.timestamp),
                            })
                    await websocket.send_text(json.dumps(payload))
                    await asyncio.sleep(5)
            finally:
                db.close()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, client_ip, user_key)


@app.get("/metrics", tags=["Monitoring"])
def metrics(current_user: models.User = Depends(auth.require_role("ADMIN"))):
    """Prometheus scrape endpoint for basic HTTP/runtime metrics."""
    uptime = max(0.0, time.time() - APP_STARTED_AT)
    lines = [
        "# HELP iot_app_uptime_seconds Application uptime in seconds",
        "# TYPE iot_app_uptime_seconds gauge",
        f"iot_app_uptime_seconds {uptime:.6f}",
        "# HELP iot_http_requests_total Total HTTP requests handled",
        "# TYPE iot_http_requests_total counter",
        f"iot_http_requests_total {HTTP_REQUESTS_TOTAL}",
        "# HELP iot_http_request_errors_total Total HTTP requests ending in server errors",
        "# TYPE iot_http_request_errors_total counter",
        f"iot_http_request_errors_total {HTTP_REQUEST_ERRORS_TOTAL}",
        "# HELP iot_http_request_duration_seconds_sum Cumulative HTTP request duration in seconds",
        "# TYPE iot_http_request_duration_seconds_sum counter",
        f"iot_http_request_duration_seconds_sum {HTTP_REQUEST_DURATION_SECONDS_SUM:.6f}",
        "# HELP iot_websocket_active_connections Current active WebSocket client connections",
        "# TYPE iot_websocket_active_connections gauge",
        f"iot_websocket_active_connections {manager.get_stats()['active_connections']}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


# ═══════════════════════════════════════════════════════════════════════════════
#  WHATSAPP NOTIFICATION ENDPOINTS  (GREEN-API – FREE)
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/whatsapp/config", response_model=schemas.WhatsAppConfigOut, tags=["WhatsApp"])
def get_whatsapp_config(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Get current WhatsApp notification configuration."""
    return whatsapp_notifier.get_config()


@app.post("/whatsapp/recipients/add", response_model=schemas.WhatsAppConfigOut, tags=["WhatsApp"])
def add_whatsapp_recipient(
    body: schemas.WhatsAppRecipientAdd,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Add a WhatsApp recipient phone number."""
    whatsapp_notifier.add_recipient(body.phone)
    return whatsapp_notifier.get_config()


@app.post("/whatsapp/recipients/remove", response_model=schemas.WhatsAppConfigOut, tags=["WhatsApp"])
def remove_whatsapp_recipient(
    body: schemas.WhatsAppRecipientRemove,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Remove a WhatsApp recipient phone number."""
    whatsapp_notifier.remove_recipient(body.phone)
    return whatsapp_notifier.get_config()


@app.post("/whatsapp/test", response_model=schemas.WhatsAppTestResult, tags=["WhatsApp"])
def test_whatsapp(
    body: schemas.WhatsAppTestMessage = schemas.WhatsAppTestMessage(),
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Send a test WhatsApp message to verify setup."""
    result = whatsapp_notifier.send_test_message(phone=body.phone)
    return result


@app.post("/whatsapp/alerts/pause", response_model=schemas.WhatsAppConfigOut, tags=["WhatsApp"])
def pause_whatsapp_alerts(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Pause all WhatsApp alert notifications (prototype toggle)."""
    whatsapp_notifier.pause_alerts()
    return whatsapp_notifier.get_config()


@app.post("/whatsapp/alerts/resume", response_model=schemas.WhatsAppConfigOut, tags=["WhatsApp"])
def resume_whatsapp_alerts(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Resume WhatsApp alert notifications (prototype toggle)."""
    whatsapp_notifier.resume_alerts()
    return whatsapp_notifier.get_config()


@app.post("/whatsapp/webhook", tags=["WhatsApp"])
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    GREEN-API webhook — receives incoming WhatsApp messages.
    v5.2: Doctors reply 'ACK <alert_id>' to acknowledge a specific alert.
    Backward compatible: plain 'ACK' acknowledges the latest pending alert.
    No auth required (GREEN-API calls this endpoint).
    """
    try:
        body = await request.json()
        logger.info("WhatsApp webhook received: typeWebhook=%s", body.get("typeWebhook"))

        msg_type = body.get("typeWebhook")
        if msg_type != "incomingMessageReceived":
            return {"status": "ignored", "reason": "not an incoming message"}

        # Parse sender phone
        sender_data = body.get("senderData", {})
        sender_phone = sender_data.get("sender", "").replace("@c.us", "")

        # Parse message text
        message_data = body.get("messageData", {})
        text_data = message_data.get("textMessageData", {})
        text = text_data.get("textMessage", "").strip()

        logger.info("WhatsApp reply from %s: '%s'", sender_phone, text)

        text_upper = text.upper()

        # ── v5.2: Parse "ACK <alert_id>" for granular acknowledgement ────
        import re
        ack_match = re.match(r"^ACK\s+(\d+)$", text_upper)

        if ack_match:
            # Granular: acknowledge specific alert
            target_alert_id = int(ack_match.group(1))
            alert = db.query(models.Alert).filter(
                models.Alert.alert_id == target_alert_id
            ).first()

            if not alert or alert.status not in ("PENDING", "ESCALATED"):
                return {"status": "no_matching_alert", "alert_id": target_alert_id}

            # Verify sender is the assigned doctor for this patient
            patient = db.query(models.Patient).filter(
                models.Patient.patient_id == alert.patient_id
            ).first()
            doctor = None
            if patient and patient.assigned_doctor:
                doctor = db.query(models.Doctor).filter(
                    models.Doctor.doctor_id == patient.assigned_doctor
                ).first()

            if doctor and doctor.phone:
                clean_doc_phone = doctor.phone.strip().lstrip("+")
                clean_sender = sender_phone.strip().lstrip("+")
                if clean_doc_phone[-10:] != clean_sender[-10:]:
                    logger.warning("ACK from non-assigned doctor %s for alert #%s", sender_phone, target_alert_id)
                    return {"status": "forbidden", "detail": "Not authorized to acknowledge this alert"}
            else:
                return {"status": "forbidden", "detail": "Not authorized to acknowledge this alert"}

            alert.status = "ACKNOWLEDGED"
            doctor_user = db.query(models.User).filter(models.User.doctor_id == patient.assigned_doctor).first() if patient else None
            alert.acknowledged_by = doctor_user.user_id if doctor_user else None
            alert.acknowledged_at = datetime.now(timezone.utc)
            db.commit()
            if doctor_user:
                crud.write_audit(db, "ACKNOWLEDGE", "alert", entity_id=target_alert_id, user_id=doctor_user.user_id)

            # Remove from pending tracker
            whatsapp_notifier.acknowledge_alert_by_id(target_alert_id, sender_phone)

            doctor_name = doctor.name if doctor else "Doctor"
            whatsapp_notifier.send_whatsapp_message(
                sender_phone,
                f"✅ Thank you, {doctor_name}!\n"
                f"Alert #{target_alert_id} marked as ACKNOWLEDGED.\n"
                f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            return {"status": "acknowledged", "alert_ids": [target_alert_id]}

        elif text_upper in ("ACK", "1", "ACKNOWLEDGE", "OK", "YES"):
            # Backward compatible: acknowledge all/latest pending alerts for this doctor
            candidate_ids = whatsapp_notifier.acknowledge_by_phone(sender_phone)
            acknowledged_ids: list[int] = []

            if candidate_ids:
                for alert_id in candidate_ids:
                    alert = db.query(models.Alert).filter(
                        models.Alert.alert_id == alert_id
                    ).first()
                    if alert and alert.status in ("PENDING", "ESCALATED"):
                        patient = db.query(models.Patient).filter(
                            models.Patient.patient_id == alert.patient_id
                        ).first()
                        doctor = None
                        doctor_user = None
                        if patient and patient.assigned_doctor:
                            doctor = db.query(models.Doctor).filter(
                                models.Doctor.doctor_id == patient.assigned_doctor
                            ).first()
                            doctor_user = db.query(models.User).filter(
                                models.User.doctor_id == patient.assigned_doctor
                            ).first()
                        if not doctor or not doctor.phone:
                            continue
                        clean_doc_phone = doctor.phone.strip().lstrip("+")
                        clean_sender = sender_phone.strip().lstrip("+")
                        if clean_doc_phone[-10:] != clean_sender[-10:]:
                            continue

                        alert.status = "ACKNOWLEDGED"
                        alert.acknowledged_by = doctor_user.user_id if doctor_user else None
                        alert.acknowledged_at = datetime.now(timezone.utc)
                        db.commit()
                        acknowledged_ids.append(alert_id)
                        if doctor_user:
                            crud.write_audit(db, "ACKNOWLEDGE", "alert", entity_id=alert_id, user_id=doctor_user.user_id)
                        logger.info("Alert #%s marked ACKNOWLEDGED via WhatsApp by %s",
                                    alert_id, sender_phone)

            if acknowledged_ids:
                doctor = db.query(models.Doctor).filter(
                    models.Doctor.phone.like(f"%{sender_phone[-10:]}%")
                ).first()
                doctor_name = doctor.name if doctor else "Doctor"

                whatsapp_notifier.send_whatsapp_message(
                    sender_phone,
                    f"✅ Thank you, {doctor_name}!\n"
                    f"Alert(s) #{', #'.join(map(str, acknowledged_ids))} "
                    f"marked as ACKNOWLEDGED.\n"
                    f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                return {"status": "acknowledged", "alert_ids": acknowledged_ids}
            else:
                return {"status": "no_pending_alerts", "phone": sender_phone}

        return {"status": "received", "action": "none"}
    except Exception as e:
        logger.error("WhatsApp webhook error: %s", e, exc_info=True)
        return {"status": "error", "detail": "Unable to process webhook payload"}


# ═══════════════════════════════════════════════════════════════════════════════
#  ROOT & ADVANCED HEALTH CHECKS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/", tags=["Health"])
def root():
    return {
        "message": "Patient Monitor API is running",
        "version": "5.2.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.get("/health/db", response_model=schemas.HealthDetail, tags=["Health"])
def health_db(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Check database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "detail": "PostgreSQL reachable"}
    except Exception as e:
        logger.error("DB health check failed: %s", e)
        return {"status": "degraded", "detail": "Database connectivity check failed"}


@app.get("/health/redis", response_model=schemas.HealthDetail, tags=["Health"])
def health_redis(current_user: models.User = Depends(auth.require_role("ADMIN"))):
    """Check Redis connectivity."""
    try:
        r = get_redis_client()
        if r:
            r.ping()
            return {"status": "ok", "detail": "Redis reachable"}
        else:
            return {"status": "disabled", "detail": "Redis not running — using degraded mode"}
    except Exception:
        return {"status": "disabled", "detail": "Redis not running — using direct scheduler mode"}


@app.get("/health/whatsapp", response_model=schemas.HealthDetail, tags=["Health"])
def health_whatsapp(current_user: models.User = Depends(auth.require_role("ADMIN"))):
    """Check WhatsApp GREEN-API connectivity."""
    try:
        config = whatsapp_notifier.get_config()
        if not config["enabled"]:
            return {"status": "disabled", "detail": "WhatsApp notifications disabled"}
        if not config["credentials_set"]:
            return {"status": "degraded", "detail": "GREEN-API credentials not configured"}
        return {"status": "ok", "detail": f"{config['recipient_count']} recipients configured"}
    except Exception:
        return {"status": "degraded", "detail": "WhatsApp connectivity check failed"}


@app.get("/health/full", response_model=schemas.HealthCheckOut, tags=["Health"])
def health_full(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    """Comprehensive health check of all services."""
    db_health = health_db(db)
    redis_health = health_redis()
    wa_health = health_whatsapp()

    overall = "ok"
    for check in [db_health, redis_health, wa_health]:
        s = check.get("status") if isinstance(check, dict) else getattr(check, "status", "ok")
        if s == "degraded":
            overall = "degraded"
            break

    return {
        "status": overall,
        "db": db_health,
        "redis": redis_health,
        "whatsapp": wa_health,
    }


@app.get("/vitals/source", response_model=schemas.VitalsSourceConfigOut, tags=["Vitals"])
def get_vitals_source_config(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    _ = current_user
    config = data_sources.get_data_source_config()
    return {
        "source": config["source"],
        "thingspeak_channel_id": config["thingspeak_channel_id"] or None,
        "thingspeak_read_api_key_set": bool(config["thingspeak_read_api_key"]),
        "thingspeak_temp_unit": config["thingspeak_temp_unit"],
        "thingspeak_stale_seconds": config["thingspeak_stale_seconds"],
    }


@app.put("/vitals/source", response_model=schemas.VitalsSourceConfigOut, tags=["Vitals"])
def update_vitals_source_config(
    payload: schemas.VitalsSourceConfigUpdate,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
):
    _ = current_user
    try:
        config = data_sources.update_data_source_config(source=payload.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "source": config["source"],
        "thingspeak_channel_id": config["thingspeak_channel_id"] or None,
        "thingspeak_read_api_key_set": bool(config["thingspeak_read_api_key"]),
        "thingspeak_temp_unit": config["thingspeak_temp_unit"],
        "thingspeak_stale_seconds": config["thingspeak_stale_seconds"],
    }


@app.get("/admin/fake-vitals/status", response_model=schemas.FakeVitalsControlOut, tags=["Admin Controls"])
def fake_vitals_status(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    _ = current_user
    return {
        "enabled": _setting_bool(db, FAKE_VITALS_ENABLED_SETTING_KEY, default=True),
    }


@app.post("/admin/fake-vitals/force-start", response_model=schemas.FakeVitalsControlActionOut, tags=["Admin Controls"])
def force_start_fake_vitals(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    _set_setting_bool(db, FAKE_VITALS_ENABLED_SETTING_KEY, True)
    crud.write_audit(db, "UPDATE", "fake_vitals_control", user_id=current_user.user_id)
    return {
        "detail": "Fake vitals generation force-started",
        "enabled": True,
    }


@app.post("/admin/fake-vitals/force-stop", response_model=schemas.FakeVitalsControlActionOut, tags=["Admin Controls"])
def force_stop_fake_vitals(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    _set_setting_bool(db, FAKE_VITALS_ENABLED_SETTING_KEY, False)
    crud.write_audit(db, "UPDATE", "fake_vitals_control", user_id=current_user.user_id)
    return {
        "detail": "Fake vitals generation force-stopped",
        "enabled": False,
    }


@app.post("/admin/vitals/cleanup", response_model=schemas.VitalsCleanupResultOut, tags=["Admin Controls"])
def cleanup_vitals(
    payload: schemas.VitalsCleanupRequest,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    _ = current_user
    now_utc = datetime.now(timezone.utc)
    cutoff = None
    if payload.mode == "last_24h":
        cutoff = now_utc - timedelta(hours=24)
    elif payload.mode == "last_7d":
        cutoff = now_utc - timedelta(days=7)
    elif payload.mode == "last_30d":
        cutoff = now_utc - timedelta(days=30)
    elif payload.mode == "before_datetime":
        if not payload.before_datetime:
            raise HTTPException(status_code=400, detail="before_datetime is required for mode=before_datetime")
        cutoff = payload.before_datetime

    vitals_q = db.query(models.Vitals.vital_id)
    if payload.source in {"fake", "thingspeak"}:
        vitals_q = vitals_q.filter(models.Vitals.source == payload.source)
    if cutoff is not None:
        vitals_q = vitals_q.filter(models.Vitals.timestamp <= cutoff)

    vitals_subq = vitals_q.subquery()
    has_vitals = db.query(vitals_subq.c.vital_id).first()
    if not has_vitals:
        return {
            "detail": "No vitals matched cleanup filters",
            "deleted_vitals": 0,
            "deleted_alerts": 0,
            "deleted_escalations": 0,
            "deleted_notifications": 0,
            "deleted_whatsapp_logs": 0,
            "deleted_sla_records": 0,
        }

    alerts_q = db.query(models.Alert.alert_id).filter(
        models.Alert.vital_id.in_(db.query(vitals_subq.c.vital_id))
    )
    alerts_subq = alerts_q.subquery()

    deleted_escalations = 0
    deleted_notifications = 0
    deleted_whatsapp_logs = 0
    has_alerts = db.query(alerts_subq.c.alert_id).first()
    if has_alerts:
        alert_id_query = db.query(alerts_subq.c.alert_id)
        deleted_escalations = db.query(models.AlertEscalation).filter(
            models.AlertEscalation.alert_id.in_(alert_id_query)
        ).delete(synchronize_session=False)
        deleted_notifications = db.query(models.AlertNotification).filter(
            models.AlertNotification.alert_id.in_(alert_id_query)
        ).delete(synchronize_session=False)
        deleted_whatsapp_logs = db.query(models.WhatsAppLog).filter(
            models.WhatsAppLog.alert_id.in_(alert_id_query)
        ).delete(synchronize_session=False)

    deleted_sla_records = db.query(models.SLARecord).filter(
        models.SLARecord.alert_id.in_(db.query(alerts_subq.c.alert_id))
    ).delete(synchronize_session=False)
    deleted_alerts = db.query(models.Alert).filter(
        models.Alert.alert_id.in_(db.query(alerts_subq.c.alert_id))
    ).delete(synchronize_session=False)
    deleted_vitals = db.query(models.Vitals).filter(
        models.Vitals.vital_id.in_(db.query(vitals_subq.c.vital_id))
    ).delete(synchronize_session=False)
    db.commit()

    crud.write_audit(db, "DELETE", "vitals_cleanup", user_id=current_user.user_id)
    return {
        "detail": "Vitals cleanup completed",
        "deleted_vitals": deleted_vitals,
        "deleted_alerts": deleted_alerts,
        "deleted_escalations": deleted_escalations,
        "deleted_notifications": deleted_notifications,
        "deleted_whatsapp_logs": deleted_whatsapp_logs,
        "deleted_sla_records": deleted_sla_records,
    }


@app.post("/admin/reset/fresh", response_model=schemas.FreshResetResultOut, tags=["Admin Controls"])
def fresh_reset_domain_data(
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    deleted_users = db.query(models.User).filter(models.User.role != "ADMIN").count()
    deleted_patients = db.query(models.Patient).count()
    deleted_doctors = db.query(models.Doctor).count()
    deleted_nurses = db.query(models.Nurse).count()
    deleted_hospitals = db.query(models.Hospital).count()
    deleted_vitals = db.query(models.Vitals).count()
    deleted_alerts = db.query(models.Alert).count()

    # Keep admin accounts but detach them from domain entities.
    db.query(models.User).filter(models.User.role == "ADMIN").update(
        {"doctor_id": None, "nurse_id": None},
        synchronize_session=False,
    )
    db.query(models.User).filter(models.User.role != "ADMIN").delete(synchronize_session=False)

    if db.bind and db.bind.dialect.name == "postgresql":
        # Truncate domain/runtime tables in one shot to avoid FK delete-order issues.
        db.execute(
            text(
                """
                TRUNCATE TABLE
                    alert_escalations,
                    alert_notifications,
                    whatsapp_logs,
                    sla_records,
                    alerts,
                    vitals,
                    chat_messages,
                    password_reset_tokens,
                    patients,
                    doctors,
                    nurses,
                    hospitals
                RESTART IDENTITY CASCADE
                """
            )
        )
    else:
        # Portable fallback for sqlite/other engines used in local tests.
        db.query(models.AlertEscalation).delete(synchronize_session=False)
        db.query(models.AlertNotification).delete(synchronize_session=False)
        db.query(models.WhatsAppLog).delete(synchronize_session=False)
        db.query(models.SLARecord).delete(synchronize_session=False)
        db.query(models.Alert).delete(synchronize_session=False)
        db.query(models.Vitals).delete(synchronize_session=False)
        db.query(models.ChatMessage).delete(synchronize_session=False)
        db.query(models.PasswordResetToken).delete(synchronize_session=False)
        db.query(models.Patient).delete(synchronize_session=False)
        db.query(models.Doctor).delete(synchronize_session=False)
        db.query(models.Nurse).delete(synchronize_session=False)
        db.query(models.Hospital).delete(synchronize_session=False)

    db.commit()
    _set_setting_bool(db, FAKE_VITALS_ENABLED_SETTING_KEY, False)
    crud.write_audit(db, "DELETE", "fresh_reset", user_id=current_user.user_id)

    return {
        "detail": "Fresh reset completed. Admin users preserved.",
        "deleted_users": deleted_users,
        "deleted_patients": deleted_patients,
        "deleted_doctors": deleted_doctors,
        "deleted_nurses": deleted_nurses,
        "deleted_hospitals": deleted_hospitals,
        "deleted_vitals": deleted_vitals,
        "deleted_alerts": deleted_alerts,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  WHATSAPP LOGS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/whatsapp/logs", response_model=List[schemas.WhatsAppLogOut], tags=["WhatsApp"])
def list_whatsapp_logs(
    limit: int = 100,
    offset: int = 0,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    return crud.get_whatsapp_logs(db, limit=limit, offset=offset)
