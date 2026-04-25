"""
fake_generator.py
Generates vital signs via the configured data source and persists them
via crud.create_vitals.  Also runs the alert engine and sends WhatsApp
notifications when alerts are triggered.
"""

import logging
import crud
import models
import whatsapp_notifier
from data_sources import get_source, get_active_source_name

logger = logging.getLogger(__name__)


def backfill_history(db, patient_id: int, source=None, count: int = 50):
    """
    If the patient has no vitals from the current source, fetch history
    from the provider and persist it (silently, without triggering alerts).
    """
    if source is None:
        source = get_source()
        
    # Check if we already have data for this patient/source
    from models import Vitals
    active_name = get_active_source_name()
    exists = db.query(Vitals).filter(Vitals.patient_id == patient_id, Vitals.source == active_name).first()
    if exists:
        return
        
    logger.info("Backfilling history for patient %d from source %s", patient_id, active_name)
    history = source.get_history(patient_id, count=count)
    for entry in history:
        try:
            # Persist without alert syncing to avoid flooding notifications for old data
            crud.create_vitals(db, entry)
        except Exception as e:
            logger.warning("Failed to save history entry for P%d: %s", patient_id, e)


def save_fake(db, patient_id: int, source=None):
    """Generate vitals via the active source, persist them, then run the alert engine.
    Sends WhatsApp notifications for any triggered alerts.
    """
    if source is None:
        source = get_source()
        
    data = source.get_vitals(patient_id)

    # Persist vitals
    vital_record = crud.create_vitals(db=db, vital=data)

    triggered, new_alerts = crud.sync_alerts_for_vital(db=db, vital_record=vital_record)

    for alert in new_alerts:
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
                    logger.info("⏸️  WhatsApp PAUSED — skipping alert %s for patient %s", alert.alert_type, patient_name)
                else:
                    # FIX 13: Let send_alert_notification() resolve recipients from DB
                    # (patient's assigned doctor/nurse phones via get_patient_recipients)
                    whatsapp_notifier.send_alert_notification(
                        alert_type=alert.alert_type,
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
