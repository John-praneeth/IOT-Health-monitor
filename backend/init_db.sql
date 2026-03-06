-- ============================================================
--  patient_monitor  –  Database initialisation script v5.0
--  Enterprise: soft deletes, SLA, WhatsApp logs, indexes
-- ============================================================

-- 1. Core Tables ----------------------------------------------------------

CREATE TABLE IF NOT EXISTS hospitals (
    hospital_id SERIAL PRIMARY KEY,
    name        VARCHAR(100),
    location    VARCHAR(200),
    phone       VARCHAR(20),
    email       VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS doctors (
    doctor_id      SERIAL PRIMARY KEY,
    name           VARCHAR(100),
    specialization VARCHAR(100),
    hospital_id    INT REFERENCES hospitals(hospital_id) ON DELETE SET NULL,
    phone          VARCHAR(20),
    email          VARCHAR(100),
    is_freelancer  BOOLEAN DEFAULT FALSE,
    is_available   BOOLEAN DEFAULT TRUE,
    is_active      BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE IF NOT EXISTS nurses (
    nurse_id    SERIAL PRIMARY KEY,
    name        VARCHAR(100),
    department  VARCHAR(100),
    hospital_id INT REFERENCES hospitals(hospital_id) ON DELETE SET NULL,
    phone       VARCHAR(20),
    email       VARCHAR(100),
    is_active   BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    patient_id      SERIAL PRIMARY KEY,
    name            VARCHAR(100),
    age             INT,
    room_number     VARCHAR(20),
    hospital_id     INT REFERENCES hospitals(hospital_id) ON DELETE SET NULL,
    assigned_doctor INT REFERENCES doctors(doctor_id) ON DELETE SET NULL,
    assigned_nurse  INT REFERENCES nurses(nurse_id) ON DELETE SET NULL,
    is_active       BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE IF NOT EXISTS vitals (
    vital_id       SERIAL PRIMARY KEY,
    patient_id     INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    heart_rate     INT,
    spo2           INT,
    temperature    FLOAT,
    timestamp      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        SERIAL PRIMARY KEY,
    patient_id      INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    vital_id        INT REFERENCES vitals(vital_id) ON DELETE SET NULL,
    alert_type      VARCHAR(50),
    status          VARCHAR(20) DEFAULT 'PENDING',
    created_at      TIMESTAMP DEFAULT NOW(),
    acknowledged_by INT,
    acknowledged_at TIMESTAMP
);

-- 2. Auth & Audit Tables --------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN','DOCTOR','NURSE')),
    doctor_id     INT REFERENCES doctors(doctor_id),
    nurse_id      INT REFERENCES nurses(nurse_id)
);

CREATE TABLE IF NOT EXISTS alert_escalations (
    escalation_id       SERIAL PRIMARY KEY,
    alert_id            INT NOT NULL REFERENCES alerts(alert_id),
    escalated_to_doctor INT NOT NULL REFERENCES doctors(doctor_id),
    escalated_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_notifications (
    notification_id SERIAL PRIMARY KEY,
    alert_id        INT NOT NULL REFERENCES alerts(alert_id),
    user_id         INT NOT NULL REFERENCES users(user_id),
    message         VARCHAR(500) NOT NULL,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    log_id    SERIAL PRIMARY KEY,
    user_id   INT,
    action    VARCHAR(100) NOT NULL,
    entity    VARCHAR(50)  NOT NULL,
    entity_id INT,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id      SERIAL PRIMARY KEY,
    patient_id      INT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    sender_username VARCHAR(100) NOT NULL,
    sender_role     VARCHAR(20) NOT NULL,
    message         VARCHAR(2000) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 3. Indexes ---------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_alert_esc_alert ON alert_escalations(alert_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity, timestamp);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON alert_notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_chat_patient ON chat_messages(patient_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_patient ON alerts(patient_id);
CREATE INDEX IF NOT EXISTS idx_vitals_patient_ts ON vitals(patient_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_doctors_active ON doctors(is_active);
CREATE INDEX IF NOT EXISTS idx_nurses_active ON nurses(is_active);
CREATE INDEX IF NOT EXISTS idx_patients_active ON patients(is_active);

-- 4. Enterprise Tables ─────────────────────────────────────────────────────

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

CREATE TABLE IF NOT EXISTS sla_records (
    sla_id                SERIAL PRIMARY KEY,
    alert_id              INT NOT NULL UNIQUE REFERENCES alerts(alert_id),
    patient_id            INT NOT NULL REFERENCES patients(patient_id),
    response_time_seconds INT,
    breached              BOOLEAN DEFAULT FALSE,
    created_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sla_breached ON sla_records(breached);

-- NOTE: For seed data, run:  python seed_db.py
