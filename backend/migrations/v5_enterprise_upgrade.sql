-- ============================================================
--  v5.0 Migration Script — Enterprise Upgrade
--  Run AFTER init_db.sql (which creates base tables)
--  Adds: soft deletes, indexes, WhatsApp logs, SLA tracking
-- ============================================================

-- 1. Soft Delete Columns ---------------------------------------------------
ALTER TABLE doctors  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE nurses   ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;

-- 2. Alert improvements ----------------------------------------------------
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMP;

-- 3. Performance Indexes ---------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_patient ON alerts(patient_id);
CREATE INDEX IF NOT EXISTS idx_vitals_patient_ts ON vitals(patient_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON alert_notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_doctors_active ON doctors(is_active);
CREATE INDEX IF NOT EXISTS idx_nurses_active ON nurses(is_active);
CREATE INDEX IF NOT EXISTS idx_patients_active ON patients(is_active);

-- 4. WhatsApp Notification Log ---------------------------------------------
CREATE TABLE IF NOT EXISTS whatsapp_logs (
    log_id       SERIAL PRIMARY KEY,
    alert_id     INT REFERENCES alerts(alert_id),
    recipient    VARCHAR(20) NOT NULL,
    message_type VARCHAR(20) NOT NULL,
    status       VARCHAR(20) DEFAULT 'PENDING',
    attempts     INT DEFAULT 0,
    error        VARCHAR(500),
    created_at   TIMESTAMP DEFAULT NOW(),
    sent_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wa_log_alert ON whatsapp_logs(alert_id);
CREATE INDEX IF NOT EXISTS idx_wa_log_status ON whatsapp_logs(status);

-- 5. SLA Tracking ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS sla_records (
    sla_id                SERIAL PRIMARY KEY,
    alert_id              INT NOT NULL UNIQUE REFERENCES alerts(alert_id),
    patient_id            INT NOT NULL REFERENCES patients(patient_id),
    response_time_seconds INT,
    breached              BOOLEAN DEFAULT FALSE,
    created_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sla_breached ON sla_records(breached);
