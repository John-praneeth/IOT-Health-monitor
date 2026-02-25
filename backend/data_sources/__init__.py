"""
data_sources/__init__.py  –  Factory that returns the configured VitalSource.
"""

import os
from data_sources.base import VitalSource
from data_sources.fake_source import FakeSource
from data_sources.thingspeak_source import ThingSpeakSource


def get_source() -> VitalSource:
    name = os.getenv("DATA_SOURCE", "fake").lower()
    if name == "thingspeak":
        return ThingSpeakSource()
    return FakeSource()
