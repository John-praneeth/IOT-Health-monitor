"""
auth.py  –  JWT authentication & role-based access control.
"""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

import models
from database import SessionLocal, get_redis_client
from logger import log_security_event

# ── Settings ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "iot-healthcare-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")

_revoked_jtis: dict[str, float] = {}

# ── OAuth2 scheme ─────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Token helpers ─────────────────────────────────────────────────────────────
def _cleanup_revocations() -> None:
    now = time.time()
    for jti, exp in list(_revoked_jtis.items()):
        if exp <= now:
            _revoked_jtis.pop(jti, None)


def _revoke_key(jti: str) -> str:
    return f"jwt:revoked:{jti}"


def revoke_token_jti(jti: Optional[str], exp: Optional[int]) -> None:
    if not jti or not exp:
        return

    ttl = max(1, int(exp - time.time()))
    r = get_redis_client()
    if r:
        r.set(_revoke_key(jti), "1", ex=ttl)
        return

    _cleanup_revocations()
    _revoked_jtis[jti] = float(exp)


def is_token_revoked(jti: Optional[str]) -> bool:
    if not jti:
        return True
    r = get_redis_client()
    if r:
        return bool(r.exists(_revoke_key(jti)))

    _cleanup_revocations()
    return jti in _revoked_jtis


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": uuid.uuid4().hex,
            "typ": "access",
        }
    )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": uuid.uuid4().hex,
            "typ": "refresh",
        }
    )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(
    token: str,
    *,
    expected_type: Optional[str] = None,
    verify_exp: bool = True,
) -> Optional[dict]:
    options = {"verify_exp": verify_exp}
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options=options)
    token_type = payload.get("typ")
    if expected_type and token_type != expected_type:
        return None
    return payload


def issue_token_pair(user: models.User) -> tuple[str, str]:
    access_token = create_access_token({"sub": user.username, "role": user.role})
    refresh_token = create_refresh_token({"sub": user.username, "role": user.role})
    return access_token, refresh_token


def reset_auth_security_state() -> None:
    _revoked_jtis.clear()


# ── DB dependency (re-used from main – but we need one here too) ──────────────
def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Current user dependency ──────────────────────────────────────────────────
def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(_get_db),
    request: Request = None,
) -> Optional[models.User]:
    """
    If a valid JWT is present, return the User.
    If no token is sent, return None (public access).
    """
    if token is None:
        return None
    try:
        payload = decode_token(token, expected_type="access")
        if payload is None:
            log_security_event("TOKEN_VALIDATION_FAILED", request=request, reason="wrong_token_type")
            return None
        if is_token_revoked(payload.get("jti")):
            log_security_event("TOKEN_VALIDATION_FAILED", request=request, reason="token_revoked")
            return None
        username: str = payload.get("sub")
        if username is None:
            log_security_event("TOKEN_VALIDATION_FAILED", request=request, reason="missing_subject")
            return None
    except ExpiredSignatureError:
        log_security_event("TOKEN_VALIDATION_FAILED", request=request, reason="token_expired")
        return None
    except JWTError:
        log_security_event("TOKEN_VALIDATION_FAILED", request=request, reason="invalid_token")
        return None

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        log_security_event("TOKEN_VALIDATION_FAILED", request=request, user=username, reason="user_not_found")
    return user


def require_auth(
    current_user: Optional[models.User] = Depends(get_current_user),
) -> models.User:
    """Raise 401 if user is not authenticated."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_token(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def require_role(*roles: str):
    """Return a dependency that requires one of the listed roles."""
    def _dependency(current_user: models.User = Depends(require_auth)) -> models.User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not allowed. Required: {', '.join(roles)}",
            )
        return current_user
    return _dependency


# ── CRUD helpers for users ────────────────────────────────────────────────────
def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def create_user(db: Session, username: str, password: str, role: str,
                doctor_id: int = None, nurse_id: int = None) -> models.User:
    user = models.User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        doctor_id=doctor_id,
        nurse_id=nurse_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
