"""
tests/test_e2e_multimodal.py
────────────────────────────
End-to-End Integration and Validation Tests for the Multimodal AI Engine.
"""

import os
import sys
import base64
import numpy as np

# Ensure backend path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import ClinicalData, Patient, Hospital, Doctor, Nurse


def _admin_headers(client):
    """Helper to authenticate as admin and get authorization headers."""
    resp = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_multimodal_diagnostics_e2e(client, db):
    """
    E2E test verifying:
      1. Hospital, doctor, nurse, and patient creation.
      2. Fetching initial AI diagnostics (defaults/vitals only).
      3. Uploading multimodal text, image, audio, and documents.
      4. Checking classification output, risk severity, confidence, and modalities.
      5. Retrieving database-backed clinical data.
      6. Fetching the unified embedding space projection.
    """
    headers = _admin_headers(client)

    # 1. Create dependencies
    # Create hospital
    resp = client.post("/hospitals", json={
        "name": "General Hospital",
        "location": "Boston",
        "phone": "555-0199",
        "email": "info@bostonhospital.com"
    }, headers=headers)
    assert resp.status_code == 200
    hosp_id = resp.json()["hospital_id"]

    # Create doctor
    resp = client.post("/doctors", json={
        "name": "Dr. House",
        "specialization": "Diagnostics",
        "hospital_id": hosp_id,
        "phone": "555-0188",
        "email": "house@bostonhospital.com"
    }, headers=headers)
    assert resp.status_code == 200
    doc_id = resp.json()["doctor_id"]

    # Create nurse
    resp = client.post("/nurses", json={
        "name": "Nurse Jackie",
        "department": "ER",
        "hospital_id": hosp_id,
        "phone": "555-0177",
        "email": "jackie@bostonhospital.com"
    }, headers=headers)
    assert resp.status_code == 200
    nurse_id = resp.json()["nurse_id"]

    # Create patient
    resp = client.post("/patients", json={
        "name": "John Doe",
        "age": 45,
        "room_number": "304-A",
        "hospital_id": hosp_id,
        "assigned_doctor": doc_id,
        "assigned_nurse": nurse_id
    }, headers=headers)
    assert resp.status_code == 200
    patient_id = resp.json()["patient_id"]

    # 2. Add vitals feed for the patient (so we have vitals modality)
    resp = client.post("/vitals", json={
        "patient_id": patient_id,
        "heart_rate": 80,
        "spo2": 95,
        "temperature": 99.0
    }, headers=headers)
    assert resp.status_code == 200

    # 3. Get initial AI diagnostics
    resp = client.get(f"/ai/diagnostics/{patient_id}", headers=headers)
    assert resp.status_code == 200
    diag = resp.json()
    assert diag["patient_id"] == patient_id
    assert diag["patient_name"] == "John Doe"
    assert diag["classification"] == "AI_STABLE"
    assert "vitals" in diag["modalities_used"]
    assert "text" not in diag["modalities_used"]

    # Sleep for 1.1s to avoid UNIQUE constraint collision on timestamp
    import time
    time.sleep(1.1)

    # Post highly abnormal vitals to trigger abnormal classification
    resp = client.post("/vitals", json={
        "patient_id": patient_id,
        "heart_rate": 125,
        "spo2": 84,
        "temperature": 103.5
    }, headers=headers)
    assert resp.status_code == 200

    # 4. Upload Multimodal Clinical Data (Clinical Notes + Image + Audio + Lab Document)
    dummy_img_b64 = base64.b64encode(np.random.randint(0, 256, 1000, dtype=np.uint8).tobytes()).decode()
    dummy_audio_b64 = base64.b64encode(np.random.randint(0, 256, 5000, dtype=np.uint8).tobytes()).decode()
    
    upload_payload = {
        "clinical_text": "Patient has severe breathing difficulty, dyspnea, and critical low oxygen saturation levels.",
        "image_b64": dummy_img_b64,
        "audio_b64": dummy_audio_b64,
        "document_text": "HEMOGLOBIN: 8.5 (low), WBC: 16000 (high), CRP: elevated. CRITICAL PANIC ALERT."
    }

    resp = client.post(f"/ai/upload/{patient_id}", json=upload_payload, headers=headers)
    assert resp.status_code == 200
    upload_diag = resp.json()
    
    # Verify diagnostic updates
    assert upload_diag["patient_id"] == patient_id
    assert "stored_modalities" in upload_diag
    assert set(upload_diag["stored_modalities"]) == {"text", "image", "audio", "document"}
    
    # Encoders should produce abnormal classification due to strong breathing/sepsis flags in text & document
    assert upload_diag["classification"] != "AI_STABLE"
    assert len(upload_diag["modalities_used"]) == 5  # vitals, text, image, audio, document
    assert upload_diag["risk_severity"] > 40  # Risk score should be elevated due to abnormalities

    # Verify softmax confidence properties
    conf = upload_diag["confidence"]
    assert len(conf) == 8
    assert abs(sum(conf.values()) - 1.0) < 0.01

    # 5. Fetch Saved Clinical Data from DB via Endpoint
    resp = client.get(f"/ai/clinical-data/{patient_id}", headers=headers)
    assert resp.status_code == 200
    stored_records = resp.json()
    assert len(stored_records) == 4
    modalities = {r["modality"] for r in stored_records}
    assert modalities == {"text", "image", "audio", "document"}

    # 6. Fetch Embedding Space Projection
    resp = client.get("/ai/embedding-space", headers=headers)
    assert resp.status_code == 200
    space = resp.json()
    assert "centroids" in space
    assert len(space["centroids"]) == 8
    assert "patients" in space
    assert len(space["patients"]) >= 1
    
    # Confirm John Doe is in the embedding space
    patient_points = [p for p in space["patients"] if p["patient_id"] == patient_id]
    assert len(patient_points) == 1
    john_point = patient_points[0]
    assert john_point["name"] == "John Doe"
    assert len(john_point["embedding"]) == 16
    assert john_point["classification"] != "AI_STABLE"
    assert len(john_point["modalities_used"]) == 5
