"""
ai_diagnostics.py
─────────────────
Orchestration layer for multimodal AI diagnostics.

Ties together multimodal_encoders (encoding) and ml_engine (classification)
to produce structured diagnostic reports for patients.
"""

import logging
import json
from datetime import datetime, timezone

import numpy as np

import ml_engine
from multimodal_encoders import get_fusion_engine

logger = logging.getLogger("ai_diagnostics")


def run_multimodal_diagnosis(
    patient_id: int,
    heart_rate: float = None,
    spo2: float = None,
    temperature: float = None,
    clinical_text: str = None,
    image_b64: str = None,
    audio_b64: str = None,
    document_text: str = None,
) -> dict:
    """
    Run the full multimodal AI diagnostic pipeline for a patient.

    Steps:
        1. Encode each modality → per-modality embeddings (ℝ⁸ each)
        2. Fuse → unified embedding (ℝ¹⁶)
        3. Classify in unified embedding space
        4. Compute risk severity & temporal trend
        5. Record embedding in history

    Returns a structured diagnostic report dict.
    """
    engine = get_fusion_engine()

    # ── Step 1+2: Encode and Fuse ──
    fusion_result = engine.encode_all(
        heart_rate=heart_rate,
        spo2=spo2,
        temperature=temperature,
        clinical_text=clinical_text,
        image_b64=image_b64,
        audio_b64=audio_b64,
        document_text=document_text,
    )

    unified_embedding = fusion_result["unified_embedding"]
    modality_embeddings = fusion_result["modality_embeddings"]
    modalities_used = fusion_result["modalities_used"]
    modality_contributions = fusion_result["modality_contributions"]

    # ── Step 3: Classify ──
    classification = ml_engine.classify_in_unified_space(unified_embedding)

    # ── Step 4: Risk & Trend ──
    anomaly_score = ml_engine.get_anomaly_score(unified_embedding)
    risk_severity = ml_engine.compute_risk_severity(
        unified_embedding, classification, patient_id
    )
    trend = ml_engine.compute_temporal_trend(patient_id)

    # ── Step 5: Record in history ──
    ml_engine.record_embedding(patient_id, unified_embedding, anomaly_score)

    # ── Build report ──
    report = {
        "patient_id": patient_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # Classification
        "classification": classification["label"],
        "confidence": classification["confidence"],
        "anomaly_score": round(anomaly_score, 4),
        "risk_severity": risk_severity,

        # Temporal
        "trend": trend["trend"],
        "trend_velocity": trend["velocity"],

        # Embedding data (for visualization)
        "unified_embedding": [round(float(x), 4) for x in unified_embedding],
        "modality_embeddings": {
            name: [round(float(x), 4) for x in emb]
            for name, emb in modality_embeddings.items()
        },

        # Modality info
        "modalities_used": modalities_used,
        "modality_contributions": {
            k: round(v, 4) for k, v in modality_contributions.items()
        },

        # Historical trajectory
        "embedding_history": ml_engine.get_embedding_history(patient_id),
    }

    logger.info(
        "AI Diagnosis: patient=%d state=%s risk=%d trend=%s modalities=%s",
        patient_id,
        classification["label"],
        risk_severity,
        trend["trend"],
        modalities_used,
    )

    return report


def get_patient_diagnostics_from_db(patient_id: int, db) -> dict:
    """
    Convenience: fetch latest vitals from DB, run diagnosis, and optionally
    include stored clinical data.
    """
    import models

    # Get latest vitals
    from crud import get_latest_vital, _active_source_name
    vital = get_latest_vital(db, patient_id)

    hr = float(vital.heart_rate) if vital else None
    spo2 = float(vital.spo2) if vital else None
    temp = float(vital.temperature) if vital else None

    # Get latest clinical data per modality (if ClinicalData table exists)
    clinical_text = None
    image_b64 = None
    audio_b64 = None
    document_text = None

    try:
        for modality_name, attr in [
            ("text", "clinical_text"),
            ("image", "image_b64"),
            ("audio", "audio_b64"),
            ("document", "document_text"),
        ]:
            record = (
                db.query(models.ClinicalData)
                .filter(
                    models.ClinicalData.patient_id == patient_id,
                    models.ClinicalData.modality == modality_name,
                )
                .order_by(models.ClinicalData.created_at.desc())
                .first()
            )
            if record and record.content:
                if modality_name == "text":
                    clinical_text = record.content
                elif modality_name == "image":
                    image_b64 = record.content
                elif modality_name == "audio":
                    audio_b64 = record.content
                elif modality_name == "document":
                    document_text = record.content
    except Exception as e:
        logger.debug("Could not fetch clinical data: %s", e)

    return run_multimodal_diagnosis(
        patient_id=patient_id,
        heart_rate=hr,
        spo2=spo2,
        temperature=temp,
        clinical_text=clinical_text,
        image_b64=image_b64,
        audio_b64=audio_b64,
        document_text=document_text,
    )


def get_all_patient_diagnostics(db) -> list[dict]:
    """Run diagnostics for all active patients."""
    import models

    patients = db.query(models.Patient).filter(
        models.Patient.is_active == True
    ).all()

    results = []
    for patient in patients:
        try:
            diag = get_patient_diagnostics_from_db(patient.patient_id, db)
            diag["patient_name"] = patient.name
            diag["room_number"] = patient.room_number
            results.append(diag)
        except Exception as e:
            logger.warning("Diagnosis failed for patient %d: %s", patient.patient_id, e)

    return results


def get_embedding_space_data(db) -> dict:
    """
    Returns the full embedding space visualization data:
        - centroids: dict of label → position
        - patients: list of {patient_id, name, position, classification}
    """
    centroids = ml_engine.get_centroids_for_visualization()

    import models
    patients = db.query(models.Patient).filter(
        models.Patient.is_active == True
    ).all()

    patient_points = []
    for patient in patients:
        try:
            diag = get_patient_diagnostics_from_db(patient.patient_id, db)
            patient_points.append({
                "patient_id": patient.patient_id,
                "name": patient.name,
                "embedding": diag["unified_embedding"],
                "classification": diag["classification"],
                "risk_severity": diag["risk_severity"],
                "modalities_used": diag["modalities_used"],
            })
        except Exception as e:
            logger.debug("Skipping patient %d in embedding space: %s", patient.patient_id, e)

    return {
        "centroids": centroids,
        "patients": patient_points,
        "dimensions": 16,
        "projection_axes": [0, 1],  # Default PCA axes for 2D projection
    }
