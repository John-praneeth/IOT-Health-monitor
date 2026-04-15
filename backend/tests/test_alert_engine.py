"""
tests/test_alert_engine.py  –  Unit tests for the alert threshold engine.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alert_engine import check_alerts


class FakeVital:
    """Minimal stand-in for an ORM Vitals object."""
    def __init__(self, hr=80, spo2=98, temp=36.8):
        self.heart_rate = hr
        self.spo2 = spo2
        self.temperature = temp


def test_normal_vitals_no_alert():
    v = FakeVital(hr=80, spo2=98, temp=36.8)
    assert check_alerts(v) == []


def test_high_heart_rate():
    v = FakeVital(hr=115)
    alerts = check_alerts(v)
    assert "HIGH_HEART_RATE" in alerts


def test_low_heart_rate():
    v = FakeVital(hr=45)
    alerts = check_alerts(v)
    assert "LOW_HEART_RATE" in alerts


def test_low_spo2():
    v = FakeVital(spo2=88)
    alerts = check_alerts(v)
    assert "LOW_SPO2" in alerts


def test_high_temp():
    v = FakeVital(temp=40.1)
    alerts = check_alerts(v)
    assert "HIGH_TEMP" in alerts


def test_low_temp():
    v = FakeVital(temp=34.2)
    alerts = check_alerts(v)
    assert "LOW_TEMP" in alerts


def test_multiple_alerts():
    v = FakeVital(hr=120, spo2=85, temp=40.3)
    alerts = check_alerts(v)
    assert "HIGH_HEART_RATE" in alerts
    assert "LOW_SPO2" in alerts
    assert "HIGH_TEMP" in alerts
    assert len(alerts) == 3
