from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the same directory as this file (backend/)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Create a backend/.env file with: DATABASE_URL=postgresql://user:pass@localhost:5432/patient_monitor"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,          # verify connections before use
    pool_size=5,
    max_overflow=10,
    connect_args={"connect_timeout": 5},  # fail fast if DB unreachable
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Redis Safe Mode ──────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_REQUIRED = os.getenv("REDIS_REQUIRED", "false").lower() in ("true", "1", "yes")

_redis_available = False
_redis_client = None


def check_redis() -> bool:
    """Check Redis connectivity. Returns True if reachable."""
    global _redis_available, _redis_client
    try:
        import redis as _redis
        r = _redis.from_url(REDIS_URL, socket_connect_timeout=2)
        r.ping()
        _redis_available = True
        _redis_client = r
        logger.info("✅ Redis connected at %s", REDIS_URL)
        return True
    except ImportError:
        logger.warning("⚠️ redis package not installed — running without Redis")
        _redis_available = False
        return False
    except Exception as e:
        logger.warning("⚠️ Redis unavailable (%s) — running in degraded mode", e)
        _redis_available = False
        return False


def get_redis_client():
    """Get Redis client if available, otherwise None."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None
    check_redis()
    return _redis_client


def is_redis_available() -> bool:
    """Check if Redis is currently available."""
    global _redis_available
    return _redis_available


def require_redis_on_startup():
    """Call during app startup. If REDIS_REQUIRED=true and Redis is down, refuse to start."""
    available = check_redis()
    if REDIS_REQUIRED and not available:
        logger.critical("❌ REDIS_REQUIRED=true but Redis is unavailable. Refusing to start.")
        sys.exit(1)
    elif not available:
        logger.warning("⚠️ Redis not available. Rate limiter and pub/sub WebSocket will be degraded.")

