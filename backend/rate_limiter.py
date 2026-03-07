"""
rate_limiter.py  –  Rate limiting for FastAPI using slowapi.
• 5 login attempts/minute per IP
• 100 API requests/minute per user

v5.1: Fail-open when Redis is unavailable.
"""

import os
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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
    """Attach rate limiter to the FastAPI app. Fails open on errors."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
