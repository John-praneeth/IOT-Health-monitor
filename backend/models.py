from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, TIMESTAMP, func, CheckConstraint
from sqlalchemy.orm import relationship
from database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    hospital_id = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100))
    location    = Column(String(200))
    phone       = Column(String(20), nullable=True)
    email       = Column(String(100), nullable=True)

    doctors  = relationship("Doctor",  back_populates="hospital")
    nurses   = relationship("Nurse",   back_populates="hospital")
    patients = relationship("Patient", back_populates="hospital")


class Doctor(Base):
    __tablename__ = "doctors"

    doctor_id      = Column(Integer, primary_key=True, index=True)
    name           = Column(String(100))
    specialization = Column(String(100), nullable=True)
    hospital_id    = Column(Integer, ForeignKey("hospitals.hospital_id"), nullable=True)
    phone          = Column(String(20))
    email          = Column(String(100))
    is_freelancer  = Column(Boolean, default=False)
    is_available   = Column(Boolean, default=True)

    hospital = relationship("Hospital", back_populates="doctors")
    patients = relationship("Patient", back_populates="doctor")


class Nurse(Base):
    __tablename__ = "nurses"

    nurse_id    = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100))
    department  = Column(String(100), nullable=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.hospital_id"), nullable=True)
    phone       = Column(String(20))
    email       = Column(String(100))

    hospital = relationship("Hospital", back_populates="nurses")
    patients = relationship("Patient", back_populates="nurse")


class Patient(Base):
    __tablename__ = "patients"

    patient_id      = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100))
    age             = Column(Integer)
    room_number     = Column(String(20))
    hospital_id     = Column(Integer, ForeignKey("hospitals.hospital_id"), nullable=True)
    assigned_doctor = Column(Integer, ForeignKey("doctors.doctor_id"), nullable=True)
    assigned_nurse  = Column(Integer, ForeignKey("nurses.nurse_id"), nullable=True)

    hospital = relationship("Hospital", back_populates="patients")
    doctor   = relationship("Doctor",   back_populates="patients")
    nurse    = relationship("Nurse",    back_populates="patients")


class Vitals(Base):
    __tablename__ = "vitals"

    vital_id       = Column(Integer, primary_key=True, index=True)
    patient_id     = Column(Integer, ForeignKey("patients.patient_id"))
    heart_rate     = Column(Integer)
    spo2           = Column(Integer)
    temperature    = Column(Float)
    blood_pressure = Column(String(20))
    timestamp      = Column(TIMESTAMP, server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    alert_id        = Column(Integer, primary_key=True, index=True)
    patient_id      = Column(Integer, ForeignKey("patients.patient_id"))
    vital_id        = Column(Integer, ForeignKey("vitals.vital_id"))
    alert_type      = Column(String(50))
    status          = Column(String(20), default="PENDING")
    created_at      = Column(TIMESTAMP, server_default=func.now())
    acknowledged_by = Column(Integer, nullable=True)

    escalations   = relationship("AlertEscalation", back_populates="alert")
    notifications = relationship("AlertNotification", back_populates="alert")


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH & AUDIT TABLES
# ═══════════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    user_id       = Column(Integer, primary_key=True, index=True)
    username      = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(20), nullable=False)
    doctor_id     = Column(Integer, ForeignKey("doctors.doctor_id"), nullable=True)
    nurse_id      = Column(Integer, ForeignKey("nurses.nurse_id"), nullable=True)

    __table_args__ = (
        CheckConstraint("role IN ('ADMIN','DOCTOR','NURSE')", name="ck_user_role"),
    )


class AlertEscalation(Base):
    __tablename__ = "alert_escalations"

    escalation_id       = Column(Integer, primary_key=True, index=True)
    alert_id            = Column(Integer, ForeignKey("alerts.alert_id"), nullable=False)
    escalated_to_doctor = Column(Integer, ForeignKey("doctors.doctor_id"), nullable=False)
    escalated_at        = Column(TIMESTAMP, server_default=func.now())

    alert  = relationship("Alert",  back_populates="escalations")
    doctor = relationship("Doctor")


class AlertNotification(Base):
    """Per-user notification: created when an alert is escalated to a doctor/nurse."""
    __tablename__ = "alert_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    alert_id        = Column(Integer, ForeignKey("alerts.alert_id"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    message         = Column(String(500), nullable=False)
    is_read         = Column(Boolean, default=False)
    created_at      = Column(TIMESTAMP, server_default=func.now())

    alert = relationship("Alert", back_populates="notifications")
    user  = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id    = Column(Integer, primary_key=True, index=True)
    user_id   = Column(Integer, nullable=True)
    action    = Column(String(100), nullable=False)
    entity    = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    timestamp = Column(TIMESTAMP, server_default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id      = Column(Integer, primary_key=True, index=True)
    patient_id      = Column(Integer, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    sender_username = Column(String(100), nullable=False)
    sender_role     = Column(String(20), nullable=False)
    message         = Column(String(2000), nullable=False)
    created_at      = Column(TIMESTAMP, server_default=func.now())

    patient = relationship("Patient")
