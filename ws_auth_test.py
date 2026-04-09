"""WebSocket authentication probe for backend security verification.

Tests four scenarios against a WebSocket endpoint:
1) Valid token
2) Missing token
3) Invalid token
4) Expired token
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlencode

import websockets
from websockets.exceptions import InvalidStatusCode, InvalidStatus, ConnectionClosedError


# Configure tokens here before running.
VALID_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJBRE1JTiIsImV4cCI6MTc3NTU3Njk5M30._WGivGMnL6L_uZRHumTDm6suqM6pb3Jv8yj0v49vtys"
EXPIRED_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJBRE1JTiIsInVzZXJfaWQiOiIxIiwiZXhwIjoxNzc1NTcxNTkzfQ.fxUvLcAKZi6N06BdbAQen5KX_C1E1Q-9qPnJ1dQQA2s"
INVALID_TOKEN = "fake_token"

# Target endpoint.
WS_BASE_URL = "ws://localhost:8000/ws/vitals"


@dataclass
class CaseResult:
    name: str
    passed: bool
    output: str


def _build_url(token: Optional[str]) -> str:
    if token is None:
        return WS_BASE_URL
    return f"{WS_BASE_URL}?{urlencode({'token': token})}"


async def _probe_connection(name: str, token: Optional[str], expect_success: bool) -> CaseResult:
    url = _build_url(token)
    start = time.perf_counter()
    try:
        async with websockets.connect(url) as ws:
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Optional: try to read one message quickly if server sends immediate data.
            server_msg = None
            try:
                server_msg = await asyncio.wait_for(ws.recv(), timeout=1.5)
            except asyncio.TimeoutError:
                server_msg = "(no immediate message)"

            if expect_success:
                return CaseResult(
                    name=name,
                    passed=True,
                    output=f"[TEST] {name} -> ✅ PASS (connected in {elapsed_ms:.1f} ms, server: {server_msg})",
                )

            # If we connected when we expected rejection, this is unexpected.
            return CaseResult(
                name=name,
                passed=False,
                output=f"[TEST] {name} -> ⚠️ ERROR (unexpected connection in {elapsed_ms:.1f} ms)",
            )

    except InvalidStatusCode as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if expect_success:
            return CaseResult(
                name=name,
                passed=False,
                output=(
                    f"[TEST] {name} -> ⚠️ ERROR "
                    f"(rejected with status {exc.status_code} in {elapsed_ms:.1f} ms)"
                ),
            )
        return CaseResult(
            name=name,
            passed=True,
            output=f"[TEST] {name} -> ❌ REJECTED (expected, status {exc.status_code})",
        )

    except InvalidStatus as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = getattr(exc.response, "status_code", "unknown")
        if expect_success:
            return CaseResult(
                name=name,
                passed=False,
                output=(
                    f"[TEST] {name} -> ⚠️ ERROR "
                    f"(rejected with status {status} in {elapsed_ms:.1f} ms)"
                ),
            )
        return CaseResult(
            name=name,
            passed=True,
            output=f"[TEST] {name} -> ❌ REJECTED (expected, status {status})",
        )

    except ConnectionClosedError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if expect_success:
            return CaseResult(
                name=name,
                passed=False,
                output=(
                    f"[TEST] {name} -> ⚠️ ERROR "
                    f"(connection closed unexpectedly: code={exc.code}, reason={exc.reason}, {elapsed_ms:.1f} ms)"
                ),
            )
        return CaseResult(
            name=name,
            passed=True,
            output=(
                f"[TEST] {name} -> ❌ REJECTED "
                f"(expected close: code={exc.code}, reason={exc.reason})"
            ),
        )

    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - start) * 1000
        return CaseResult(
            name=name,
            passed=False,
            output=f"[TEST] {name} -> ⚠️ ERROR ({type(exc).__name__}: {exc}, {elapsed_ms:.1f} ms)",
        )


def _validate_config() -> Tuple[bool, list[str]]:
    errors = []
    if not VALID_TOKEN:
        errors.append("VALID_TOKEN is empty")
    if not EXPIRED_TOKEN:
        errors.append("EXPIRED_TOKEN is empty")
    return (len(errors) == 0, errors)


async def test_valid_token() -> CaseResult:
    if not VALID_TOKEN:
        return CaseResult(
            name="Valid Token",
            passed=False,
            output="[TEST] Valid Token -> ⚠️ ERROR (VALID_TOKEN is empty)",
        )
    return await _probe_connection("Valid Token", VALID_TOKEN, expect_success=True)


async def test_missing_token() -> CaseResult:
    return await _probe_connection("Missing Token", None, expect_success=False)


async def test_invalid_token() -> CaseResult:
    return await _probe_connection("Invalid Token", INVALID_TOKEN, expect_success=False)


async def test_expired_token() -> CaseResult:
    if not EXPIRED_TOKEN:
        return CaseResult(
            name="Expired Token",
            passed=False,
            output="[TEST] Expired Token -> ⚠️ ERROR (EXPIRED_TOKEN is empty)",
        )
    return await _probe_connection("Expired Token", EXPIRED_TOKEN, expect_success=False)


async def run_all() -> int:
    print("WebSocket Auth Probe")
    print(f"Endpoint: {WS_BASE_URL}")
    print()

    config_ok, config_errors = _validate_config()
    if not config_ok:
        print("Token configuration warnings:")
        for err in config_errors:
            print(f"- {err}")
        print()

    results = []
    results.append(await test_valid_token())
    results.append(await test_missing_token())
    results.append(await test_invalid_token())
    results.append(await test_expired_token())

    for item in results:
        print(item.output)

    passed = sum(1 for item in results if item.passed)
    total = len(results)
    failed = total - passed

    print()
    print("Summary:")
    print(f"Passed: {passed} / {total}")
    print(f"Failed: {failed} / {total}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_all()))
