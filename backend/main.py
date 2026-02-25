"""
main.py  –  FastAPI backend for IoT Healthcare Patient Monitor.
Version 4.0 – Freelancer doctors, specialization, escalation notifications.
"""

import asyncio
import json
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import auth
import crud
import models
import schemas
from database import engine, Base, SessionLocal

# ── Create tables ─────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="IoT Healthcare Patient Monitor",
    version="4.0.0",
    description="Real-time patient monitoring with freelancer doctor management, specialization-based escalation, and notifications.",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
import os
origins = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def register(body: schemas.RegisterRequest, db: Session = Depends(get_db)):
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
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = auth.get_user_by_username(db, body.username)
    if not user or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth.create_access_token({"sub": user.username, "role": user.role})
    crud.write_audit(db, "LOGIN", "user", entity_id=user.user_id)
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
    db: Session = Depends(get_db),
):
    return crud.get_doctors(db, hospital_id=hospital_id, specialization=specialization)


@app.post("/doctors", response_model=schemas.DoctorOut, tags=["Doctors"])
def create_doctor(
    doctor: schemas.DoctorCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    return crud.create_doctor(db, doctor)


@app.get("/doctors/{doctor_id}", response_model=schemas.DoctorOut, tags=["Doctors"])
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    d = crud.get_doctor(db, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return d


@app.delete("/doctors/{doctor_id}", tags=["Doctors"])
def delete_doctor(
    doctor_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    d = crud.delete_doctor(db, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"detail": "Doctor deleted"}


@app.get("/doctors/{doctor_id}/patients", response_model=List[schemas.PatientOut], tags=["Doctors"])
def list_doctor_patients(doctor_id: int, db: Session = Depends(get_db)):
    return crud.get_patients(db, doctor_id=doctor_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  NURSE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/nurses", response_model=List[schemas.NurseOut], tags=["Nurses"])
def list_nurses(hospital_id: Optional[int] = None, db: Session = Depends(get_db)):
    return crud.get_nurses(db, hospital_id=hospital_id)


@app.post("/nurses", response_model=schemas.NurseOut, tags=["Nurses"])
def create_nurse(
    nurse: schemas.NurseCreate,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    return crud.create_nurse(db, nurse)


@app.get("/nurses/{nurse_id}", response_model=schemas.NurseOut, tags=["Nurses"])
def get_nurse(nurse_id: int, db: Session = Depends(get_db)):
    n = crud.get_nurse(db, nurse_id)
    if not n:
        raise HTTPException(status_code=404, detail="Nurse not found")
    return n


@app.delete("/nurses/{nurse_id}", tags=["Nurses"])
def delete_nurse(
    nurse_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    n = crud.delete_nurse(db, nurse_id)
    if not n:
        raise HTTPException(status_code=404, detail="Nurse not found")
    return {"detail": "Nurse deleted"}


@app.get("/nurses/{nurse_id}/patients", response_model=List[schemas.PatientOut], tags=["Nurses"])
def list_nurse_patients(nurse_id: int, db: Session = Depends(get_db)):
    return crud.get_patients(db, nurse_id=nurse_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  PATIENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/patients", response_model=List[schemas.PatientOut], tags=["Patients"])
def list_patients(
    doctor_id: Optional[int] = None,
    nurse_id: Optional[int] = None,
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
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    p = crud.get_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return p


@app.delete("/patients/{patient_id}", tags=["Patients"])
def delete_patient(
    patient_id: int,
    current_user: models.User = Depends(auth.require_role("ADMIN", "DOCTOR")),
    db: Session = Depends(get_db),
):
    p = crud.delete_patient(db, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"detail": "Patient deleted"}


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
def create_vitals(vital: schemas.VitalsCreate, db: Session = Depends(get_db)):
    return crud.create_vitals(db=db, vital=vital)


@app.get("/vitals", response_model=List[schemas.VitalsOut], tags=["Vitals"])
def get_vitals(
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return crud.get_vitals(db, patient_id=patient_id, doctor_id=doctor_id, limit=limit)


@app.get("/vitals/latest/{patient_id}", response_model=schemas.VitalsOut, tags=["Vitals"])
def get_latest_vital(patient_id: int, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db),
):
    return crud.get_alerts(db, status=status, doctor_id=doctor_id)


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
def dashboard_stats(db: Session = Depends(get_db)):
    return crud.get_dashboard_stats(db)


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT ENDPOINTS  (per-patient treatment chat)
# ═══════════════════════════════════════════════════════════════════════════════
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
#  WEBSOCKET – real-time vitals push
# ═══════════════════════════════════════════════════════════════════════════════
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)

    async def broadcast(self, message: str):
        for conn in list(self.active_connections):
            try:
                await conn.send_text(message)
            except Exception:
                self.active_connections.remove(conn)


manager = ConnectionManager()


@app.websocket("/ws/vitals")
async def ws_vitals(websocket: WebSocket, db: Session = Depends(get_db)):
    """Streams the latest vitals for ALL patients every 5 seconds."""
    await manager.connect(websocket)
    try:
        while True:
            patients = crud.get_patients(db)
            payload = []
            for p in patients:
                v = crud.get_latest_vital(db, p.patient_id)
                if v:
                    payload.append(
                        {
                            "patient_id": p.patient_id,
                            "name": p.name,
                            "room": p.room_number,
                            "heart_rate": v.heart_rate,
                            "spo2": v.spo2,
                            "temperature": v.temperature,
                            "blood_pressure": v.blood_pressure,
                            "timestamp": str(v.timestamp),
                        }
                    )
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ═══════════════════════════════════════════════════════════════════════════════
#  ROOT & HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/", tags=["Health"])
def root():
    return {
        "message": "Patient Monitor API is running",
        "version": "4.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
