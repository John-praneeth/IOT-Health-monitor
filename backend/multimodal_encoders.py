"""
multimodal_encoders.py
─────────────────────
Multimodal Embedding Encoders for the Unified Health Embedding Space.

Architecture:
    Raw Input ──► Modality Encoder ──► e ∈ ℝ⁸ (per-modality embedding)
    [e₁ ⊕ e₂ ⊕ … ⊕ eₖ] ──► Fusion Layer ──► f ∈ ℝ¹⁶ (unified embedding)

Each encoder normalises heterogeneous clinical data into a common
8-dimensional vector so that downstream classification can operate in a
single, unified embedding space regardless of which modalities are present.
"""

import numpy as np
import base64
import re
import logging
import math

logger = logging.getLogger("multimodal_encoders")

# ─── Constants ────────────────────────────────────────────────────────────────
MODALITY_DIM = 8          # Each encoder outputs ℝ⁸
UNIFIED_DIM = 16          # Fused embedding lives in ℝ¹⁶
NUM_MODALITIES = 5        # vitals, text, image, audio, document

MODALITY_NAMES = ["vitals", "text", "image", "audio", "document"]

# Learnable fusion weights (importance of each modality)
# Vitals are most reliable for IoT health monitoring, text next, etc.
MODALITY_WEIGHTS = {
    "vitals":   1.0,
    "text":     0.85,
    "image":    0.70,
    "audio":    0.75,
    "document": 0.80,
}


# ═════════════════════════════════════════════════════════════════════════════
#  1. VITALS ENCODER  (HR, SpO₂, Temperature → ℝ⁸)
# ═════════════════════════════════════════════════════════════════════════════

class VitalsEncoder:
    """
    Encodes IoT sensor vitals into an 8D embedding vector.

    Features:
        [0] HR z-score          (centred on 75 bpm, σ=20)
        [1] SpO₂ z-score       (centred on 98%, σ=4)
        [2] Temp z-score       (centred on 98.6°F, σ=2)
        [3] HR² deviation      (squared, captures extreme HR)
        [4] SpO₂ deficit       (max(0, 95 - spo2) / 10, captures desaturation)
        [5] Temp polarity      (sign × magnitude of temp deviation)
        [6] Multi-signal score (composite abnormality)
        [7] Vitals entropy     (how "spread" abnormality is across signals)
    """

    # Clinical reference baselines
    HR_MEAN, HR_STD = 75.0, 20.0
    SPO2_MEAN, SPO2_STD = 98.0, 4.0
    TEMP_MEAN, TEMP_STD = 98.6, 2.0

    def encode(self, heart_rate: float, spo2: float, temperature: float) -> np.ndarray:
        # Z-scores
        hr_z = (heart_rate - self.HR_MEAN) / self.HR_STD
        spo2_z = (spo2 - self.SPO2_MEAN) / self.SPO2_STD
        temp_z = (temperature - self.TEMP_MEAN) / self.TEMP_STD

        # Derived features
        hr_sq = hr_z ** 2 * np.sign(hr_z)          # Squared deviation, preserving direction
        spo2_deficit = max(0.0, (95.0 - spo2)) / 10.0   # Desaturation below 95%
        temp_polarity = np.sign(temp_z) * abs(temp_z)     # Signed magnitude

        # Multi-signal composite: RMS of z-scores
        multi_signal = np.sqrt((hr_z**2 + spo2_z**2 + temp_z**2) / 3.0)

        # Abnormality entropy: how spread the abnormality is
        abs_scores = np.array([abs(hr_z), abs(spo2_z), abs(temp_z)]) + 1e-8
        probs = abs_scores / abs_scores.sum()
        entropy = -np.sum(probs * np.log(probs + 1e-10))

        embedding = np.array([
            hr_z, spo2_z, temp_z,
            hr_sq, spo2_deficit, temp_polarity,
            multi_signal, entropy
        ], dtype=np.float64)

        return embedding


# ═════════════════════════════════════════════════════════════════════════════
#  2. TEXT ENCODER  (Clinical notes → ℝ⁸)
# ═════════════════════════════════════════════════════════════════════════════

class TextEncoder:
    """
    Encodes clinical text notes into an 8D embedding using medical keyword
    TF-IDF with clinical severity weighting.

    Features are grouped into clinical categories:
        [0] Cardiac score      (tachycardia, bradycardia, arrhythmia, …)
        [1] Respiratory score  (dyspnea, hypoxia, apnea, …)
        [2] Thermoregulatory   (fever, hypothermia, rigors, …)
        [3] Neurological       (confusion, seizure, syncope, …)
        [4] Inflammatory       (sepsis, infection, elevated WBC, …)
        [5] Hemodynamic        (hypotension, shock, edema, …)
        [6] Overall severity   (critical, emergency, unstable, …)
        [7] Text confidence    (normalised word count → signal strength)
    """

    CATEGORY_KEYWORDS = {
        "cardiac": {
            "tachycardia": 1.0, "bradycardia": 1.0, "arrhythmia": 0.9,
            "palpitation": 0.7, "palpitations": 0.7, "irregular heartbeat": 0.9,
            "chest pain": 0.8, "angina": 0.8, "cardiac arrest": 1.0,
            "elevated heart rate": 0.8, "rapid pulse": 0.7, "heart failure": 1.0,
            "murmur": 0.6, "atrial fibrillation": 0.9, "afib": 0.9,
        },
        "respiratory": {
            "dyspnea": 1.0, "hypoxia": 1.0, "apnea": 0.9, "cyanosis": 1.0,
            "shortness of breath": 0.9, "respiratory distress": 1.0,
            "wheezing": 0.6, "stridor": 0.8, "oxygen desaturation": 1.0,
            "low spo2": 0.9, "low oxygen": 0.9, "breathing difficulty": 0.8,
            "tachypnea": 0.8, "pneumonia": 0.7, "pulmonary": 0.5,
        },
        "thermoregulatory": {
            "fever": 0.8, "high fever": 1.0, "hypothermia": 1.0,
            "hyperthermia": 1.0, "rigors": 0.7, "chills": 0.6,
            "elevated temperature": 0.8, "febrile": 0.8, "pyrexia": 0.9,
            "low temperature": 0.8, "cold extremities": 0.5,
        },
        "neurological": {
            "confusion": 0.8, "seizure": 1.0, "syncope": 0.9,
            "altered mental status": 1.0, "unresponsive": 1.0,
            "disoriented": 0.7, "lethargic": 0.7, "coma": 1.0,
            "stroke": 1.0, "unconscious": 1.0, "drowsy": 0.5,
        },
        "inflammatory": {
            "sepsis": 1.0, "infection": 0.7, "elevated wbc": 0.8,
            "leukocytosis": 0.8, "bacteremia": 0.9, "abscess": 0.6,
            "inflammatory": 0.5, "crp elevated": 0.7, "procalcitonin": 0.8,
            "systemic inflammatory": 0.9, "sirs": 0.9,
        },
        "hemodynamic": {
            "hypotension": 1.0, "shock": 1.0, "edema": 0.6,
            "hypertension": 0.5, "blood pressure drop": 0.9,
            "fluid overload": 0.7, "dehydration": 0.6, "hemorrhage": 1.0,
            "bleeding": 0.8, "low blood pressure": 0.9, "vasopressor": 0.9,
        },
        "severity": {
            "critical": 1.0, "emergency": 1.0, "unstable": 0.9,
            "deteriorating": 0.9, "worsening": 0.8, "declining": 0.7,
            "acute": 0.6, "severe": 0.8, "life-threatening": 1.0,
            "urgent": 0.7, "code blue": 1.0, "rapid response": 0.9,
            "icu": 0.8, "intubation": 0.9, "ventilator": 0.8,
        },
    }

    def encode(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(MODALITY_DIM, dtype=np.float64)

        text_lower = text.lower().strip()
        word_count = len(text_lower.split())

        scores = []
        categories = ["cardiac", "respiratory", "thermoregulatory",
                       "neurological", "inflammatory", "hemodynamic", "severity"]

        for category in categories:
            keywords = self.CATEGORY_KEYWORDS[category]
            score = 0.0
            for keyword, weight in keywords.items():
                # Count occurrences
                count = text_lower.count(keyword)
                if count > 0:
                    # TF-IDF style: term frequency × importance weight
                    tf = count / max(word_count, 1)
                    score += tf * weight * 10.0  # Scale up for meaningful values
            scores.append(min(score, 3.0))  # Cap at 3.0 to avoid extreme values

        # Text confidence: based on word count (more words = more signal)
        text_confidence = min(word_count / 50.0, 1.0)
        scores.append(text_confidence)

        return np.array(scores, dtype=np.float64)


# ═════════════════════════════════════════════════════════════════════════════
#  3. IMAGE ENCODER  (Medical image base64 → ℝ⁸)
# ═════════════════════════════════════════════════════════════════════════════

class ImageEncoder:
    """
    Encodes medical image data into an 8D embedding using statistical
    features extracted from the raw image bytes.

    Features:
        [0] Mean intensity         (brightness indicator)
        [1] Intensity std          (contrast indicator)
        [2] Intensity skewness     (asymmetry of pixel distribution)
        [3] Dark pixel ratio       (ratio of very dark pixels, potential pathology)
        [4] Bright pixel ratio     (ratio of very bright pixels)
        [5] Edge density estimate  (high-frequency content proxy)
        [6] Data entropy           (information content)
        [7] Image confidence       (based on data size adequacy)
    """

    def encode(self, image_b64: str) -> np.ndarray:
        if not image_b64 or not image_b64.strip():
            return np.zeros(MODALITY_DIM, dtype=np.float64)

        try:
            # Decode base64 to raw bytes
            raw = base64.b64decode(image_b64)
            data = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)

            if len(data) < 100:
                return np.zeros(MODALITY_DIM, dtype=np.float64)

            # Statistical features from pixel values
            mean_val = np.mean(data) / 255.0
            std_val = np.std(data) / 255.0

            # Skewness
            centered = data - np.mean(data)
            std_raw = np.std(data) + 1e-8
            skewness = np.mean((centered / std_raw) ** 3)

            # Dark/bright pixel ratios
            dark_ratio = np.sum(data < 50) / len(data)
            bright_ratio = np.sum(data > 200) / len(data)

            # Edge density: approximate via differences between adjacent bytes
            diffs = np.abs(np.diff(data))
            edge_density = np.mean(diffs > 30)  # High-gradient transitions

            # Data entropy
            hist, _ = np.histogram(data, bins=64, range=(0, 256))
            probs = hist / (hist.sum() + 1e-10)
            entropy = -np.sum(probs * np.log2(probs + 1e-10)) / 6.0  # Normalise to ~[0,1]

            # Confidence based on data size
            confidence = min(len(data) / 50000.0, 1.0)

            embedding = np.array([
                mean_val, std_val, skewness / 3.0,
                dark_ratio, bright_ratio, edge_density,
                entropy, confidence
            ], dtype=np.float64)

            return embedding

        except Exception as e:
            logger.warning("ImageEncoder error: %s", e)
            return np.zeros(MODALITY_DIM, dtype=np.float64)


# ═════════════════════════════════════════════════════════════════════════════
#  4. AUDIO ENCODER  (Audio waveform base64 → ℝ⁸)
# ═════════════════════════════════════════════════════════════════════════════

class AudioEncoder:
    """
    Encodes audio waveform data into an 8D embedding using amplitude and
    spectral features.

    Features:
        [0] Mean amplitude          (average signal level)
        [1] Amplitude std           (signal variability)
        [2] Peak amplitude          (max signal excursion)
        [3] Zero-crossing rate      (frequency content proxy)
        [4] Low-energy frame ratio  (ratio of quiet segments)
        [5] Amplitude range         (dynamic range)
        [6] RMS energy              (signal power)
        [7] Audio confidence        (data adequacy)
    """

    def encode(self, audio_b64: str) -> np.ndarray:
        if not audio_b64 or not audio_b64.strip():
            return np.zeros(MODALITY_DIM, dtype=np.float64)

        try:
            raw = base64.b64decode(audio_b64)
            # Interpret as 8-bit unsigned PCM for simplicity
            data = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)

            if len(data) < 100:
                return np.zeros(MODALITY_DIM, dtype=np.float64)

            # Normalise to [-1, 1] range
            signal = (data - 128.0) / 128.0

            mean_amp = np.mean(np.abs(signal))
            std_amp = np.std(signal)
            peak_amp = np.max(np.abs(signal))

            # Zero-crossing rate
            sign_changes = np.diff(np.sign(signal))
            zcr = np.sum(sign_changes != 0) / len(signal)

            # Low-energy frame ratio (frames with energy < 30% of mean)
            frame_size = max(len(signal) // 20, 1)
            frames = [signal[i:i+frame_size] for i in range(0, len(signal) - frame_size, frame_size)]
            if frames:
                frame_energies = [np.mean(f**2) for f in frames]
                mean_energy = np.mean(frame_energies) + 1e-10
                low_energy_ratio = sum(1 for e in frame_energies if e < 0.3 * mean_energy) / len(frames)
            else:
                low_energy_ratio = 0.0

            # Dynamic range
            amp_range = peak_amp - np.min(np.abs(signal))

            # RMS energy
            rms = np.sqrt(np.mean(signal ** 2))

            # Confidence
            confidence = min(len(data) / 10000.0, 1.0)

            embedding = np.array([
                mean_amp, std_amp, peak_amp,
                zcr, low_energy_ratio, amp_range,
                rms, confidence
            ], dtype=np.float64)

            return embedding

        except Exception as e:
            logger.warning("AudioEncoder error: %s", e)
            return np.zeros(MODALITY_DIM, dtype=np.float64)


# ═════════════════════════════════════════════════════════════════════════════
#  5. DOCUMENT ENCODER  (Lab reports / clinical documents → ℝ⁸)
# ═════════════════════════════════════════════════════════════════════════════

class DocumentEncoder:
    """
    Encodes clinical documents and lab reports into an 8D embedding by
    extracting lab value keywords and assessing severity.

    Features:
        [0] Haematology score     (WBC, RBC, haemoglobin, platelet mentions)
        [1] Metabolic score       (glucose, sodium, potassium, creatinine)
        [2] Inflammatory markers  (CRP, ESR, procalcitonin)
        [3] Liver/Renal function  (ALT, AST, BUN, GFR)
        [4] Abnormality count     (mentions of "high", "low", "elevated", "abnormal")
        [5] Critical flag count   (mentions of "critical", "panic", "stat")
        [6] Numeric density       (ratio of numbers in text, indicates data-rich reports)
        [7] Document confidence   (text length adequacy)
    """

    LAB_CATEGORIES = {
        "haematology": [
            "wbc", "rbc", "hemoglobin", "haemoglobin", "hgb", "platelet",
            "plt", "hematocrit", "hct", "neutrophil", "lymphocyte",
            "white blood cell", "red blood cell", "anemia", "leukocyte",
        ],
        "metabolic": [
            "glucose", "sodium", "potassium", "calcium", "magnesium",
            "chloride", "bicarbonate", "hba1c", "a1c", "blood sugar",
            "bmp", "cmp", "electrolyte", "creatinine", "bun",
        ],
        "inflammatory": [
            "crp", "c-reactive", "esr", "procalcitonin", "ferritin",
            "sed rate", "interleukin", "il-6", "d-dimer", "fibrinogen",
        ],
        "organ_function": [
            "alt", "ast", "bilirubin", "albumin", "gfr", "egfr",
            "troponin", "bnp", "nt-probnp", "lipase", "amylase",
            "ldh", "alkaline phosphatase", "alp", "liver function",
            "renal function", "kidney function",
        ],
    }

    ABNORMALITY_WORDS = [
        "high", "low", "elevated", "decreased", "abnormal", "above normal",
        "below normal", "out of range", "positive", "reactive",
    ]

    CRITICAL_WORDS = [
        "critical", "panic", "stat", "urgent", "alert", "flagged",
        "life-threatening", "immediate", "emergency",
    ]

    def encode(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(MODALITY_DIM, dtype=np.float64)

        text_lower = text.lower().strip()
        word_count = max(len(text_lower.split()), 1)

        # Lab category scores
        scores = []
        for category in ["haematology", "metabolic", "inflammatory", "organ_function"]:
            keywords = self.LAB_CATEGORIES[category]
            count = sum(text_lower.count(kw) for kw in keywords)
            score = min(count / word_count * 20.0, 3.0)
            scores.append(score)

        # Abnormality count
        abnormal_count = sum(text_lower.count(w) for w in self.ABNORMALITY_WORDS)
        scores.append(min(abnormal_count / word_count * 15.0, 3.0))

        # Critical flags
        critical_count = sum(text_lower.count(w) for w in self.CRITICAL_WORDS)
        scores.append(min(critical_count / word_count * 20.0, 3.0))

        # Numeric density: ratio of tokens that are numbers
        tokens = text_lower.split()
        numeric_tokens = sum(1 for t in tokens if re.match(r'^[\d.,]+$', t))
        numeric_density = numeric_tokens / word_count
        scores.append(min(numeric_density * 3.0, 1.0))

        # Document confidence
        confidence = min(word_count / 40.0, 1.0)
        scores.append(confidence)

        return np.array(scores, dtype=np.float64)


# ═════════════════════════════════════════════════════════════════════════════
#  MULTIMODAL FUSION ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class MultimodalFusionEngine:
    """
    Fuses per-modality embeddings (each ∈ ℝ⁸) into a unified embedding ∈ ℝ¹⁶.

    Pipeline:
        1. Weight each modality embedding by its importance + availability
        2. Concatenate all 5 embeddings → ℝ⁴⁰
        3. Apply linear projection W_fusion (40 × 16) → ℝ¹⁶

    The projection matrix W_fusion is a fixed, deterministic matrix derived
    from a seeded random initialisation (simulating a trained projection layer).
    """

    def __init__(self):
        self.vitals_encoder = VitalsEncoder()
        self.text_encoder = TextEncoder()
        self.image_encoder = ImageEncoder()
        self.audio_encoder = AudioEncoder()
        self.document_encoder = DocumentEncoder()

        # Deterministic "learned" projection matrix (40 → 16)
        rng = np.random.RandomState(seed=42)
        raw = rng.randn(NUM_MODALITIES * MODALITY_DIM, UNIFIED_DIM)
        # Orthogonal-ish initialisation via QR decomposition
        q, _ = np.linalg.qr(raw)
        self.W_fusion = q[:, :UNIFIED_DIM] * 0.5  # Scale down

        # Bias term
        self.b_fusion = np.zeros(UNIFIED_DIM)

    def encode_all(
        self,
        heart_rate: float = None,
        spo2: float = None,
        temperature: float = None,
        clinical_text: str = None,
        image_b64: str = None,
        audio_b64: str = None,
        document_text: str = None,
    ) -> dict:
        """
        Encode all available modalities and fuse into unified embedding.

        Returns dict with:
            - unified_embedding: np.ndarray ∈ ℝ¹⁶
            - modality_embeddings: dict[str, np.ndarray] (each ∈ ℝ⁸)
            - modalities_used: list[str]
            - modality_contributions: dict[str, float] (0-1 weights)
        """
        modality_embeddings = {}
        modalities_used = []

        # ── Encode each modality ──
        if heart_rate is not None and spo2 is not None and temperature is not None:
            modality_embeddings["vitals"] = self.vitals_encoder.encode(
                heart_rate, spo2, temperature
            )
            modalities_used.append("vitals")
        else:
            modality_embeddings["vitals"] = np.zeros(MODALITY_DIM)

        if clinical_text:
            modality_embeddings["text"] = self.text_encoder.encode(clinical_text)
            modalities_used.append("text")
        else:
            modality_embeddings["text"] = np.zeros(MODALITY_DIM)

        if image_b64:
            modality_embeddings["image"] = self.image_encoder.encode(image_b64)
            modalities_used.append("image")
        else:
            modality_embeddings["image"] = np.zeros(MODALITY_DIM)

        if audio_b64:
            modality_embeddings["audio"] = self.audio_encoder.encode(audio_b64)
            modalities_used.append("audio")
        else:
            modality_embeddings["audio"] = np.zeros(MODALITY_DIM)

        if document_text:
            modality_embeddings["document"] = self.document_encoder.encode(document_text)
            modalities_used.append("document")
        else:
            modality_embeddings["document"] = np.zeros(MODALITY_DIM)

        # ── Compute modality contributions ──
        modality_contributions = {}
        for name in MODALITY_NAMES:
            if name in modalities_used:
                emb_norm = float(np.linalg.norm(modality_embeddings[name]))
                modality_contributions[name] = MODALITY_WEIGHTS[name] * min(emb_norm / 2.0, 1.0)
            else:
                modality_contributions[name] = 0.0

        # ── Weight and concatenate ──
        weighted_parts = []
        for name in MODALITY_NAMES:
            weight = modality_contributions.get(name, 0.0) if name in modalities_used else 0.0
            weighted_emb = modality_embeddings[name] * max(weight, 0.0)
            weighted_parts.append(weighted_emb)

        concatenated = np.concatenate(weighted_parts)  # ℝ⁴⁰

        # ── Project to unified space ──
        unified = concatenated @ self.W_fusion + self.b_fusion  # ℝ¹⁶

        return {
            "unified_embedding": unified,
            "modality_embeddings": modality_embeddings,
            "modalities_used": modalities_used,
            "modality_contributions": modality_contributions,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
_fusion_engine = None

def get_fusion_engine() -> MultimodalFusionEngine:
    """Returns the singleton fusion engine instance."""
    global _fusion_engine
    if _fusion_engine is None:
        _fusion_engine = MultimodalFusionEngine()
    return _fusion_engine
