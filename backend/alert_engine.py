"""
alert_engine.py
Evaluates a Vitals ORM object and returns a list of triggered alert types.
"""


THRESHOLDS = {
    "HIGH_HEART_RATE": lambda v: v.heart_rate > 110,
    "LOW_HEART_RATE":  lambda v: v.heart_rate < 50,
    "LOW_SPO2":        lambda v: v.spo2 < 90,
    "HIGH_TEMP":       lambda v: v.temperature > 101.0,
    "LOW_TEMP":        lambda v: v.temperature < 96.0,
}


def check_alerts(vital, db=None) -> list[str]:
    """
    Parameters
    ----------
    vital : models.Vitals ORM instance or any object with heart_rate / spo2 / temperature attrs.
    db : Optional SessionLocal to check for existing active alerts.

    Returns
    -------
    list[str]  –  names of triggered alert types (empty list = all normal).
    """
    triggered = []
    
    # ── Check thresholds ──
    for alert_type, condition in THRESHOLDS.items():
        try:
            if condition(vital):
                triggered.append(alert_type)
        except Exception:
            pass
            
    if not triggered or db is None:
        return triggered

    # ── Filter out types that already have active (unresolved) alerts ──
    try:
        import models
        existing_active = db.query(models.Alert.alert_type).filter(
            models.Alert.patient_id == vital.patient_id,
            models.Alert.status.in_(["PENDING", "ESCALATED"]),
        ).all()
        active_types = {a.alert_type for a in existing_active}
        
        # Only return types that are NOT already active
        return [t for t in triggered if t not in active_types]
    except Exception as e:
        import logging
        logging.error("Error filtering duplicate alerts: %s", e)
        return triggered
