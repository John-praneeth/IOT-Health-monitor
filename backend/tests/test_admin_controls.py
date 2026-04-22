"""
tests/test_admin_controls.py  -  Tests for admin runtime and maintenance endpoints.
"""

import auth
import models


def _admin_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_fake_vitals_force_toggle(client):
    headers = _admin_headers(client)

    status_resp = client.get("/admin/fake-vitals/status", headers=headers)
    assert status_resp.status_code == 200
    assert "enabled" in status_resp.json()

    stop_resp = client.post("/admin/fake-vitals/force-stop", headers=headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["enabled"] is False

    status_after_stop = client.get("/admin/fake-vitals/status", headers=headers)
    assert status_after_stop.status_code == 200
    assert status_after_stop.json()["enabled"] is False

    start_resp = client.post("/admin/fake-vitals/force-start", headers=headers)
    assert start_resp.status_code == 200
    assert start_resp.json()["enabled"] is True


def test_cleanup_vitals_by_source(client, db):
    headers = _admin_headers(client)

    patient = models.Patient(name="Cleanup Patient", age=35, room_number="CL-101")
    db.add(patient)
    db.commit()
    db.refresh(patient)

    fake_vital = models.Vitals(
        patient_id=patient.patient_id,
        heart_rate=125,
        spo2=92,
        temperature=101.2,
        source="fake",
    )
    ts_vital = models.Vitals(
        patient_id=patient.patient_id,
        heart_rate=78,
        spo2=98,
        temperature=98.6,
        source="thingspeak",
    )
    db.add_all([fake_vital, ts_vital])
    db.commit()
    db.refresh(fake_vital)
    db.refresh(ts_vital)

    fake_alert = models.Alert(
        patient_id=patient.patient_id,
        vital_id=fake_vital.vital_id,
        alert_type="HIGH_HEART_RATE",
        source="fake",
        status="PENDING",
    )
    db.add(fake_alert)
    db.commit()
    db.refresh(fake_alert)

    db.add(models.SLARecord(alert_id=fake_alert.alert_id, patient_id=patient.patient_id, breached=False))
    db.add(models.WhatsAppLog(alert_id=fake_alert.alert_id, recipient="919999999999", message_type="alert", status="SENT"))
    db.commit()

    resp = client.post(
        "/admin/vitals/cleanup",
        headers=headers,
        json={"mode": "all", "source": "fake"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_vitals"] >= 1
    assert body["deleted_alerts"] >= 1

    remaining_fake = db.query(models.Vitals).filter(models.Vitals.source == "fake").count()
    remaining_ts = db.query(models.Vitals).filter(models.Vitals.source == "thingspeak").count()
    remaining_alerts = db.query(models.Alert).count()

    assert remaining_fake == 0
    assert remaining_ts == 1
    assert remaining_alerts == 0


def test_fresh_reset_clears_domain_and_preserves_admin(client, db):
    headers = _admin_headers(client)

    hospital = models.Hospital(name="Reset Hospital", location="City")
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    doctor = models.Doctor(name="Reset Doctor", hospital_id=hospital.hospital_id)
    nurse = models.Nurse(name="Reset Nurse", hospital_id=hospital.hospital_id)
    db.add_all([doctor, nurse])
    db.commit()
    db.refresh(doctor)
    db.refresh(nurse)

    patient = models.Patient(
        name="Reset Patient",
        age=41,
        room_number="RS-1",
        hospital_id=hospital.hospital_id,
        assigned_doctor=doctor.doctor_id,
        assigned_nurse=nurse.nurse_id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    staff_user = models.User(
        username="temp_staff",
        password_hash=auth.hash_password("password123"),
        role="DOCTOR",
        doctor_id=doctor.doctor_id,
    )
    db.add(staff_user)
    db.commit()

    vital = models.Vitals(patient_id=patient.patient_id, heart_rate=110, spo2=95, temperature=100.1, source="fake")
    db.add(vital)
    db.commit()
    db.refresh(vital)

    alert = models.Alert(patient_id=patient.patient_id, vital_id=vital.vital_id, alert_type="FEVER", source="fake", status="PENDING")
    db.add(alert)
    db.commit()

    resp = client.post("/admin/reset/fresh", headers=headers)
    assert resp.status_code == 200

    stats = resp.json()
    assert stats["deleted_patients"] >= 1
    assert stats["deleted_doctors"] >= 1
    assert stats["deleted_nurses"] >= 1
    assert stats["deleted_hospitals"] >= 1

    assert db.query(models.Patient).count() == 0
    assert db.query(models.Doctor).count() == 0
    assert db.query(models.Nurse).count() == 0
    assert db.query(models.Hospital).count() == 0
    assert db.query(models.Vitals).count() == 0
    assert db.query(models.Alert).count() == 0
    assert db.query(models.User).filter(models.User.role != "ADMIN").count() == 0
    assert db.query(models.User).filter(models.User.role == "ADMIN").count() == 1

    setting = db.query(models.AppSetting).filter(models.AppSetting.setting_key == "fake_vitals_generation_enabled").first()
    assert setting is not None
    assert setting.setting_value == "false"
