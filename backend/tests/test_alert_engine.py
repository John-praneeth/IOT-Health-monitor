"""
tests/test_alert_engine.py  –  Unit tests for the alert threshold engine.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alert_engine import check_alerts


class FakeVital:
    """Minimal stand-in for an ORM Vitals object."""
    def __init__(self, patient_id=1, hr=80, spo2=98, temp=98.6):
        self.patient_id = patient_id
        self.heart_rate = hr
        self.spo2 = spo2
        self.temperature = temp


def test_normal_vitals_no_alert():
    v = FakeVital(hr=80, spo2=98, temp=98.6)
    assert check_alerts(v) == []


def test_high_heart_rate():
    v = FakeVital(patient_id=101, hr=115)
    # First heartbeat: raw trigger but no formal alert
    assert "HIGH_HEART_RATE" not in check_alerts(v)
    # Second heartbeat: persists, so formal alert triggered
    alerts = check_alerts(v)
    assert "HIGH_HEART_RATE" in alerts


def test_low_heart_rate():
    v = FakeVital(patient_id=102, hr=45)
    check_alerts(v) # 1
    alerts = check_alerts(v) # 2
    assert "LOW_HEART_RATE" in alerts


def test_low_spo2():
    v = FakeVital(patient_id=103, spo2=88)
    check_alerts(v) # 1
    alerts = check_alerts(v) # 2
    assert "LOW_SPO2" in alerts


def test_high_temp():
    v = FakeVital(patient_id=104, temp=102.1)
    check_alerts(v) # 1
    alerts = check_alerts(v) # 2
    assert "HIGH_TEMP" in alerts


def test_low_temp():
    v = FakeVital(patient_id=105, temp=95.2)
    check_alerts(v) # 1
    alerts = check_alerts(v) # 2
    assert "LOW_TEMP" in alerts


def test_multiple_alerts():
    v = FakeVital(patient_id=106, hr=120, spo2=85, temp=102.3)
    check_alerts(v) # 1
    alerts = check_alerts(v) # 2
    assert "HIGH_HEART_RATE" in alerts
    assert "LOW_SPO2" in alerts
    assert "HIGH_TEMP" in alerts
    assert len(alerts) == 3
