"""
data_sources/thingspeak_source.py  –  Reads vitals from a ThingSpeak channel.
"""

import os
import httpx
from data_sources.base import VitalSource


THINGSPEAK_CHANNEL = os.getenv("THINGSPEAK_CHANNEL_ID", "")
THINGSPEAK_API_KEY = os.getenv("THINGSPEAK_READ_API_KEY", "")
THINGSPEAK_BASE    = "https://api.thingspeak.com"


class ThingSpeakSource(VitalSource):
    """
    Fetches the latest entry from a ThingSpeak channel.
    Expected field mapping:
        field1 → heart_rate
        field2 → spo2
        field3 → temperature
        field4 → blood_pressure
    """

    def get_vitals(self, patient_id: int) -> dict:
        url = f"{THINGSPEAK_BASE}/channels/{THINGSPEAK_CHANNEL}/feeds/last.json"
        params = {"api_key": THINGSPEAK_API_KEY}
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        return {
            "patient_id": patient_id,
            "heart_rate": int(data.get("field1", 72)),
            "spo2": int(data.get("field2", 98)),
            "temperature": round(float(data.get("field3", 98.6)), 1),
            "blood_pressure": str(data.get("field4", "120/80")),
        }
