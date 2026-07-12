-- ============================================================
--  v5.1 Migration Script — Enterprise Patch
--  Run AFTER v5_enterprise_upgrade.sql
--  Adds: last_checked_at on alerts, idempotency_key on whatsapp_logs
-- ============================================================

-- FIX 5: Track last abnormal vitals check time (do not reset SLA timer)
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP;

-- FIX 6: WhatsApp idempotency key (alert_id + event_type + phone)
ALTER TABLE whatsapp_logs ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(100);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wa_log_idempotency
    ON whatsapp_logs(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Additional index for dedup queries (PENDING + ESCALATED)
CREATE INDEX IF NOT EXISTS idx_alerts_patient_type_status
    ON alerts(patient_id, alert_type, status);
