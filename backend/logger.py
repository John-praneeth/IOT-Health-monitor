"""
logger.py - Security-focused structured logging helpers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

_logger = logging.getLogger("security")

SENSITIVE_KEYS = {"authorization", "password", "token", "refresh_token", "access_token"}


def _mask_value(value: Any) -> str:
    if value is None:
        return ""
    return "***"


def sanitize_headers(headers: dict[str, Any] | None) -> dict[str, Any]:
    if not headers:
        return {}
    result: dict[str, Any] = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_KEYS:
            result[k] = _mask_value(v)
        else:
            result[k] = v
    return result


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    result: dict[str, Any] = {}
    for k, v in payload.items():
        if k.lower() in SENSITIVE_KEYS:
            result[k] = _mask_value(v)
        else:
            result[k] = v
    return result


def request_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def log_security_event(
    event: str,
    *,
    request: Request | None = None,
    user: str | None = None,
    ip: str | None = None,
    level: int = logging.WARNING,
    **fields: Any,
) -> None:
    payload = {
        "event": event,
        "user": user or "anonymous",
        "ip": ip or request_ip(request),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(sanitize_payload(fields))
    _logger.log(level, "SECURITY_EVENT", extra={"action": "security_event", "extra_data": payload})
