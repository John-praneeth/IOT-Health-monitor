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


# ── Sensitivity Configuration ────────────────────────────────────────────────
# Minimum consecutive abnormal readings required to trigger a new alert record.
# This prevents temporary sensor noise (spikes) from flooding the clinical log.
MIN_CONSECUTIVE_READINGS = 2

# In-memory buffer to track consecutive abnormal states per patient per type.
# Format: { (patient_id, alert_type): count }
_consecutive_abnormal_counts: dict[tuple[int, str], int] = {}
# Counter to trigger periodic cleanup of the memory buffer
_cleanup_tick = 0


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
    global _cleanup_tick
    raw_triggered = []
    
    # ── 1. Check raw thresholds ──
    for alert_type, condition in THRESHOLDS.items():
        try:
            if condition(vital):
                raw_triggered.append(alert_type)
        except Exception:
            pass

    # ── 2. Update consecutive counters and filter by sensitivity ──
    formal_triggered = []
    patient_id = getattr(vital, "patient_id", None)
    
    if patient_id is not None:
        for alert_type in THRESHOLDS.keys():
            key = (patient_id, alert_type)
            if alert_type in raw_triggered:
                _consecutive_abnormal_counts[key] = _consecutive_abnormal_counts.get(key, 0) + 1
                if _consecutive_abnormal_counts[key] >= MIN_CONSECUTIVE_READINGS:
                    formal_triggered.append(alert_type)
            else:
                _consecutive_abnormal_counts.pop(key, None)

    # Periodic cleanup of stagnant counters (every 500 checks)
    _cleanup_tick += 1
    if _cleanup_tick > 500:
        _cleanup_tick = 0
        # If the buffer is large, prune it (already mostly handled by pop above, 
        # but this catches orphaned entries if logic changes)
        if len(_consecutive_abnormal_counts) > 1000:
            _consecutive_abnormal_counts.clear()

    if not formal_triggered or db is None:
        return formal_triggered

    # ── 3. Deduplicate against already active alerts in DB ──
    try:
        import models
        existing_active = db.query(models.Alert.alert_type).filter(
            models.Alert.patient_id == patient_id,
            models.Alert.status.in_(["PENDING", "ESCALATED"]),
        ).all()
        active_types = {a.alert_type for a in existing_active}
        
        return [t for t in formal_triggered if t not in active_types]
    except Exception as e:
        import logging
        logging.error("Error filtering formal duplicate alerts: %s", e)
        return formal_triggered
