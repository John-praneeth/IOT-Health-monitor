-- ============================================================
--  patient_monitor  –  Database initialisation script v4.0
--  Features: specialization, freelancer doctors, notifications
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
    is_available   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS nurses (
    nurse_id    SERIAL PRIMARY KEY,
    name        VARCHAR(100),
    department  VARCHAR(100),
    hospital_id INT REFERENCES hospitals(hospital_id) ON DELETE SET NULL,
    phone       VARCHAR(20),
    email       VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS patients (
    patient_id      SERIAL PRIMARY KEY,
    name            VARCHAR(100),
    age             INT,
    room_number     VARCHAR(20),
    hospital_id     INT REFERENCES hospitals(hospital_id) ON DELETE SET NULL,
    assigned_doctor INT REFERENCES doctors(doctor_id) ON DELETE SET NULL,
    assigned_nurse  INT REFERENCES nurses(nurse_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS vitals (
    vital_id       SERIAL PRIMARY KEY,
    patient_id     INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    heart_rate     INT,
    spo2           INT,
    temperature    FLOAT,
    blood_pressure VARCHAR(20),
    timestamp      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        SERIAL PRIMARY KEY,
    patient_id      INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    vital_id        INT REFERENCES vitals(vital_id) ON DELETE SET NULL,
    alert_type      VARCHAR(50),
    status          VARCHAR(20) DEFAULT 'PENDING',
    created_at      TIMESTAMP DEFAULT NOW(),
    acknowledged_by INT
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

-- 4. Seed Data -------------------------------------------------------------

INSERT INTO hospitals (name, location, phone, email) VALUES
    ('City General Hospital', 'Downtown', '555-1000', 'info@citygeneral.com'),
    ('Sunrise Medical Center', 'Uptown', '555-2000', 'info@sunrise.com')
ON CONFLICT DO NOTHING;

INSERT INTO doctors (name, specialization, hospital_id, phone, email, is_freelancer, is_available) VALUES
    ('Dr. Sarah Chen',    'Cardiology',     1, '555-0101', 'sarah.chen@citygeneral.com',    FALSE, TRUE),
    ('Dr. James Wilson',  'Neurology',      2, '555-0102', 'james.wilson@sunrise.com',      FALSE, TRUE),
    ('Dr. Maria Garcia',  'Cardiology',     1, '555-0103', 'maria.garcia@citygeneral.com',  FALSE, TRUE),
    ('Dr. Alex Kumar',    'Pulmonology',    NULL, '555-0104', 'alex.kumar@freelance.com',    TRUE,  TRUE),
    ('Dr. Priya Sharma',  'Cardiology',     NULL, '555-0105', 'priya.sharma@freelance.com',  TRUE,  TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO nurses (name, department, hospital_id, phone, email) VALUES
    ('Nurse Emily Davis',    'ICU',       1, '555-0201', 'emily.davis@citygeneral.com'),
    ('Nurse Robert Lee',     'Cardiology', 1, '555-0202', 'robert.lee@citygeneral.com'),
    ('Nurse Anna Taylor',    'Neurology',  2, '555-0203', 'anna.taylor@sunrise.com'),
    ('Nurse Michael Scott',  'General',    2, '555-0204', 'michael.scott@sunrise.com'),
    ('Nurse Lisa White',     'ICU',        1, '555-0205', 'lisa.white@citygeneral.com'),
    ('Nurse Tom Harris',     'Emergency',  2, '555-0206', 'tom.harris@sunrise.com')
ON CONFLICT DO NOTHING;

INSERT INTO patients (name, age, room_number, hospital_id, assigned_doctor, assigned_nurse) VALUES
    ('Alice Johnson',  34, '101-A', 1, 1, 1),
    ('Bob Martinez',   67, '102-B', 1, 1, 2),
    ('Carol Williams', 52, '201-A', 2, 2, 3),
    ('David Brown',    45, '202-B', 2, 2, 4),
    ('Eva Green',      29, '103-C', 1, 3, 5)
ON CONFLICT DO NOTHING;

-- 5. Seed admin user (password: admin123) ----------------------------------
-- Hash generated with bcrypt
INSERT INTO users (username, password_hash, role)
VALUES ('admin', '$2b$12$ihXuiWERY5kZ3hZEuffq1OJ3egboI/r.2AsGDTFO93eh8genX3Wki', 'ADMIN')
ON CONFLICT (username) DO NOTHING;
