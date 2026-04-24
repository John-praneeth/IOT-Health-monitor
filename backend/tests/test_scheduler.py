"""
tests/test_scheduler.py  -  Regression tests for scheduler loop behavior.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scheduler


class _StopLoop(BaseException):
    """Sentinel exception used to exit the infinite scheduler loop in tests."""


class _FakeSetting:
    def __init__(self, setting_value: str):
        self.setting_value = setting_value


class _FakeQuery:
    def __init__(self, setting_value: str):
        self._setting = _FakeSetting(setting_value)

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._setting


class _FakeDB:
    def __init__(self, setting_value: str):
        self._setting_value = setting_value

    def query(self, _model):
        return _FakeQuery(self._setting_value)

    def close(self):
        return None


def test_scheduler_sleeps_when_fake_vitals_disabled(monkeypatch):
    """When generation is disabled, the loop must still sleep to avoid busy-spin."""
    calls = {"session": 0, "sleep": 0}

    def fake_session_local():
        calls["session"] += 1
        if calls["session"] > 1:
            raise _StopLoop()
        return _FakeDB("false")

    def fake_sleep(seconds):
        assert seconds == scheduler.INTERVAL_SECONDS
        calls["sleep"] += 1

    monkeypatch.setattr(scheduler, "SessionLocal", fake_session_local)
    monkeypatch.setattr(scheduler.time, "sleep", fake_sleep)

    with pytest.raises(_StopLoop):
        scheduler.run()

    assert calls["sleep"] == 1
