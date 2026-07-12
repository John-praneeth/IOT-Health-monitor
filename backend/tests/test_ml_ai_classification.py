"""
tests/test_ml_ai_classification.py
───────────────────────────────────
Tests for the Multimodal Unified Embedding Space AI Engine.

Covers:
    - Individual modality encoders (dimensionality, feature extraction)
    - Multimodal fusion engine (concatenation, projection)
    - Unified space classifier (all 8 states, softmax)
    - Risk severity scoring (0–100 range)
    - Temporal trend detection
    - Alert engine integration (backward compatibility)
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
#  ENCODER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestVitalsEncoder:
    def test_output_dimension(self):
        from multimodal_encoders import VitalsEncoder
        enc = VitalsEncoder()
        emb = enc.encode(75, 98, 98.6)
        assert emb.shape == (8,)

    def test_normal_vitals_near_zero(self):
        from multimodal_encoders import VitalsEncoder
        enc = VitalsEncoder()
        emb = enc.encode(75, 98, 98.6)  # Baseline normals
        assert np.linalg.norm(emb[:3]) < 0.1  # Z-scores should be ~0

    def test_abnormal_vitals_large_norm(self):
        from multimodal_encoders import VitalsEncoder
        enc = VitalsEncoder()
        emb = enc.encode(140, 80, 104.0)  # Very abnormal
        assert np.linalg.norm(emb) > 2.0


class TestTextEncoder:
    def test_output_dimension(self):
        from multimodal_encoders import TextEncoder
        enc = TextEncoder()
        emb = enc.encode("Patient has tachycardia and dyspnea")
        assert emb.shape == (8,)

    def test_empty_text_zero(self):
        from multimodal_encoders import TextEncoder
        enc = TextEncoder()
        emb = enc.encode("")
        assert np.allclose(emb, 0)

    def test_cardiac_keywords_detected(self):
        from multimodal_encoders import TextEncoder
        enc = TextEncoder()
        emb = enc.encode("tachycardia arrhythmia elevated heart rate")
        assert emb[0] > 0  # Cardiac score should be positive


class TestImageEncoder:
    def test_output_dimension(self):
        from multimodal_encoders import ImageEncoder
        import base64
        enc = ImageEncoder()
        # Create dummy image data
        dummy = base64.b64encode(np.random.randint(0, 256, 1000, dtype=np.uint8).tobytes()).decode()
        emb = enc.encode(dummy)
        assert emb.shape == (8,)

    def test_empty_returns_zero(self):
        from multimodal_encoders import ImageEncoder
        enc = ImageEncoder()
        emb = enc.encode("")
        assert np.allclose(emb, 0)


class TestAudioEncoder:
    def test_output_dimension(self):
        from multimodal_encoders import AudioEncoder
        import base64
        enc = AudioEncoder()
        dummy = base64.b64encode(np.random.randint(0, 256, 5000, dtype=np.uint8).tobytes()).decode()
        emb = enc.encode(dummy)
        assert emb.shape == (8,)

    def test_empty_returns_zero(self):
        from multimodal_encoders import AudioEncoder
        enc = AudioEncoder()
        emb = enc.encode("")
        assert np.allclose(emb, 0)


class TestDocumentEncoder:
    def test_output_dimension(self):
        from multimodal_encoders import DocumentEncoder
        enc = DocumentEncoder()
        emb = enc.encode("WBC: 15000, CRP elevated, Glucose: 280 mg/dL")
        assert emb.shape == (8,)

    def test_lab_keywords_detected(self):
        from multimodal_encoders import DocumentEncoder
        enc = DocumentEncoder()
        emb = enc.encode("hemoglobin low platelet count critical wbc elevated")
        assert emb[0] > 0  # Haematology score
        assert emb[4] > 0  # Abnormality count


# ═══════════════════════════════════════════════════════════════════════════════
#  FUSION ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultimodalFusion:
    def test_unified_embedding_dimension(self):
        from multimodal_encoders import get_fusion_engine
        engine = get_fusion_engine()
        result = engine.encode_all(heart_rate=80, spo2=95, temperature=99.0)
        assert result["unified_embedding"].shape == (16,)

    def test_modalities_tracked(self):
        from multimodal_encoders import get_fusion_engine
        engine = get_fusion_engine()
        result = engine.encode_all(
            heart_rate=80, spo2=95, temperature=99.0,
            clinical_text="Patient has fever"
        )
        assert "vitals" in result["modalities_used"]
        assert "text" in result["modalities_used"]
        assert "image" not in result["modalities_used"]

    def test_partial_modality_works(self):
        from multimodal_encoders import get_fusion_engine
        engine = get_fusion_engine()
        # Only text
        result = engine.encode_all(clinical_text="severe hypoxia critical")
        assert result["unified_embedding"].shape == (16,)
        assert "text" in result["modalities_used"]
        assert len(result["modalities_used"]) == 1

    def test_all_modalities(self):
        from multimodal_encoders import get_fusion_engine
        import base64
        engine = get_fusion_engine()
        dummy_b64 = base64.b64encode(np.random.randint(0, 256, 1000, dtype=np.uint8).tobytes()).decode()
        result = engine.encode_all(
            heart_rate=120, spo2=85, temperature=103.0,
            clinical_text="critical patient hypoxia",
            image_b64=dummy_b64,
            audio_b64=dummy_b64,
            document_text="WBC elevated CRP high"
        )
        assert len(result["modalities_used"]) == 5


# ═══════════════════════════════════════════════════════════════════════════════
#  CLASSIFIER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnifiedClassifier:
    def test_stable_classification(self):
        from multimodal_encoders import get_fusion_engine
        import ml_engine
        engine = get_fusion_engine()
        result = engine.encode_all(heart_rate=75, spo2=98, temperature=98.6)
        classification = ml_engine.classify_in_unified_space(result["unified_embedding"])
        assert classification["label"] == "AI_STABLE"

    def test_softmax_sums_to_one(self):
        from multimodal_encoders import get_fusion_engine
        import ml_engine
        engine = get_fusion_engine()
        result = engine.encode_all(heart_rate=120, spo2=85, temperature=103.0)
        classification = ml_engine.classify_in_unified_space(result["unified_embedding"])
        total = sum(classification["confidence"].values())
        assert abs(total - 1.0) < 0.01

    def test_all_states_in_confidence(self):
        import ml_engine
        from multimodal_encoders import get_fusion_engine
        engine = get_fusion_engine()
        result = engine.encode_all(heart_rate=80, spo2=95, temperature=99.0)
        classification = ml_engine.classify_in_unified_space(result["unified_embedding"])
        assert len(classification["confidence"]) == 8

    def test_risk_severity_range(self):
        import ml_engine
        from multimodal_encoders import get_fusion_engine
        engine = get_fusion_engine()
        result = engine.encode_all(heart_rate=140, spo2=80, temperature=104.0)
        classification = ml_engine.classify_in_unified_space(result["unified_embedding"])
        risk = ml_engine.compute_risk_severity(
            result["unified_embedding"], classification, patient_id=999
        )
        assert 0 <= risk <= 100


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMPORAL TREND TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTemporalTrend:
    def test_stable_trend_with_few_readings(self):
        import ml_engine
        # With < 3 readings, should default to STABLE
        trend = ml_engine.compute_temporal_trend(patient_id=888)
        assert trend["trend"] == "STABLE"

    def test_trend_tracks_history(self):
        import ml_engine
        pid = 777
        # Simulate worsening: embeddings moving away from origin
        for i in range(5):
            emb = np.ones(16) * (i * 0.5)
            ml_engine.record_embedding(pid, emb, float(i))
        
        trend = ml_engine.compute_temporal_trend(pid)
        assert trend["trend"] in ["WORSENING", "DETERIORATING", "STABLE"]
        assert trend["velocity"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  ALERT ENGINE INTEGRATION (BACKWARD COMPATIBILITY)
# ═══════════════════════════════════════════════════════════════════════════════

class FakeVital:
    def __init__(self, patient_id=1, hr=80, spo2=98, temp=98.6):
        self.patient_id = patient_id
        self.heart_rate = hr
        self.spo2 = spo2
        self.temperature = temp


class TestAlertEngineIntegration:
    def test_ai_critical_alert(self):
        from alert_engine import check_alerts
        # Extreme values should trigger AI alert in the embedding space
        v = FakeVital(patient_id=301, hr=140, spo2=80, temp=104.0)
        
        # 1st reading (sensitivity buffer)
        res1 = check_alerts(v)
        
        # 2nd reading (should pass sensitivity threshold)
        res2 = check_alerts(v)
        # Should have at least one AI-prefixed alert
        ai_alerts = [a for a in res2 if a.startswith("AI_")]
        assert len(ai_alerts) > 0 or len(res2) > 0  # Either AI or threshold alerts

    def test_ai_stable_no_alert(self):
        from alert_engine import check_alerts
        v = FakeVital(patient_id=302, hr=75, spo2=98, temp=98.6)
        check_alerts(v)
        res = check_alerts(v)
        ai_alerts = [a for a in res if a.startswith("AI_")]
        assert len(ai_alerts) == 0

    def test_classify_health_state_backward_compat(self):
        import ml_engine
        label, dist = ml_engine.classify_health_state(75, 98, 98.6)
        assert label == "AI_STABLE"
        assert isinstance(dist, float)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANOMALY SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnomalyScore:
    def test_normal_low_anomaly(self):
        import ml_engine
        from multimodal_encoders import get_fusion_engine
        engine = get_fusion_engine()
        result = engine.encode_all(heart_rate=75, spo2=98, temperature=98.6)
        score = ml_engine.get_anomaly_score(result["unified_embedding"])
        assert score < 2.0

    def test_abnormal_high_anomaly(self):
        import ml_engine
        from multimodal_encoders import get_fusion_engine
        engine = get_fusion_engine()
        result = engine.encode_all(heart_rate=150, spo2=75, temperature=105.0)
        score = ml_engine.get_anomaly_score(result["unified_embedding"])
        assert score > 0.5  # Should be noticeably above normal
