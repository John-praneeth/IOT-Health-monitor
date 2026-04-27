"""
tests/test_role_permissions.py  –  Tests for role-based access control.
"""

import pytest
import models
import crud


def _admin_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client, username, role, doctor_id=None, nurse_id=None):
    """Helper: register + login, return auth headers."""
    if role == "ADMIN":
        admin_resp = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
        token = admin_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    body = {"username": username, "password": "Password123!", "role": role}
    if doctor_id:
        body["doctor_id"] = doctor_id
    if nurse_id:
        body["nurse_id"] = nurse_id
    client.post("/auth/register", json=body, headers=_admin_headers(client))
    resp = client.post("/auth/login", json={"username": username, "password": "Password123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_see_audit_logs(client):
    headers = _register_and_login(client, "admin_test", "ADMIN")
    resp = client.get("/audit-logs", headers=headers)
    assert resp.status_code == 200


def test_doctor_cannot_see_audit_logs(client):
    headers = _register_and_login(client, "doctor_test", "DOCTOR")
    resp = client.get("/audit-logs", headers=headers)
    assert resp.status_code == 403


def test_nurse_cannot_see_audit_logs(client):
    headers = _register_and_login(client, "nurse_test", "NURSE")
    resp = client.get("/audit-logs", headers=headers)
    assert resp.status_code == 403


def test_public_endpoints_still_work(client):
    """Only health/public bootstrap endpoints should remain publicly accessible."""
    assert client.get("/hospitals").status_code == 200
    assert client.get("/patients").status_code == 401
    assert client.get("/vitals").status_code == 401
    assert client.get("/alerts").status_code == 401
    assert client.get("/health").status_code == 200


def test_admin_can_read_and_update_vitals_source(client):
    headers = _admin_headers(client)

    read_resp = client.get("/vitals/source", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["source"] in ("fake", "thingspeak")

    switch_to_thingspeak = client.put(
        "/vitals/source",
        headers=headers,
        json={"source": "thingspeak"},
    )
    # ThingSpeak details are backend env-driven. If channel ID is not configured
    # in test env, backend correctly rejects the source switch.
    assert switch_to_thingspeak.status_code in (200, 400)

    switch_to_fake = client.put(
        "/vitals/source",
        headers=headers,
        json={"source": "fake"},
    )
    assert switch_to_fake.status_code == 200
    assert switch_to_fake.json()["source"] == "fake"


def test_non_admin_cannot_manage_vitals_source(client):
    doctor_headers = _register_and_login(client, "doctor_source_test", "DOCTOR")
    assert client.get("/vitals/source", headers=doctor_headers).status_code == 403
    assert (
        client.put(
            "/vitals/source",
            headers=doctor_headers,
            json={"source": "fake"},
        ).status_code
        == 403
    )


def test_vitals_are_isolated_by_active_source(client, db, monkeypatch):
    headers = _admin_headers(client)

    patient_resp = client.post(
        "/patients",
        headers=headers,
        json={
            "name": "Source Split Patient",
            "age": 42,
            "room_number": "SRC-1",
            "hospital_id": None,
            "assigned_doctor": None,
            "assigned_nurse": None,
        },
    )
    assert patient_resp.status_code == 200
    patient_id = patient_resp.json()["patient_id"]

    db.add(models.Vitals(patient_id=patient_id, heart_rate=71, spo2=98, temperature=98.4, source="fake"))
    db.add(models.Vitals(patient_id=patient_id, heart_rate=89, spo2=97, temperature=99.1, source="thingspeak"))
    db.commit()

    monkeypatch.setattr(crud, "_active_source_name", lambda: "fake")
    fake_resp = client.get(f"/vitals?patient_id={patient_id}", headers=headers)
    assert fake_resp.status_code == 200
    fake_vitals = fake_resp.json()
    assert len(fake_vitals) == 1
    assert fake_vitals[0]["heart_rate"] == 71

    monkeypatch.setattr(crud, "_active_source_name", lambda: "thingspeak")
    ts_resp = client.get(f"/vitals?patient_id={patient_id}", headers=headers)
    assert ts_resp.status_code == 200
    ts_vitals = ts_resp.json()
    assert len(ts_vitals) == 1
    assert ts_vitals[0]["heart_rate"] == 89
