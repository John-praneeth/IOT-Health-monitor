"""
rate_limiter.py  –  Rate limiting for FastAPI using slowapi.
• 5 login attempts/minute per IP
• 100 API requests/minute per user

v5.1: Fail-safe fallback to in-memory limiter when Redis is unavailable.
"""

import os
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from logger import log_security_event

logger = logging.getLogger(__name__)

# ── Limiter instance ──────────────────────────────────────────────────────────
# Uses Redis if REDIS_URL is set and reachable, otherwise in-memory
REDIS_URL = os.getenv("REDIS_URL", "")


def _get_storage_uri() -> str:
    """Determine storage backend: Redis if available, else in-memory."""
    if REDIS_URL:
        try:
            import redis as _redis
            r = _redis.from_url(REDIS_URL, socket_connect_timeout=2)
            r.ping()
            logger.info("Rate limiter using Redis: %s", REDIS_URL)
            return REDIS_URL
        except Exception as e:
            logger.warning("Rate limiter Redis unavailable (%s) — falling back to in-memory", e)
    return "memory://"


storage_uri = _get_storage_uri()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri=storage_uri,
    strategy="fixed-window",
)

# Specific rate limits
LOGIN_LIMIT = "5/minute"


def setup_rate_limiter(app):
    """Attach rate limiter to the FastAPI app with fail-safe limits."""
    def _logged_rate_limit_handler(request, exc):
        log_security_event(
            "RATE_LIMIT_HIT",
            request=request,
            ip=get_remote_address(request),
            method=request.method,
            path=request.url.path,
        )
        return _rate_limit_exceeded_handler(request, exc)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _logged_rate_limit_handler)
