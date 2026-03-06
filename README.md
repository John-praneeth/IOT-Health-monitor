# 🏥 IoT Healthcare Patient Monitor

A **full-stack real-time patient vital-sign monitoring system** built with **FastAPI + React + PostgreSQL**.  
Monitors heart rate, SpO₂, and temperature every 10 seconds — fires alerts, escalates unacknowledged alerts, sends **WhatsApp notifications** to doctors and nurses via GREEN-API, and delivers live chart updates to the browser over WebSocket.

> **GitHub:** [John-praneeth/IOT-Health-monitor](https://github.com/John-praneeth/IOT-Health-monitor) · **Branch:** `railway-deploy`

---

## �� Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Feature List](#2-feature-list)
3. [Project Structure](#3-project-structure)
4. [Quick Start — Local Development](#4-quick-start--local-development)
5. [Environment Variables](#5-environment-variables)
6. [Starting the App](#6-starting-the-app)
7. [System Architecture & Data Flow](#7-system-architecture--data-flow)
8. [Backend — File-by-File Breakdown](#8-backend--file-by-file-breakdown)
9. [Vitals Pipeline — How It Works End-to-End](#9-vitals-pipeline--how-it-works-end-to-end)
10. [Alert Engine — Logic & Thresholds](#10-alert-engine--logic--thresholds)
11. [Alert Escalation Flow](#11-alert-escalation-flow)
12. [WhatsApp Notification System](#12-whatsapp-notification-system)
13. [WebSocket — Real-Time Live Updates](#13-websocket--real-time-live-updates)
14. [Authentication & JWT Flow](#14-authentication--jwt-flow)
15. [Role-Based Access Control](#15-role-based-access-control)
16. [API Reference](#16-api-reference)
17. [Database Schema](#17-database-schema)
18. [Frontend Pages](#18-frontend-pages)
19. [Rate Limiting](#19-rate-limiting)
20. [Audit Logging](#20-audit-logging)
21. [Default Accounts](#21-default-accounts)
22. [Docker](#22-docker)
23. [ThingSpeak Integration (Future)](#23-thingspeak-integration-future)

---

## 1. Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI (Python 3.12) | REST API + WebSocket server |
| **Frontend** | React 19 + React Router v7 | Single-page application |
| **Database** | PostgreSQL 16 | Persistent data store |
| **ORM** | SQLAlchemy | Python↔DB bridge |
| **Auth** | JWT (python-jose) + bcrypt | Stateless token auth |
| **WhatsApp** | GREEN-API (free tier) | Alert delivery over WhatsApp |
| **Charts** | Chart.js + react-chartjs-2 | Live vitals visualisation |
| **HTTP Client** | Axios (frontend) / httpx (backend) | API calls |
| **Rate Limiting** | slowapi | Protect login + API endpoints |
| **Real-time** | WebSocket + Redis pub/sub | Push vitals to browser |
| **Logging** | Python JSON logger | Structured request tracing |
| **Web Server** | nginx (Docker only) | Serve React build + proxy API |
| **Container** | Docker Compose | One-command full stack |

---

## 2. Feature List

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Live Dashboard** | Real-time counters — patients, doctors, nurses, hospitals, pending & escalated alerts |
| 2 | **Real-Time Vitals** | Heart rate, SpO₂, temperature recorded every 10 s; live charts update over WebSocket |
| 3 | **Fake Vitals Generator** | Generates realistic vitals with random drift + rare spikes to simulate real IoT hardware |
| 4 | **Alert Engine** | Auto-fires alerts when vitals cross thresholds; auto-resolves when vitals normalise |
| 5 | **Alert De-duplication** | Duplicate PENDING/ESCALATED alerts of the same type are suppressed per patient |
| 6 | **Alert Escalation** | PENDING alerts not acknowledged within 2 min are escalated to same-specialization doctors |
| 7 | **WhatsApp Alerts** | Alerts sent to assigned doctor + nurse via GREEN-API; doctors reply `ACK` or `ACK <id>` |
| 8 | **WhatsApp Webhook** | Incoming WhatsApp replies are parsed to auto-acknowledge alerts in the database |
| 9 | **In-App Notifications** | Per-user unread notification bell, populated on escalation |
| 10 | **Pause / Resume** | Admin can pause all WhatsApp alerts without stopping the backend |
| 11 | **Multi-Hospital** | Doctors, nurses, and patients belong to hospitals; dropdowns are hospital-filtered |
| 12 | **Role-Based Access** | 3 roles: ADMIN / DOCTOR / NURSE — enforced on every protected endpoint |
| 13 | **Patient Chat** | Per-patient treatment chat visible only to assigned doctor, nurse, or admin |
| 14 | **Audit Logs** | Every CREATE / UPDATE / DELETE / LOGIN action is time-stamped and stored |
| 15 | **Rate Limiting** | 5 login attempts/min per IP; 100 API requests/min per user |
| 16 | **System Status** | Live health check for PostgreSQL, Redis, and WhatsApp from the admin panel |
| 17 | **Self-Registration** | Doctors and nurses can self-register; admin creates accounts directly from staff pages |
| 18 | **Request Tracing** | Every HTTP request gets a unique `X-Request-ID` header for log correlation |

---

## 3. Project Structure

```
IoT_healthCare/
├── backend/
│   ├── main.py              # FastAPI app — all REST + WebSocket endpoints (~980 lines)
│   ├── models.py            # SQLAlchemy ORM models (12 tables)
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── crud.py              # All database read/write operations
│   ├── auth.py              # JWT creation/validation + bcrypt + role guards
│   ├── alert_engine.py      # Vital threshold rules — returns triggered alert types
│   ├── scheduler.py         # Standalone process: generates vitals every 10 s
│   ├── fake_generator.py    # Orchestrates: get vitals → save → run alerts → send WhatsApp
│   ├── database.py          # SQLAlchemy engine + session factory + Redis safe-mode
│   ├── whatsapp_notifier.py # GREEN-API sender + pending-response tracker + ACK logic
│   ├── rate_limiter.py      # slowapi setup — Redis-backed or in-memory fallback
│   ├── exception_handlers.py# Global FastAPI exception handlers
│   ├── json_logger.py       # Structured JSON logging + request ID context var
│   ├── seed_db.py           # Optional: seed sample hospitals/doctors/patients
│   ├── data_sources/
│   │   ├── base.py          # Abstract VitalSource interface
│   │   ├── fake_source.py   # Fake vitals data source (default)
│   │   └── thingspeak_source.py  # ThingSpeak IoT data source (future)
│   ├── requirements.txt
│   └── .env                 # ← you create this (see Section 5)
│
├── frontend/
│   ├── src/
│   │   ├── App.js           # Root component — routing + sidebar nav + auth guard
│   │   ├── api.js           # All Axios calls, JWT inject, auto-logout on 401
│   │   └── pages/
│   │       ├── Login.js         # Login + self-register flow
│   │       ├── Dashboard.js     # Live stat cards + WebSocket connection
│   │       ├── Patients.js      # CRUD + assign doctor/nurse
│   │       ├── Doctors.js       # CRUD + optional login creation
│   │       ├── Nurses.js        # CRUD + optional login creation
│   │       ├── Vitals.js        # Live charts per patient
│   │       ├── Alerts.js        # Alert list + acknowledge button
│   │       ├── Hospitals.js     # Hospital management (admin)
│   │       ├── WhatsAppConfig.js# Pause/resume + recipients overview (admin)
│   │       ├── SystemStatus.js  # DB/Redis/WhatsApp health + alert counts (admin)
│   │       ├── AuditLogs.js     # Full audit trail (admin)
│   │       └── PatientChat.js   # Per-patient treatment chat
│   ├── package.json
│   └── public/
│
├── docker-compose.yml
└── README.md
```

---

## 4. Quick Start — Local Development

### Prerequisites

| Tool | Minimum Version |
|------|----------------|
| Python | 3.11+ |
| Node.js | 18+ |
| PostgreSQL | 14+ (running locally) |
| Redis | Optional (WebSocket pub/sub; app works without it) |

### 1 — Clone the repo

```bash
git clone https://github.com/John-praneeth/IOT-Health-monitor.git
cd IOT-Health-monitor
```

### 2 — Create the database

Open `psql` (or any PostgreSQL client) and run:

```sql
CREATE DATABASE patient_monitor;
```

> Tables are created **automatically** by SQLAlchemy on first backend startup — no migration scripts needed.

### 3 — Set up the backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# Install all dependencies
pip install -r requirements.txt

# Create the .env file (see Section 5)
```

### 4 — Set up the frontend

```bash
cd frontend
npm install
```

---

## 5. Environment Variables

Create `backend/.env` with the following content:

```env
# ── Database ────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/patient_monitor

# ── Auth ────────────────────────────────────────────────────────────────────
SECRET_KEY=change-this-to-a-long-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ── Data Source ──────────────────────────────────────────────────────────────
# "fake"        = auto-generated realistic vitals (for development / demo)
# "thingspeak"  = pull from real IoT device via ThingSpeak API (future)
DATA_SOURCE=fake

# ── ThingSpeak (only needed when DATA_SOURCE=thingspeak) ──────────────────
# THINGSPEAK_CHANNEL_ID=your_channel_id
# THINGSPEAK_READ_API_KEY=your_api_key
# THINGSPEAK_TEMP_UNIT=F

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000

# ── WhatsApp (GREEN-API) ─────────────────────────────────────────────────────
WHATSAPP_ENABLED=true
GREEN_API_ID=your_instance_id
GREEN_API_TOKEN=your_api_token
WHATSAPP_RECIPIENTS=
```

### Getting GREEN-API credentials (free, ~2 minutes)

1. Go to [console.green-api.com](https://console.green-api.com) and sign up for free
2. Click **Create Instance** → choose **Developer (Free)** plan
3. Scan the QR code with WhatsApp *(Settings → Linked Devices → Link a Device)*
4. Copy **idInstance** → set as `GREEN_API_ID`
5. Copy **apiTokenInstance** → set as `GREEN_API_TOKEN`
6. Restart the backend — WhatsApp is ready

---

## 6. Starting the App

You need **3 terminals** running simultaneously.

### Terminal 1 — Backend API

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

| URL | Resource |
|-----|---------|
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | Swagger interactive docs |
| http://localhost:8000/redoc | ReDoc documentation |

> The backend **creates all database tables** on first run via `Base.metadata.create_all()`.

### Terminal 2 — Vitals Scheduler

```bash
cd backend
source venv/bin/activate
python scheduler.py
```

- Generates vitals for every patient every **10 seconds**
- Fires alerts when thresholds are crossed
- Escalates un-acknowledged PENDING alerts after **2 minutes**

> ⚠️ Without the scheduler running, the Vitals page is empty and no alerts fire.

### Terminal 3 — Frontend

```bash
cd frontend
npm start
```

Frontend runs at **http://localhost:3000**

---

### VS Code Tasks (shortcut)

Pre-configured tasks are available. Press `Ctrl+Shift+P` → **Tasks: Run Task**:

| Task Label | Command |
|-----------|---------|
| **Start Backend** | `uvicorn main:app --host 0.0.0.0 --port 8000` |
| **Start Frontend** | `npm start` |
| **Start Scheduler** | `python scheduler.py` |

---

## 7. System Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  SCHEDULER PROCESS  (scheduler.py — every 10 seconds)               │
│                                                                      │
│   1. Query all patients from PostgreSQL                              │
│   2. fake_generator.save_fake(db, patient_id) for each patient       │
│      ├── data_sources.get_source() → FakeVitalSource.get_vitals()    │
│      ├── crud.create_vitals()  →  INSERT into vitals table           │
│      ├── alert_engine.check_alerts()  →  check 5 thresholds         │
│      ├── Auto-resolve old PENDING/ESCALATED → RESOLVED               │
│      ├── crud.create_alert()  →  INSERT (de-duplicated)              │
│      └── whatsapp_notifier.send_alert_notification()                 │
│   3. crud.escalate_stale_alerts()  →  PENDING > 2 min → ESCALATED   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ writes to
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│  POSTGRESQL DATABASE  (patient_monitor)                               │
│  hospitals · doctors · nurses · patients · vitals · alerts            │
│  alert_escalations · alert_notifications · users                      │
│  audit_logs · chat_messages · whatsapp_logs                           │
└──────────┬────────────────────────────────────────────┬──────────────┘
           │ reads / writes                             │ reads
           ▼                                            ▼
┌──────────────────────────────┐        ┌───────────────────────────────┐
│  FASTAPI BACKEND (port 8000) │        │  WebSocket  /ws/vitals        │
│  • REST endpoints            │        │                               │
│  • JWT auth middleware        │        │  Mode 1 — Redis available:    │
│  • Rate limiting (slowapi)    │        │    Async pub/sub subscriber   │
│  • Request ID tracing         │        │    broadcasts to all clients  │
│  • Structured JSON logs       │        │                               │
└──────────┬───────────────────┘        │  Mode 2 — No Redis:           │
           │ HTTP/JSON                  │    Poll DB every 5 s          │
           ▼                            └──────────────┬────────────────┘
┌──────────────────────────────────────────────────────┘
│  REACT FRONTEND  (port 3000)
│  App.js: routes + sidebar + auth guard
│  api.js: Axios + JWT inject + auto-logout on 401
│  Dashboard → WebSocket updates + stat cards
│  Vitals    → Live Chart.js per patient
│  Alerts    → List + acknowledge button
│  Admin     → Hospitals, WhatsApp, System Status, Audit Logs
└──────────┬───────────────────────────────────────────
           │ WhatsApp messages
           ▼
┌────────────────────────────────────────────────────────┐
│  GREEN-API  (WhatsApp)                                  │
│  • Alert messages → assigned doctor + nurse phones      │
│  • Doctor replies "ACK" or "ACK <id>" via WhatsApp      │
│  • Webhook → POST /whatsapp/webhook → DB update         │
└────────────────────────────────────────────────────────┘
```

---

## 8. Backend — File-by-File Breakdown

### `main.py` — FastAPI Application (~980 lines)

The single entry point for all HTTP and WebSocket traffic.

**Startup sequence (in order):**
1. `setup_logging()` — initialise structured JSON logging
2. `require_redis_on_startup()` — optional Redis check (warns but never crashes the app)
3. `Base.metadata.create_all(bind=engine)` — auto-create all 12 DB tables on first run
4. `CORSMiddleware` — allow origins from `CORS_ORIGINS` env var
5. `setup_rate_limiter(app)` — attach slowapi with Redis or in-memory storage
6. Request ID middleware — attach `X-Request-ID` to every request and response
7. `startup_redis_subscriber` (async event) — if Redis is up, start the pub/sub background task

**Endpoint groups:**

| Tag | Prefix | Key Endpoints |
|-----|--------|---------------|
| Auth | `/auth` | `POST /login`, `POST /register`, `POST /register/doctor`, `POST /register/nurse`, `GET /me` |
| Hospitals | `/hospitals` | `GET`, `POST` |
| Doctors | `/doctors` | `GET`, `POST`, `GET /{id}`, `DELETE /{id}`, `GET /{id}/patients` |
| Nurses | `/nurses` | `GET`, `POST`, `GET /{id}`, `DELETE /{id}`, `GET /{id}/patients` |
| Patients | `/patients` | `GET`, `POST`, `GET /{id}`, `DELETE /{id}`, `PATCH /{id}/assign_doctor`, `PATCH /{id}/assign_nurse` |
| Vitals | `/vitals` | `POST`, `GET`, `GET /latest/{patient_id}` |
| Alerts | `/alerts` | `GET`, `PATCH /{id}/acknowledge` |
| Escalations | `/escalations` | `GET` |
| Notifications | `/notifications` | `GET /my`, `PATCH /{id}/read`, `POST /read-all` |
| Dashboard | `/dashboard` | `GET /stats` |
| Chat | `/patients/{id}/chat` | `GET`, `POST` |
| Audit | `/audit-logs` | `GET` |
| WhatsApp | `/whatsapp` | `GET /config`, `POST /alerts/pause`, `POST /alerts/resume`, `POST /webhook`, `GET /logs` |
| Health | `/health` | `GET /`, `GET /db`, `GET /redis`, `GET /whatsapp`, `GET /full` |
| WebSocket | `/ws/vitals` | Live vitals push |

---

### `models.py` — SQLAlchemy ORM Models

Defines all 12 database tables as Python classes:

| Class | Table | Key Columns |
|-------|-------|-------------|
| `Hospital` | `hospitals` | `hospital_id`, `name`, `location`, `phone`, `email` |
| `Doctor` | `doctors` | `doctor_id`, `name`, `specialization`, `hospital_id`, `phone`, `is_freelancer`, `is_available` |
| `Nurse` | `nurses` | `nurse_id`, `name`, `department`, `hospital_id`, `phone` |
| `Patient` | `patients` | `patient_id`, `name`, `age`, `room_number`, `hospital_id`, `assigned_doctor`, `assigned_nurse` |
| `Vitals` | `vitals` | `vital_id`, `patient_id`, `heart_rate`, `spo2`, `temperature`, `timestamp` |
| `Alert` | `alerts` | `alert_id`, `patient_id`, `vital_id`, `alert_type`, `status`, `created_at`, `acknowledged_by`, `acknowledged_at` |
| `AlertEscalation` | `alert_escalations` | `escalation_id`, `alert_id`, `escalated_to_doctor`, `escalated_at` |
| `AlertNotification` | `alert_notifications` | `notification_id`, `alert_id`, `user_id`, `message`, `is_read` |
| `User` | `users` | `user_id`, `username`, `password_hash`, `role`, `doctor_id`, `nurse_id` |
| `AuditLog` | `audit_logs` | `log_id`, `user_id`, `action`, `entity`, `entity_id`, `timestamp` |
| `ChatMessage` | `chat_messages` | `message_id`, `patient_id`, `sender_username`, `sender_role`, `message` |
| `WhatsAppLog` | `whatsapp_logs` | `log_id`, `alert_id`, `recipient`, `status`, `attempts`, `idempotency_key` |

---

### `crud.py` — Database Operations

All reads and writes go through `crud.py`. Key functions:

| Function | What it does |
|----------|-------------|
| `create_vitals(db, vital)` | INSERT a vitals record; accepts dict or Pydantic object |
| `get_vitals(db, patient_id, doctor_id, limit, offset)` | Fetch vitals with optional patient or doctor filter |
| `get_latest_vital(db, patient_id)` | Fetch the single most-recent vital for a patient |
| `create_alert(db, patient_id, vital_id, alert_type)` | INSERT alert with de-duplication check; updates `last_checked_at` if duplicate PENDING |
| `get_alerts(db, status, doctor_id, limit, offset)` | Fetch alerts filtered by status and/or doctor |
| `acknowledge_alert(db, alert_id, acknowledged_by)` | Set `status=ACKNOWLEDGED`, stamp `acknowledged_at` |
| `escalate_stale_alerts(db, threshold_minutes=2)` | Find PENDING alerts older than threshold → ESCALATED, create escalation records + notifications, send WhatsApp escalation |
| `create_patient(db, patient)` | INSERT patient + write audit log |
| `delete_patient(db, patient_id)` | Hard delete — removes vitals first (FK), then patient |
| `create_doctor(db, doctor)` | INSERT doctor; optionally creates linked User account if credentials provided |
| `delete_doctor(db, doctor_id)` | Hard delete — nullifies `doctor_id` on linked users first |
| `_enrich_patient(patient)` | Appends computed fields: `doctor_name`, `nurse_name`, `hospital_name` |
| `get_dashboard_stats(db)` | COUNT queries for all stat cards on dashboard |
| `create_chat_message(db, ...)` | INSERT chat message for patient |
| `create_whatsapp_log(db, ...)` | INSERT WhatsApp delivery record with idempotency check |
| `write_audit(db, action, entity, entity_id, user_id)` | INSERT audit log entry |

---

### `schemas.py` — Pydantic Schemas

Request/response validation models. Key schemas:

| Schema | Direction | Used for |
|--------|-----------|---------|
| `VitalsCreate` | Request | POST /vitals body |
| `VitalsOut` | Response | GET /vitals, WebSocket payloads |
| `AlertOut` | Response | GET /alerts — includes `patient_name`, `room_number` |
| `DashboardStats` | Response | GET /dashboard/stats |
| `TokenResponse` | Response | POST /auth/login — contains `access_token`, `role`, `username`, `doctor_id`, `nurse_id` |
| `DoctorCreate` | Request | POST /doctors — includes optional `username`/`password` for linked user |
| `WhatsAppConfigOut` | Response | GET /whatsapp/config |
| `HealthCheckOut` | Response | GET /health/full |
| `ChatMessageOut` | Response | GET /patients/{id}/chat |

---

### `auth.py` — Authentication & RBAC

| Function | Purpose |
|----------|---------|
| `hash_password(password)` | bcrypt-hash a plain-text password |
| `verify_password(plain, hashed)` | bcrypt compare |
| `create_access_token(data, expires_delta)` | Sign a JWT with HS256, embed `sub` (username) and `role` |
| `get_current_user(token, db)` | Decode JWT → lookup user in DB → return User or None |
| `require_auth(current_user)` | FastAPI dependency: raise 401 if not authenticated |
| `require_role(*roles)` | Dependency factory: raise 403 if user's role not in allowed list |
| `create_user(db, username, password, role, doctor_id, nurse_id)` | Hash password + INSERT User |

Token lifetime defaults to **30 minutes** (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

---

### `database.py` — Engine & Redis

- Loads `backend/.env` via `python-dotenv` at import time
- Creates SQLAlchemy `engine` with `pool_pre_ping=True`, `pool_size=5`, `max_overflow=10`, `connect_timeout=5`
- `check_redis()` — tries `redis.ping()` on startup; sets global `_redis_available` flag
- `get_redis_client()` — returns live Redis client or `None` (never raises)
- `is_redis_available()` — checked throughout to decide WebSocket mode + rate limiter storage

---

### `alert_engine.py` — Threshold Rules

```python
THRESHOLDS = {
    "HIGH_HEART_RATE": lambda v: v.heart_rate > 110,
    "LOW_HEART_RATE":  lambda v: v.heart_rate < 50,
    "LOW_SPO2":        lambda v: v.spo2 < 90,
    "HIGH_TEMP":       lambda v: v.temperature > 101.0,
    "LOW_TEMP":        lambda v: v.temperature < 96.0,
}
```

`check_alerts(vital)` iterates all 5 rules against the vitals object and returns a list of triggered alert type strings. An empty list means all vitals are normal.

---

### `scheduler.py` — Vitals Scheduler

Runs as a standalone process (`python scheduler.py`). Loop every `INTERVAL_SECONDS = 10`:

1. Open a fresh DB session
2. Query all `Patient` rows
3. For each patient → `fake_generator.save_fake(db, patient_id)`
4. Log the result (HR / SpO₂ / Temp / Alerts triggered)
5. Call `crud.escalate_stale_alerts(db, threshold_minutes=2)` — escalate anything older than 2 min
6. Close DB session → sleep 10 seconds

---

### `fake_generator.py` — Vitals Generator & Orchestrator

`save_fake(db, patient_id)` is the core orchestration function that ties everything together:

1. `get_source()` → returns the configured data source (`FakeVitalSource` by default)
2. `source.get_vitals(patient_id)` → returns `{patient_id, heart_rate, spo2, temperature}`
3. `crud.create_vitals(db, data)` → INSERT into vitals table
4. `alert_engine.check_alerts(vital_record)` → get list of triggered types
5. **Auto-resolve logic:**
   - If *no* alerts triggered → resolve ALL PENDING/ESCALATED alerts for this patient
   - If *some* alerts triggered → resolve only the types that are no longer abnormal
6. For each newly triggered type → `crud.create_alert()` (de-duplicated)
7. If new alert created AND WhatsApp not paused → `whatsapp_notifier.send_alert_notification()`
8. Returns `(vital_record, triggered_list)`

---

### `whatsapp_notifier.py` — GREEN-API Sender

**Key functions:**

| Function | What it does |
|----------|-------------|
| `send_whatsapp_message(phone, text)` | POST to `https://api.green-api.com/waInstance{ID}/sendMessage/{TOKEN}` |
| `send_alert_notification(alert_type, patient_name, ...)` | Build alert message, resolve doctor + nurse phones from DB via `get_patient_recipients()`, send, track in `_pending_responses` |
| `send_escalation_notification(alert_type, ..., recipients)` | Send escalation message to a list of phones |
| `get_patient_recipients(db, patient_id, hospital_id)` | Query assigned doctor + nurse phone numbers from DB |
| `pause_alerts()` / `resume_alerts()` | Write / remove `.whatsapp_paused` flag file |
| `is_alerts_paused()` | Check if pause flag file exists |
| `track_pending_response(alert_id, doctor_phone, ...)` | Add to `_pending_responses` dict — track unanswered alerts |
| `acknowledge_by_phone(doctor_phone)` | Called on `ACK` webhook reply — returns list of alert_ids acknowledged |
| `acknowledge_alert_by_id(alert_id, doctor_phone)` | Called on `ACK <id>` reply — granular single-alert acknowledgement |
| `get_unresponded_alerts()` | Returns alerts not acknowledged within `ESCALATION_TIMEOUT_MINUTES = 5` |

**Pause / Resume mechanism:**  
Uses a file `.whatsapp_paused` in the `backend/` folder. Both the API process and scheduler process check this file — so pausing from the UI affects both processes immediately without restarting either.

---

### `data_sources/` — Data Source Abstraction

Allows swapping between fake vitals and real IoT sensors without changing any business logic.

| File | Class | Description |
|------|-------|-------------|
| `base.py` | `VitalSource` (ABC) | Abstract base: `get_vitals(patient_id) -> dict` |
| `fake_source.py` | `FakeVitalSource` | Generates realistic random vitals with drift and occasional spikes |
| `thingspeak_source.py` | `ThingSpeakSource` | Reads from ThingSpeak channel via HTTP API (future integration) |

`data_sources/__init__.py` exposes `get_source()` — reads `DATA_SOURCE` env var and returns the appropriate class instance.

---

## 9. Vitals Pipeline — How It Works End-to-End

```
scheduler.py  runs every 10 seconds
│
└─► for each patient in DB:
        │
        └─► fake_generator.save_fake(db, patient_id)
                │
                ├─ 1. data_sources.get_source()
                │       └─► FakeVitalSource.get_vitals(patient_id)
                │               └─► { patient_id, heart_rate, spo2, temperature }
                │
                ├─ 2. crud.create_vitals(db, vital_data)
                │       └─► INSERT INTO vitals
                │
                ├─ 3. alert_engine.check_alerts(vital_record)
                │       └─► returns ["HIGH_HEART_RATE"] or [] etc.
                │
                ├─ 4. Auto-resolve:
                │       ├─ all normal  → UPDATE alerts SET status="RESOLVED" (all pending)
                │       └─ some still bad → RESOLVED only for types that normalised
                │
                ├─ 5. crud.create_alert(db, patient_id, vital_id, alert_type)
                │       ├─ De-dupe check: PENDING same type exists? → skip
                │       └─► INSERT INTO alerts (status="PENDING")
                │               └─► write_audit("CREATE", "alert")
                │
                └─ 6. whatsapp_notifier.send_alert_notification(...)
                        ├─► get_patient_recipients(db, patient_id)
                        │       └─► Query doctor + nurse phones
                        ├─► send_whatsapp_message(doctor_phone, alert_msg)
                        ├─► send_whatsapp_message(nurse_phone,  alert_msg)
                        └─► track_pending_response(alert_id, doctor_phone, ...)

After all patients processed:
└─► crud.escalate_stale_alerts(db, threshold_minutes=2)
        ├─► Find PENDING alerts older than 2 min
        ├─► UPDATE alerts SET status="ESCALATED"
        ├─► Find same-specialization doctors at same hospital
        ├─► INSERT INTO alert_escalations (one row per escalated doctor)
        ├─► INSERT INTO alert_notifications (notify each doctor + all hospital nurses)
        └─► whatsapp_notifier.send_escalation_notification(...)
```

---

## 10. Alert Engine — Logic & Thresholds

### Vital Thresholds

| Alert Type | Trigger Condition | Unit |
|------------|-------------------|------|
| `HIGH_HEART_RATE` | heart_rate **> 110** | bpm |
| `LOW_HEART_RATE` | heart_rate **< 50** | bpm |
| `LOW_SPO2` | spo2 **< 90** | % |
| `HIGH_TEMP` | temperature **> 101.0** | °F |
| `LOW_TEMP` | temperature **< 96.0** | °F |

### De-duplication Rule

Before creating a new alert, `crud.create_alert()` checks for an existing `PENDING` or `ESCALATED` alert of the **same type for the same patient**.  
If one exists:
- Updates `last_checked_at` (tracks that the vital is still abnormal)
- Returns `None` — no new DB row, no new WhatsApp message

This prevents alert floods when a vital stays abnormal across multiple 10-second scheduler cycles.

### Auto-Resolve Rule

Every scheduler cycle, after `check_alerts()`:
- If new vitals are **fully normal** → resolve ALL pending/escalated alerts for that patient
- If some vitals are still abnormal → resolve only the alert types that **have normalised**

Alerts clear automatically the moment the patient's vitals return to normal — no manual action needed.

---

## 11. Alert Escalation Flow

```
Alert created → status: PENDING
│
│  (2 minutes pass, no acknowledgement)
▼
scheduler.py  →  crud.escalate_stale_alerts()
│
├─► UPDATE alerts SET status = "ESCALATED"
│
├─► Find same-specialization available doctors at the patient's hospital
│       (excluding the already-assigned doctor)
│       Falls back to any available doctor at same hospital if no match
│
├─► INSERT INTO alert_escalations  (one row per found doctor)
│
├─► INSERT INTO alert_notifications
│       • Each found doctor's user account
│       • All nurses at the patient's hospital
│
└─► WhatsApp escalation messages sent to:
        • All same-specialization doctors' phones
        • Assigned doctor's phone

Doctor receives WhatsApp → replies "ACK 42"  (42 = alert_id)
│
└─► GREEN-API calls  POST /whatsapp/webhook
        ├─► typeWebhook = "incomingMessageReceived"
        ├─► Parse sender phone + message text
        ├─► regex match "ACK\s+(\d+)"  →  alert_id = 42
        ├─► UPDATE alerts SET status = "ACKNOWLEDGED", acknowledged_at = now()
        └─► WhatsApp confirmation reply sent back to doctor
```

### Alert Status Values

| Status | Meaning |
|--------|---------|
| `PENDING` | Alert fired, not yet seen or acted on |
| `ESCALATED` | PENDING > 2 min — escalated to additional doctors |
| `ACKNOWLEDGED` | Doctor acknowledged (UI button or WhatsApp ACK reply) |
| `RESOLVED` | Vitals returned to normal — auto-resolved by the scheduler |

---

## 12. WhatsApp Notification System

### Alert Message Format

When an alert fires, the assigned doctor and nurse receive a WhatsApp message containing:
- 🚨 Patient name and room number
- Alert type (e.g. `HIGH_HEART_RATE`)
- Exact reading that triggered it (HR bpm / SpO₂ % / Temp °F)
- Timestamp (UTC)
- Instruction: _Reply "ACK" or "ACK \<alert\_id\>" to acknowledge_

### Doctor ACK via WhatsApp

| Reply | Action |
|-------|--------|
| `ACK` | Acknowledge **all** pending alerts for this doctor's phone number |
| `ACK 42` | Acknowledge only alert #42 (granular) |
| `1`, `YES`, `OK`, `ACKNOWLEDGE` | Same as `ACK` (backward compatible) |

### How the Webhook Works

1. Doctor replies to the WhatsApp alert message
2. GREEN-API calls `POST /whatsapp/webhook` on the backend
3. Backend checks `typeWebhook = "incomingMessageReceived"`
4. Extracts sender phone and message text
5. Regex `ACK\s+(\d+)` matches granular ACK; plain `ACK` does bulk ACK
6. Looks up alert in DB + `_pending_responses` in-memory tracker
7. Sets `status = "ACKNOWLEDGED"` in PostgreSQL
8. Sends a confirmation WhatsApp reply back to the doctor

### Pause / Resume

Admins can halt WhatsApp alerts from the UI without touching the code or restarting services:
- `pause_alerts()` → writes `.whatsapp_paused` file inside `backend/`
- `is_alerts_paused()` → checks if that file exists before every send
- Both the backend API process and scheduler process share this file-based flag
- In-app alerts and escalation notifications continue working while paused

### Phone Number Format

Numbers must be in **international format without `+`** — e.g., Indian numbers: `919876543210`

---

## 13. WebSocket — Real-Time Live Updates

Endpoint: `ws://localhost:8000/ws/vitals`

### Mode 1 — Event-Driven (Redis available)

```
scheduler.py  →  [publishes to Redis channel "iot:vitals"]
                        │
                        ▼
_redis_vitals_subscriber()  (background asyncio task, started on FastAPI startup)
        └─► await pubsub.listen()
        └─► on message → manager.broadcast(data)
                        │
                        ▼
All connected browser clients receive the update instantly
```

### Mode 2 — Polling Fallback (no Redis)

- Each connected WebSocket client triggers a DB `SELECT` every 5 seconds
- Fetches latest vitals for all patients
- Sends a JSON array `[{patient_id, name, room, heart_rate, spo2, temperature, timestamp}]`

### `ConnectionManager` Class

Handles per-IP rate limiting and broadcast:

| Method | Purpose |
|--------|---------|
| `connect(ws, client_ip)` | Accept WS; enforce `WS_CONNECTION_LIMIT = 50` per IP |
| `disconnect(ws, client_ip)` | Remove from active list; decrement IP counter |
| `check_message_rate(client_ip)` | Enforce `WS_MESSAGES_PER_MINUTE = 120` |
| `broadcast(message)` | Send text to all active connections |

---

## 14. Authentication & JWT Flow

```
Browser                              FastAPI Backend
  │                                          │
  │  POST /auth/login                        │
  │  { username, password }                  │
  │─────────────────────────────────────────►│
  │                                          │  1. get_user_by_username()
  │                                          │  2. verify_password()  (bcrypt)
  │                                          │  3. create_access_token()
  │                                          │     { sub: username, role, exp: +30min }
  │                                          │  4. write_audit("LOGIN")
  │◄─────────── { access_token, role, username, doctor_id }
  │
  │  All subsequent requests:
  │  Authorization: Bearer <token>
  │─────────────────────────────────────────►│
  │                                          │  get_current_user():
  │                                          │    → jwt.decode(token, SECRET_KEY)
  │                                          │    → db.query(User).filter(username)
  │                                          │    → return User object
  │                                          │  require_role("ADMIN"):
  │                                          │    → check user.role in ["ADMIN"]
```

The frontend (`api.js`) automatically:
- Injects `Authorization: Bearer <token>` on every Axios request
- Calls `logout()` and redirects to `/login` on any `401` response

---

## 15. Role-Based Access Control

| Action | ADMIN | DOCTOR | NURSE |
|--------|:-----:|:------:|:-----:|
| View patients / vitals / alerts | ✅ | ✅ | ✅ |
| Add / edit patients | ✅ | ✅ | ✅ |
| Delete patients | ✅ | ✅ | ❌ |
| Add doctors | ✅ | ❌ | ❌ |
| Add nurses | ✅ | ✅ | ❌ |
| Delete doctors | ✅ | ❌ | ❌ |
| Delete nurses | ✅ | ✅ | ❌ |
| Acknowledge alerts | ✅ | ✅ | ❌ |
| Add hospitals | ✅ | ❌ | ❌ |
| Configure WhatsApp | ✅ | ❌ | ❌ |
| View audit logs | ✅ | ❌ | ❌ |
| View system status | ✅ | ❌ | ❌ |
| Patient chat | ✅ (any) | ✅ (assigned only) | ✅ (assigned only) |

> Chat access is enforced server-side by `_check_chat_access()` in `main.py` — raises `403` if the requesting doctor or nurse is not the one assigned to that specific patient.

---

## 16. API Reference

Base URL: `http://localhost:8000`

### Auth

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| POST | `/auth/login` | ❌ | Login — returns JWT + role |
| GET | `/auth/me` | ✅ | Get current user info |
| POST | `/auth/register` | ❌ | Register DOCTOR or NURSE user |
| POST | `/auth/register/doctor` | ❌ | Doctor self-registration → JWT |
| POST | `/auth/register/nurse` | ❌ | Nurse self-registration → JWT |

### Hospitals / Doctors / Nurses / Patients

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| GET / POST | `/hospitals` | POST: ADMIN | List / create hospitals |
| GET / POST | `/doctors` | POST: ADMIN | List / create doctors |
| DELETE | `/doctors/{id}` | ADMIN | Permanently delete doctor |
| GET | `/doctors/{id}/patients` | ❌ | Patients assigned to doctor |
| GET / POST | `/nurses` | POST: ADMIN/DOCTOR | List / create nurses |
| DELETE | `/nurses/{id}` | ADMIN/DOCTOR | Permanently delete nurse |
| GET / POST | `/patients` | POST: Any auth | List / create patients |
| DELETE | `/patients/{id}` | ADMIN/DOCTOR | Delete patient + all vitals |
| PATCH | `/patients/{id}/assign_doctor` | Any auth | Assign doctor to patient |
| PATCH | `/patients/{id}/assign_nurse` | Any auth | Assign nurse to patient |

### Vitals

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| POST | `/vitals` | ❌ | Submit a vitals reading |
| GET | `/vitals` | ❌ | List vitals (filter by `patient_id`, `doctor_id`) |
| GET | `/vitals/latest/{patient_id}` | ❌ | Latest vital for a patient |

### Alerts & Escalations

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| GET | `/alerts` | ❌ | List alerts (filter by `status`, `doctor_id`) |
| PATCH | `/alerts/{id}/acknowledge` | ADMIN/DOCTOR | Acknowledge an alert |
| GET | `/escalations` | ❌ | List escalation records |

### Notifications

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| GET | `/notifications/my` | Any auth | My unread/all notifications |
| PATCH | `/notifications/{id}/read` | Any auth | Mark one notification read |
| POST | `/notifications/read-all` | Any auth | Mark all notifications read |

### Dashboard, Chat, Audit, Health

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| GET | `/dashboard/stats` | ❌ | All stat card counts |
| GET/POST | `/patients/{id}/chat` | Assigned + Admin | Patient treatment chat |
| GET | `/audit-logs` | ADMIN | Full audit trail |
| GET | `/health/full` | ❌ | DB + Redis + WhatsApp health |
| GET | `/health/db` | ❌ | PostgreSQL connectivity |
| GET | `/health/redis` | ❌ | Redis connectivity |
| GET | `/health/whatsapp` | ❌ | GREEN-API connectivity |

### WhatsApp

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| GET | `/whatsapp/config` | ADMIN | Config + credentials status |
| POST | `/whatsapp/alerts/pause` | ADMIN | Pause all WhatsApp alerts |
| POST | `/whatsapp/alerts/resume` | ADMIN | Resume WhatsApp alerts |
| POST | `/whatsapp/webhook` | ❌ | GREEN-API incoming message handler |
| GET | `/whatsapp/logs` | ADMIN | Delivery log records |

Full interactive docs: **http://localhost:8000/docs**

---

## 17. Database Schema

### Table Relationships

```
Hospital ──────────────────────────────────────────────────┐
   │                                                        │
   ├──< Doctor ────────────────────────────────────────────┤
   │       │ (assigned_doctor FK)                          │
   ├──< Nurse ─────────────────────────────────────────────┤
   │       │ (assigned_nurse FK)                           │
   └───────┴────────────────────────────────────► Patient  │
                                                     │      │
                                                     ├──< Vitals
                                                     │
                                                     ├──< Alerts ──< AlertEscalations ──► Doctor
                                                     │         │
                                                     │         └──< AlertNotifications ──► User
                                                     │
                                                     └──< ChatMessages

User ──── (optional FK) ──► Doctor / Nurse
AuditLog ──── (optional FK) ──► User
WhatsAppLog ──── (optional FK) ──► Alert
```

### Key Database Indexes

| Table | Index Columns | Purpose |
|-------|---------------|---------|
| `vitals` | `(patient_id, timestamp DESC)` | Fast latest-vital lookups |
| `alerts` | `(status)` | Fast pending / escalated filter |
| `alerts` | `(patient_id)` | Fast per-patient alert queries |
| `whatsapp_logs` | `(idempotency_key)` | Prevent duplicate WhatsApp sends |
| `users` | `(username)` | Fast login lookups |

---

## 18. Frontend Pages

### Page Inventory

| Page | Route | Role | Key Features |
|------|-------|------|-------------|
| **Login** | `/login` | Public | Login form + self-register tabs for doctor/nurse |
| **Dashboard** | `/` | All | Stat cards, WebSocket live counter updates |
| **Patients** | `/patients` | All | CRUD table, assign doctor/nurse (hospital-filtered dropdowns), chat button |
| **Doctors** | `/doctors` | All | CRUD, optionally create login credentials at creation time |
| **Nurses** | `/nurses` | All | CRUD, optionally create login credentials at creation time |
| **Vitals** | `/vitals` | All | Patient selector, live Chart.js line charts — HR / SpO₂ / Temp |
| **Alerts** | `/alerts` | All | Alert table with status badges, acknowledge button (ADMIN/DOCTOR) |
| **Hospitals** | `/hospitals` | Admin | CRUD for hospital records |
| **WhatsApp Config** | `/whatsapp` | Admin | Status cards, pause/resume toggle, auto-populated recipients list |
| **System Status** | `/status` | Admin | Live DB/Redis/WhatsApp health, alert activity counts, quick API links |
| **Audit Logs** | `/audit-logs` | Admin | Paginated full action history |
| **Patient Chat** | via Patients | Assigned + Admin | Per-patient treatment notes, sender role badge |

### `api.js` — Axios API Layer

All Axios calls are centralised here. Key behaviours:

1. **JWT injection** — `Authorization: Bearer <token>` added to every request from `localStorage`
2. **Auto-logout** — any `401` response triggers `localStorage.removeItem('token')` and redirect to `/login`
3. **Base URL** — defaults to `http://localhost:8000`; override with `REACT_APP_API_URL` env var

---

## 19. Rate Limiting

| Endpoint | Limit | Per |
|----------|-------|-----|
| `POST /auth/login` | 5 requests/minute | IP address |
| All other endpoints | 100 requests/minute | IP address |

Returns `429 Too Many Requests` when exceeded.

**Storage priority:**
1. Redis (if `REDIS_URL` reachable) — shared limits across multiple backend instances
2. In-memory — single-instance fallback (no config needed — always works)

---

## 20. Audit Logging

Every significant action is written to `audit_logs` by `crud.write_audit()`:

| Action | Entity | When |
|--------|--------|------|
| `LOGIN` | `user` | Successful login |
| `REGISTER` | `user` | New user registered |
| `SELF_REGISTER` | `doctor` / `nurse` | Self-registration |
| `CREATE` | `hospital` / `doctor` / `nurse` / `patient` / `alert` | Record created |
| `DELETE` | `doctor` / `nurse` / `patient` | Hard delete |

View the full log at **http://localhost:3000/audit-logs** (admin) or `GET /audit-logs` (API).

---

## 21. Default Accounts

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | ADMIN |

> Create the admin account by running `python seed_db.py` in the backend, or by inserting directly into the `users` table.  
> Doctors and nurses can self-register from the Login page, or an admin can create them with login credentials from the Doctors / Nurses management pages.

---

## 22. Docker

Run the full stack with a single command — no Python or Node.js installation required:

```bash
docker compose up --build
```

| URL | Service |
|-----|---------|
| http://localhost | React frontend (via nginx) |
| http://localhost:8000 | FastAPI backend |
| http://localhost:8000/docs | Swagger interactive docs |

Stop all services:

```bash
docker compose down
```

> The Docker Compose file includes PostgreSQL and Redis containers. The backend reads environment variables from `backend/.env` — create it before running Docker.

---

## 23. ThingSpeak Integration (Future)

The codebase is already fully wired for real IoT sensor data — only the `.env` needs to change.

**To switch from fake vitals to a real ThingSpeak channel:**

1. Update `backend/.env`:
   ```env
   DATA_SOURCE=thingspeak
   THINGSPEAK_CHANNEL_ID=your_channel_id
   THINGSPEAK_READ_API_KEY=your_read_api_key
   THINGSPEAK_TEMP_UNIT=F
   ```

2. Expected ThingSpeak field mapping:
   - Field 1 → `heart_rate`
   - Field 2 → `spo2`
   - Field 3 → `temperature`

3. Restart the scheduler — `data_sources/get_source()` reads `DATA_SOURCE` at startup and returns a `ThingSpeakSource` instance automatically. **No other code changes needed.**

The `ThingSpeakSource` class uses `httpx` (already in `requirements.txt`) to call the ThingSpeak feeds API.

---

## License

MIT
