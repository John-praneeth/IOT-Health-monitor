"""
data_sources/thingspeak_source.py
Reads real-time vitals from a ThingSpeak IoT channel.

Hardware sensor uploads:
    field1 → Heart Rate (bpm)
    field2 → SpO2 (%)
    field3 → Temperature (°F)
"""

import os
import logging
from datetime import datetime, timezone

import httpx
from data_sources.base import VitalSource

logger = logging.getLogger(__name__)

THINGSPEAK_BASE = "https://api.thingspeak.com"

# ── Config from ENV ───────────────────────────────────────────────────────────
THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID", "")
THINGSPEAK_API_KEY    = os.getenv("THINGSPEAK_READ_API_KEY", "")
THINGSPEAK_TEMP_UNIT  = os.getenv("THINGSPEAK_TEMP_UNIT", "F").upper()

# How old the reading can be before we consider it stale (seconds)
STALE_THRESHOLD = int(os.getenv("THINGSPEAK_STALE_SECONDS", "120"))


class ThingSpeakSource(VitalSource):
    """
    Fetches the latest entry from a ThingSpeak channel connected to an
    IoT health-monitoring hardware device (MAX30102 + MLX90614 / DS18B20).
    """

    def __init__(self):
        self.channel_id = THINGSPEAK_CHANNEL_ID
        self.api_key    = THINGSPEAK_API_KEY
        self.temp_unit  = THINGSPEAK_TEMP_UNIT
        logger.info(
            "ThingSpeak source initialised — channel=%s  temp_unit=%s",
            self.channel_id or "(not set)", self.temp_unit,
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def get_vitals(self, patient_id: int) -> dict:
        """Fetch the latest reading from ThingSpeak and return a vitals dict."""

        if not self.channel_id:
            logger.error("THINGSPEAK_CHANNEL_ID not set — returning fallback vitals")
            return self._fallback(patient_id, "no_channel")

        entry = self._fetch_latest()
        if entry is None:
            return self._fallback(patient_id, "fetch_failed")

        # ── Parse fields ──────────────────────────────────────────────────
        hr   = self._safe_float(entry.get("field1"), 0)
        spo2 = self._safe_float(entry.get("field2"), 0)
        temp = self._safe_float(entry.get("field3"), 0)

        # Convert °C → °F if needed
        if self.temp_unit == "C" and temp > 0:
            temp = round(temp * 9 / 5 + 32, 1)

        # ── Validate (sensor sends 0 when not on finger) ─────────────────
        if hr <= 0 or spo2 <= 0 or temp <= 0:
            logger.warning(
                "Sensor reads zero (device idle?) — HR=%.0f SpO2=%.0f Temp=%.1f",
                hr, spo2, temp,
            )
            return self._fallback(patient_id, "sensor_zero")

        if not (20 < hr < 300):
            logger.warning("Heart rate out of range: %.0f", hr)
            return self._fallback(patient_id, "invalid_hr")

        if not (40 < spo2 <= 100):
            logger.warning("SpO2 out of range: %.0f", spo2)
            return self._fallback(patient_id, "invalid_spo2")

        if not (70 < temp < 115):
            logger.warning("Temperature out of range: %.1f°F", temp)
            return self._fallback(patient_id, "invalid_temp")

        # ── Stale-data check ─────────────────────────────────────────────
        if self._is_stale(entry):
            return self._fallback(patient_id, "stale_data")

        logger.info(
            "ThingSpeak → patient %d  HR=%.0f  SpO2=%.0f%%  Temp=%.1f°F",
            patient_id, hr, spo2, temp,
        )

        return {
            "patient_id": patient_id,
            "heart_rate": int(round(hr)),
            "spo2": int(round(spo2)),
            "temperature": round(temp, 1),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_latest(self) -> dict | None:
        """GET the last feed entry from ThingSpeak."""
        url = f"{THINGSPEAK_BASE}/channels/{self.channel_id}/feeds/last.json"
        params = {}
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            resp = httpx.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data
                logger.warning("Empty response from ThingSpeak")
            else:
                logger.error("ThingSpeak HTTP %d: %s", resp.status_code, resp.text[:200])
        except httpx.TimeoutException:
            logger.error("ThingSpeak request timed out")
        except httpx.ConnectError:
            logger.error("Cannot reach ThingSpeak — check internet connection")
        except Exception as exc:
            logger.error("ThingSpeak error: %s", exc)
        return None

    def _is_stale(self, entry: dict) -> bool:
        """Return True if the reading is older than STALE_THRESHOLD seconds."""
        created = entry.get("created_at", "")
        if not created:
            return False
        try:
            ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > STALE_THRESHOLD:
                logger.warning("ThingSpeak data is %.0fs old (threshold %ds) — stale", age, STALE_THRESHOLD)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        """Parse a ThingSpeak field value to float safely."""
        if value is None:
            return default
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _fallback(patient_id: int, reason: str) -> dict:
        """Return safe normal-range vitals (won't trigger alerts)."""
        logger.warning("Using fallback vitals for patient %d (%s)", patient_id, reason)
        return {
            "patient_id": patient_id,
            "heart_rate": 75,
            "spo2": 98,
            "temperature": 98.6,
        }
