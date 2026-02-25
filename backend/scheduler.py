"""
scheduler.py
Continuously generates fake vitals for every patient in the DB every N seconds.
Also runs alert escalation: PENDING alerts older than ESCALATION_MINUTES → ESCALATED.
Run independently:  python scheduler.py
"""

import time
import logging
from database import SessionLocal
import models
import fake_generator
import crud

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [SCHEDULER]  %(message)s",
    datefmt="%H:%M:%S",
)

INTERVAL_SECONDS = 10
ESCALATION_MINUTES = 2


def run():
    logging.info("Scheduler started.  Interval = %ds  |  Escalation = %d min", INTERVAL_SECONDS, ESCALATION_MINUTES)
    while True:
        db = SessionLocal()
        try:
            patients = db.query(models.Patient).all()
            if not patients:
                logging.warning("No patients found in DB.  Waiting…")

            # ── Generate fake vitals ─────────────────────────────────────
            for p in patients:
                vital, alerts = fake_generator.save_fake(db, p.patient_id)
                alert_str = ", ".join(alerts) if alerts else "—"
                logging.info(
                    "Patient %-3s | HR=%3d  SpO2=%3d%%  Temp=%.1f°F  BP=%-9s | Alerts: %s",
                    p.patient_id,
                    vital.heart_rate,
                    vital.spo2,
                    vital.temperature,
                    vital.blood_pressure,
                    alert_str,
                )

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
            db.close()

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
