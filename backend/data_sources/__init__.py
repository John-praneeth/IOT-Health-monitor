"""
data_sources/__init__.py  –  Factory that returns the configured VitalSource.

Set DATA_SOURCE=thingspeak in .env to use real IoT hardware.
Set DATA_SOURCE=fake (default) to use simulated data.
"""

import os
import logging
from data_sources.base import VitalSource

logger = logging.getLogger(__name__)

_source_instance: VitalSource | None = None


def get_source() -> VitalSource:
    """Return the configured data source (singleton)."""
    global _source_instance

    if _source_instance is not None:
        return _source_instance

    name = os.getenv("DATA_SOURCE", "fake").lower().strip()

    if name == "thingspeak":
        from data_sources.thingspeak_source import ThingSpeakSource
        _source_instance = ThingSpeakSource()
        logger.info("📡 Data source: ThingSpeak (real IoT hardware)")
    else:
        from data_sources.fake_source import FakeSource
        _source_instance = FakeSource()
        logger.info("🎲 Data source: FakeSource (simulated vitals)")

    return _source_instance
