"""
fake_generator.py
Generates vital signs via the configured data source and persists them
via crud.create_vitals.  Also runs the alert engine and sends WhatsApp
notifications when alerts are triggered.
"""

import logging
import crud
import models
import alert_engine
import whatsapp_notifier
from data_sources import get_source

logger = logging.getLogger(__name__)


def save_fake(db, patient_id: int):
    """Generate vitals via the active source, persist them, then run the alert engine.
    Sends WhatsApp notifications for any triggered alerts.
    """
    source = get_source()
    data = source.get_vitals(patient_id)

    # Persist vitals
    vital_record = crud.create_vitals(db=db, vital=data)

    # Run alert engine on the saved record
    triggered = alert_engine.check_alerts(vital_record)

    # Auto-resolve: if a previously-triggered alert type is no longer triggered,
    # mark its PENDING/ESCALATED alert as RESOLVED (vitals returned to normal)
    if not triggered:
        # All vitals are normal — resolve ALL pending/escalated alerts for this patient
        pending = db.query(models.Alert).filter(
            models.Alert.patient_id == patient_id,
            models.Alert.status.in_(["PENDING", "ESCALATED"]),
        ).all()
        for old_alert in pending:
            old_alert.status = "RESOLVED"
            logger.info("Auto-resolved alert #%s (%s) for patient %s — vitals normal",
                        old_alert.alert_id, old_alert.alert_type, patient_id)
        if pending:
            db.commit()
    else:
        # Some alerts triggered — resolve only the types that are no longer abnormal
        triggered_set = set(triggered)
        pending = db.query(models.Alert).filter(
            models.Alert.patient_id == patient_id,
            models.Alert.status.in_(["PENDING", "ESCALATED"]),
            ~models.Alert.alert_type.in_(triggered_set),
        ).all()
        for old_alert in pending:
            old_alert.status = "RESOLVED"
            logger.info("Auto-resolved alert #%s (%s) for patient %s — vital normalized",
                        old_alert.alert_id, old_alert.alert_type, patient_id)
        if pending:
            db.commit()

    for alert_type in triggered:
        alert = crud.create_alert(
            db=db,
            patient_id=patient_id,
            vital_id=vital_record.vital_id,
            alert_type=alert_type,
        )

        # Send WhatsApp notification for new alerts (not duplicates)
        if alert and alert.status == "PENDING":
            try:
                patient = db.query(models.Patient).filter(
                    models.Patient.patient_id == patient_id
                ).first()
                patient_name = patient.name if patient else f"Patient {patient_id}"
                room_number = patient.room_number if patient else "N/A"
                hospital_id = patient.hospital_id if patient else None

                # Check pause state BEFORE sending
                if whatsapp_notifier.is_alerts_paused():
                    logger.info("⏸️  WhatsApp PAUSED — skipping alert %s for patient %s", alert_type, patient_name)
                else:
                    # FIX 13: Let send_alert_notification() resolve recipients from DB
                    # (patient's assigned doctor/nurse phones via get_patient_recipients)
                    whatsapp_notifier.send_alert_notification(
                        alert_type=alert_type,
                        patient_name=patient_name,
                        patient_id=patient_id,
                        room_number=room_number,
                        vital_data={
                            "heart_rate": vital_record.heart_rate,
                            "spo2": vital_record.spo2,
                            "temperature": vital_record.temperature,
                        },
                        alert_id=alert.alert_id,
                        hospital_id=hospital_id,
                    )
            except Exception as e:
                logger.error("WhatsApp alert notification failed: %s", e)

    return vital_record, triggered
