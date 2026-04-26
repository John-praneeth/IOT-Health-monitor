"""
data_sources/thingspeak_source.py
Reads real-time vitals from a ThingSpeak IoT channel.

Hardware sensor uploads:
    field1 → Heart Rate (bpm)
    field2 → SpO2 (%)
    field3 → Temperature (°F)
"""

import logging
from datetime import datetime, timezone

import httpx
from data_sources.base import VitalSource
from data_sources.fake_source import FakeSource

logger = logging.getLogger(__name__)

THINGSPEAK_BASE = "https://api.thingspeak.com"


class ThingSpeakSource(VitalSource):
    """
    Fetches the latest entry from a ThingSpeak channel connected to an
    IoT health-monitoring hardware device (MAX30102 + MLX90614 / DS18B20).
    """

    def __init__(self, *, channel_id: str, api_key: str = "", temp_unit: str = "F", stale_threshold: int = 120):
        self.channel_id = channel_id
        self.api_key = api_key
        self.temp_unit = temp_unit.upper()
        self.stale_threshold = stale_threshold
        self._fallback_source = FakeSource()
        self._cache_latest: dict | None = None
        self._cache_timestamp: float = 0
        logger.info(
            "ThingSpeak source initialised — channel=%s  temp_unit=%s",
            self.channel_id or "(not set)", self.temp_unit,
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def get_vitals(self, patient_id: int) -> dict:
        """Fetch the latest reading from ThingSpeak and return a vitals dict."""
        import time

        if not self.channel_id:
            logger.error("THINGSPEAK_CHANNEL_ID not set — returning fallback vitals")
            return self._fallback(patient_id, "no_channel")

        # Use cache if fresh (2 seconds) to avoid per-patient rate limiting
        now = time.time()
        if self._cache_latest and (now - self._cache_timestamp < 2):
            return self._parse_entry(self._cache_latest, patient_id)

        entry = self._fetch_latest()
        if entry is None:
            return self._fallback(patient_id, "fetch_failed")

        self._cache_latest = entry
        self._cache_timestamp = now
        return self._parse_entry(entry, patient_id)

    def get_history(self, patient_id: int, count: int = 50) -> list[dict]:
        """Fetch historical readings from ThingSpeak for backfilling."""
        if not self.channel_id:
            return []

        url = f"{THINGSPEAK_BASE}/channels/{self.channel_id}/feeds.json"
        params = {"results": count}
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            resp = httpx.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                feeds = data.get("feeds", [])
                results = []
                for entry in feeds:
                    parsed = self._parse_entry(entry, patient_id, skip_stale_check=True)
                    if not parsed.get("is_fallback"):
                        results.append(parsed)
                return results
            else:
                logger.error("ThingSpeak History HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("ThingSpeak history error: %s", exc)
        return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_entry(self, entry: dict, patient_id: int, skip_stale_check: bool = False) -> dict:
        """Centralized parser for a single ThingSpeak feed entry."""
        # ── Parse fields ──────────────────────────────────────────────────
        hr   = self._safe_float(entry.get("field1"), 0)
        spo2 = self._safe_float(entry.get("field2"), 0)
        temp = self._safe_float(entry.get("field3"), 0)

        # Convert °C → °F if needed
        if self.temp_unit == "C" and temp > 0:
            temp = round(temp * 9 / 5 + 32, 1)

        # ── Validate (sensor sends 0 when not on finger) ─────────────────
        if hr <= 0 or spo2 <= 0 or temp <= 0:
            return self._fallback(patient_id, "sensor_zero")

        # Allow lower SpO2 for hardware test values (e.g. sensor returning 36)
        if not (20 < hr < 300) or not (0 < spo2 <= 100) or not (70 < temp < 115):
            return self._fallback(patient_id, "invalid_range")

        # ── Stale-data check ─────────────────────────────────────────────
        if not skip_stale_check and self._is_stale(entry):
            return self._fallback(patient_id, "stale_data")

        # Extract timestamp
        ts = None
        created = entry.get("created_at")
        if created:
            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                pass

        return {
            "patient_id": patient_id,
            "heart_rate": int(round(hr)),
            "spo2": int(round(spo2)),
            "temperature": round(temp, 1),
            "timestamp": ts,
        }


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
                if isinstance(data, dict) and data:
                    return data
                logger.warning("Empty or non-dictionary response from ThingSpeak")
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
            if age > self.stale_threshold:
                logger.warning("ThingSpeak data is %.0fs old (threshold %ds) — stale", age, self.stale_threshold)
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

    def _fallback(self, patient_id: int, reason: str) -> dict:
        """Return dynamic fallback vitals so the UI stays alive when IoT hardware fails."""
        logger.warning("Using dynamic FakeSource fallback for patient %d (%s)", patient_id, reason)
        vitals = self._fallback_source.get_vitals(patient_id)
        # We can add an indicator that this is fallback data if needed by the frontend
        vitals["is_fallback"] = True
        return vitals
