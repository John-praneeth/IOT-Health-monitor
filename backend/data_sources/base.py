"""
data_sources/base.py  –  Abstract interface for vital-sign data providers.
"""

from abc import ABC, abstractmethod
from typing import Dict


class VitalSource(ABC):
    """
    All data sources must implement `get_vitals(patient_id)`.
    Returns a dict matching VitalsCreate fields.
    """

    @abstractmethod
    def get_vitals(self, patient_id: int) -> Dict:
        ...
