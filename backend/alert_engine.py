"""
alert_engine.py
Evaluates a Vitals ORM object and returns a list of triggered alert types.
"""


THRESHOLDS = {
    "HIGH_HEART_RATE": lambda v: v.heart_rate > 110,
    "LOW_HEART_RATE":  lambda v: v.heart_rate < 50,
    "LOW_SPO2":        lambda v: v.spo2 < 90,
    "HIGH_TEMP":       lambda v: v.temperature > 39.0,
    "LOW_TEMP":        lambda v: v.temperature < 35.0,
}


def check_alerts(vital) -> list[str]:
    """
    Parameters
    ----------
    vital : models.Vitals ORM instance or any object with heart_rate / spo2 / temperature attrs.

    Returns
    -------
    list[str]  –  names of triggered alert types (empty list = all normal).
    """
    triggered = []
    for alert_type, condition in THRESHOLDS.items():
        try:
            if condition(vital):
                triggered.append(alert_type)
        except Exception:
            pass
    return triggered
