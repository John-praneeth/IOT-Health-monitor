"""
whatsapp_notifier.py
Sends WhatsApp notifications for health alerts using GREEN-API (FREE).

How GREEN-API works:
─────────────────────
1. Sign up for a FREE account at https://console.green-api.com
2. Create an instance and scan the QR code with your WhatsApp.
3. Copy your "idInstance" and "apiTokenInstance" from the dashboard.
4. Set them in .env:
       GREEN_API_ID=your_id_instance
       GREEN_API_TOKEN=your_api_token_instance
5. Add recipient phone numbers via the /whatsapp/recipients/add endpoint
   or set them in .env as:
       WHATSAPP_RECIPIENTS=919876543210,911234567890

Free Developer plan: $0/month, 3 chats, unlimited messages!
Docs: https://green-api.com/en/docs/api/sending/SendMessage/
"""

import os
import logging
import threading
from datetime import datetime, timedelta, timezone
import httpx

logger = logging.getLogger(__name__)

# Prevent outbound request URL logs from exposing provider credentials in path.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── Feature toggle ────────────────────────────────────────────────────────────
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "true").lower() in ("true", "1", "yes")

# ── Runtime alert toggle (for prototype use – start/stop WhatsApp alerts) ─────
# Uses a file-based flag so the toggle works across processes (backend + scheduler)
_PAUSE_FLAG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".whatsapp_paused")


def pause_alerts():
    """Pause all WhatsApp alert sending (persisted toggle)."""
    with open(_PAUSE_FLAG_FILE, "w") as f:
        f.write("paused")
    logger.info("⏸️  WhatsApp alerts PAUSED")


def resume_alerts():
    """Resume WhatsApp alert sending (persisted toggle)."""
    try:
        os.remove(_PAUSE_FLAG_FILE)
    except FileNotFoundError:
        pass
    logger.info("▶️  WhatsApp alerts RESUMED")


def is_alerts_paused() -> bool:
    return os.path.exists(_PAUSE_FLAG_FILE)


# ── Pending Response Tracker ─────────────────────────────────────────────────
# Tracks alerts waiting for doctor WhatsApp acknowledgement
# { alert_id: { doctor_phone, patient_name, alert_type, patient_id,
#               room_number, vital_data, sent_at, hospital_id, escalated } }
_pending_responses: dict = {}
_pending_lock = threading.Lock()

ESCALATION_TIMEOUT_MINUTES = 5  # escalate if no reply within this time


def track_pending_response(alert_id: int, doctor_phone: str, patient_name: str,
                           alert_type: str, patient_id: int, room_number: str,
                           vital_data: dict, hospital_id: int):
    """Track that we're waiting for a doctor to acknowledge this alert via WhatsApp."""
    with _pending_lock:
        if alert_id not in _pending_responses:
            _pending_responses[alert_id] = {
                "doctor_phone": doctor_phone.strip().lstrip("+"),
                "patient_name": patient_name,
                "alert_type": alert_type,
                "patient_id": patient_id,
                "room_number": room_number,
                "vital_data": vital_data,
                "sent_at": datetime.now(timezone.utc),
                "hospital_id": hospital_id,
                "escalated": False,
            }
    logger.info("Tracking pending response for alert #%s from doctor phone %s", alert_id, doctor_phone)


def acknowledge_by_phone(doctor_phone: str) -> list:
    """
    Called when a doctor replies 'ACK' or '1' via WhatsApp.
    Returns list of alert_ids that were acknowledged.
    """
    clean_phone = doctor_phone.strip().lstrip("+")
    acknowledged = []
    with _pending_lock:
        for alert_id in list(_pending_responses.keys()):
            if _pending_responses[alert_id]["doctor_phone"] == clean_phone:
                acknowledged.append(alert_id)
                del _pending_responses[alert_id]
                logger.info("Alert #%s acknowledged via WhatsApp by %s", alert_id, clean_phone)
    return acknowledged


def acknowledge_alert_by_id(alert_id: int, doctor_phone: str = None) -> bool:
    """
    v5.2 FIX 5: Acknowledge a specific alert by its ID.
    Returns True if the alert was found and removed from pending, False otherwise.
    """
    with _pending_lock:
        if alert_id in _pending_responses:
            if doctor_phone:
                clean_phone = doctor_phone.strip().lstrip("+")
                if _pending_responses[alert_id]["doctor_phone"] != clean_phone:
                    logger.warning(
                        "Alert #%s ACK by %s but assigned to %s — allowing anyway",
                        alert_id, clean_phone, _pending_responses[alert_id]["doctor_phone"],
                    )
            del _pending_responses[alert_id]
            logger.info("Alert #%s acknowledged via WhatsApp (by_id)", alert_id)
            return True
    logger.debug("Alert #%s not found in pending responses", alert_id)
    return False


def get_unresponded_alerts() -> list:
    """Return alerts that have not been acknowledged within ESCALATION_TIMEOUT_MINUTES."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ESCALATION_TIMEOUT_MINUTES)
    unresponded = []
    with _pending_lock:
        for alert_id, data in _pending_responses.items():
            if data["sent_at"] < cutoff and not data["escalated"]:
                unresponded.append({"alert_id": alert_id, **data})
    return unresponded


def mark_escalated(alert_id: int):
    """Mark an alert as escalated so we don't escalate it again."""
    with _pending_lock:
        if alert_id in _pending_responses:
            _pending_responses[alert_id]["escalated"] = True


def get_pending_count() -> int:
    with _pending_lock:
        return len(_pending_responses)


# ── GREEN-API credentials (global for all recipients) ─────────────────────────
GREEN_API_URL = os.getenv("GREEN_API_URL", "https://api.green-api.com")
GREEN_API_ID = os.getenv("GREEN_API_ID", "")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN", "")

# ── Recipients ────────────────────────────────────────────────────────────────
# MVP / GREEN-API Free Plan:
# WhatsApp numbers are pulled from DB (doctor/nurse registration) — NOT hardcoded.
# The WHATSAPP_RECIPIENTS env var is kept only as an optional fallback.
_env_recipients_raw = os.getenv("WHATSAPP_RECIPIENTS", "")


def _parse_recipients(raw: str) -> list[str]:
    """Parse comma-separated phone numbers into a list."""
    result = []
    for entry in raw.split(","):
        phone = entry.strip().lstrip("+")
        if phone:
            result.append(phone)
    return result


DEFAULT_RECIPIENTS: list[str] = _parse_recipients(_env_recipients_raw)

# In-memory store of recipients added via API
_configured_recipients: list[str] = []


def _normalize_phone(phone: str) -> str | None:
    """Normalize a phone number: strip +, validate it looks usable."""
    if not phone:
        return None
    phone = phone.strip().lstrip("+")
    if len(phone) >= 10:
        return phone
    return None


def get_patient_recipients(patient_id: int) -> list[str]:
    """
    Fetch WhatsApp recipients from the DB for a given patient.
    Returns only the phone number of the patient's assigned doctor.
    """
    recipients = []
    try:
        from database import SessionLocal
        import models as m
        db = SessionLocal()
        try:
            patient = db.query(m.Patient).filter(
                m.Patient.patient_id == patient_id
            ).first()
            if not patient:
                logger.warning("get_patient_recipients: patient %s not found", patient_id)
                return recipients

            # Assigned doctor's phone
            if patient.assigned_doctor:
                doctor = db.query(m.Doctor).filter(
                    m.Doctor.doctor_id == patient.assigned_doctor,
                    m.Doctor.is_active,
                ).first()
                if doctor:
                    phone = _normalize_phone(doctor.phone)
                    if phone:
                        recipients.append(phone)
                        logger.debug("DB recipient: doctor %s (%s)", doctor.name, phone)

        finally:
            db.close()
    except Exception as exc:
        logger.error("get_patient_recipients failed: %s", exc)
    return recipients


def _phone_to_chat_id(phone: str) -> str:
    """Convert a phone number to GREEN-API chatId format: 919876543210@c.us"""
    phone = phone.strip().lstrip("+")
    return f"{phone}@c.us"


# ── Recipient management ─────────────────────────────────────────────────────

def get_all_recipients() -> list[str]:
    """Return all configured recipient phone numbers (env + API-configured).
    NOTE: For MVP / GREEN-API free plan, prefer get_patient_recipients(patient_id)
    which pulls numbers from DB. This function is kept as a fallback for
    test messages and config display.
    """
    seen = set()
    merged = []
    for phone in DEFAULT_RECIPIENTS + _configured_recipients:
        if phone not in seen:
            seen.add(phone)
            merged.append(phone)
    return merged


def add_recipient(phone: str) -> list[str]:
    """Add a WhatsApp recipient phone number."""
    phone = phone.strip().lstrip("+")
    if not phone:
        return get_all_recipients()
    # Avoid duplicates
    if phone not in _configured_recipients and phone not in DEFAULT_RECIPIENTS:
        _configured_recipients.append(phone)
        logger.info("Added WhatsApp recipient: %s", phone)
    return get_all_recipients()


def remove_recipient(phone: str) -> list[str]:
    """Remove a WhatsApp recipient by phone number."""
    global _configured_recipients
    phone = phone.strip().lstrip("+")
    _configured_recipients = [r for r in _configured_recipients if r != phone]
    logger.info("Removed WhatsApp recipient: %s", phone)
    return get_all_recipients()


# ── Alert message formatting ─────────────────────────────────────────────────

ALERT_DESCRIPTIONS = {
    "HIGH_HEART_RATE": "🫀 High Heart Rate (>110 bpm)",
    "LOW_HEART_RATE":  "🫀 Low Heart Rate (<50 bpm)",
    "LOW_SPO2":        "🫁 Low SpO2 (<90%)",
    "HIGH_TEMP":       "🌡️ High Temperature (>101°F)",
    "LOW_TEMP":        "🌡️ Low Temperature (<96°F)",
}

SEVERITY = {
    "HIGH_HEART_RATE": "🔴 CRITICAL",
    "LOW_HEART_RATE":  "🔴 CRITICAL",
    "LOW_SPO2":        "🔴 CRITICAL",
    "HIGH_TEMP":       "🟠 WARNING",
    "LOW_TEMP":        "🟠 WARNING",
}


def _format_alert_message(
    alert_type: str,
    patient_name: str,
    patient_id: int,
    room_number: str,
    vital_data: dict,
    alert_id: int = None,
) -> str:
    severity = SEVERITY.get(alert_type, "⚠️ ALERT")
    description = ALERT_DESCRIPTIONS.get(alert_type, alert_type)

    # v5.2 FIX 5: Include specific ACK instruction with alert_id
    ack_line = f"⚡ Reply *ACK {alert_id}* to acknowledge this alert." if alert_id else "⚡ Reply *ACK* to acknowledge."

    return (
        f"🏥 *IoT Health Monitor Alert*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"{severity}\n"
        f"*Alert:* {description}\n"
        f"*Alert ID:* #{alert_id if alert_id else 'N/A'}\n"
        f"\n"
        f"👤 *Patient:* {patient_name} (ID: {patient_id})\n"
        f"🚪 *Room:* {room_number}\n"
        f"\n"
        f"📊 *Current Vitals:*\n"
        f"  • Heart Rate: {vital_data.get('heart_rate', 'N/A')} bpm\n"
        f"  • SpO2: {vital_data.get('spo2', 'N/A')}%\n"
        f"  • Temperature: {vital_data.get('temperature', 'N/A')}°F\n"
        f"\n"
        f"⏰ *Immediate attention required!*\n"
        f"\n"
        f"{ack_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


def _format_escalation_message(
    alert_type: str,
    patient_name: str,
    patient_id: int,
    room_number: str,
) -> str:
    description = ALERT_DESCRIPTIONS.get(alert_type, alert_type)

    return (
        f"🏥 *IoT Health Monitor – ESCALATION*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"🔺 *ALERT ESCALATED*\n"
        f"*Alert:* {description}\n"
        f"\n"
        f"👤 *Patient:* {patient_name} (ID: {patient_id})\n"
        f"🚪 *Room:* {room_number}\n"
        f"\n"
        f"⚠️ Original assigned doctor did not respond.\n"
        f"🚨 *This alert has been escalated!*\n"
        f"\n"
        f"Please check the patient immediately.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# ── Send via GREEN-API ───────────────────────────────────────────────────────

def send_whatsapp_message(phone: str, body: str, retries: int = 3,
                          alert_id: int = None, event_type: str = "NEW",
                          buttons: list = None) -> bool:
    """Send a WhatsApp message via GREEN-API (FREE) with retry + exponential backoff.
    Supports interactive buttons via the sendButtons endpoint.
    """
    import time

    if not WHATSAPP_ENABLED:
        logger.debug("WhatsApp notifications are disabled.")
        return False

    if not GREEN_API_ID or not GREEN_API_TOKEN:
        logger.error("❌ GREEN-API credentials not configured (GREEN_API_ID / GREEN_API_TOKEN)")
        return False

    # Build idempotency key
    idem_key = f"{alert_id}:{event_type}:{phone}" if alert_id else None

    # Idempotency: check if already successfully sent
    if idem_key:
        try:
            from database import SessionLocal
            import models as m
            db = SessionLocal()
            try:
                existing = db.query(m.WhatsAppLog).filter(
                    m.WhatsAppLog.idempotency_key == idem_key,
                    m.WhatsAppLog.status == "SENT",
                ).first()
                if existing:
                    logger.info("WhatsApp idempotency hit: %s already sent, skipping", idem_key)
                    return True
            finally:
                db.close()
        except Exception:
            pass

    # Determine endpoint and payload based on buttons
    chat_id = _phone_to_chat_id(phone)
    if buttons:
        # v5.2: Use 2026 GREEN-API Interactive Reply specification
        method = "sendInteractiveButtonsReply"
        payload = {
            "chatId": chat_id,
            "body": body,
            "footer": "Medical Monitoring System",
            "buttons": buttons
        }
    else:
        method = "sendMessage"
        payload = {
            "chatId": chat_id,
            "message": body
        }

    url = f"{GREEN_API_URL}/waInstance{GREEN_API_ID}/{method}/{GREEN_API_TOKEN}"

    for attempt in range(1, retries + 1):
        try:
            response = httpx.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                data = response.json()
                logger.info("✅ WhatsApp %s sent to %s (id: %s, attempt: %d)",
                            method, phone, data.get("idMessage", ""), attempt)

                # Track metrics
                try:
                    from metrics import WHATSAPP_SEND_COUNTER
                    WHATSAPP_SEND_COUNTER.labels(status="success").inc()
                except ImportError:
                    pass

                # Log to DB with idempotency key
                _log_whatsapp_to_db(phone, "alert", "SENT",
                                    alert_id=alert_id, idempotency_key=idem_key)
                return True
            else:
                logger.error(
                    "❌ GREEN-API error for %s: HTTP %d – %s (attempt %d/%d)",
                    phone, response.status_code, response.text[:200], attempt, retries,
                )
                
                # v5.2 Resiliency: If buttons are blocked by provider, fallback to plain text instantly
                if buttons and response.status_code in (400, 403, 404):
                    logger.warning("Interactive buttons rejected by WhatsApp provider. Falling back to standard text message.")
                    buttons = None
                    method = "sendMessage"
                    payload = {"chatId": chat_id, "message": body}
                    url = f"{GREEN_API_URL}/waInstance{GREEN_API_ID}/{method}/{GREEN_API_TOKEN}"
                    continue # Retry immediately with plain text

        except httpx.TimeoutException:
            logger.error("⏱️ Timeout sending WhatsApp to %s (attempt %d/%d)", phone, attempt, retries)
        except Exception as e:
            logger.error("❌ Unexpected error sending WhatsApp to %s: %s (attempt %d/%d)",
                         phone, e, attempt, retries)

        # Exponential backoff: 2s, 4s, 8s
        if attempt < retries:
            backoff = 2 ** attempt
            logger.info("Retrying in %ds...", backoff)
            time.sleep(backoff)

    # All retries failed
    try:
        from metrics import WHATSAPP_SEND_COUNTER
        WHATSAPP_SEND_COUNTER.labels(status="failure").inc()
    except ImportError:
        pass

    _log_whatsapp_to_db(phone, "alert", "FAILED", error="All retries exhausted",
                        alert_id=alert_id, idempotency_key=idem_key)
    return False


def _log_whatsapp_to_db(recipient: str, msg_type: str, status: str,
                        error: str = None, alert_id: int = None,
                        idempotency_key: str = None):
    """Best-effort log to DB with idempotency check."""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            import models as m
            # Idempotency: if this key already succeeded, skip
            if idempotency_key:
                existing = db.query(m.WhatsAppLog).filter(
                    m.WhatsAppLog.idempotency_key == idempotency_key,
                    m.WhatsAppLog.status == "SENT",
                ).first()
                if existing:
                    return
            log = m.WhatsAppLog(
                alert_id=alert_id,
                recipient=recipient,
                message_type=msg_type,
                status=status,
                attempts=1,
                error=error,
                idempotency_key=idempotency_key,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # Best-effort logging


def send_alert_notification(
    alert_type: str,
    patient_name: str,
    patient_id: int,
    room_number: str,
    vital_data: dict,
    recipients: list[str] = None,
    alert_id: int = None,
    hospital_id: int = None,
) -> dict:
    """Send a WhatsApp alert to the assigned doctor only. Returns delivery status."""
    if not WHATSAPP_ENABLED:
        return {"enabled": False, "sent": 0, "failed": 0}

    if is_alerts_paused():
        logger.debug("WhatsApp alerts are paused. Skipping alert for patient %s.", patient_id)
        return {"enabled": True, "paused": True, "sent": 0, "failed": 0}

    # Strict recipient policy: assigned doctor only.
    target = get_patient_recipients(patient_id)

    if not target:
        logger.warning("No assigned doctor recipient for patient %s. Skipping alert.", patient_id)
        return {"enabled": True, "sent": 0, "failed": 0, "reason": "no_assigned_doctor_recipient"}

    # v5.2: alert message now includes ACK instruction with alert_id
    message = _format_alert_message(
        alert_type=alert_type,
        patient_name=patient_name,
        patient_id=patient_id,
        room_number=room_number,
        vital_data=vital_data,
        alert_id=alert_id,
    )

    # v5.2: Add interactive Acknowledge button
    buttons = []
    if alert_id:
        buttons.append({
            "buttonId": f"ACK {alert_id}",
            "buttonText": "✅ Acknowledge"
        })

    results = {"enabled": True, "sent": 0, "failed": 0, "details": []}
    for phone in target:
        ok = send_whatsapp_message(phone, message, alert_id=alert_id, event_type="NEW", buttons=buttons)
        results["sent" if ok else "failed"] += 1
        results["details"].append({"to": phone, "success": ok})

    # Track the first recipient (assigned doctor) for acknowledgement timeout
    if results["sent"] > 0 and alert_id and hospital_id and target:
        track_pending_response(
            alert_id=alert_id,
            doctor_phone=target[0],
            patient_name=patient_name,
            alert_type=alert_type,
            patient_id=patient_id,
            room_number=room_number,
            vital_data=vital_data,
            hospital_id=hospital_id,
        )

    logger.info("WhatsApp alert: sent=%d, failed=%d", results["sent"], results["failed"])
    return results


def send_escalation_notification(
    alert_type: str,
    patient_name: str,
    patient_id: int,
    room_number: str,
    recipients: list[str] = None,
    alert_id: int = None,
) -> dict:
    """Send a WhatsApp escalation alert. Idempotent with ESCALATION key.
    Uses explicit recipients when provided; otherwise falls back to assigned doctor.
    """
    if not WHATSAPP_ENABLED:
        return {"enabled": False, "sent": 0, "failed": 0}

    if is_alerts_paused():
        logger.debug("WhatsApp alerts are paused. Skipping escalation for patient %s.", patient_id)
        return {"enabled": True, "paused": True, "sent": 0, "failed": 0}

    if recipients:
        # Explicit escalation recipient list from caller (e.g., same-spec doctors).
        target = []
        seen = set()
        for phone in recipients:
            normalized = _normalize_phone(phone)
            if normalized and normalized not in seen:
                seen.add(normalized)
                target.append(normalized)
    else:
        # Fallback policy: patient's assigned doctor.
        target = get_patient_recipients(patient_id)

    if not target:
        logger.warning("No escalation recipient configured. Skipping escalation.")
        return {"enabled": True, "sent": 0, "failed": 0, "reason": "no_escalation_recipient"}

    message = _format_escalation_message(
        alert_type=alert_type,
        patient_name=patient_name,
        patient_id=patient_id,
        room_number=room_number,
    )

    # v5.2: Add interactive Acknowledge button
    buttons = []
    if alert_id:
        buttons.append({
            "buttonId": f"ACK {alert_id}",
            "buttonText": "🚨 Resolve"
        })

    results = {"enabled": True, "sent": 0, "failed": 0, "details": []}
    for phone in target:
        ok = send_whatsapp_message(phone, message, alert_id=alert_id, event_type="ESCALATION", buttons=buttons)
        results["sent" if ok else "failed"] += 1
        results["details"].append({"to": phone, "success": ok})

    logger.info("WhatsApp escalation: sent=%d, failed=%d", results["sent"], results["failed"])
    return results


def send_test_message(phone: str = None) -> dict:
    """Send a test WhatsApp message to verify the setup works."""
    if not GREEN_API_ID or not GREEN_API_TOKEN:
        return {"success": False, "error": "GREEN-API credentials not configured. Set GREEN_API_ID and GREEN_API_TOKEN in .env"}

    if phone:
        target_phone = phone.strip().lstrip("+")
    else:
        all_r = get_all_recipients()
        if not all_r:
            return {"success": False, "error": "No recipients configured. Add a phone number first."}
        target_phone = all_r[0]

    body = (
        "✅ *IoT Health Monitor – Test Message*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        "Your WhatsApp alert notifications are working correctly!\n"
        "\n"
        "You will receive alerts when:\n"
        "• Heart rate is abnormal (>110 or <50 bpm)\n"
        "• SpO2 drops below 90%\n"
        "• Temperature is abnormal (>101°F or <96°F)\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    # v5.2: Add test button
    buttons = [
        {
            "buttonId": "TEST_ACK",
            "buttonText": "🧪 Verify Handshake"
        }
    ]

    ok = send_whatsapp_message(target_phone, body, buttons=buttons)
    return {"success": ok, "to": target_phone}


def get_config() -> dict:
    """Return current WhatsApp notification config.
    
    NOTE: `recipients` and `recipient_count` are kept for backward compatibility
    with the WhatsAppConfigOut schema and frontend. They show the env/API-configured
    fallback numbers. Actual alert recipients come from DB (patient's assigned
    doctor phone) at send time — see get_patient_recipients().
    """
    env_recipients = get_all_recipients()
    return {
        "enabled": WHATSAPP_ENABLED,
        "alerts_paused": is_alerts_paused(),
        "provider": "green-api",
        "credentials_set": bool(GREEN_API_ID and GREEN_API_TOKEN),
        "recipients": env_recipients,
        "recipient_count": len(env_recipients),
        "pending_acknowledgements": get_pending_count(),
        "recipient_source": "database (assigned doctor registration)",
        "note": "Primary recipients are pulled from the patient's assigned doctor phone in DB. The list above is for test/config use only.",
    }
