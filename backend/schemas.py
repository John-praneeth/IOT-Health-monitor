from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime


class ProjectBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


def validate_password_complexity(v: str) -> str:
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one numerical digit")
    return v


# ── Vitals ──────────────────────────────────────────────────────────────────
class VitalsBase(ProjectBaseModel):
    patient_id: int
    heart_rate: int = Field(..., ge=30, le=220)
    spo2: int = Field(..., ge=70, le=100)
    temperature: float = Field(..., ge=85, le=110)


class VitalsCreate(VitalsBase):
    pass


class VitalsOut(VitalsBase):
    vital_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Alerts ───────────────────────────────────────────────────────────────────
class AlertOut(ProjectBaseModel):
    alert_id: int
    patient_id: int
    vital_id: Optional[int] = None
    alert_type: str
    status: str
    created_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Patients ─────────────────────────────────────────────────────────────────
class PatientBase(ProjectBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=130)
    room_number: str = Field(..., min_length=1, max_length=20)
    hospital_id: Optional[int] = None
    assigned_doctor: Optional[int] = None
    assigned_nurse: Optional[int] = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(ProjectBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=130)
    room_number: str = Field(..., min_length=1, max_length=20)
    hospital_id: Optional[int] = None
    assigned_doctor: Optional[int] = None
    assigned_nurse: Optional[int] = None


class PatientOut(PatientBase):
    patient_id: int
    doctor_name: Optional[str] = None
    nurse_name: Optional[str] = None
    hospital_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Hospitals ─────────────────────────────────────────────────────────────────
class HospitalBase(ProjectBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)


class HospitalCreate(HospitalBase):
    pass


class HospitalUpdate(HospitalBase):
    pass


class HospitalOut(HospitalBase):
    hospital_id: int
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Doctors ───────────────────────────────────────────────────────────────────
class DoctorBase(ProjectBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    specialization: Optional[str] = Field(None, max_length=100)
    hospital_id: Optional[int] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    is_freelancer: Optional[bool] = False
    is_available: Optional[bool] = True


class DoctorCreate(DoctorBase):
    username: Optional[str] = Field(None, max_length=100)   # if set, a login account is created
    password: Optional[str] = Field(None, min_length=6, max_length=200)   # required when username is provided


class DoctorUpdate(ProjectBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    specialization: Optional[str] = Field(None, max_length=100)
    hospital_id: Optional[int] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    is_freelancer: Optional[bool] = False
    is_available: Optional[bool] = True


class DoctorOut(DoctorBase):
    doctor_id: int
    hospital_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Doctor Self-Registration ──────────────────────────────────────────────────
class DoctorSelfRegister(ProjectBaseModel):
    """Used by POST /auth/register/doctor — creates Doctor + User in one step."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=200)
    name: str = Field(..., min_length=1, max_length=100)
    specialization: str = Field(..., min_length=1, max_length=100)
    hospital_id: Optional[int] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    is_freelancer: bool = True

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v):
        return validate_password_complexity(v)


# ── Nurses ────────────────────────────────────────────────────────────────────
class NurseBase(ProjectBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    hospital_id: Optional[int] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)


class NurseCreate(NurseBase):
    username: Optional[str] = Field(None, max_length=100)   # if set, a login account is created
    password: Optional[str] = Field(None, min_length=6, max_length=200)   # required when username is provided


class NurseUpdate(ProjectBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    hospital_id: Optional[int] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)


class NurseOut(NurseBase):
    nurse_id: int
    hospital_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Nurse Self-Registration ──────────────────────────────────────────────────
class NurseSelfRegister(ProjectBaseModel):
    """Used by POST /auth/register/nurse — creates Nurse + User in one step."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=200)
    name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    hospital_id: Optional[int] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v):
        return validate_password_complexity(v)


# ── Assignment ────────────────────────────────────────────────────────────────
class AssignDoctor(ProjectBaseModel):
    doctor_id: Optional[int] = None


class AssignNurse(ProjectBaseModel):
    nurse_id: Optional[int] = None


# ── Alert Acknowledge ─────────────────────────────────────────────────────────
class AlertAcknowledge(ProjectBaseModel):
    acknowledged_by: int


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterRequest(ProjectBaseModel):
    """Staff registration (ADMIN creates other staff users)."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=200)
    role: str = Field(..., pattern=r"^(ADMIN|DOCTOR|NURSE)$")
    doctor_id: Optional[int] = None
    nurse_id: Optional[int] = None

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v):
        return validate_password_complexity(v)


class LoginRequest(ProjectBaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class ResetPasswordRequest(ProjectBaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=200)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v):
        return validate_password_complexity(v)


class ForgotPasswordStartRequest(ProjectBaseModel):
    username: str = Field(..., min_length=1, max_length=100)


class ForgotPasswordConfirmRequest(ProjectBaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    verification_code: str = Field(..., min_length=4, max_length=20)
    new_password: str = Field(..., min_length=8, max_length=200)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v):
        return validate_password_complexity(v)


class TokenResponse(ProjectBaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    doctor_id: Optional[int] = None
    nurse_id: Optional[int] = None


class UserOut(ProjectBaseModel):
    user_id: int
    username: str
    role: str
    doctor_id: Optional[int] = None
    nurse_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Alert Escalation ─────────────────────────────────────────────────────────
class EscalationOut(ProjectBaseModel):
    escalation_id: int
    alert_id: int
    escalated_to_doctor: int
    escalated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Alert Notification ────────────────────────────────────────────────────────
class AlertNotificationOut(ProjectBaseModel):
    notification_id: int
    alert_id: int
    user_id: int
    message: str
    is_read: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Audit Log ─────────────────────────────────────────────────────────────────
class AuditLogOut(ProjectBaseModel):
    log_id: int
    user_id: Optional[int] = None
    action: str
    entity: str
    entity_id: Optional[int] = None
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Chat Messages ─────────────────────────────────────────────────────────────
class ChatMessageCreate(ProjectBaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessageOut(ProjectBaseModel):
    message_id: int
    patient_id: int
    sender_username: str
    sender_role: str
    message: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Dashboard Stats ───────────────────────────────────────────────────────────
class DashboardStats(ProjectBaseModel):
    total_patients: int
    total_doctors: int
    total_nurses: int
    total_hospitals: int
    pending_alerts: int
    escalated_alerts: int
    acknowledged_alerts: int
    duplicate_vitals_count: int = 0


# ── WhatsApp Configuration ───────────────────────────────────────────────────
class WhatsAppConfigOut(ProjectBaseModel):
    enabled: bool
    alerts_paused: bool = False
    provider: str
    credentials_set: bool
    recipients: List[str]
    recipient_count: int
    pending_acknowledgements: int = 0


class WhatsAppRecipientAdd(ProjectBaseModel):
    phone: str = Field(..., description="Phone number with country code (no + prefix), e.g. 919876543210")


class WhatsAppRecipientRemove(ProjectBaseModel):
    phone: str


class WhatsAppRecipientsSet(ProjectBaseModel):
    phones: List[str] = Field(..., description="List of phone numbers")


class WhatsAppTestMessage(ProjectBaseModel):
    phone: Optional[str] = Field(None, description="Phone number to test (optional, uses first recipient)")


class WhatsAppTestResult(ProjectBaseModel):
    success: bool
    to: Optional[str] = None
    error: Optional[str] = None


# ── WhatsApp Log ──────────────────────────────────────────────────────────────
class WhatsAppLogOut(ProjectBaseModel):
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

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ── Health Check ──────────────────────────────────────────────────────────────
class HealthDetail(ProjectBaseModel):
    status: str
    detail: Optional[str] = None


class HealthCheckOut(ProjectBaseModel):
    status: str
    db: Optional[HealthDetail] = None
    redis: Optional[HealthDetail] = None
    whatsapp: Optional[HealthDetail] = None


# ── Runtime / Maintenance Controls ───────────────────────────────────────────
class FakeVitalsControlOut(ProjectBaseModel):
    enabled: bool


class FakeVitalsControlActionOut(ProjectBaseModel):
    detail: str
    enabled: bool


class VitalsCleanupRequest(ProjectBaseModel):
    mode: str = Field(..., pattern=r"^(last_24h|last_7d|last_30d|before_datetime|all)$")
    before_datetime: Optional[datetime] = None
    source: str = Field(default="all", pattern=r"^(all|fake|thingspeak)$")


class VitalsCleanupResultOut(ProjectBaseModel):
    detail: str
    deleted_vitals: int
    deleted_alerts: int
    deleted_escalations: int
    deleted_notifications: int
    deleted_whatsapp_logs: int
    deleted_sla_records: int


class FreshResetResultOut(ProjectBaseModel):
    detail: str
    deleted_users: int
    deleted_patients: int
    deleted_doctors: int
    deleted_nurses: int
    deleted_hospitals: int
    deleted_vitals: int
    deleted_alerts: int


# ── Pagination Meta ───────────────────────────────────────────────────────────
class PaginationParams(ProjectBaseModel):
    limit: int = 50
    offset: int = 0


class VitalsSourceConfigOut(ProjectBaseModel):
    source: str
    thingspeak_channel_id: Optional[str] = None
    thingspeak_read_api_key_set: bool = False
    thingspeak_temp_unit: str = "F"
    thingspeak_stale_seconds: int = 120


class VitalsSourceConfigUpdate(ProjectBaseModel):
    source: str = Field(..., pattern=r"^(fake|thingspeak)$")
