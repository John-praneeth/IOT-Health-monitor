"""
data_sources/fake_source.py  –  Random generator (demo / testing).
"""

import random
from data_sources.base import VitalSource


class FakeSource(VitalSource):
    """Generates random but medically plausible vital signs."""

    def get_vitals(self, patient_id: int) -> dict:
        # 80% chance of normal vitals, 20% chance of abnormal (triggering alerts)
        if random.random() < 0.8:
            # Normal vitals — no alerts triggered
            return {
                "patient_id": patient_id,
                "heart_rate": random.randint(60, 100),
                "spo2": random.randint(94, 100),
                "temperature": round(random.uniform(97.0, 99.5), 1),
            }
        else:
            # Abnormal vitals — may trigger alerts
            return {
                "patient_id": patient_id,
                "heart_rate": random.randint(45, 130),
                "spo2": random.randint(85, 100),
                "temperature": round(random.uniform(96.5, 103.5), 1),
            }
