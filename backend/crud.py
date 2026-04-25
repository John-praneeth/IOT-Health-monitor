"""
crud.py  –  Database operations for the Patient Monitor system.
"""

import os
import logging
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

import models
import schemas
import whatsapp_notifier
import alert_engine
import data_sources

logger = logging.getLogger(__name__)


def _normalize_source_name(value: str | None) -> str:
    src = (value or "fake").strip().lower()
    return src if src in {"fake", "thingspeak"} else "fake"


def _active_source_name() -> str:
    try:
        return _normalize_source_name(data_sources.get_data_source_config().get("source"))
    except Exception:
        return "fake"


# ── Audit Log ─────────────────────────────────────────────────────────────────
def write_audit(db: Session, action: str, entity: str, entity_id: int = None, user_id: int = None):
    log = models.AuditLog(
        user_id=user_id, action=action, entity=entity,
        entity_id=entity_id, timestamp=datetime.now(),
    )
    db.add(log)
    db.commit()


def get_audit_logs(db: Session, entity: str = None, limit: int = 200, offset: int = 0):
    q = db.query(models.AuditLog)
    if entity:
        q = q.filter(models.AuditLog.entity == entity)
    return q.order_by(models.AuditLog.timestamp.desc()).offset(offset).limit(limit).all()


# ── Vitals ────────────────────────────────────────────────────────────────────
def create_vitals(db: Session, vital):
    if isinstance(vital, dict):
        payload = dict(vital)
    else:
        payload = vital.model_dump()
    payload["source"] = _normalize_source_name(payload.get("source") or _active_source_name())
    db_vital = models.Vitals(**payload)
    db.add(db_vital)
    db.commit()
    db.refresh(db_vital)
    return db_vital


def sync_alerts_for_vital(db: Session, vital_record: models.Vitals):
    """
    Evaluate thresholds for a saved vital row and synchronize alert state.
    Returns tuple: (triggered_types, new_alerts).
    """
    patient_id = vital_record.patient_id
    source = _normalize_source_name(getattr(vital_record, "source", None) or _active_source_name())
    triggered = alert_engine.check_alerts(vital_record)

    if not triggered:
        pending = db.query(models.Alert).filter(
            models.Alert.patient_id == patient_id,
            models.Alert.source == source,
            models.Alert.status.in_(["PENDING", "ESCALATED"]),
        ).all()
        for old_alert in pending:
            old_alert.status = "RESOLVED"
            logger.info(
                "Auto-resolved alert #%s (%s) for patient %s — vitals normal",
                old_alert.alert_id,
                old_alert.alert_type,
                patient_id,
            )
        if pending:
            db.commit()
        return triggered, []

    triggered_set = set(triggered)
    pending = db.query(models.Alert).filter(
        models.Alert.patient_id == patient_id,
        models.Alert.source == source,
        models.Alert.status.in_(["PENDING", "ESCALATED"]),
        ~models.Alert.alert_type.in_(triggered_set),
    ).all()
    for old_alert in pending:
        old_alert.status = "RESOLVED"
        logger.info(
            "Auto-resolved alert #%s (%s) for patient %s — vital normalized",
            old_alert.alert_id,
            old_alert.alert_type,
            patient_id,
        )
    if pending:
        db.commit()

    new_alerts = []
    for alert_type in triggered:
        alert = create_alert(
            db=db,
            patient_id=patient_id,
            vital_id=vital_record.vital_id,
            alert_type=alert_type,
            source=source,
        )
        if alert:
            new_alerts.append(alert)

    return triggered, new_alerts


def get_vitals(
    db: Session,
    patient_id: int = None,
    doctor_id: int = None,
    nurse_id: int = None,
    patient_ids: list[int] | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(models.Vitals)
    source_name = _normalize_source_name(source or _active_source_name())
    q = q.filter(models.Vitals.source == source_name)
    if patient_id:
        q = q.filter(models.Vitals.patient_id == patient_id)
        
    _p_ids = None
    if doctor_id:
        _p_ids = [p.patient_id for p in get_patients_by_doctor(db, doctor_id)]
    elif nurse_id:
        _p_ids = [p.patient_id for p in get_patients(db, nurse_id=nurse_id)]
    elif patient_ids is not None:
        _p_ids = patient_ids

    if _p_ids is not None:
        if not _p_ids:
            return []
        q = q.filter(models.Vitals.patient_id.in_(_p_ids))
        
    return q.order_by(models.Vitals.timestamp.desc()).offset(offset).limit(limit).all()


def get_latest_vital(db: Session, patient_id: int):
    source_name = _active_source_name()
    return (
        db.query(models.Vitals)
        .filter(models.Vitals.patient_id == patient_id, models.Vitals.source == source_name)
        .order_by(models.Vitals.timestamp.desc())
        .first()
    )


# ── Alerts ────────────────────────────────────────────────────────────────────
def create_alert(db: Session, patient_id: int, vital_id: int, alert_type: str, source: str | None = None):
    source_name = _normalize_source_name(source or _active_source_name())
    # De-duplicate: skip if a PENDING or ESCALATED alert of the same type already exists
    duplicate = (
        db.query(models.Alert)
        .filter(
            models.Alert.patient_id == patient_id,
            models.Alert.source == source_name,
            models.Alert.alert_type == alert_type,
            models.Alert.status.in_(["PENDING", "ESCALATED"]),
        )
        .first()
    )
    if duplicate:
        # Update last_checked_at to track that abnormal vitals are still occurring
        duplicate.last_checked_at = datetime.now()
        db.commit()
        logger.debug("Duplicate alert suppressed: %s for patient %s (updated last_checked_at)", alert_type, patient_id)
        return None  # Return None so callers know this is a duplicate, not a new alert

    new_alert = models.Alert(
        patient_id=patient_id,
        vital_id=vital_id,
        alert_type=alert_type,
        source=source_name,
        status="PENDING",
        created_at=datetime.now(),
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    write_audit(db, "CREATE", "alert", entity_id=new_alert.alert_id)
    return new_alert


def get_alerts(
    db: Session,
    status: str = None,
    doctor_id: int = None,
    nurse_id: int = None,
    patient_ids: list[int] | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    q = db.query(models.Alert)
    source_name = _normalize_source_name(source or _active_source_name())
    q = q.filter(models.Alert.source == source_name)
    if status:
        q = q.filter(models.Alert.status == status)
    if doctor_id:
        patient_ids = [p.patient_id for p in get_patients_by_doctor(db, doctor_id)]
        q = q.filter(models.Alert.patient_id.in_(patient_ids))
    if nurse_id:
        patient_ids = [p.patient_id for p in get_patients(db, nurse_id=nurse_id)]
        q = q.filter(models.Alert.patient_id.in_(patient_ids))
    if patient_ids is not None:
        if not patient_ids:
            return []
        q = q.filter(models.Alert.patient_id.in_(patient_ids))
    return q.order_by(models.Alert.created_at.desc()).offset(offset).limit(limit).all()


def acknowledge_alert(
    db: Session,
    alert_id: int,
    current_user: models.User,
    allow_admin_override: bool = False,
):
    alert = db.query(models.Alert).filter(models.Alert.alert_id == alert_id).with_for_update().first()
    if not alert:
        return None

    if alert.status == "ACKNOWLEDGED":
        raise HTTPException(status_code=400, detail="Alert already acknowledged")

    patient = db.query(models.Patient).filter(models.Patient.patient_id == alert.patient_id).first()
    if not patient:
        return None

    if current_user.role == "DOCTOR":
        if not current_user.doctor_id or patient.assigned_doctor != current_user.doctor_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to acknowledge this alert",
            )
    elif current_user.role == "ADMIN":
        if not allow_admin_override:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to acknowledge this alert",
            )
    else:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to acknowledge this alert",
        )

    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_by = current_user.user_id
    alert.acknowledged_at = datetime.now()
    db.commit()
    db.refresh(alert)
    write_audit(db, "ACKNOWLEDGE", "alert", entity_id=alert.alert_id, user_id=current_user.user_id)
    return alert


def escalate_stale_alerts(db: Session, threshold_minutes: int = 2):
    """
    Mark PENDING alerts older than `threshold_minutes` as ESCALATED.
    Create escalation records for same-specialization doctors.
    Create notifications for those doctors + nurses at the patient's hospital.
    """
    cutoff = datetime.now() - timedelta(minutes=threshold_minutes)
    source_name = _active_source_name()
    stale = (
        db.query(models.Alert)
        .filter(
            models.Alert.status == "PENDING",
            models.Alert.created_at < cutoff,
            models.Alert.source == source_name,
        )
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

        # Find same-specialization doctors at the SAME hospital (exclude the assigned one)
        same_spec_doctors = []
        if specialization and patient.hospital_id:
            same_spec_doctors = (
                db.query(models.Doctor)
                .filter(
                    models.Doctor.specialization == specialization,
                    models.Doctor.is_available == True,
                    models.Doctor.doctor_id != (patient.assigned_doctor or -1),
                    models.Doctor.hospital_id == patient.hospital_id,
                )
                .all()
            )
            # If no doctors found at same hospital, try any doctor with matching hospital
            if not same_spec_doctors:
                same_spec_doctors = (
                    db.query(models.Doctor)
                    .filter(
                        models.Doctor.is_available == True,
                        models.Doctor.doctor_id != (patient.assigned_doctor or -1),
                        models.Doctor.hospital_id == patient.hospital_id,
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

        # Send WhatsApp escalation notification to escalated doctors + assigned staff
        try:
            escalation_recipients = []
            # Add same-spec doctors' phones (only valid Indian numbers)
            for doc in same_spec_doctors:
                if doc.phone:
                    phone = doc.phone.strip().lstrip("+")
                    if phone.startswith("91") and len(phone) >= 12:
                        escalation_recipients.append(phone)
            # Add assigned doctor's phone
            if assigned_doctor and assigned_doctor.phone:
                phone = assigned_doctor.phone.strip().lstrip("+")
                if phone.startswith("91") and len(phone) >= 12:
                    escalation_recipients.append(phone)
            # De-duplicate
            escalation_recipients = list(dict.fromkeys(escalation_recipients))

            if escalation_recipients:
                whatsapp_notifier.send_escalation_notification(
                    alert_type=alert.alert_type,
                    patient_name=patient.name,
                    patient_id=patient.patient_id,
                    room_number=patient.room_number,
                    recipients=escalation_recipients,
                    alert_id=alert.alert_id,
                )
        except Exception as e:
            logger.error("WhatsApp escalation notification failed for alert %s: %s", alert.alert_id, e)

    if escalated:
        db.commit()

    return escalated


def get_escalations(db: Session, alert_id: int = None, doctor_id: int = None, limit: int = 100, offset: int = 0):
    q = db.query(models.AlertEscalation)
    if alert_id:
        q = q.filter(models.AlertEscalation.alert_id == alert_id)
    if doctor_id:
        q = q.filter(models.AlertEscalation.escalated_to_doctor == doctor_id)
    return q.order_by(models.AlertEscalation.escalated_at.desc()).offset(offset).limit(limit).all()


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


def get_patients(
    db: Session,
    doctor_id: int = None,
    nurse_id: int = None,
    patient_ids: list[int] | None = None,
    limit: int = 200,
    offset: int = 0,
):
    q = db.query(models.Patient)
    if doctor_id:
        q = q.filter(models.Patient.assigned_doctor == doctor_id)
    if nurse_id:
        q = q.filter(models.Patient.assigned_nurse == nurse_id)
    if patient_ids is not None:
        if not patient_ids:
            return []
        q = q.filter(models.Patient.patient_id.in_(patient_ids))
    return [_enrich_patient(p) for p in q.offset(offset).limit(limit).all()]


def get_patients_by_doctor(db: Session, doctor_id: int):
    return db.query(models.Patient).filter(
        models.Patient.assigned_doctor == doctor_id,
    ).all()


def get_patient(db: Session, patient_id: int):
    p = db.query(models.Patient).filter(
        models.Patient.patient_id == patient_id,
    ).first()
    return _enrich_patient(p) if p else None


def _validate_patient_links(
    db: Session,
    hospital_id: int | None,
    assigned_doctor: int | None,
    assigned_nurse: int | None,
):
    if hospital_id is not None:
        hospital = db.query(models.Hospital).filter(models.Hospital.hospital_id == hospital_id).first()
        if not hospital:
            raise ValueError("Hospital not found")

    doctor = None
    if assigned_doctor is not None:
        doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == assigned_doctor).first()
        if not doctor:
            raise ValueError("Doctor not found")

    nurse = None
    if assigned_nurse is not None:
        nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == assigned_nurse).first()
        if not nurse:
            raise ValueError("Nurse not found")

    if doctor and not doctor.is_freelancer and doctor.hospital_id is not None:
        if hospital_id is None:
            raise ValueError("Patient hospital is required for a hospital-based doctor")
        if doctor.hospital_id != hospital_id:
            raise ValueError("Assigned doctor does not belong to the patient's hospital")

    if nurse and nurse.hospital_id is not None:
        if hospital_id is None:
            raise ValueError("Patient hospital is required when assigning a nurse")
        if nurse.hospital_id != hospital_id:
            raise ValueError("Assigned nurse does not belong to the patient's hospital")


def create_patient(db: Session, patient: schemas.PatientCreate, user_id: int):
    _validate_patient_links(
        db,
        hospital_id=patient.hospital_id,
        assigned_doctor=patient.assigned_doctor,
        assigned_nurse=patient.assigned_nurse,
    )
    db_patient = models.Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    write_audit(db, "CREATE", "patient", entity_id=db_patient.patient_id, user_id=user_id)
    return _enrich_patient(db_patient)


def update_patient(db: Session, patient_id: int, payload: schemas.PatientUpdate, user_id: int):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    if not patient:
        return None
    _validate_patient_links(
        db,
        hospital_id=payload.hospital_id,
        assigned_doctor=payload.assigned_doctor,
        assigned_nurse=payload.assigned_nurse,
    )
    for field, value in payload.model_dump().items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    write_audit(db, "UPDATE", "patient", entity_id=patient_id, user_id=user_id)
    return _enrich_patient(patient)


def delete_patient(db: Session, patient_id: int, user_id: int):
    """Hard delete: physically remove patient and all their related data from the DB.
    Cascades: vitals, alerts, escalations, notifications, chat messages.
    """
    patient = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    if patient:
        # Get all alerts for this patient to delete related escalations/notifications
        alerts = db.query(models.Alert).filter(models.Alert.patient_id == patient_id).all()
        alert_ids = [a.alert_id for a in alerts]
        
        # Delete related escalations
        if alert_ids:
            db.query(models.AlertEscalation).filter(models.AlertEscalation.alert_id.in_(alert_ids)).delete(synchronize_session=False)
        
        # Delete related notifications
        if alert_ids:
            db.query(models.AlertNotification).filter(models.AlertNotification.alert_id.in_(alert_ids)).delete(synchronize_session=False)
        
        # Delete related WhatsApp logs
        if alert_ids:
            db.query(models.WhatsAppLog).filter(models.WhatsAppLog.alert_id.in_(alert_ids)).delete(synchronize_session=False)
        
        # Delete SLA records
        db.query(models.SLARecord).filter(models.SLARecord.patient_id == patient_id).delete(synchronize_session=False)
        
        # Delete chat messages
        db.query(models.ChatMessage).filter(models.ChatMessage.patient_id == patient_id).delete(synchronize_session=False)
        
        # Delete alerts
        db.query(models.Alert).filter(models.Alert.patient_id == patient_id).delete(synchronize_session=False)
        
        # Delete all vitals
        db.query(models.Vitals).filter(models.Vitals.patient_id == patient_id).delete(synchronize_session=False)
        
        # Delete patient first; audit only after successful commit.
        db.delete(patient)
        db.commit()
        write_audit(db, "DELETE", "patient", entity_id=patient_id, user_id=user_id)
    return patient


def assign_doctor(db: Session, patient_id: int, doctor_id: int | None):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    if not patient:
        return None
    if doctor_id is None:
        patient.assigned_doctor = None
        _validate_patient_links(
            db,
            hospital_id=patient.hospital_id,
            assigned_doctor=None,
            assigned_nurse=patient.assigned_nurse,
        )
        db.commit()
        db.refresh(patient)
        return _enrich_patient(patient)
    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == doctor_id).first()
    if not doctor:
        return None
    patient.assigned_doctor = doctor_id
    _validate_patient_links(
        db,
        hospital_id=patient.hospital_id,
        assigned_doctor=doctor_id,
        assigned_nurse=patient.assigned_nurse,
    )
    db.commit()
    db.refresh(patient)
    return _enrich_patient(patient)


def assign_nurse(db: Session, patient_id: int, nurse_id: int | None):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == patient_id).first()
    if not patient:
        return None
    if nurse_id is None:
        patient.assigned_nurse = None
        _validate_patient_links(
            db,
            hospital_id=patient.hospital_id,
            assigned_doctor=patient.assigned_doctor,
            assigned_nurse=None,
        )
        db.commit()
        db.refresh(patient)
        return _enrich_patient(patient)
    nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == nurse_id).first()
    if not nurse:
        return None
    patient.assigned_nurse = nurse_id
    _validate_patient_links(
        db,
        hospital_id=patient.hospital_id,
        assigned_doctor=patient.assigned_doctor,
        assigned_nurse=nurse_id,
    )
    db.commit()
    db.refresh(patient)
    return _enrich_patient(patient)


# ── Doctors ───────────────────────────────────────────────────────────────────
def _enrich_doctor(doctor):
    doctor.hospital_name = doctor.hospital.name if doctor.hospital else None
    return doctor


def get_doctors(db: Session, hospital_id: int = None, specialization: str = None, limit: int = 200, offset: int = 0):
    q = db.query(models.Doctor)
    if hospital_id:
        q = q.filter(models.Doctor.hospital_id == hospital_id)
    if specialization:
        q = q.filter(models.Doctor.specialization == specialization)
    return [_enrich_doctor(d) for d in q.offset(offset).limit(limit).all()]


def get_doctor(db: Session, doctor_id: int):
    d = db.query(models.Doctor).filter(
        models.Doctor.doctor_id == doctor_id,
    ).first()
    return _enrich_doctor(d) if d else None


def create_doctor(db: Session, doctor: schemas.DoctorCreate, user_id: int):
    doctor_data = doctor.model_dump(exclude={"username", "password"})
    db_doctor = models.Doctor(**doctor_data)
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    write_audit(db, "CREATE", "doctor", entity_id=db_doctor.doctor_id, user_id=user_id)
    # Create a linked User account if credentials were provided
    if doctor.username and doctor.password:
        import auth as _auth
        _auth.create_user(db, doctor.username, doctor.password, "DOCTOR", doctor_id=db_doctor.doctor_id)
    return _enrich_doctor(db_doctor)


def update_doctor(db: Session, doctor_id: int, payload: schemas.DoctorUpdate, user_id: int):
    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == doctor_id).first()
    if not doctor:
        return None
    for field, value in payload.model_dump().items():
        setattr(doctor, field, value)
    db.commit()
    db.refresh(doctor)
    write_audit(db, "UPDATE", "doctor", entity_id=doctor_id, user_id=user_id)
    return _enrich_doctor(doctor)


def delete_doctor(db: Session, doctor_id: int, user_id: int):
    """Hard delete: physically remove doctor from the DB.
    Handles all FK constraints:
    - Nullifies patient.assigned_doctor
    - Deletes alert escalations assigned to this doctor
    - Nullifies user.doctor_id
    """
    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == doctor_id).first()
    if doctor:
        # 1. Nullify FK on linked patient records
        db.query(models.Patient).filter(models.Patient.assigned_doctor == doctor_id).update({"assigned_doctor": None})
        
        # 2. Delete alert escalations assigned to this doctor
        db.query(models.AlertEscalation).filter(models.AlertEscalation.escalated_to_doctor == doctor_id).delete()
        
        # 3. Nullify FK on linked user accounts
        db.query(models.User).filter(models.User.doctor_id == doctor_id).update({"doctor_id": None})
        
        # 4. Delete doctor first; audit only after successful commit.
        db.delete(doctor)
        db.commit()
        write_audit(db, "DELETE", "doctor", entity_id=doctor_id, user_id=user_id)
    return doctor


# ── Nurses ────────────────────────────────────────────────────────────────────
def _enrich_nurse(nurse):
    nurse.hospital_name = nurse.hospital.name if nurse.hospital else None
    return nurse


def get_nurses(db: Session, hospital_id: int = None, limit: int = 200, offset: int = 0):
    q = db.query(models.Nurse)
    if hospital_id:
        q = q.filter(models.Nurse.hospital_id == hospital_id)
    return [_enrich_nurse(n) for n in q.offset(offset).limit(limit).all()]


def get_nurse(db: Session, nurse_id: int):
    n = db.query(models.Nurse).filter(
        models.Nurse.nurse_id == nurse_id,
    ).first()
    return _enrich_nurse(n) if n else None


def create_nurse(db: Session, nurse: schemas.NurseCreate, user_id: int):
    nurse_data = nurse.model_dump(exclude={"username", "password"})
    db_nurse = models.Nurse(**nurse_data)
    db.add(db_nurse)
    db.commit()
    db.refresh(db_nurse)
    write_audit(db, "CREATE", "nurse", entity_id=db_nurse.nurse_id, user_id=user_id)
    # Create a linked User account if credentials were provided
    if nurse.username and nurse.password:
        import auth as _auth
        _auth.create_user(db, nurse.username, nurse.password, "NURSE", nurse_id=db_nurse.nurse_id)
    return _enrich_nurse(db_nurse)


def update_nurse(db: Session, nurse_id: int, payload: schemas.NurseUpdate, user_id: int):
    nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == nurse_id).first()
    if not nurse:
        return None
    for field, value in payload.model_dump().items():
        setattr(nurse, field, value)
    db.commit()
    db.refresh(nurse)
    write_audit(db, "UPDATE", "nurse", entity_id=nurse_id, user_id=user_id)
    return _enrich_nurse(nurse)


def delete_nurse(db: Session, nurse_id: int, user_id: int):
    """Hard delete: physically remove nurse from the DB.
    Also nullifies nurse_id on any linked user accounts and patients.
    """
    nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == nurse_id).first()
    if nurse:
        # Nullify FK on linked patient records
        db.query(models.Patient).filter(models.Patient.assigned_nurse == nurse_id).update({"assigned_nurse": None})
        # Nullify FK on linked user accounts before deleting
        db.query(models.User).filter(models.User.nurse_id == nurse_id).update({"nurse_id": None})
        # Delete nurse first; audit only after successful commit.
        db.delete(nurse)
        db.commit()
        write_audit(db, "DELETE", "nurse", entity_id=nurse_id, user_id=user_id)
    return nurse


# ── Hospitals ─────────────────────────────────────────────────────────────────
def get_hospitals(db: Session):
    return db.query(models.Hospital).all()


def create_hospital(db: Session, hospital: schemas.HospitalCreate):
    db_hospital = models.Hospital(**hospital.model_dump())
    db.add(db_hospital)
    db.commit()
    db.refresh(db_hospital)
    write_audit(db, "CREATE", "hospital", entity_id=db_hospital.hospital_id)
    return db_hospital


def get_hospital(db: Session, hospital_id: int):
    return db.query(models.Hospital).filter(models.Hospital.hospital_id == hospital_id).first()


def update_hospital(db: Session, hospital_id: int, payload: schemas.HospitalUpdate, user_id: int):
    hospital = db.query(models.Hospital).filter(models.Hospital.hospital_id == hospital_id).first()
    if not hospital:
        return None
    for field, value in payload.model_dump().items():
        setattr(hospital, field, value)
    db.commit()
    db.refresh(hospital)
    write_audit(db, "UPDATE", "hospital", entity_id=hospital_id, user_id=user_id)
    return hospital


# ── Dashboard Stats ───────────────────────────────────────────────────────────
def _duplicate_vitals_count_for_patients(
    db: Session,
    patient_ids: list[int] | None = None,
    source: str | None = None,
) -> int:
    source_name = _normalize_source_name(source or _active_source_name())
    q = (
        db.query(
            models.Vitals.patient_id,
            models.Vitals.timestamp,
            func.count(models.Vitals.vital_id).label("c"),
        )
        .filter(models.Vitals.source == source_name)
        .group_by(models.Vitals.patient_id, models.Vitals.timestamp)
        .having(func.count(models.Vitals.vital_id) > 1)
    )
    if patient_ids is not None:
        if not patient_ids:
            return 0
        q = q.filter(models.Vitals.patient_id.in_(patient_ids))
    return q.count()


def get_dashboard_stats(db: Session, current_user: models.User):
    patient_q = db.query(models.Patient)
    source_name = _active_source_name()
    alert_q = db.query(models.Alert).filter(models.Alert.source == source_name)
    patient_ids_for_scope = None

    if current_user.role == "DOCTOR":
        if not current_user.doctor_id:
            return schemas.DashboardStats(
                total_patients=0,
                total_doctors=0,
                total_nurses=0,
                total_hospitals=0,
                pending_alerts=0,
                escalated_alerts=0,
                acknowledged_alerts=0,
                duplicate_vitals_count=0,
            )
        doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == current_user.doctor_id).first()
        if doctor and doctor.hospital_id:
            patient_q = patient_q.filter(
                (models.Patient.assigned_doctor == current_user.doctor_id)
                | (models.Patient.hospital_id == doctor.hospital_id)
            )
            patient_ids_for_scope = [
                row[0] for row in db.query(models.Patient.patient_id).filter(
                    (models.Patient.assigned_doctor == current_user.doctor_id)
                    | (models.Patient.hospital_id == doctor.hospital_id)
                ).all()
            ]
        else:
            patient_q = patient_q.filter(models.Patient.assigned_doctor == current_user.doctor_id)
            patient_ids_for_scope = [p.patient_id for p in get_patients_by_doctor(db, current_user.doctor_id)]
        alert_q = alert_q.filter(models.Alert.patient_id.in_(patient_ids_for_scope or [-1]))
    elif current_user.role == "NURSE":
        if not current_user.nurse_id:
            return schemas.DashboardStats(
                total_patients=0,
                total_doctors=0,
                total_nurses=0,
                total_hospitals=0,
                pending_alerts=0,
                escalated_alerts=0,
                acknowledged_alerts=0,
                duplicate_vitals_count=0,
            )
        nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == current_user.nurse_id).first()
        if nurse and nurse.hospital_id:
            patient_q = patient_q.filter(
                (models.Patient.assigned_nurse == current_user.nurse_id)
                | (models.Patient.hospital_id == nurse.hospital_id)
            )
            patient_ids_for_scope = [
                row[0] for row in db.query(models.Patient.patient_id).filter(
                    (models.Patient.assigned_nurse == current_user.nurse_id)
                    | (models.Patient.hospital_id == nurse.hospital_id)
                ).all()
            ]
        else:
            patient_q = patient_q.filter(models.Patient.assigned_nurse == current_user.nurse_id)
            patient_ids_for_scope = [
                p.patient_id for p in get_patients(db, nurse_id=current_user.nurse_id)
            ]
        alert_q = alert_q.filter(models.Alert.patient_id.in_(patient_ids_for_scope or [-1]))

    return schemas.DashboardStats(
        total_patients=patient_q.count(),
        total_doctors=db.query(models.Doctor).count(),
        total_nurses=db.query(models.Nurse).count(),
        total_hospitals=db.query(models.Hospital).count(),
        pending_alerts=alert_q.filter(models.Alert.status == "PENDING").count(),
        escalated_alerts=alert_q.filter(models.Alert.status == "ESCALATED").count(),
        acknowledged_alerts=alert_q.filter(models.Alert.status == "ACKNOWLEDGED").count(),
        duplicate_vitals_count=_duplicate_vitals_count_for_patients(db, patient_ids_for_scope, source=source_name),
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


# ── WhatsApp Logs ─────────────────────────────────────────────────────────────
def create_whatsapp_log(db: Session, alert_id: int = None, recipient: str = "",
                         message_type: str = "alert", status: str = "PENDING",
                         error: str = None, idempotency_key: str = None):
    # Check idempotency — do not duplicate successful sends
    if idempotency_key:
        existing = db.query(models.WhatsAppLog).filter(
            models.WhatsAppLog.idempotency_key == idempotency_key,
            models.WhatsAppLog.status == "SENT",
        ).first()
        if existing:
            logger.debug("WhatsApp idempotency hit: %s already SENT", idempotency_key)
            return existing

    log = models.WhatsAppLog(
        alert_id=alert_id,
        recipient=recipient,
        message_type=message_type,
        status=status,
        attempts=1,
        error=error,
        idempotency_key=idempotency_key,
        created_at=datetime.now(),
        sent_at=datetime.now() if status == "SENT" else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_whatsapp_logs(db: Session, limit: int = 100, offset: int = 0):
    return (
        db.query(models.WhatsAppLog)
        .order_by(models.WhatsAppLog.created_at.desc())
        .offset(offset).limit(limit).all()
    )
