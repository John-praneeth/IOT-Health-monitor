"""
auth.py  –  JWT authentication & role-based access control.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import models
from database import SessionLocal

# ── Settings ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "iot-healthcare-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# ── OAuth2 scheme ─────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Token helpers ─────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


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
) -> Optional[models.User]:
    """
    If a valid JWT is present, return the User.
    If no token is sent, return None (public access).
    """
    if token is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None

    user = db.query(models.User).filter(models.User.username == username).first()
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
