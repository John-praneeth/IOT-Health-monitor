"""
tests/test_role_permissions.py  –  Tests for role-based access control.
"""

import pytest


def _register_and_login(client, username, role, doctor_id=None, nurse_id=None):
    """Helper: register + login, return auth headers."""
    body = {"username": username, "password": "password123", "role": role}
    if doctor_id:
        body["doctor_id"] = doctor_id
    if nurse_id:
        body["nurse_id"] = nurse_id
    client.post("/auth/register", json=body)
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
    """Hospitals, patients, vitals, alerts should remain publicly accessible."""
    assert client.get("/hospitals").status_code == 200
    assert client.get("/patients").status_code == 200
    assert client.get("/vitals").status_code == 200
    assert client.get("/alerts").status_code == 200
    assert client.get("/health").status_code == 200
