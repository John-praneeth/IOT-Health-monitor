"""
fake_generator.py
Generates vital signs via the configured data source and persists them
via crud.create_vitals.  Also runs the alert engine.
"""

import crud
import alert_engine
from data_sources import get_source


# Keep the legacy helper for backward compatibility
def generate_fake_vitals(patient_id: int) -> dict:
    """Return a dict matching VitalsCreate fields using the configured source."""
    source = get_source()
    return source.get_vitals(patient_id)


def save_fake(db, patient_id: int):
    """Generate vitals via the active source, persist them, then run the alert engine."""
    data = generate_fake_vitals(patient_id)

    # Persist vitals
    vital_record = crud.create_vitals(db=db, vital=data)

    # Run alert engine on the saved record
    triggered = alert_engine.check_alerts(vital_record)
    for alert_type in triggered:
        crud.create_alert(
            db=db,
            patient_id=patient_id,
            vital_id=vital_record.vital_id,
            alert_type=alert_type,
        )

    return vital_record, triggered
