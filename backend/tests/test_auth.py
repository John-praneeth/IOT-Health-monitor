"""
tests/test_auth.py  –  Integration tests for auth endpoints.
"""

import pytest


def test_register_and_login(client):
    # Register (non-admin role, since ADMIN registration is blocked)
    resp = client.post("/auth/register", json={
        "username": "testdoctor",
        "password": "secret123",
        "role": "DOCTOR",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testdoctor"
    assert data["role"] == "DOCTOR"

    # Login
    resp = client.post("/auth/login", json={
        "username": "testdoctor",
        "password": "secret123",
    })
    assert resp.status_code == 200
    token_data = resp.json()
    assert "access_token" in token_data
    assert token_data["role"] == "DOCTOR"

    # /auth/me
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testdoctor"


def test_admin_registration_blocked(client):
    """ADMIN role cannot be created via /auth/register."""
    resp = client.post("/auth/register", json={
        "username": "sneaky_admin",
        "password": "secret123",
        "role": "ADMIN",
    })
    assert resp.status_code == 403


def test_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "dup_user",
        "password": "pass1234",
        "role": "NURSE",
    })
    resp = client.post("/auth/register", json={
        "username": "dup_user",
        "password": "pass5678",
        "role": "NURSE",
    })
    assert resp.status_code == 400


def test_invalid_login(client):
    resp = client.post("/auth/login", json={
        "username": "nonexistent",
        "password": "wrong",
    })
    assert resp.status_code == 401


def test_protected_endpoint_without_token(client):
    resp = client.get("/audit-logs")
    assert resp.status_code == 401
