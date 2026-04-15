from datetime import datetime, timezone

import models
import whatsapp_notifier


def _login_headers(client, username: str, password: str):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _admin_headers(client):
    return _login_headers(client, "admin", "admin123")


def _create_doctor_user(client, admin_headers, username: str, phone: str):
    resp = client.post(
        "/doctors",
        json={
            "name": f"Dr {username}",
            "specialization": "Cardiology",
            "phone": phone,
            "email": f"{username}@example.com",
            "username": username,
            "password": "password123",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    doctor_id = resp.json()["doctor_id"]
    headers = _login_headers(client, username, "password123")
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    return {"doctor_id": doctor_id, "headers": headers, "user_id": me.json()["user_id"]}


def _create_nurse_user(client, admin_headers, username: str, phone: str):
    resp = client.post(
        "/nurses",
        json={
            "name": f"Nurse {username}",
            "department": "ICU",
            "phone": phone,
            "email": f"{username}@example.com",
            "username": username,
            "password": "password123",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    nurse_id = resp.json()["nurse_id"]
    headers = _login_headers(client, username, "password123")
    return {"nurse_id": nurse_id, "headers": headers}


def _create_patient(client, actor_headers, doctor_id: int, nurse_id: int | None = None):
    body = {
        "name": "Patient One",
        "age": 45,
        "room_number": "A-101",
        "assigned_doctor": doctor_id,
        "assigned_nurse": nurse_id,
    }
    resp = client.post("/patients", json=body, headers=actor_headers)
    assert resp.status_code == 200
    return resp.json()["patient_id"]


def _create_pending_alert(db, patient_id: int):
    alert = models.Alert(
        patient_id=patient_id,
        vital_id=None,
        alert_type="LOW_SPO2",
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert.alert_id


def test_only_assigned_doctor_can_acknowledge(client, db):
    admin = _admin_headers(client)
    assigned = _create_doctor_user(client, admin, "doc_assigned", "919900000001")
    patient_id = _create_patient(client, admin, assigned["doctor_id"])
    alert_id = _create_pending_alert(db, patient_id)

    resp = client.patch(
        f"/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": 999999},
        headers=assigned["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["acknowledged_by"] == assigned["user_id"]


def test_nurse_cannot_acknowledge(client, db):
    admin = _admin_headers(client)
    assigned = _create_doctor_user(client, admin, "doc_for_nurse_test", "919900000002")
    nurse = _create_nurse_user(client, admin, "nurse_no_ack", "919900000003")
    patient_id = _create_patient(client, admin, assigned["doctor_id"], nurse["nurse_id"])
    alert_id = _create_pending_alert(db, patient_id)

    resp = client.patch(
        f"/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": 1},
        headers=nurse["headers"],
    )
    assert resp.status_code == 403


def test_other_doctor_cannot_acknowledge(client, db):
    admin = _admin_headers(client)
    assigned = _create_doctor_user(client, admin, "doc_owner", "919900000004")
    other = _create_doctor_user(client, admin, "doc_other", "919900000005")
    patient_id = _create_patient(client, admin, assigned["doctor_id"])
    alert_id = _create_pending_alert(db, patient_id)

    resp = client.patch(
        f"/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": 1},
        headers=other["headers"],
    )
    assert resp.status_code == 403
    payload = resp.json()
    detail = payload.get("detail") or payload.get("message") or str(payload)
    assert "Not authorized to acknowledge this alert" in detail


def test_patient_access_control(client):
    admin = _admin_headers(client)
    assigned = _create_doctor_user(client, admin, "doc_patient_owner", "919900000006")
    other = _create_doctor_user(client, admin, "doc_patient_other", "919900000007")
    patient_id = _create_patient(client, admin, assigned["doctor_id"])

    denied = client.get(f"/patients/{patient_id}", headers=other["headers"])
    assert denied.status_code == 403

    allowed = client.get(f"/patients/{patient_id}", headers=assigned["headers"])
    assert allowed.status_code == 200


def test_chat_access_control(client):
    admin = _admin_headers(client)
    assigned = _create_doctor_user(client, admin, "doc_chat_owner", "919900000008")
    other = _create_doctor_user(client, admin, "doc_chat_other", "919900000009")
    nurse = _create_nurse_user(client, admin, "nurse_chat_owner", "919900000010")
    patient_id = _create_patient(client, admin, assigned["doctor_id"], nurse["nurse_id"])

    denied = client.get(f"/patients/{patient_id}/chat", headers=other["headers"])
    assert denied.status_code == 403

    allowed = client.post(
        f"/patients/{patient_id}/chat",
        json={"message": "Patient stable."},
        headers=nurse["headers"],
    )
    assert allowed.status_code == 200


def test_alert_not_sent_to_nurse(monkeypatch):
    sent_to = []

    monkeypatch.setattr(whatsapp_notifier, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(
        whatsapp_notifier,
        "get_patient_recipients",
        lambda patient_id: ["919900000011"],
    )
    monkeypatch.setattr(
        whatsapp_notifier,
        "send_whatsapp_message",
        lambda phone, body, alert_id=None, event_type="NEW", retries=3: sent_to.append(phone) or True,
    )

    whatsapp_notifier.send_alert_notification(
        alert_type="LOW_SPO2",
        patient_name="P1",
        patient_id=1,
        room_number="A-1",
        vital_data={"spo2": 84},
        recipients=["919900000011", "919900000012"],
        alert_id=101,
        hospital_id=1,
    )

    assert sent_to == ["919900000011"]


def test_invalid_vitals_rejected(client):
    admin = _admin_headers(client)
    assigned = _create_doctor_user(client, admin, "doc_vitals", "919900000013")
    patient_id = _create_patient(client, admin, assigned["doctor_id"])

    resp = client.post(
        "/vitals",
        json={
            "patient_id": patient_id,
            "heart_rate": 500,
            "spo2": 150,
            "temperature": -5,
        },
        headers=admin,
    )
    assert resp.status_code == 422
