"""
ml_engine.py
────────────
Unified Embedding Space Classifier for Multimodal Health Monitoring.

Operates in ℝ¹⁶ — the fused output of the MultimodalFusionEngine.
Uses nearest-centroid classification with softmax confidence scoring,
temporal trend analysis, and composite risk severity scoring.
"""

import numpy as np
import logging
from collections import defaultdict

logger = logging.getLogger("ml_engine")

# ─── Clinical State Centroids in ℝ¹⁶ ─────────────────────────────────────────
# These represent the "ideal" embedding for each clinical state.
# Derived from domain knowledge: each centroid is positioned in the unified
# space such that patients with that condition are closest to it.

_rng = np.random.RandomState(seed=7)  # Deterministic for reproducibility

# Base directions for each state (manually designed, then projected)
_BASE_DIRECTIONS = {
    "AI_STABLE":       np.array([0]*16, dtype=np.float64),
    "AI_TACHYCARDIA":  None,
    "AI_BRADYCARDIA":  None,
    "AI_HYPOXIA":      None,
    "AI_HYPERTHERMIA": None,
    "AI_HYPOTHERMIA":  None,
    "AI_SEPSIS_RISK":  None,
    "AI_CRITICAL":     None,
}

def _init_centroids():
    """
    Initialise clinically meaningful centroids in ℝ¹⁶.
    Each centroid is placed along specific axes to represent the clinical
    signature of that condition in the unified embedding space.
    """
    dim = 16
    centroids = {}

    # STABLE = origin
    centroids["AI_STABLE"] = np.zeros(dim)

    # TACHYCARDIA: high on vitals-HR axis (dim 0-2), moderate elsewhere
    c = np.zeros(dim)
    c[0], c[1], c[6] = 1.8, 0.3, 0.5
    centroids["AI_TACHYCARDIA"] = c

    # BRADYCARDIA: negative HR axis
    c = np.zeros(dim)
    c[0], c[1], c[6] = -1.5, 0.2, 0.4
    centroids["AI_BRADYCARDIA"] = c

    # HYPOXIA: low SpO2 axis (dim 1-3), respiratory text features
    c = np.zeros(dim)
    c[1], c[3], c[7], c[8] = -2.0, 1.2, 0.8, 0.6
    centroids["AI_HYPOXIA"] = c

    # HYPERTHERMIA: high temp axis (dim 2,4)
    c = np.zeros(dim)
    c[2], c[4], c[9] = 2.0, 1.0, 0.5
    centroids["AI_HYPERTHERMIA"] = c

    # HYPOTHERMIA: low temp
    c = np.zeros(dim)
    c[2], c[4], c[9] = -1.8, -0.8, 0.4
    centroids["AI_HYPOTHERMIA"] = c

    # SEPSIS_RISK: inflammatory + multi-system
    c = np.zeros(dim)
    c[0], c[2], c[5], c[10], c[11] = 1.0, 1.2, 1.5, 1.8, 1.0
    centroids["AI_SEPSIS_RISK"] = c

    # CRITICAL: multi-axis severe deviation
    c = np.zeros(dim)
    c[0], c[1], c[2], c[5], c[6], c[10], c[12] = 2.0, -2.5, 1.5, 2.0, 2.0, 1.5, 1.8
    centroids["AI_CRITICAL"] = c

    return centroids


CENTROIDS = _init_centroids()
STATE_LABELS = list(CENTROIDS.keys())
NUM_STATES = len(STATE_LABELS)


# ─── Temporal Trend Tracking ──────────────────────────────────────────────────
# Rolling buffer of embeddings per patient for trend detection.
_patient_embedding_history: dict[int, list[tuple[np.ndarray, float]]] = defaultdict(list)
MAX_HISTORY = 20  # Keep last 20 embeddings per patient


def _softmax(distances: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """
    Convert distances to probabilities via softmax over negative distances.
    Smaller distance = higher probability.
    """
    neg_d = -distances / temperature
    neg_d -= neg_d.max()  # Numerical stability
    exp_d = np.exp(neg_d)
    return exp_d / (exp_d.sum() + 1e-10)


def classify_in_unified_space(unified_embedding: np.ndarray) -> dict:
    """
    Classify a unified embedding (ℝ¹⁶) against clinical state centroids.

    Returns:
        {
            "label": str,
            "confidence": dict[str, float],   # softmax probabilities
            "distance": float,                  # distance to best centroid
            "distances": dict[str, float],     # all distances
        }
    """
    distances = {}
    dist_array = np.zeros(NUM_STATES)

    for i, (label, centroid) in enumerate(CENTROIDS.items()):
        d = float(np.linalg.norm(unified_embedding - centroid))
        distances[label] = round(d, 4)
        dist_array[i] = d

    # Softmax confidence
    probs = _softmax(dist_array, temperature=1.5)
    confidence = {STATE_LABELS[i]: round(float(probs[i]), 4) for i in range(NUM_STATES)}

    # Best label
    best_idx = np.argmin(dist_array)
    best_label = STATE_LABELS[best_idx]
    best_dist = float(dist_array[best_idx])

    # Anomaly score (distance from STABLE origin)
    anomaly_score = float(np.linalg.norm(unified_embedding - CENTROIDS["AI_STABLE"]))

    # If anomaly score is low, force STABLE classification
    if anomaly_score < 1.0:
        stable_idx = STATE_LABELS.index("AI_STABLE")
        best_label = "AI_STABLE"
        best_dist = float(dist_array[stable_idx])

    return {
        "label": best_label,
        "confidence": confidence,
        "distance": round(best_dist, 4),
        "distances": distances,
    }


def compute_risk_severity(
    unified_embedding: np.ndarray,
    classification: dict,
    patient_id: int = None,
) -> int:
    """
    Computes a 0–100 risk severity score based on:
        1. Distance from STABLE centroid (40%)
        2. Confidence entropy (30%) — low entropy = more certain = higher risk if abnormal
        3. Temporal trend velocity (30%) — worsening trend increases risk

    Returns int 0–100.
    """
    # 1. Distance from STABLE
    stable_dist = float(np.linalg.norm(unified_embedding - CENTROIDS["AI_STABLE"]))
    dist_score = min(stable_dist / 4.0, 1.0)  # Normalise: 4.0 = maximum expected

    # 2. Confidence entropy
    probs = np.array(list(classification["confidence"].values()))
    probs = probs + 1e-10
    entropy = -np.sum(probs * np.log(probs))
    max_entropy = np.log(NUM_STATES)
    normalised_entropy = entropy / max_entropy
    # Low entropy when abnormal = high risk
    if classification["label"] != "AI_STABLE":
        entropy_score = 1.0 - normalised_entropy
    else:
        entropy_score = normalised_entropy * 0.3  # Low risk when stable

    # 3. Temporal trend
    trend_score = 0.0
    if patient_id is not None:
        trend_info = compute_temporal_trend(patient_id)
        if trend_info["trend"] == "DETERIORATING":
            trend_score = 1.0
        elif trend_info["trend"] == "WORSENING":
            trend_score = 0.7
        elif trend_info["trend"] == "STABLE":
            trend_score = 0.3
        else:  # IMPROVING
            trend_score = 0.1

    risk = dist_score * 0.4 + entropy_score * 0.3 + trend_score * 0.3
    return max(0, min(100, int(risk * 100)))


def record_embedding(patient_id: int, unified_embedding: np.ndarray, anomaly_score: float):
    """Store embedding in the per-patient rolling buffer."""
    history = _patient_embedding_history[patient_id]
    history.append((unified_embedding.copy(), anomaly_score))
    if len(history) > MAX_HISTORY:
        _patient_embedding_history[patient_id] = history[-MAX_HISTORY:]


def compute_temporal_trend(patient_id: int) -> dict:
    """
    Analyse the patient's embedding trajectory over time.

    Returns:
        {
            "trend": "IMPROVING" | "STABLE" | "WORSENING" | "DETERIORATING",
            "velocity": float,          # magnitude of drift
            "direction": list[float],   # 16D direction vector
        }
    """
    history = _patient_embedding_history.get(patient_id, [])

    if len(history) < 3:
        return {"trend": "STABLE", "velocity": 0.0, "direction": [0.0] * 16}

    # Compare recent embeddings to earlier ones
    recent = [h[0] for h in history[-3:]]
    earlier = [h[0] for h in history[:min(3, len(history))]]

    recent_mean = np.mean(recent, axis=0)
    earlier_mean = np.mean(earlier, axis=0)

    # Drift vector: from earlier to recent
    drift = recent_mean - earlier_mean
    velocity = float(np.linalg.norm(drift))

    # Are we moving toward or away from STABLE?
    stable = CENTROIDS["AI_STABLE"]
    dist_earlier = float(np.linalg.norm(earlier_mean - stable))
    dist_recent = float(np.linalg.norm(recent_mean - stable))

    delta = dist_recent - dist_earlier

    if velocity < 0.1:
        trend = "STABLE"
    elif delta < -0.2:
        trend = "IMPROVING"
    elif delta < 0.3:
        trend = "STABLE"
    elif delta < 0.8:
        trend = "WORSENING"
    else:
        trend = "DETERIORATING"

    return {
        "trend": trend,
        "velocity": round(velocity, 4),
        "direction": [round(float(d), 4) for d in drift],
    }


def get_anomaly_score(unified_embedding: np.ndarray) -> float:
    """Distance-based anomaly score: distance from STABLE centroid."""
    return float(np.linalg.norm(unified_embedding - CENTROIDS["AI_STABLE"]))


def get_embedding_history(patient_id: int) -> list[list[float]]:
    """Returns the stored embedding trajectory for a patient."""
    history = _patient_embedding_history.get(patient_id, [])
    return [[round(float(x), 4) for x in emb] for emb, _ in history]


# ─── Backward-Compatible API ──────────────────────────────────────────────────
# These functions maintain the existing interface used by alert_engine.py

def classify_health_state(heart_rate: float, spo2: float, temperature: float):
    """
    Legacy API: classify using vitals only.
    Internally creates a vitals-only unified embedding.
    """
    from multimodal_encoders import get_fusion_engine

    engine = get_fusion_engine()
    result = engine.encode_all(
        heart_rate=heart_rate,
        spo2=spo2,
        temperature=temperature,
    )

    unified = result["unified_embedding"]
    classification = classify_in_unified_space(unified)

    return classification["label"], classification["distance"]


def normalize_vitals(heart_rate: float, spo2: float, temperature: float) -> np.ndarray:
    """Legacy API: returns the vitals embedding (ℝ⁸) for backward compat."""
    from multimodal_encoders import VitalsEncoder
    return VitalsEncoder().encode(heart_rate, spo2, temperature)


def get_centroids_for_visualization() -> dict:
    """Returns centroid positions for frontend embedding space plot."""
    return {
        label: [round(float(x), 4) for x in centroid]
        for label, centroid in CENTROIDS.items()
    }
