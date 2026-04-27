#!/bin/sh
set -eu

echo "Starting backend container..."

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is required."
  exit 1
fi

if [ -z "${SECRET_KEY:-}" ]; then
  echo "ERROR: SECRET_KEY is required."
  exit 1
fi

secret_lower=$(printf '%s' "$SECRET_KEY" | tr '[:upper:]' '[:lower:]')
case "$secret_lower" in
  *change-me*|*super-secret-key-change-in-production*|*test-secret-key*)
    echo "ERROR: SECRET_KEY is insecure. Set a long random value (at least 32 chars)."
    exit 1
    ;;
esac

echo "Applying critical schema updates..."
python - <<'PY'
from database import SessionLocal, engine
from sqlalchemy import text
db = SessionLocal()
try:
    if engine.name == "postgresql":
        db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS details VARCHAR(1000);"))
        db.execute(text("ALTER TABLE alert_escalations ALTER COLUMN escalated_to_doctor DROP NOT NULL;"))
        db.commit()
        print("Schema updates verified.")
except Exception as e:
    db.rollback()
    print(f"Migration note (safe to ignore if applied): {e}")
finally:
    db.close()
PY

SEED_DB_ON_STARTUP="${SEED_DB_ON_STARTUP:-true}"
if [ "$SEED_DB_ON_STARTUP" = "true" ]; then
  if [ -n "${ADMIN_PASSWORD:-}" ]; then
    echo "Running seed_db.py (ADMIN_PASSWORD provided)..."
    python seed_db.py
  else
    echo "ADMIN_PASSWORD is not set. Checking whether an ADMIN user already exists..."
    if python - <<'PY'
from database import SessionLocal
import models

db = SessionLocal()
try:
    has_admin = db.query(models.User).filter(models.User.role == "ADMIN").first() is not None
finally:
    db.close()

raise SystemExit(0 if has_admin else 1)
PY
    then
      echo "Admin user already exists. Skipping seed step."
    else
      echo "ERROR: ADMIN_PASSWORD is required for first deployment (no ADMIN user found)."
      echo "Set ADMIN_PASSWORD and redeploy, or set SEED_DB_ON_STARTUP=false if seeding is managed externally."
      exit 1
    fi
  fi
else
  echo "Skipping seed step because SEED_DB_ON_STARTUP=false."
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"