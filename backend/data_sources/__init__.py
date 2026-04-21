"""Factory and runtime configuration for vitals data sources."""

import os
import logging
from typing import Any

from database import SessionLocal
from data_sources.base import VitalSource
from models import AppSetting

logger = logging.getLogger(__name__)

_source_instance: VitalSource | None = None
_source_signature: tuple[Any, ...] | None = None

_SETTING_KEYS = {
    "source": "vitals.source",
}

_DEFAULT_CONFIG = {
    "source": os.getenv("DATA_SOURCE", "fake").lower().strip() or "fake",
    "thingspeak_channel_id": os.getenv("THINGSPEAK_CHANNEL_ID", "").strip(),
    "thingspeak_read_api_key": os.getenv("THINGSPEAK_READ_API_KEY", "").strip(),
    "thingspeak_temp_unit": os.getenv("THINGSPEAK_TEMP_UNIT", "F").upper().strip() or "F",
    "thingspeak_stale_seconds": int(os.getenv("THINGSPEAK_STALE_SECONDS", "120")),
}


def _compute_signature(config: dict[str, Any]) -> tuple[Any, ...]:
    return (
        config["source"],
        config["thingspeak_channel_id"],
        bool(config["thingspeak_read_api_key"]),
        config["thingspeak_temp_unit"],
        config["thingspeak_stale_seconds"],
    )


def _read_db_overrides(db) -> dict[str, Any]:
    rows = (
        db.query(AppSetting)
        .filter(AppSetting.setting_key.in_(_SETTING_KEYS.values()))
        .all()
    )
    values = {row.setting_key: row.setting_value for row in rows}
    return {
        "source": values.get(_SETTING_KEYS["source"]),
    }


def _normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    source = (raw.get("source") or _DEFAULT_CONFIG["source"]).strip().lower()
    if source not in {"fake", "thingspeak"}:
        source = "fake"

    temp_unit = (raw.get("thingspeak_temp_unit") or _DEFAULT_CONFIG["thingspeak_temp_unit"]).strip().upper()
    if temp_unit not in {"F", "C"}:
        temp_unit = "F"

    stale_raw = raw.get("thingspeak_stale_seconds")
    try:
        stale_seconds = int(stale_raw) if stale_raw is not None else _DEFAULT_CONFIG["thingspeak_stale_seconds"]
    except (TypeError, ValueError):
        stale_seconds = _DEFAULT_CONFIG["thingspeak_stale_seconds"]
    stale_seconds = min(max(stale_seconds, 10), 3600)

    channel_raw = raw.get("thingspeak_channel_id")
    if channel_raw is None:
        channel_id = _DEFAULT_CONFIG["thingspeak_channel_id"]
    else:
        channel_id = str(channel_raw).strip()

    api_key_raw = raw.get("thingspeak_read_api_key")
    if api_key_raw is None:
        api_key = _DEFAULT_CONFIG["thingspeak_read_api_key"]
    else:
        api_key = str(api_key_raw).strip()

    return {
        "source": source,
        "thingspeak_channel_id": channel_id,
        "thingspeak_read_api_key": api_key,
        "thingspeak_temp_unit": temp_unit,
        "thingspeak_stale_seconds": stale_seconds,
    }


def get_data_source_config() -> dict[str, Any]:
    db = SessionLocal()
    try:
        merged = dict(_DEFAULT_CONFIG)
        source_override = _read_db_overrides(db).get("source")
        if source_override is not None:
            merged["source"] = source_override
        return _normalize_config(merged)
    finally:
        db.close()


def update_data_source_config(
    *,
    source: str,
) -> dict[str, Any]:
    updates = {"source": source}
    current = get_data_source_config()
    current.update(updates)
    normalized = _normalize_config(current)
    if normalized["source"] == "thingspeak" and not normalized["thingspeak_channel_id"]:
        raise ValueError("ThingSpeak channel ID is required when source is 'thingspeak'")

    db = SessionLocal()
    try:
        db.merge(AppSetting(setting_key=_SETTING_KEYS["source"], setting_value=normalized["source"]))
        db.commit()
    finally:
        db.close()

    global _source_instance, _source_signature
    _source_instance = None
    _source_signature = None
    return get_data_source_config()


def get_source() -> VitalSource:
    """Return the configured data source, refreshing if config changed."""
    global _source_instance, _source_signature
    config = get_data_source_config()
    signature = _compute_signature(config)

    if _source_instance is not None and _source_signature == signature:
        return _source_instance

    if config["source"] == "thingspeak":
        from data_sources.thingspeak_source import ThingSpeakSource

        _source_instance = ThingSpeakSource(
            channel_id=config["thingspeak_channel_id"],
            api_key=config["thingspeak_read_api_key"],
            temp_unit=config["thingspeak_temp_unit"],
            stale_threshold=config["thingspeak_stale_seconds"],
        )
        logger.info("📡 Data source: ThingSpeak (real IoT hardware)")
    else:
        from data_sources.fake_source import FakeSource

        _source_instance = FakeSource()
        logger.info("🎲 Data source: FakeSource (simulated vitals)")

    _source_signature = signature
    return _source_instance
