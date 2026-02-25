# 🏥 IoT Healthcare Patient Monitor — v4.0

A **production-grade, real-time patient vital-sign monitoring system** built with **FastAPI + React + PostgreSQL**.

> **v4.0 Highlights** — Freelancer doctor self-registration · nurse self-registration · specialization-based alert escalation · real-time notification system · per-patient treatment chat · hospital-based management · RBAC · Docker Compose.

---

## 📑 Table of Contents

1. [Architecture](#architecture)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [Quick Start (Docker)](#quick-start-docker)
5. [Quick Start (Local)](#quick-start-local)
6. [API Reference](#api-reference)
7. [Authentication & Roles](#authentication--roles)
8. [Data Source Abstraction](#data-source-abstraction)
9. [Alert Engine & Escalation](#alert-engine--escalation)
10. [Frontend Pages](#frontend-pages)
11. [Testing](#testing)
12. [Project Structure](#project-structure)
13. [Environment Variables](#environment-variables)
14. [Database Schema](#database-schema)
15. [Contributing](#contributing)

---

## Architecture

```
┌──────────────┐       REST / WS        ┌──────────────────────┐
│   React SPA  │ ◄────────────────────►  │    FastAPI Backend   │
│  (port 80)   │                         │    (port 8000)       │
└──────────────┘                         │  • JWT Auth + RBAC   │
                                         │  • CORS              │
                                         │  • Notifications     │
                                         │  • Audit Logging     │
                                         └──────────┬───────────┘
                                                    │
                                         ┌──────────▼───────────┐
                                         │    PostgreSQL 16     │
                                         │  patient_monitor DB  │
                                         └──────────┬───────────┘
                                                    │
                                         ┌──────────▼───────────┐
                                         │   Scheduler (10 s)   │
                                         │  Data Source → Vitals │
                                         │  Alert Engine → Alerts│
                                         │  Escalation (2 min)  │
                                         └───────────────────────┘
```

---

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **JWT Auth + RBAC** | Role-based access control (ADMIN, DOCTOR, NURSE). Protected endpoints. |
| 2 | **Doctor Self-Registration** | Freelancer or hospital doctors register themselves with specialization. |
| 3 | **Nurse Self-Registration** | Nurses register with department and hospital affiliation. |
| 4 | **Specialization-Based Escalation** | Unacknowledged alerts (2 min) escalate to same-specialty doctors + hospital nurses. |
| 5 | **Notification System** | Bell icon with unread count. Escalated alerts create per-user notifications. |
| 6 | **Per-Patient Chat** | Real-time treatment discussion thread per patient (doctors, nurses, admin). |
| 7 | **Hospital Management** | ADMIN can manage hospitals. Staff self-register under hospitals. |
| 8 | **Dashboard Stats** | At-a-glance stats: patients, doctors, nurses, hospitals, alert breakdown. |
| 9 | **Duplicate Alert Prevention** | Same `alert_type` + `patient_id` won't re-fire while PENDING. |
| 10 | **Data Source Abstraction** | Swap between `fake` (random) and `thingspeak` (IoT) via env var. |
| 11 | **Docker Production Setup** | `docker compose up --build` — Postgres + Backend + Scheduler + Frontend. |
| 12 | **Chart.js Trend Charts** | Interactive line charts for HR, SpO₂, and Temperature per patient. |
| 13 | **Audit Logging** | Every action logged. ADMIN-only audit log viewer with entity filter. |
| 14 | **Pytest Test Suite** | Alert engine, auth flow, and RBAC tests. |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic v2 |
| **Frontend** | React 19, React Router v7, Axios, Chart.js + react-chartjs-2 |
| **Database** | PostgreSQL 16 |
| **Auth** | bcrypt (password hashing), python-jose (JWT) |
| **Testing** | pytest, FastAPI TestClient, SQLite |
| **DevOps** | Docker, Docker Compose, nginx |

---

## Quick Start (Docker)

```bash
git clone <your-repo-url>
cd IoT_healthCare
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

**Default admin credentials**: `admin` / `admin123`

---

## Quick Start (Local)

### Prerequisites
- Python 3.12+ & pip
- Node.js 18+ & npm
- PostgreSQL 14+

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create database and seed data
createdb patient_monitor
psql -U postgres -d patient_monitor -f init_db.sql
```

Create `backend/.env`:
```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/patient_monitor
SECRET_KEY=change-me-use-openssl-rand-hex-32
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATA_SOURCE=fake
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

```bash
# Start API server
uvicorn main:app --host 0.0.0.0 --port 8000

# Start scheduler (separate terminal)
python scheduler.py
```

### 2. Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm start
```

Open **http://localhost:3000** — login with `admin` / `admin123`.

---

## API Reference

### Health
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | — | API info |
| GET | `/health` | — | Health check |

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | — | Staff registration (non-admin roles) |
| POST | `/auth/register/doctor` | — | Doctor self-registration → JWT |
| POST | `/auth/register/nurse` | — | Nurse self-registration → JWT |
| POST | `/auth/login` | — | Login → JWT |
| GET | `/auth/me` | Bearer | Current user profile |

### Hospitals
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/hospitals` | — | List hospitals |
| POST | `/hospitals` | ADMIN | Create hospital |

### Doctors
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/doctors` | — | List (filter: `?specialization=`, `?hospital_id=`) |
| POST | `/doctors` | ADMIN | Create doctor |
| GET | `/doctors/{id}` | — | Get by ID |
| DELETE | `/doctors/{id}` | ADMIN | Delete |
| GET | `/doctors/{id}/patients` | — | Doctor's patients |

### Nurses
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/nurses` | — | List (filter: `?hospital_id=`) |
| POST | `/nurses` | ADMIN, DOCTOR | Create nurse |
| GET | `/nurses/{id}` | — | Get by ID |
| DELETE | `/nurses/{id}` | ADMIN, DOCTOR | Delete |
| GET | `/nurses/{id}/patients` | — | Nurse's patients |

### Patients
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/patients` | — | List (filter: `?doctor_id=`, `?nurse_id=`) |
| POST | `/patients` | ADMIN, DOCTOR, NURSE | Create patient |
| GET | `/patients/{id}` | — | Get by ID |
| DELETE | `/patients/{id}` | ADMIN, DOCTOR | Delete |
| PATCH | `/patients/{id}/assign_doctor` | ADMIN, DOCTOR, NURSE | Assign doctor |
| PATCH | `/patients/{id}/assign_nurse` | ADMIN, DOCTOR, NURSE | Assign nurse |

### Vitals
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/vitals` | — | List (filter: `?patient_id=`, `?doctor_id=`, `?limit=`) |
| POST | `/vitals` | — | Create vital reading |
| GET | `/vitals/latest/{patient_id}` | — | Latest vital for patient |
| WS | `/ws/vitals` | — | WebSocket: streams all patients every 5s |

### Alerts & Escalations
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/alerts` | — | List (filter: `?status=`, `?doctor_id=`) |
| PATCH | `/alerts/{id}/acknowledge` | ADMIN, DOCTOR | Acknowledge alert |
| GET | `/escalations` | — | Escalation records |

### Notifications
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/notifications/my` | Bearer | My notifications (`?unread_only=true`) |
| PATCH | `/notifications/{id}/read` | Bearer | Mark one as read |
| POST | `/notifications/read-all` | Bearer | Mark all as read |

### Chat
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/patients/{id}/chat` | Bearer | Get chat messages |
| POST | `/patients/{id}/chat` | Bearer | Send chat message |

### Dashboard & Audit
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/dashboard/stats` | — | Dashboard statistics |
| GET | `/audit-logs` | ADMIN | Audit trail (filter: `?entity=`, `?limit=`) |

---

## Authentication & Roles

| Role | Permissions |
|------|-------------|
| **ADMIN** | Full access — manage hospitals, doctors, nurses, patients, audit logs |
| **DOCTOR** | Manage patients & nurses, acknowledge alerts, chat, notifications |
| **NURSE** | Enroll patients, assign doctors/nurses, chat, notifications |

### Self-Registration
- **Doctors**: `POST /auth/register/doctor` — provide name, specialization, hospital, freelancer status
- **Nurses**: `POST /auth/register/nurse` — provide name, department, hospital

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

---

## Data Source Abstraction

Set `DATA_SOURCE` environment variable:

| Value | Source | Description |
|-------|--------|-------------|
| `fake` (default) | `FakeSource` | Random medically plausible vitals |
| `thingspeak` | `ThingSpeakSource` | Reads from a ThingSpeak IoT channel |

For ThingSpeak, also set `THINGSPEAK_CHANNEL_ID` and `THINGSPEAK_READ_API_KEY`.

**Adding a custom source**: Create a class in `backend/data_sources/` extending `VitalSource` with `get_vitals(patient_id) → dict`.

---

## Alert Engine & Escalation

### Thresholds
| Alert Type | Condition |
|------------|-----------|
| `HIGH_HEART_RATE` | heart_rate > 110 bpm |
| `LOW_HEART_RATE` | heart_rate < 50 bpm |
| `LOW_SPO2` | spo2 < 90% |
| `HIGH_TEMP` | temperature > 101.0°F |
| `LOW_TEMP` | temperature < 96.0°F |

### Escalation Workflow
1. Alert created → `PENDING`
2. 2 minutes unacknowledged → `ESCALATED`
3. Notifications sent to **same-specialization doctors** + **hospital nurses**
4. Escalation records created in `alert_escalations`
5. Staff acknowledge → `ACKNOWLEDGED`

---

## Frontend Pages

| Page | Route | Access | Description |
|------|-------|--------|-------------|
| **Login** | `/login` | Public | Sign in, doctor registration, nurse registration (3 tabs) |
| **Dashboard** | `/` | All | Stats cards, notification bell with unread count |
| **Patients** | `/patients` | All | CRUD, assign doctor/nurse, vitals modal, chat |
| **Doctors** | `/doctors` | All | List with specialization filter, freelancer badge |
| **Nurses** | `/nurses` | All | List with department badges |
| **Vitals** | `/vitals` | All | Vitals log with trend charts |
| **Alerts** | `/alerts` | All | Alert list, acknowledge, escalation status |
| **Hospitals** | `/hospitals` | ADMIN | Hospital management |
| **Audit Logs** | `/audit-logs` | ADMIN | Action audit trail with entity filter |

---

## Testing

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

| File | Description |
|------|-------------|
| `test_alert_engine.py` | Threshold checks: normal, high/low HR, SpO₂, temp, multi-alert |
| `test_auth.py` | Register, login, `/auth/me`, duplicate username, admin block, protected endpoints |
| `test_role_permissions.py` | Admin audit access, doctor/nurse 403, public endpoints accessible |

---

## Project Structure

```
IoT_healthCare/
├── docker-compose.yml
├── README.md
├── .gitignore
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env                          # Local env variables (git-ignored)
│   ├── main.py                       # FastAPI app + all routes
│   ├── auth.py                       # JWT auth, password hashing, RBAC
│   ├── models.py                     # SQLAlchemy ORM models (11 tables)
│   ├── schemas.py                    # Pydantic v2 request/response schemas
│   ├── crud.py                       # Database operations, escalation, notifications
│   ├── database.py                   # Engine, session, Base
│   ├── alert_engine.py               # Threshold-based alert evaluation
│   ├── fake_generator.py             # Vitals generation via data source
│   ├── scheduler.py                  # Periodic vitals + escalation runner
│   ├── init_db.sql                   # Full schema + seed data
│   ├── data_sources/                 # Pluggable vital-sign providers
│   │   ├── __init__.py               # Factory: get_source()
│   │   ├── base.py                   # Abstract VitalSource interface
│   │   ├── fake_source.py            # Random generator
│   │   └── thingspeak_source.py      # ThingSpeak IoT channel reader
│   └── tests/
│       ├── conftest.py               # Fixtures (SQLite test DB, TestClient)
│       ├── test_alert_engine.py      # Alert threshold unit tests
│       ├── test_auth.py              # Auth integration tests
│       └── test_role_permissions.py  # RBAC permission tests
│
└── frontend/
    ├── Dockerfile
    ├── nginx.conf                    # Reverse proxy to backend
    ├── package.json
    ├── public/index.html
    └── src/
        ├── api.js                    # Axios client + token interceptor
        ├── App.js                    # Router, auth guard, sidebar
        ├── App.css                   # Dark-themed styles
        ├── index.js
        └── pages/
            ├── Login.js              # Sign in + self-registration tabs
            ├── Dashboard.js          # Stats + notification bell
            ├── Patients.js           # Patient management + chat
            ├── Doctors.js            # Doctor list + specialization filter
            ├── Nurses.js             # Nurse list + department badges
            ├── Vitals.js             # Vitals log + Chart.js trends
            ├── Alerts.js             # Alert management
            ├── Hospitals.js          # Hospital CRUD (admin)
            ├── AuditLogs.js          # Audit trail (admin)
            └── PatientChat.js        # Treatment chat component
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | *(required)* | PostgreSQL connection string |
| `SECRET_KEY` | `iot-healthcare-super-secret-key-change-in-production` | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `DATA_SOURCE` | `fake` | Vital source: `fake` or `thingspeak` |
| `CORS_ORIGINS` | `http://localhost,http://localhost:3000,http://localhost:5173` | Allowed origins |
| `THINGSPEAK_CHANNEL_ID` | *(optional)* | ThingSpeak channel ID |
| `THINGSPEAK_READ_API_KEY` | *(optional)* | ThingSpeak read API key |

---

## Database Schema

### Tables (11)

| Table | Purpose |
|-------|---------|
| `hospitals` | Hospital registry |
| `doctors` | Doctor profiles (specialization, freelancer status) |
| `nurses` | Nurse profiles (department) |
| `patients` | Patient records with doctor/nurse/hospital assignments |
| `vitals` | Time-series vital signs |
| `alerts` | Threshold-triggered alerts (PENDING → ESCALATED → ACKNOWLEDGED) |
| `users` | Auth accounts with roles (ADMIN, DOCTOR, NURSE) |
| `alert_escalations` | Escalation records (which doctor, when) |
| `alert_notifications` | Per-user notifications for escalated alerts |
| `audit_logs` | Action audit trail |
| `chat_messages` | Per-patient treatment chat |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write tests for new functionality
4. Ensure all tests pass: `python -m pytest tests/ -v`
5. Submit a pull request

---

**Built with ❤️ for healthcare IoT monitoring.**
