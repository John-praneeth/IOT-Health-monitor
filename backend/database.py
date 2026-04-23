from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import sys
import logging
import time
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

db_connect_args: dict[str, object] = {}
if DATABASE_URL.startswith("postgresql"):
    connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))
    statement_timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "15000"))
    lock_timeout_ms = int(os.getenv("DB_LOCK_TIMEOUT_MS", "3000"))
    idle_tx_timeout_ms = int(os.getenv("DB_IDLE_TX_TIMEOUT_MS", "30000"))
    db_connect_args = {
        "connect_timeout": connect_timeout,
        "options": (
            f"-c statement_timeout={statement_timeout_ms} "
            f"-c lock_timeout={lock_timeout_ms} "
            f"-c idle_in_transaction_session_timeout={idle_tx_timeout_ms}"
        ),
    }

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,          # verify connections before use
    pool_size=5,
    max_overflow=10,
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "10")),
    connect_args=db_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Redis Safe Mode ──────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_REQUIRED = os.getenv("REDIS_REQUIRED", "false").lower() in ("true", "1", "yes")
REDIS_CONNECT_TIMEOUT = float(os.getenv("REDIS_CONNECT_TIMEOUT", "1.0"))
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "1.0"))

_redis_available = False
_redis_client = None
_redis_last_check_at = 0.0
_redis_recheck_interval = float(os.getenv("REDIS_RECHECK_INTERVAL_SECONDS", "5.0"))


def check_redis() -> bool:
    """Check Redis connectivity. Returns True if reachable."""
    global _redis_available, _redis_client
    try:
        import redis as _redis
        r = _redis.from_url(
            REDIS_URL,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            retry_on_timeout=False,
            health_check_interval=30,
        )
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
    global _redis_client, _redis_available, _redis_last_check_at
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None
            _redis_available = False
            _redis_last_check_at = time.time()
            return None
    now = time.time()
    if now - _redis_last_check_at < _redis_recheck_interval:
        return None
    _redis_last_check_at = now
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

