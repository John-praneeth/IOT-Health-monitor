import logging

import pytest
from starlette.websockets import WebSocketDisconnect

import main
from rate_limiter import limiter


def _login(client, username="admin", password="Admin123!"):
    return client.post("/auth/login", json={"username": username, "password": password})


def _auth_headers(client):
    resp = _login(client)
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


def test_token_revocation_blocks_access(client):
    headers, token = _auth_headers(client)
    ok = client.get("/auth/me", headers=headers)
    assert ok.status_code == 200

    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    blocked = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 401


def test_refresh_token_flow(client):
    login = _login(client)
    assert login.status_code == 200

    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


def test_logout_invalidates_token(client):
    headers, _ = _auth_headers(client)
    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    refresh = client.post("/auth/refresh")
    assert refresh.status_code == 401


def test_failed_login_logging(client, caplog):
    caplog.set_level(logging.WARNING)
    resp = client.post("/auth/login", json={"username": "admin", "password": "Bad-pass1"})
    assert resp.status_code == 401

    events = []
    for rec in caplog.records:
        payload = getattr(rec, "extra_data", {})
        if isinstance(payload, dict):
            events.append(payload.get("event"))
    assert "FAILED_LOGIN" in events


def test_websocket_message_rate_limit(client, monkeypatch):
    login = _login(client)
    assert login.status_code == 200
    token = login.json()["access_token"]

    monkeypatch.setattr(main, "is_redis_available", lambda: True)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/vitals?token={token}") as ws:
            for _ in range(main.WS_MESSAGES_PER_SECOND + 2):
                ws.send_text("ping")
            ws.receive_text()


def test_bruteforce_block(client):
    for _ in range(5):
        resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    limiter.reset()  # isolate brute-force block from slowapi quota
    blocked = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert blocked.status_code == 429
