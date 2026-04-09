"""
main.py  –  FastAPI backend for IoT Healthcare Patient Monitor v5.2.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from jose import JWTError, jwt

import auth
import crud
import models
import schemas
import whatsapp_notifier
from database import engine, Base, SessionLocal, require_redis_on_startup, get_redis_client, is_redis_available
from json_logger import setup_logging, request_id_var, generate_request_id
from rate_limiter import limiter, setup_rate_limiter, LOGIN_LIMIT
from exception_handlers import setup_exception_handlers

# ── Setup structured logging ─────────────────────────────────────────────────
setup_logging()

# ── Redis startup check ───────────────────────────────────────────────────────
require_redis_on_startup()

# ── Create tables ─────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)

# ── WebSocket config ──────────────────────────────────────────────────────────
WS_CONNECTION_LIMIT = int(os.getenv("WS_CONNECTION_LIMIT", "50"))
WS_MESSAGES_PER_MINUTE = int(os.getenv("WS_MESSAGES_PER_MINUTE", "120"))
WS_BROADCAST_MODE = os.getenv("WS_BROADCAST_MODE", "event")  # "event" (incremental) or "full"
WS_REDIS_CHANNEL = "iot:vitals"

# ── Basic Prometheus-compatible metrics (no external dependency) ─────────────
APP_STARTED_AT = time.time()
HTTP_REQUESTS_TOTAL = 0
HTTP_REQUEST_ERRORS_TOTAL = 0
HTTP_REQUEST_DURATION_SECONDS_SUM = 0.0

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="IoT Healthcare Patient Monitor",
    description="Real-time patient vital-sign monitoring with WhatsApp alerts, "
                "Redis pub/sub WebSocket, and role-based access control.",
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
    return response


# ── DB Dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    crud.write_audit(db, "REGISTER", "user", entity_id=user.user_id)
    return user


@app.post("/auth/register/doctor", response_model=schemas.TokenResponse, tags=["Auth"])
def register_doctor(body: schemas.DoctorSelfRegister, db: Session = Depends(get_db)):
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
    crud.write_audit(db, "SELF_REGISTER", "doctor", entity_id=doctor.doctor_id)

    token = auth.create_access_token({"sub": user.username, "role": user.role})
    return schemas.TokenResponse(
        access_token=token, role=user.role, username=user.username,
        doctor_id=doctor.doctor_id,
    )


@app.post("/auth/register/nurse", response_model=schemas.TokenResponse, tags=["Auth"])
def register_nurse(body: schemas.NurseSelfRegister, db: Session = Depends(get_db)):
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
    crud.write_audit(db, "SELF_REGISTER", "nurse", entity_id=nurse.nurse_id)

    token = auth.create_access_token({"sub": user.username, "role": user.role})
    return schemas.TokenResponse(
        access_token=token, role=user.role, username=user.username,
        nurse_id=nurse.nurse_id,
    )


@app.post("/auth/login", response_model=schemas.TokenResponse, tags=["Auth"])
@limiter.limit(LOGIN_LIMIT)
def login(body: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth.get_user_by_username(db, body.username)
    if not user or not auth.verify_password(body.password, user.password_hash):
        logger.warning("Failed login attempt for username: %s", body.username,
                        extra={"action": "login_failed"})
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth.create_access_token({"sub": user.username, "role": user.role})
    crud.write_audit(db, "LOGIN", "user", entity_id=user.user_id)
    logger.info("User logged in: %s (role: %s)", user.username, user.role,
                extra={"action": "login_success"})

    return schemas.TokenResponse(
        access_token=token, role=user.role, username=user.username,
        doctor_id=user.doctor_id, nurse_id=user.nurse_id,
    )


@app.get("/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def me(current_user: models.User = Depends(auth.require_auth)):
    return current_user


# ═══════════════════════════════════════════════════════════════════════════════
#  HOSPITAL ENDPOINTS  (ADMIN only for create)
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/hospitals", response_model=List[schemas.HospitalOut], tags=["Hospitals"])
def list_hospitals(db: Session = Depends(get_db)):
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
    return crud.create_doctor(db, doctor)


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


@app.delete("/doctors/{doctor_id}", tags=["Doctors"],
            summary="Delete doctor",
            description="Hard delete: permanently removes the doctor record from the database.")
def delete_doctor(
    doctor_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    d = crud.delete_doctor(db, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"detail": "Doctor deleted successfully"}


@app.get("/doctors/{doctor_id}/patients", response_model=List[schemas.PatientOut], tags=["Doctors"])
def list_doctor_patients(
    doctor_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_patients(db, doctor_id=doctor_id)


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
    return crud.create_nurse(db, nurse)


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


@app.delete("/nurses/{nurse_id}", tags=["Nurses"],
            summary="Delete nurse",
            description="Hard delete: permanently removes the nurse record from the database.")
def delete_nurse(
    nurse_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    n = crud.delete_nurse(db, nurse_id)
    if not n:
        raise HTTPException(status_code=404, detail="Nurse not found")
    return {"detail": "Nurse deleted successfully"}


@app.get("/nurses/{nurse_id}/patients", response_model=List[schemas.PatientOut], tags=["Nurses"])
def list_nurse_patients(
    nurse_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_patients(db, nurse_id=nurse_id)


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
    return crud.get_patients(db, doctor_id=doctor_id, nurse_id=nurse_id)


@app.post("/patients", response_model=schemas.PatientOut, tags=["Patients"])
def create_patient(
    patient: schemas.PatientCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR", "NURSE")),
    db: Session = Depends(get_db),
):
    return crud.create_patient(db, patient)


@app.get("/patients/{patient_id}", response_model=schemas.PatientOut, tags=["Patients"])
def get_patient(
    patient_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    p = crud.get_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return p


@app.delete("/patients/{patient_id}", tags=["Patients"],
            summary="Delete patient",
            description="Hard delete: permanently removes the patient and all their vitals from the database.")
def delete_patient(
    patient_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    p = crud.delete_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"detail": "Patient deleted successfully"}


@app.patch("/patients/{patient_id}/assign_doctor", response_model=schemas.PatientOut, tags=["Patients"])
def assign_doctor(
    patient_id: int,
    body: schemas.AssignDoctor,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR", "NURSE")),
    db: Session = Depends(get_db),
):
    p = crud.assign_doctor(db, patient_id, body.doctor_id)
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
    p = crud.assign_nurse(db, patient_id, body.nurse_id)
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
    return crud.create_vitals(db=db, vital=vital)


@app.get("/vitals", response_model=List[schemas.VitalsOut], tags=["Vitals"])
def get_vitals(
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    return crud.get_vitals(db, patient_id=patient_id, doctor_id=doctor_id, limit=limit, offset=offset)


@app.get("/vitals/latest/{patient_id}", response_model=schemas.VitalsOut, tags=["Vitals"])
def get_latest_vital(
    patient_id: int,
    current_user: models.User = Depends(auth.require_auth),
    db: Session = Depends(get_db),
):
    v = crud.get_latest_vital(db, patient_id)
    if not v:
        raise HTTPException(status_code=404, detail="No vitals found for this patient")
    return v


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
    return crud.get_alerts(db, status=status, doctor_id=doctor_id, limit=limit, offset=offset)


@app.patch("/alerts/{alert_id}/acknowledge", response_model=schemas.AlertOut, tags=["Alerts"])
def acknowledge_alert(
    alert_id: int,
    body: schemas.AlertAcknowledge,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    alert = crud.acknowledge_alert(db, alert_id, body.acknowledged_by)
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
    return crud.get_dashboard_stats(db)


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT ENDPOINTS  (per-patient treatment chat — v5.2: authorization check)
# ═══════════════════════════════════════════════════════════════════════════════

def _check_chat_access(current_user: models.User, patient, db: Session):
    """v5.2 FIX 6: Only ADMIN, assigned doctor, or assigned nurse can access chat."""
    if current_user.role == "ADMIN":
        return
    if current_user.doctor_id and patient.assigned_doctor == current_user.doctor_id:
        return
    if current_user.nurse_id and patient.assigned_nurse == current_user.nurse_id:
        return
    raise HTTPException(
        status_code=403,
        detail="You are not assigned to this patient. Only ADMIN, assigned doctor, or assigned nurse can access patient chat.",
    )


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
    _check_chat_access(current_user, p, db)
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
    _check_chat_access(current_user, p, db)
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
        self._msg_counts: dict[str, int] = {}
        self._msg_reset_time: dict[str, float] = {}

    async def connect(self, ws: WebSocket, client_ip: str = "unknown"):
        current = self._ip_counts.get(client_ip, 0)
        if current >= WS_CONNECTION_LIMIT:
            await ws.close(code=1008, reason="Too many WebSocket connections from this IP")
            return False
        await ws.accept()
        self.active_connections.append(ws)
        self._ip_counts[client_ip] = current + 1
        return True

    def disconnect(self, ws: WebSocket, client_ip: str = "unknown"):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        current = self._ip_counts.get(client_ip, 1)
        self._ip_counts[client_ip] = max(0, current - 1)

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

# ── Redis pub/sub subscriber (background task) ────────────────────────────────
_redis_subscriber_started = False


async def _redis_vitals_subscriber():
    """Subscribe to Redis pub/sub channel and broadcast to all WebSocket clients.
    Event-driven: scheduler publishes → Redis channel → backend subscribes → broadcast.
    Uses redis.asyncio for non-blocking pub/sub.
    """
    import redis.asyncio as aioredis
    from database import REDIS_URL
    logger.info("Starting Redis pub/sub subscriber on channel: %s", WS_REDIS_CHANNEL)
    while True:
        try:
            r = aioredis.from_url(REDIS_URL, socket_connect_timeout=5)
            pubsub = r.pubsub()
            await pubsub.subscribe(WS_REDIS_CHANNEL)
            async for raw_message in pubsub.listen():
                if raw_message["type"] == "message":
                    data = raw_message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await manager.broadcast(data)
        except Exception as e:
            logger.warning("Redis subscriber error (reconnecting in 3s): %s", e)
            await asyncio.sleep(3)


@app.on_event("startup")
async def startup_redis_subscriber():
    """Start the Redis pub/sub subscriber as a background task."""
    global _redis_subscriber_started
    if not _redis_subscriber_started and is_redis_available():
        asyncio.create_task(_redis_vitals_subscriber())
        _redis_subscriber_started = True
        logger.info("Redis pub/sub WebSocket subscriber started (v5.2 event-driven)")


def _get_ws_user(token: str, db: Session) -> Optional[models.User]:
    """Resolve a WebSocket user from a JWT token."""
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None
    return db.query(models.User).filter(models.User.username == username).first()


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
        await websocket.accept()
        await websocket.close(code=1008, reason="Missing auth token")
        return

    db = SessionLocal()
    try:
        user = _get_ws_user(token, db)
    finally:
        db.close()

    if not user:
        await websocket.accept()
        await websocket.close(code=1008, reason="Invalid auth token")
        return

    client_ip = websocket.client.host if websocket.client else "unknown"
    accepted = await manager.connect(websocket, client_ip)
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
                    patients = crud.get_patients(db)
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
        manager.disconnect(websocket, client_ip)


@app.get("/metrics", tags=["Monitoring"])
def metrics():
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
                    # Still allow — doctor may be escalated-to doctor

            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_at = datetime.now(timezone.utc)
            db.commit()

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
            acknowledged_ids = whatsapp_notifier.acknowledge_by_phone(sender_phone)

            if acknowledged_ids:
                for alert_id in acknowledged_ids:
                    alert = db.query(models.Alert).filter(
                        models.Alert.alert_id == alert_id
                    ).first()
                    if alert and alert.status in ("PENDING", "ESCALATED"):
                        alert.status = "ACKNOWLEDGED"
                        alert.acknowledged_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info("Alert #%s marked ACKNOWLEDGED via WhatsApp by %s",
                                    alert_id, sender_phone)

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
        return {"status": "error", "detail": str(e)}


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
def health_db(db: Session = Depends(get_db)):
    """Check database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "detail": "PostgreSQL reachable"}
    except Exception as e:
        logger.error("DB health check failed: %s", e)
        return {"status": "degraded", "detail": str(e)}


@app.get("/health/redis", response_model=schemas.HealthDetail, tags=["Health"])
def health_redis():
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
def health_whatsapp():
    """Check WhatsApp GREEN-API connectivity."""
    try:
        config = whatsapp_notifier.get_config()
        if not config["enabled"]:
            return {"status": "disabled", "detail": "WhatsApp notifications disabled"}
        if not config["credentials_set"]:
            return {"status": "degraded", "detail": "GREEN-API credentials not configured"}
        return {"status": "ok", "detail": f"{config['recipient_count']} recipients configured"}
    except Exception as e:
        return {"status": "degraded", "detail": str(e)}


@app.get("/health/full", response_model=schemas.HealthCheckOut, tags=["Health"])
def health_full(db: Session = Depends(get_db)):
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


