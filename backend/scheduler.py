"""
scheduler.py
Continuously generates vitals for every patient in the DB every N seconds.
Also runs alert escalation: PENDING alerts older than ESCALATION_MINUTES → ESCALATED.
Run independently:  python scheduler.py
"""

import json
import time
import logging
from database import SessionLocal
import models
import fake_generator
import crud
import data_sources

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [SCHEDULER]  %(message)s",
    datefmt="%H:%M:%S",
)

INTERVAL_SECONDS = 10
ESCALATION_MINUTES = 2
FAKE_VITALS_ENABLED_SETTING_KEY = "fake_vitals_generation_enabled"

# ── Redis pub/sub publisher (optional) ────────────────────────────────────────
import os
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis as _redis
            _redis_client = _redis.from_url(_redis_url, socket_connect_timeout=2)
            _redis_client.ping()
            logging.info("✅ Redis connected for pub/sub publishing")
        except Exception as e:
            logging.warning("Redis unavailable — WebSocket live push disabled: %s", e)
            _redis_client = None
    return _redis_client


def _publish_vitals(patients_vitals: list):
    """Publish latest vitals snapshot to Redis channel for WebSocket clients."""
    try:
        r = _get_redis()
        if r:
            r.publish("iot:vitals", json.dumps(patients_vitals))
    except Exception as e:
        global _redis_client
        _redis_client = None  # force reconnect next time
        logging.debug("Redis publish failed (will retry): %s", e)


def run():
    logging.info("Scheduler started.  Interval = %ds  |  Escalation = %d min", INTERVAL_SECONDS, ESCALATION_MINUTES)
    last_source = None
    last_enabled = None
    while True:
        db = SessionLocal()
        try:
            setting = db.query(models.AppSetting).filter(models.AppSetting.setting_key == FAKE_VITALS_ENABLED_SETTING_KEY).first()
            enabled = True if not setting else str(setting.setting_value or "").strip().lower() in {"1", "true", "yes", "on"}
            if enabled != last_enabled:
                logging.info("Fake vitals generation is now %s", "ENABLED" if enabled else "DISABLED")
                last_enabled = enabled
            if not enabled:
                # Avoid a tight loop when generation is disabled.
                time.sleep(INTERVAL_SECONDS)
                continue

            current_source = data_sources.get_data_source_config()["source"]
            if current_source != last_source:
                logging.info("Vitals source switched to: %s", current_source)
                last_source = current_source

            patients = db.query(models.Patient).all()
            if not patients:
                logging.warning("No patients found in DB.  Waiting…")

            # ── Generate vitals from active data source ──────────────────
            active_source = data_sources.get_source()
            vitals_snapshot = []
            for p in patients:
                # One-time backfill if DB is empty for this source
                fake_generator.backfill_history(db, p.patient_id, source=active_source)
                
                vital, alerts = fake_generator.save_fake(db, p.patient_id, source=active_source)
                alert_str = ", ".join(alerts) if alerts else "—"
                logging.info(
                    "Patient %-3s | HR=%3d  SpO2=%3d%%  Temp=%.1f°F | Alerts: %s",
                    p.patient_id,
                    vital.heart_rate,
                    vital.spo2,
                    vital.temperature,
                    alert_str,
                )
                vitals_snapshot.append({
                    "patient_id": p.patient_id,
                    "name": p.name,
                    "room": p.room_number,
                    "heart_rate": vital.heart_rate,
                    "spo2": vital.spo2,
                    "temperature": vital.temperature,
                    "timestamp": str(vital.timestamp),
                    "alerts": alerts,
                })

            # ── Publish to Redis for WebSocket live push ─────────────────
            if vitals_snapshot:
                _publish_vitals(vitals_snapshot)

            # ── Escalation check ─────────────────────────────────────────
            escalated = crud.escalate_stale_alerts(db, threshold_minutes=ESCALATION_MINUTES)
            if escalated:
                logging.warning(
                    "⚠️  ESCALATED %d alert(s): %s",
                    len(escalated),
                    ", ".join(f"#{a.alert_id} (P{a.patient_id} {a.alert_type})" for a in escalated),
                )

        except Exception as exc:
            logging.error("Scheduler error: %s", exc)
        finally:
            try:
                db.close()
            except Exception as exc:
                logging.warning("DB session close failed (continuing): %s", exc)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
