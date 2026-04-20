"""
tests/test_role_permissions.py  –  Tests for role-based access control.
"""

import pytest


def _admin_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client, username, role, doctor_id=None, nurse_id=None):
    """Helper: register + login, return auth headers."""
    if role == "ADMIN":
        admin_resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        token = admin_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    body = {"username": username, "password": "password123", "role": role}
    if doctor_id:
        body["doctor_id"] = doctor_id
    if nurse_id:
        body["nurse_id"] = nurse_id
    client.post("/auth/register", json=body, headers=_admin_headers(client))
    resp = client.post("/auth/login", json={"username": username, "password": "password123"})
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
    assert client.get("/hospitals").status_code == 401
    assert client.get("/patients").status_code == 401
    assert client.get("/vitals").status_code == 401
    assert client.get("/alerts").status_code == 401
    assert client.get("/health").status_code == 200


def test_admin_can_read_and_update_vitals_source(client):
    headers = _admin_headers(client)

    read_resp = client.get("/vitals/source", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["source"] in ("fake", "thingspeak")

    invalid_switch = client.put(
        "/vitals/source",
        headers=headers,
        json={"source": "thingspeak", "thingspeak_channel_id": ""},
    )
    assert invalid_switch.status_code == 400

    switch_resp = client.put(
        "/vitals/source",
        headers=headers,
        json={
            "source": "thingspeak",
            "thingspeak_channel_id": "1234567",
            "thingspeak_temp_unit": "F",
            "thingspeak_stale_seconds": 120,
        },
    )
    assert switch_resp.status_code == 200
    assert switch_resp.json()["source"] == "thingspeak"
    assert switch_resp.json()["thingspeak_channel_id"] == "1234567"


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
