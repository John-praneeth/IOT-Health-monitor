"""
data_sources/fake_source.py  –  Random generator (demo / testing).
"""

import random
from data_sources.base import VitalSource


class FakeSource(VitalSource):
    """Generates random but medically plausible vital signs."""

    def get_vitals(self, patient_id: int) -> dict:
        return {
            "patient_id": patient_id,
            "heart_rate": random.randint(45, 130),
            "spo2": random.randint(85, 100),
            "temperature": round(random.uniform(96.5, 103.5), 1),
            "blood_pressure": f"{random.randint(90, 160)}/{random.randint(55, 95)}",
        }
