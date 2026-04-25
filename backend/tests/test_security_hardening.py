from datetime import datetime, timezone

import main
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


def _create_patient(client, actor_headers, doctor_id: int, nurse_id: int | None = None, hospital_id: int | None = None):
    body = {
        "name": "Patient One",
        "age": 45,
        "room_number": "A-101",
        "assigned_doctor": doctor_id,
        "assigned_nurse": nurse_id,
        "hospital_id": hospital_id,
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


def test_authorized_nurse_can_acknowledge(client, db):
    admin = _admin_headers(client)
    # Hospital 1
    h1_resp = client.post("/hospitals", json={"name": "H1", "location": "L1"}, headers=admin)
    h1_id = h1_resp.json()["hospital_id"]
    
    assigned_doc = _create_doctor_user(client, admin, "doc_h1", "919900000002")
    # Update doctor hospital
    client.put(f"/doctors/{assigned_doc['doctor_id']}", json={"name": "Doc H1", "hospital_id": h1_id}, headers=admin)
    
    nurse = _create_nurse_user(client, admin, "nurse_h1", "919900000003")
    # Update nurse hospital
    client.put(f"/nurses/{nurse['nurse_id']}", json={"name": "Nurse H1", "hospital_id": h1_id}, headers=admin)
    
    patient_id = _create_patient(client, admin, assigned_doc["doctor_id"], nurse["nurse_id"], hospital_id=h1_id)
    alert_id = _create_pending_alert(db, patient_id)

    # Nurse at same hospital can acknowledge
    resp = client.patch(
        f"/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": 1},
        headers=nurse["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACKNOWLEDGED"


def test_other_doctor_at_same_hospital_can_acknowledge(client, db):
    admin = _admin_headers(client)
    # Hospital 1
    h1_resp = client.post("/hospitals", json={"name": "H1_Doc", "location": "L1"}, headers=admin)
    h1_id = h1_resp.json()["hospital_id"]
    
    assigned_doc = _create_doctor_user(client, admin, "doc_assigned", "919900000004")
    client.put(f"/doctors/{assigned_doc['doctor_id']}", json={"name": "Doc Assigned", "hospital_id": h1_id}, headers=admin)
    
    other_doc = _create_doctor_user(client, admin, "doc_other", "919900000005")
    client.put(f"/doctors/{other_doc['doctor_id']}", json={"name": "Doc Other", "hospital_id": h1_id}, headers=admin)
    
    patient_id = _create_patient(client, admin, assigned_doc["doctor_id"], hospital_id=h1_id)
    alert_id = _create_pending_alert(db, patient_id)

    # Other doctor at same hospital can acknowledge
    resp = client.patch(
        f"/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": 1},
        headers=other_doc["headers"],
    )
    assert resp.status_code == 200


def test_staff_at_different_hospital_cannot_acknowledge(client, db):
    admin = _admin_headers(client)
    # Hospital 1
    h1 = client.post("/hospitals", json={"name": "H1", "location": "L1"}, headers=admin).json()["hospital_id"]
    # Hospital 2
    h2 = client.post("/hospitals", json={"name": "H2", "location": "L2"}, headers=admin).json()["hospital_id"]
    
    doc_h1 = _create_doctor_user(client, admin, "doc_h1_only", "919900000100")
    client.put(f"/doctors/{doc_h1['doctor_id']}", json={"name": "Doc H1", "hospital_id": h1}, headers=admin)
    
    doc_h2 = _create_doctor_user(client, admin, "doc_h2_only", "919900000200")
    client.put(f"/doctors/{doc_h2['doctor_id']}", json={"name": "Doc H2", "hospital_id": h2}, headers=admin)
    
    patient_h1 = _create_patient(client, admin, doc_h1["doctor_id"], hospital_id=h1)
    alert_id = _create_pending_alert(db, patient_h1)

    # Doctor at DIFFERENT hospital cannot acknowledge
    resp = client.patch(
        f"/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": 1},
        headers=doc_h2["headers"],
    )
    assert resp.status_code == 403



def test_patient_access_control(client):
    admin = _admin_headers(client)
    assigned = _create_doctor_user(client, admin, "doc_patient_owner", "919900000006")
    other = _create_doctor_user(client, admin, "doc_patient_other", "919900000007")
    patient_id = _create_patient(client, admin, assigned["doctor_id"])

    denied = client.get(f"/patients/{patient_id}", headers=other["headers"])
    assert denied.status_code == 403

    allowed = client.get(f"/patients/{patient_id}", headers=assigned["headers"])
    assert allowed.status_code == 200


def test_nurse_cannot_create_patient(client):
    admin = _admin_headers(client)
    doctor = _create_doctor_user(client, admin, "doc_for_nurse_create", "919900000014")
    nurse = _create_nurse_user(client, admin, "nurse_no_create", "919900000015")

    resp = client.post(
        "/patients",
        json={
            "name": "Blocked Patient",
            "age": 40,
            "room_number": "X-1",
            "assigned_doctor": doctor["doctor_id"],
            "assigned_nurse": nurse["nurse_id"],
        },
        headers=nurse["headers"],
    )
    assert resp.status_code == 403


def test_doctor_cannot_assign_outside_scope(client):
    admin = _admin_headers(client)
    owner = _create_doctor_user(client, admin, "doc_assign_owner", "919900000016")
    other = _create_doctor_user(client, admin, "doc_assign_other", "919900000017")
    nurse = _create_nurse_user(client, admin, "nurse_assign_target", "919900000018")

    patient_id = _create_patient(client, admin, owner["doctor_id"])

    resp = client.patch(
        f"/patients/{patient_id}/assign_nurse",
        json={"nurse_id": nurse["nurse_id"]},
        headers=other["headers"],
    )
    assert resp.status_code == 403


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


def test_escalation_uses_explicit_recipients(monkeypatch):
    sent_to = []

    monkeypatch.setattr(whatsapp_notifier, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(whatsapp_notifier, "is_alerts_paused", lambda: False)
    monkeypatch.setattr(
        whatsapp_notifier,
        "get_patient_recipients",
        lambda patient_id: ["919900000099"],
    )
    monkeypatch.setattr(
        whatsapp_notifier,
        "send_whatsapp_message",
        lambda phone, body, alert_id=None, event_type="NEW", retries=3: sent_to.append(phone) or True,
    )

    result = whatsapp_notifier.send_escalation_notification(
        alert_type="LOW_SPO2",
        patient_name="P1",
        patient_id=1,
        room_number="A-1",
        recipients=["+919900000011", "919900000012", "919900000011"],
        alert_id=101,
    )

    assert result["sent"] == 2
    assert result["failed"] == 0
    assert sent_to == ["919900000011", "919900000012"]


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


def test_whatsapp_webhook_rejects_invalid_secret(monkeypatch, client):
    monkeypatch.setattr(main, "WHATSAPP_WEBHOOK_SECRET", "super-secret")

    resp = client.post(
        "/whatsapp/webhook",
        json={"typeWebhook": "incomingMessageReceived"},
    )
    assert resp.status_code == 403


def test_whatsapp_webhook_accepts_valid_secret(monkeypatch, client):
    monkeypatch.setattr(main, "WHATSAPP_WEBHOOK_SECRET", "super-secret")

    resp = client.post(
        "/whatsapp/webhook",
        json={"typeWebhook": "statusInstanceChanged"},
        headers={"x-whatsapp-webhook-secret": "super-secret"},
    )
    assert resp.status_code == 200
    assert resp.json().get("status") == "ignored"
