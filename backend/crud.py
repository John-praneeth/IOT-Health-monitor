"""
crud.py  –  Database operations for the Patient Monitor system.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

import models
import schemas

logger = logging.getLogger(__name__)


# ── Audit Log ─────────────────────────────────────────────────────────────────
def write_audit(db: Session, action: str, entity: str, entity_id: int = None, user_id: int = None):
    log = models.AuditLog(
        user_id=user_id, action=action, entity=entity,
        entity_id=entity_id, timestamp=datetime.now(),
    )
    db.add(log)
    db.commit()


def get_audit_logs(db: Session, entity: str = None, limit: int = 200):
    q = db.query(models.AuditLog)
    if entity:
        q = q.filter(models.AuditLog.entity == entity)
    return q.order_by(models.AuditLog.timestamp.desc()).limit(limit).all()


# ── Vitals ────────────────────────────────────────────────────────────────────
def create_vitals(db: Session, vital):
    if isinstance(vital, dict):
        db_vital = models.Vitals(**vital)
    else:
        db_vital = models.Vitals(**vital.dict())
    db.add(db_vital)
    db.commit()
    db.refresh(db_vital)
    return db_vital


def get_vitals(db: Session, patient_id: int = None, doctor_id: int = None, limit: int = 50):
    q = db.query(models.Vitals)
    if patient_id:
        q = q.filter(models.Vitals.patient_id == patient_id)
    if doctor_id:
        patient_ids = [p.patient_id for p in get_patients_by_doctor(db, doctor_id)]
        q = q.filter(models.Vitals.patient_id.in_(patient_ids))
    return q.order_by(models.Vitals.timestamp.desc()).limit(limit).all()


def get_latest_vital(db: Session, patient_id: int):
    return (
        db.query(models.Vitals)
        .filter(models.Vitals.patient_id == patient_id)
        .order_by(models.Vitals.timestamp.desc())
        .first()
    )


# ── Alerts ────────────────────────────────────────────────────────────────────
def create_alert(db: Session, patient_id: int, vital_id: int, alert_type: str):
    # De-duplicate: skip if a PENDING alert of the same type already exists
    duplicate = (
        db.query(models.Alert)
        .filter(
            models.Alert.patient_id == patient_id,
            models.Alert.alert_type == alert_type,
            models.Alert.status == "PENDING",
        )
        .first()
    )
    if duplicate:
        logger.debug("Duplicate alert suppressed: %s for patient %s", alert_type, patient_id)
        return duplicate

    new_alert = models.Alert(
        patient_id=patient_id,
        vital_id=vital_id,
        alert_type=alert_type,
        status="PENDING",
        created_at=datetime.now(),
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    write_audit(db, "CREATE", "alert", entity_id=new_alert.alert_id)
    return new_alert


def get_alerts(db: Session, status: str = None, doctor_id: int = None, limit: int = 100):
    q = db.query(models.Alert)
    if status:
        q = q.filter(models.Alert.status == status)
    if doctor_id:
        patient_ids = [p.patient_id for p in get_patients_by_doctor(db, doctor_id)]
        q = q.filter(models.Alert.patient_id.in_(patient_ids))
    return q.order_by(models.Alert.created_at.desc()).limit(limit).all()


def acknowledge_alert(db: Session, alert_id: int, acknowledged_by: int):
    alert = db.query(models.Alert).filter(models.Alert.alert_id == alert_id).first()
    if alert:
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_by = acknowledged_by
        db.commit()
        db.refresh(alert)
    return alert


def escalate_stale_alerts(db: Session, threshold_minutes: int = 2):
    """
    Mark PENDING alerts older than `threshold_minutes` as ESCALATED.
    Create escalation records for same-specialization doctors.
    Create notifications for those doctors + nurses at the patient's hospital.
    """
    cutoff = datetime.now() - timedelta(minutes=threshold_minutes)
    stale = (
        db.query(models.Alert)
        .filter(models.Alert.status == "PENDING", models.Alert.created_at < cutoff)
        .all()
    )
    escalated = []
    for alert in stale:
        alert.status = "ESCALATED"
        escalated.append(alert)

        patient = db.query(models.Patient).filter(
            models.Patient.patient_id == alert.patient_id
        ).first()
        if not patient:
            continue

        # Find the assigned doctor's specialization
        assigned_doctor = None
        specialization = None
        if patient.assigned_doctor:
            assigned_doctor = db.query(models.Doctor).filter(
                models.Doctor.doctor_id == patient.assigned_doctor
            ).first()
            if assigned_doctor:
                specialization = assigned_doctor.specialization

        # Find same-specialization doctors (exclude the assigned one)
        same_spec_doctors = []
        if specialization:
            same_spec_doctors = (
                db.query(models.Doctor)
                .filter(
                    models.Doctor.specialization == specialization,
                    models.Doctor.is_available == True,
                    models.Doctor.doctor_id != (patient.assigned_doctor or -1),
                )
                .all()
            )

        # Create escalation records for each same-spec doctor
        for doc in same_spec_doctors:
            esc = models.AlertEscalation(
                alert_id=alert.alert_id,
                escalated_to_doctor=doc.doctor_id,
                escalated_at=datetime.now(),
            )
            db.add(esc)

            # Notify the doctor (via user account)
            doc_user = db.query(models.User).filter(models.User.doctor_id == doc.doctor_id).first()
            if doc_user:
                notif = models.AlertNotification(
                    alert_id=alert.alert_id,
                    user_id=doc_user.user_id,
                    message=f"🔺 ESCALATED: {alert.alert_type} for patient {patient.name} (Room {patient.room_number}). Original doctor did not respond.",
                    created_at=datetime.now(),
                )
                db.add(notif)

        # Also create escalation for the assigned doctor
        if assigned_doctor:
            esc = models.AlertEscalation(
                alert_id=alert.alert_id,
                escalated_to_doctor=assigned_doctor.doctor_id,
                escalated_at=datetime.now(),
            )
            db.add(esc)

        # Notify nurses at the patient's hospital
        if patient.hospital_id:
            hospital_nurses = (
                db.query(models.Nurse)
                .filter(models.Nurse.hospital_id == patient.hospital_id)
                .all()
            )
            for nurse in hospital_nurses:
                nurse_user = db.query(models.User).filter(models.User.nurse_id == nurse.nurse_id).first()
                if nurse_user:
                    notif = models.AlertNotification(
                        alert_id=alert.alert_id,
                        user_id=nurse_user.user_id,
                        message=f"🔺 ESCALATED: {alert.alert_type} for patient {patient.name} (Room {patient.room_number}). Please check immediately.",
                        created_at=datetime.now(),
                    )
                    db.add(notif)

    if escalated:
        db.commit()
    return escalated


def get_escalations(db: Session, alert_id: int = None, doctor_id: int = None, limit: int = 100):
    q = db.query(models.AlertEscalation)
    if alert_id:
        q = q.filter(models.AlertEscalation.alert_id == alert_id)
    if doctor_id:
        q = q.filter(models.AlertEscalation.escalated_to_doctor == doctor_id)
    return q.order_by(models.AlertEscalation.escalated_at.desc()).limit(limit).all()


# ── Notifications ─────────────────────────────────────────────────────────────
def get_notifications(db: Session, user_id: int, unread_only: bool = False, limit: int = 50):
    q = db.query(models.AlertNotification).filter(models.AlertNotification.user_id == user_id)
    if unread_only:
        q = q.filter(models.AlertNotification.is_read == False)
    return q.order_by(models.AlertNotification.created_at.desc()).limit(limit).all()


def mark_notification_read(db: Session, notification_id: int, user_id: int):
    notif = (
        db.query(models.AlertNotification)
        .filter(
            models.AlertNotification.notification_id == notification_id,
            models.AlertNotification.user_id == user_id,
        )
        .first()
    )
    if notif:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif


def mark_all_notifications_read(db: Session, user_id: int):
    db.query(models.AlertNotification).filter(
        models.AlertNotification.user_id == user_id,
        models.AlertNotification.is_read == False,
    ).update({"is_read": True})
    db.commit()


# ── Patients ──────────────────────────────────────────────────────────────────
def _enrich_patient(patient):
    """Add computed fields doctor_name, nurse_name, hospital_name."""
    patient.doctor_name   = patient.doctor.name   if patient.doctor   else None
    patient.nurse_name    = patient.nurse.name     if patient.nurse    else None
    patient.hospital_name = patient.hospital.name  if patient.hospital else None
    return patient


def get_patients(db: Session, doctor_id: int = None, nurse_id: int = None):
    q = db.query(models.Patient)
    if doctor_id:
        q = q.filter(models.Patient.assigned_doctor == doctor_id)
    if nurse_id:
        q = q.filter(models.Patient.assigned_nurse == nurse_id)
    return [_enrich_patient(p) for p in q.all()]


def get_patients_by_doctor(db: Session, doctor_id: int):
    return db.query(models.Patient).filter(models.Patient.assigned_doctor == doctor_id).all()


def get_patients_by_nurse(db: Session, nurse_id: int):
    return db.query(models.Patient).filter(models.Patient.assigned_nurse == nurse_id).all()


def get_patient(db: Session, patient_id: int):
    p = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    return _enrich_patient(p) if p else None


def create_patient(db: Session, patient: schemas.PatientCreate):
    db_patient = models.Patient(**patient.dict())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    write_audit(db, "CREATE", "patient", entity_id=db_patient.patient_id)
    return _enrich_patient(db_patient)


def delete_patient(db: Session, patient_id: int):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    if patient:
        db.delete(patient)
        db.commit()
        write_audit(db, "DELETE", "patient", entity_id=patient_id)
    return patient


def assign_doctor(db: Session, patient_id: int, doctor_id: int):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    if not patient:
        return None
    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == doctor_id).first()
    if not doctor:
        return None
    patient.assigned_doctor = doctor_id
    db.commit()
    db.refresh(patient)
    return _enrich_patient(patient)


def assign_nurse(db: Session, patient_id: int, nurse_id: int):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    if not patient:
        return None
    nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == nurse_id).first()
    if not nurse:
        return None
    patient.assigned_nurse = nurse_id
    db.commit()
    db.refresh(patient)
    return _enrich_patient(patient)


# ── Doctors ───────────────────────────────────────────────────────────────────
def _enrich_doctor(doctor):
    doctor.hospital_name = doctor.hospital.name if doctor.hospital else None
    return doctor


def get_doctors(db: Session, hospital_id: int = None, specialization: str = None):
    q = db.query(models.Doctor)
    if hospital_id:
        q = q.filter(models.Doctor.hospital_id == hospital_id)
    if specialization:
        q = q.filter(models.Doctor.specialization == specialization)
    return [_enrich_doctor(d) for d in q.all()]


def get_doctor(db: Session, doctor_id: int):
    d = db.query(models.Doctor).filter(models.Doctor.doctor_id == doctor_id).first()
    return _enrich_doctor(d) if d else None


def create_doctor(db: Session, doctor: schemas.DoctorCreate):
    db_doctor = models.Doctor(**doctor.dict())
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    write_audit(db, "CREATE", "doctor", entity_id=db_doctor.doctor_id)
    return _enrich_doctor(db_doctor)


def delete_doctor(db: Session, doctor_id: int):
    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == doctor_id).first()
    if doctor:
        db.delete(doctor)
        db.commit()
    return doctor


# ── Nurses ────────────────────────────────────────────────────────────────────
def _enrich_nurse(nurse):
    nurse.hospital_name = nurse.hospital.name if nurse.hospital else None
    return nurse


def get_nurses(db: Session, hospital_id: int = None):
    q = db.query(models.Nurse)
    if hospital_id:
        q = q.filter(models.Nurse.hospital_id == hospital_id)
    return [_enrich_nurse(n) for n in q.all()]


def get_nurse(db: Session, nurse_id: int):
    n = db.query(models.Nurse).filter(models.Nurse.nurse_id == nurse_id).first()
    return _enrich_nurse(n) if n else None


def create_nurse(db: Session, nurse: schemas.NurseCreate):
    db_nurse = models.Nurse(**nurse.dict())
    db.add(db_nurse)
    db.commit()
    db.refresh(db_nurse)
    write_audit(db, "CREATE", "nurse", entity_id=db_nurse.nurse_id)
    return _enrich_nurse(db_nurse)


def delete_nurse(db: Session, nurse_id: int):
    nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == nurse_id).first()
    if nurse:
        db.delete(nurse)
        db.commit()
    return nurse


# ── Hospitals ─────────────────────────────────────────────────────────────────
def get_hospitals(db: Session):
    return db.query(models.Hospital).all()


def create_hospital(db: Session, hospital: schemas.HospitalCreate):
    db_hospital = models.Hospital(**hospital.dict())
    db.add(db_hospital)
    db.commit()
    db.refresh(db_hospital)
    write_audit(db, "CREATE", "hospital", entity_id=db_hospital.hospital_id)
    return db_hospital


# ── Dashboard Stats ───────────────────────────────────────────────────────────
def get_dashboard_stats(db: Session):
    return schemas.DashboardStats(
        total_patients=db.query(models.Patient).count(),
        total_doctors=db.query(models.Doctor).count(),
        total_nurses=db.query(models.Nurse).count(),
        total_hospitals=db.query(models.Hospital).count(),
        pending_alerts=db.query(models.Alert).filter(models.Alert.status == "PENDING").count(),
        escalated_alerts=db.query(models.Alert).filter(models.Alert.status == "ESCALATED").count(),
        acknowledged_alerts=db.query(models.Alert).filter(models.Alert.status == "ACKNOWLEDGED").count(),
    )


# ── Chat Messages ─────────────────────────────────────────────────────────────
def create_chat_message(db: Session, patient_id: int,
                        sender_username: str, sender_role: str,
                        message: str):
    msg = models.ChatMessage(
        patient_id=patient_id,
        sender_username=sender_username,
        sender_role=sender_role,
        message=message,
        created_at=datetime.now(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_chat_messages(db: Session, patient_id: int, limit: int = 100):
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.patient_id == patient_id)
        .order_by(models.ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )
