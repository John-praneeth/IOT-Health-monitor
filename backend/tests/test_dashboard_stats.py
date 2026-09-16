"""
tests/test_dashboard_stats.py  -  /dashboard/stats alert counters.
"""

import models


def _admin_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_alerts(db, statuses):
    patient = models.Patient(name="Stats Patient", age=50, room_number="ST-1")
    db.add(patient)
    db.commit()
    db.refresh(patient)

    vital = models.Vitals(patient_id=patient.patient_id, heart_rate=120, spo2=93, temperature=101.0, source="fake")
    db.add(vital)
    db.commit()
    db.refresh(vital)

    db.add_all([
        models.Alert(
            patient_id=patient.patient_id,
            vital_id=vital.vital_id,
            alert_type="HIGH_HEART_RATE",
            source="fake",
            status=status,
        )
        for status in statuses
    ])
    db.commit()


def test_dashboard_stats_counts_each_alert_status(client, db):
    headers = _admin_headers(client)
    _seed_alerts(db, ["PENDING", "ESCALATED", "ACKNOWLEDGED", "RESOLVED", "RESOLVED", "RESOLVED"])

    resp = client.get("/dashboard/stats", headers=headers)
    assert resp.status_code == 200
    stats = resp.json()

    assert stats["pending_alerts"] == 1
    assert stats["escalated_alerts"] == 1
    assert stats["acknowledged_alerts"] == 1
    # Auto-resolved alerts (vitals returned to normal) are a distinct lifecycle
    # state and must not be folded into acknowledged.
    assert stats["resolved_alerts"] == 3
