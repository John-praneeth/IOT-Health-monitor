from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Vitals ──────────────────────────────────────────────────────────────────
class VitalsBase(BaseModel):
    patient_id: int
    heart_rate: int
    spo2: int
    temperature: float


class VitalsCreate(VitalsBase):
    pass


class VitalsOut(VitalsBase):
    vital_id: int
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Alerts ───────────────────────────────────────────────────────────────────
class AlertOut(BaseModel):
    alert_id: int
    patient_id: int
    vital_id: Optional[int] = None
    alert_type: str
    status: str
    created_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None

    class Config:
        from_attributes = True


# ── Patients ─────────────────────────────────────────────────────────────────
class PatientBase(BaseModel):
    name: str
    age: int
    room_number: str
    hospital_id: Optional[int] = None
    assigned_doctor: Optional[int] = None
    assigned_nurse: Optional[int] = None


class PatientCreate(PatientBase):
    pass


class PatientOut(PatientBase):
    patient_id: int
    doctor_name: Optional[str] = None
    nurse_name: Optional[str] = None
    hospital_name: Optional[str] = None

    class Config:
        from_attributes = True


# ── Hospitals ─────────────────────────────────────────────────────────────────
class HospitalBase(BaseModel):
    name: str
    location: str
    phone: Optional[str] = None
    email: Optional[str] = None


class HospitalCreate(HospitalBase):
    pass


class HospitalOut(HospitalBase):
    hospital_id: int

    class Config:
        from_attributes = True


# ── Doctors ───────────────────────────────────────────────────────────────────
class DoctorBase(BaseModel):
    name: str
    specialization: Optional[str] = None
    hospital_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_freelancer: Optional[bool] = False
    is_available: Optional[bool] = True


class DoctorCreate(DoctorBase):
    username: Optional[str] = None   # if set, a login account is created
    password: Optional[str] = None   # required when username is provided


class DoctorOut(DoctorBase):
    doctor_id: int
    hospital_name: Optional[str] = None

    class Config:
        from_attributes = True


# ── Doctor Self-Registration ──────────────────────────────────────────────────
class DoctorSelfRegister(BaseModel):
    """Used by POST /auth/register/doctor — creates Doctor + User in one step."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    name: str
    specialization: str
    hospital_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_freelancer: bool = True


# ── Nurses ────────────────────────────────────────────────────────────────────
class NurseBase(BaseModel):
    name: str
    department: Optional[str] = None
    hospital_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class NurseCreate(NurseBase):
    username: Optional[str] = None   # if set, a login account is created
    password: Optional[str] = None   # required when username is provided


class NurseOut(NurseBase):
    nurse_id: int
    hospital_name: Optional[str] = None

    class Config:
        from_attributes = True


# ── Nurse Self-Registration ──────────────────────────────────────────────────
class NurseSelfRegister(BaseModel):
    """Used by POST /auth/register/nurse — creates Nurse + User in one step."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    name: str
    department: Optional[str] = None
    hospital_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None


# ── Assignment ────────────────────────────────────────────────────────────────
class AssignDoctor(BaseModel):
    doctor_id: int


class AssignNurse(BaseModel):
    nurse_id: int


# ── Alert Acknowledge ─────────────────────────────────────────────────────────
class AlertAcknowledge(BaseModel):
    acknowledged_by: int


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    """Staff registration (ADMIN creates other staff users)."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    role: str = Field(..., pattern=r"^(ADMIN|DOCTOR|NURSE)$")
    doctor_id: Optional[int] = None
    nurse_id: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    doctor_id: Optional[int] = None
    nurse_id: Optional[int] = None


class UserOut(BaseModel):
    user_id: int
    username: str
    role: str
    doctor_id: Optional[int] = None
    nurse_id: Optional[int] = None

    class Config:
        from_attributes = True


# ── Alert Escalation ─────────────────────────────────────────────────────────
class EscalationOut(BaseModel):
    escalation_id: int
    alert_id: int
    escalated_to_doctor: int
    escalated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Alert Notification ────────────────────────────────────────────────────────
class AlertNotificationOut(BaseModel):
    notification_id: int
    alert_id: int
    user_id: int
    message: str
    is_read: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Audit Log ─────────────────────────────────────────────────────────────────
class AuditLogOut(BaseModel):
    log_id: int
    user_id: Optional[int] = None
    action: str
    entity: str
    entity_id: Optional[int] = None
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Chat Messages ─────────────────────────────────────────────────────────────
class ChatMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessageOut(BaseModel):
    message_id: int
    patient_id: int
    sender_username: str
    sender_role: str
    message: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Dashboard Stats ───────────────────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_patients: int
    total_doctors: int
    total_nurses: int
    total_hospitals: int
    pending_alerts: int
    escalated_alerts: int
    acknowledged_alerts: int


# ── WhatsApp Configuration ───────────────────────────────────────────────────
class WhatsAppConfigOut(BaseModel):
    enabled: bool
    alerts_paused: bool = False
    provider: str
    credentials_set: bool
    recipients: List[str]
    recipient_count: int
    pending_acknowledgements: int = 0


class WhatsAppRecipientAdd(BaseModel):
    phone: str = Field(..., description="Phone number with country code (no + prefix), e.g. 919876543210")


class WhatsAppRecipientRemove(BaseModel):
    phone: str


class WhatsAppRecipientsSet(BaseModel):
    phones: List[str] = Field(..., description="List of phone numbers")


class WhatsAppTestMessage(BaseModel):
    phone: Optional[str] = Field(None, description="Phone number to test (optional, uses first recipient)")


class WhatsAppTestResult(BaseModel):
    success: bool
    to: Optional[str] = None
    error: Optional[str] = None


# ── WhatsApp Log ──────────────────────────────────────────────────────────────
class WhatsAppLogOut(BaseModel):
    log_id: int
    alert_id: Optional[int] = None
    recipient: str
    message_type: str
    status: str
    attempts: int
    error: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Health Check ──────────────────────────────────────────────────────────────
class HealthDetail(BaseModel):
    status: str
    detail: Optional[str] = None


class HealthCheckOut(BaseModel):
    status: str
    db: Optional[HealthDetail] = None
    redis: Optional[HealthDetail] = None
    whatsapp: Optional[HealthDetail] = None


# ── Pagination Meta ───────────────────────────────────────────────────────────
class PaginationParams(BaseModel):
    limit: int = 50
    offset: int = 0
