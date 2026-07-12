"""
tests/test_auth.py  –  Integration tests for auth endpoints.
"""

def _admin_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client):
    # Register (non-admin role, since ADMIN registration is blocked)
    resp = client.post("/auth/register", json={
        "username": "testdoctor",
        "password": "Secret123!",
        "role": "DOCTOR",
    }, headers=_admin_headers(client))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testdoctor"
    assert data["role"] == "DOCTOR"

    # Login
    resp = client.post("/auth/login", json={
        "username": "testdoctor",
        "password": "Secret123!",
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
        "password": "Secret123!",
        "role": "ADMIN",
    }, headers=_admin_headers(client))
    assert resp.status_code == 403


def test_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "dup_user",
        "password": "Pass1234!",
        "role": "NURSE",
    }, headers=_admin_headers(client))
    resp = client.post("/auth/register", json={
        "username": "dup_user",
        "password": "Pass5678!",
        "role": "NURSE",
    }, headers=_admin_headers(client))
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


def test_forgot_password_two_step_flow(client):
    register = client.post(
        "/auth/register",
        json={
            "username": "reset_user",
            "password": "Oldpass123!",
            "role": "DOCTOR",
        },
        headers=_admin_headers(client),
    )
    assert register.status_code == 200

    start = client.post("/auth/forgot-password/request", json={"username": "reset_user"})
    assert start.status_code == 200
    code = start.json().get("verification_code")
    assert code

    confirm = client.post(
        "/auth/forgot-password/confirm",
        json={
            "username": "reset_user",
            "verification_code": code,
            "new_password": "Newpass123!",
        },
    )
    assert confirm.status_code == 200

    old_login = client.post("/auth/login", json={"username": "reset_user", "password": "Oldpass123!"})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"username": "reset_user", "password": "Newpass123!"})
    assert new_login.status_code == 200
