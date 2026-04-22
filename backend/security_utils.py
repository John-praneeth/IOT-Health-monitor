"""
security_utils.py - Shared runtime abuse-protection helpers.
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
import os

from database import get_redis_client
import models

FAILED_LOGIN_THRESHOLD = 5
FAILED_LOGIN_BLOCK_SECONDS = 300
MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", "3"))
ALLOW_MOBILE_IP_VARIATION = os.getenv("ALLOW_MOBILE_IP_VARIATION", "false").lower() in ("1", "true", "yes")
SUSPICIOUS_IP_WINDOW_SECONDS = int(os.getenv("SUSPICIOUS_IP_WINDOW_SECONDS", "300"))
SUSPICIOUS_REFRESH_WINDOW_SECONDS = int(os.getenv("SUSPICIOUS_REFRESH_WINDOW_SECONDS", "60"))
SUSPICIOUS_REFRESH_BURST = int(os.getenv("SUSPICIOUS_REFRESH_BURST", "5"))

_failed_attempts: dict[str, int] = defaultdict(int)
_failed_attempt_ttl: dict[str, float] = {}
_blocked_ips: dict[str, float] = {}
_refresh_state: dict[int, dict] = {}
_sessions: dict[int, list[dict]] = defaultdict(list)
_refresh_user_by_jti: dict[str, int] = {}
_anomaly_ip_history: dict[int, list[tuple[str, float]]] = defaultdict(list)
_refresh_history: dict[int, list[float]] = defaultdict(list)
logger = logging.getLogger(__name__)


def _cleanup_memory_state() -> None:
    now = time.time()
    for ip, until in list(_blocked_ips.items()):
        if until <= now:
            _blocked_ips.pop(ip, None)
    for ip, ttl in list(_failed_attempt_ttl.items()):
        if ttl <= now:
            _failed_attempt_ttl.pop(ip, None)
            _failed_attempts.pop(ip, None)


def _redis_key_failed(ip: str) -> str:
    return f"sec:failed_login:{ip}"


def _redis_key_blocked(ip: str) -> str:
    return f"sec:blocked_ip:{ip}"


def _redis_refresh_key(user_id: int) -> str:
    return f"refresh:{user_id}"


def _redis_session_key(user_id: int) -> str:
    return f"sessions:{user_id}"


def _redis_session_meta_key(jti: str) -> str:
    return f"session_meta:{jti}"


def _redis_refresh_user_key(jti: str) -> str:
    return f"refresh_user:{jti}"


def _normalize_ua(user_agent: str | None) -> str:
    return (user_agent or "").strip()[:255]


def _decode_hash(data: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for k, v in (data or {}).items():
        key = k.decode() if isinstance(k, bytes) else str(k)
        val = v.decode() if isinstance(v, bytes) else str(v)
        result[key] = val
    return result


def _ip_matches(stored: str, incoming: str) -> bool:
    if stored == incoming:
        return True
    if not ALLOW_MOBILE_IP_VARIATION:
        return False
    s = stored.split(".")
    i = incoming.split(".")
    if len(s) == 4 and len(i) == 4:
        return s[:3] == i[:3]
    return False


def _track_anomaly(user_id: int, ip: str) -> list[str]:
    now = time.time()
    reasons: list[str] = []

    ip_hist = [(p, ts) for p, ts in _anomaly_ip_history[user_id] if now - ts <= SUSPICIOUS_IP_WINDOW_SECONDS]
    ip_hist.append((ip, now))
    _anomaly_ip_history[user_id] = ip_hist
    unique_ips = {p for p, _ in ip_hist}
    if len(unique_ips) >= 3:
        reasons.append("multiple_ip_changes")

    refresh_hist = [ts for ts in _refresh_history[user_id] if now - ts <= SUSPICIOUS_REFRESH_WINDOW_SECONDS]
    refresh_hist.append(now)
    _refresh_history[user_id] = refresh_hist
    if len(refresh_hist) > SUSPICIOUS_REFRESH_BURST:
        reasons.append("rapid_refresh_requests")

    return reasons


def is_ip_blocked(ip: str) -> bool:
    r = get_redis_client()
    if r:
        try:
            return bool(r.exists(_redis_key_blocked(ip)))
        except Exception as exc:
            logger.warning("Redis failure in is_ip_blocked; using in-memory fallback: %s", exc)

    _cleanup_memory_state()
    return ip in _blocked_ips


def register_failed_login(ip: str) -> int:
    r = get_redis_client()
    if r:
        try:
            failed_key = _redis_key_failed(ip)
            blocked_key = _redis_key_blocked(ip)
            attempts = int(r.incr(failed_key))
            r.expire(failed_key, FAILED_LOGIN_BLOCK_SECONDS)
            if attempts >= FAILED_LOGIN_THRESHOLD:
                r.set(blocked_key, "1", ex=FAILED_LOGIN_BLOCK_SECONDS)
                r.delete(failed_key)
            return attempts
        except Exception as exc:
            logger.warning("Redis failure in register_failed_login; using in-memory fallback: %s", exc)

    _cleanup_memory_state()
    now = time.time()
    if _failed_attempt_ttl.get(ip, 0) <= now:
        _failed_attempts[ip] = 0
    _failed_attempts[ip] += 1
    _failed_attempt_ttl[ip] = now + FAILED_LOGIN_BLOCK_SECONDS
    if _failed_attempts[ip] >= FAILED_LOGIN_THRESHOLD:
        _blocked_ips[ip] = now + FAILED_LOGIN_BLOCK_SECONDS
        _failed_attempts[ip] = 0
    return _failed_attempts.get(ip, FAILED_LOGIN_THRESHOLD)


def reset_failed_login(ip: str) -> None:
    r = get_redis_client()
    if r:
        try:
            r.delete(_redis_key_failed(ip))
            return
        except Exception as exc:
            logger.warning("Redis failure in reset_failed_login; using in-memory fallback: %s", exc)

    _failed_attempts.pop(ip, None)
    _failed_attempt_ttl.pop(ip, None)


def reset_security_state() -> None:
    _failed_attempts.clear()
    _failed_attempt_ttl.clear()
    _blocked_ips.clear()
    _refresh_state.clear()
    _sessions.clear()
    _refresh_user_by_jti.clear()
    _anomaly_ip_history.clear()
    _refresh_history.clear()


def bind_refresh_session(
    user_id: int,
    refresh_jti: str,
    access_jti: str,
    ip_address: str,
    user_agent: str,
    expires_at: int,
) -> list[str]:
    """
    Store latest refresh binding and active session.
    Returns list of old refresh JTIs evicted due to session cap.
    """
    ua = _normalize_ua(user_agent)
    issued_at = time.time()
    expires_ts = float(expires_at or int(issued_at + 7 * 24 * 3600))
    revoked_jtis: list[str] = []

    r = get_redis_client()
    if r:
        try:
            refresh_key = _redis_refresh_key(user_id)
            r.hset(
                refresh_key,
                mapping={
                    "jti": refresh_jti,
                    "ip": ip_address,
                    "ua": ua,
                    "exp": int(expires_ts),
                },
            )
            r.expire(refresh_key, max(1, int(expires_ts - time.time())))

            sess_key = _redis_session_key(user_id)
            r.zadd(sess_key, {refresh_jti: issued_at})
            r.expire(sess_key, max(1, int(expires_ts - time.time())))
            r.hset(
                _redis_session_meta_key(refresh_jti),
                mapping={
                    "user_id": user_id,
                    "ip": ip_address,
                    "ua": ua,
                    "access_jti": access_jti,
                    "exp": int(expires_ts),
                },
            )
            r.expire(_redis_session_meta_key(refresh_jti), max(1, int(expires_ts - time.time())))
            r.set(_redis_refresh_user_key(refresh_jti), str(user_id), ex=max(1, int(expires_ts - time.time())))

            session_count = int(r.zcard(sess_key))
            if session_count > MAX_SESSIONS_PER_USER:
                overflow = session_count - MAX_SESSIONS_PER_USER
                oldest = r.zrange(sess_key, 0, overflow - 1)
                for old in oldest:
                    old_jti = old.decode() if isinstance(old, bytes) else str(old)
                    revoked_jtis.append(old_jti)
                    old_meta = _decode_hash(r.hgetall(_redis_session_meta_key(old_jti)))
                    if old_meta.get("access_jti"):
                        revoked_jtis.append(old_meta["access_jti"])
                    r.zrem(sess_key, old_jti)
                    r.delete(_redis_session_meta_key(old_jti))
                    r.delete(_redis_refresh_user_key(old_jti))
            return revoked_jtis
        except Exception as exc:
            logger.warning("Redis failure in bind_refresh_session; using in-memory fallback: %s", exc)

    _refresh_state[user_id] = {
        "jti": refresh_jti,
        "ip": ip_address,
            "ua": ua,
            "exp": expires_ts,
            "access_jti": access_jti,
        }
    _refresh_user_by_jti[refresh_jti] = user_id
    _sessions[user_id] = [
        s for s in _sessions[user_id]
        if s.get("exp", 0) > time.time()
    ]
    _sessions[user_id].append(
        {
            "jti": refresh_jti,
            "ip": ip_address,
            "ua": ua,
            "exp": expires_ts,
            "issued": issued_at,
            "access_jti": access_jti,
        }
    )
    _sessions[user_id].sort(key=lambda x: x["issued"])
    while len(_sessions[user_id]) > MAX_SESSIONS_PER_USER:
        old = _sessions[user_id].pop(0)
        old_jti = old["jti"]
        _refresh_user_by_jti.pop(old_jti, None)
        revoked_jtis.append(old_jti)
        if old.get("access_jti"):
            revoked_jtis.append(old["access_jti"])
    return revoked_jtis


def validate_refresh_request(
    user_id: int,
    refresh_jti: str,
    ip_address: str,
    user_agent: str,
) -> tuple[bool, int, str]:
    """
    Returns (allowed, http_status_code, reason).
    """
    ua = _normalize_ua(user_agent)
    r = get_redis_client()
    if r:
        state = _decode_hash(r.hgetall(_redis_refresh_key(user_id)))
        if not state:
            return False, 401, "missing_refresh_state"
        stored_jti = state.get("jti", "")
        stored_ip = state.get("ip", "")
        stored_ua = state.get("ua", "")
        if refresh_jti != stored_jti:
            return False, 401, "refresh_replay_detected"
        if not _ip_matches(stored_ip, ip_address):
            return False, 403, "token_theft_ip_mismatch"
        if stored_ua != ua:
            return False, 403, "token_theft_user_agent_mismatch"
    else:
        state = _refresh_state.get(user_id)
        if not state:
            return False, 401, "missing_refresh_state"
        if state.get("jti") != refresh_jti:
            return False, 401, "refresh_replay_detected"
        if not _ip_matches(str(state.get("ip", "")), ip_address):
            return False, 403, "token_theft_ip_mismatch"
        if str(state.get("ua", "")) != ua:
            return False, 403, "token_theft_user_agent_mismatch"

    return True, 200, "ok"


def clear_refresh_session(user_id: int, refresh_jti: str | None = None) -> None:
    r = get_redis_client()
    if r:
        if refresh_jti:
            r.zrem(_redis_session_key(user_id), refresh_jti)
            r.delete(_redis_session_meta_key(refresh_jti))
            r.delete(_redis_refresh_user_key(refresh_jti))
        state = _decode_hash(r.hgetall(_redis_refresh_key(user_id)))
        if state:
            stored_jti = state.get("jti", "")
            if not refresh_jti or refresh_jti == stored_jti:
                r.delete(_redis_refresh_key(user_id))
        return

    if refresh_jti:
        _refresh_user_by_jti.pop(refresh_jti, None)
        _sessions[user_id] = [s for s in _sessions[user_id] if s.get("jti") != refresh_jti]
    state = _refresh_state.get(user_id)
    if state and (not refresh_jti or state.get("jti") == refresh_jti):
        _refresh_state.pop(user_id, None)


def detect_suspicious_refresh_activity(user_id: int, ip_address: str) -> list[str]:
    return _track_anomaly(user_id, ip_address)


def can_access_patient_abac(db, current_user, patient) -> bool:
    if current_user.role == "ADMIN":
        return True

    if current_user.role == "DOCTOR":
        if current_user.doctor_id and patient.assigned_doctor == current_user.doctor_id:
            return True
        if current_user.doctor_id and patient.hospital_id:
            doctor = db.query(models.Doctor).filter(models.Doctor.doctor_id == current_user.doctor_id).first()
            if doctor and doctor.hospital_id and doctor.hospital_id == patient.hospital_id:
                return True
        return False

    if current_user.role == "NURSE":
        if current_user.nurse_id and patient.assigned_nurse == current_user.nurse_id:
            return True
        if current_user.nurse_id and patient.hospital_id:
            nurse = db.query(models.Nurse).filter(models.Nurse.nurse_id == current_user.nurse_id).first()
            if nurse and nurse.hospital_id and nurse.hospital_id == patient.hospital_id:
                return True
        return False

    return False
