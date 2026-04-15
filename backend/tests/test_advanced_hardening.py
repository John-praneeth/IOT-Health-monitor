import auth


def _login(client, username="admin", password="admin123", *, ip=None, ua=None):
    headers = {}
    if ip:
        headers["X-Forwarded-For"] = ip
    if ua:
        headers["User-Agent"] = ua
    return client.post("/auth/login", json={"username": username, "password": password}, headers=headers)


def _admin_headers(client):
    resp = _login(client)
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_doctor(client, headers, username, hospital_id=None):
    payload = {
        "name": f"Dr {username}",
        "specialization": "General",
        "phone": "919900001111",
        "email": f"{username}@example.com",
        "username": username,
        "password": "password123",
    }
    if hospital_id is not None:
        payload["hospital_id"] = hospital_id
    resp = client.post("/doctors", json=payload, headers=headers)
    assert resp.status_code == 200
    return resp.json()["doctor_id"]


def test_refresh_token_ip_mismatch(client):
    resp = _login(client, ip="1.1.1.1", ua="UA-ONE")
    assert resp.status_code == 200

    refresh = client.post("/auth/refresh", headers={"X-Forwarded-For": "2.2.2.2", "User-Agent": "UA-ONE"})
    assert refresh.status_code == 403


def test_refresh_token_user_agent_mismatch(client):
    resp = _login(client, ip="3.3.3.3", ua="UA-ORIG")
    assert resp.status_code == 200

    refresh = client.post("/auth/refresh", headers={"X-Forwarded-For": "3.3.3.3", "User-Agent": "UA-OTHER"})
    assert refresh.status_code == 403


def test_refresh_token_replay_attack(client):
    login = _login(client, ip="4.4.4.4", ua="UA-R1")
    assert login.status_code == 200
    old_refresh = login.cookies.get(auth.REFRESH_COOKIE_NAME)
    assert old_refresh

    ok_refresh = client.post("/auth/refresh", headers={"X-Forwarded-For": "4.4.4.4", "User-Agent": "UA-R1"})
    assert ok_refresh.status_code == 200

    replay = client.post(
        "/auth/refresh",
        headers={"X-Forwarded-For": "4.4.4.4", "User-Agent": "UA-R1"},
        cookies={auth.REFRESH_COOKIE_NAME: old_refresh},
    )
    assert replay.status_code == 401


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-XSS-Protection"] == "1; mode=block"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


def test_session_limit_enforced(client):
    tokens = []
    for idx in range(4):
        resp = _login(client, ip=f"10.0.0.{idx+1}", ua=f"UA-{idx+1}")
        assert resp.status_code == 200
        tokens.append(resp.json()["access_token"])

    first_token_access = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens[0]}"})
    assert first_token_access.status_code == 401

    latest_token_access = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens[-1]}"})
    assert latest_token_access.status_code == 200


def test_abac_hospital_access_control(client):
    admin = _admin_headers(client)

    h1 = client.post("/hospitals", json={"name": "H1", "location": "L1"}, headers=admin)
    assert h1.status_code == 200
    h2 = client.post("/hospitals", json={"name": "H2", "location": "L2"}, headers=admin)
    assert h2.status_code == 200
    h1_id = h1.json()["hospital_id"]
    h2_id = h2.json()["hospital_id"]

    doctor_owner_id = _create_doctor(client, admin, "doc_owner_abac", hospital_id=h1_id)
    _create_doctor(client, admin, "doc_same_hospital", hospital_id=h1_id)
    _create_doctor(client, admin, "doc_other_hospital", hospital_id=h2_id)

    patient = client.post(
        "/patients",
        json={
            "name": "ABAC Patient",
            "age": 50,
            "room_number": "R-1",
            "hospital_id": h1_id,
            "assigned_doctor": doctor_owner_id,
        },
        headers=admin,
    )
    assert patient.status_code == 200
    patient_id = patient.json()["patient_id"]

    same_login = _login(client, "doc_same_hospital", "password123")
    assert same_login.status_code == 200
    same_headers = {"Authorization": f"Bearer {same_login.json()['access_token']}"}
    allowed = client.get(f"/patients/{patient_id}", headers=same_headers)
    assert allowed.status_code == 200

    other_login = _login(client, "doc_other_hospital", "password123")
    assert other_login.status_code == 200
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    denied = client.get(f"/patients/{patient_id}", headers=other_headers)
    assert denied.status_code == 403
