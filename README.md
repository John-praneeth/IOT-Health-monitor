# IoT Healthcare Patient Monitor

A full-stack healthcare monitoring platform for tracking patient vitals in near real time, detecting risk conditions, and notifying care teams.

## 1. Project Overview

This project helps hospitals and clinics monitor patient health signals (heart rate, SpO2, temperature) continuously and respond faster to abnormalities.

### Problem It Solves

Manual or delayed monitoring can increase response time during critical events. This system automates:
- Vital capture and trend visibility
- Alert generation for abnormal readings
- Escalation of unacknowledged alerts
- Team notifications and acknowledgement workflows

### Target Users

- Hospital administrators
- Doctors
- Nurses
- Clinical operations teams

### Key Outcomes

- Faster alerting and triage
- Better visibility into current patient state
- Auditability of actions and access

## 2. Tech Stack

### Frontend

- React 19
- React Router v7
- Axios
- Chart.js + react-chartjs-2
- react-scripts (CRA build/runtime)

### Backend

- FastAPI
- SQLAlchemy ORM
- Pydantic
- python-jose (JWT)
- bcrypt
- slowapi (rate limiting)
- Redis client
- httpx

### Data and Infrastructure

- PostgreSQL 16
- Redis 7 (pub/sub + rate-limiter backend)
- Docker + Docker Compose
- Nginx (frontend container)

### Monitoring

- Prometheus configuration included
- Grafana provisioning/dashboards included
- Backend `/metrics` endpoint available

## 3. Architecture

The system uses a modular monolith backend plus a separate scheduler worker process.

```text
[React SPA] -> [FastAPI API + WebSocket] -> [PostgreSQL]
                           |
                           -> [Redis pub/sub + rate limit storage]

[Scheduler Worker] -> writes vitals/alerts to DB
[Scheduler Worker] -> publishes vitals snapshots to Redis channel
[FastAPI WS] -> broadcasts to connected authenticated clients
```

### High-Level Flow

1. Scheduler generates/ingests vitals for each patient every 10 seconds.
2. Backend persists vitals and evaluates alert rules.
3. Pending alerts escalate after threshold when not acknowledged.
4. Scheduler publishes vitals snapshots to Redis channel `iot:vitals`.
5. Backend WebSocket endpoint `/ws/vitals` broadcasts updates to authenticated clients.
6. Frontend dashboards consume API + WebSocket streams.

### API Structure

- Auth and user context (`/auth/*`)
- Entity management (`/hospitals`, `/doctors`, `/nurses`, `/patients`)
- Monitoring data (`/vitals`, `/alerts`, `/dashboard/stats`)
- Operations (`/notifications/*`, `/audit-logs`, `/whatsapp/*`, `/health/*`, `/metrics`)

### Authentication and Real-Time

- JWT-based auth with role checks (`ADMIN`, `DOCTOR`, `NURSE`)
- WebSocket authentication enforced via JWT token
- Token accepted via query string (`?token=...`) and bearer header handling in backend

## 4. Folder Structure

```text
IoT_healthCare/
├── backend/
│   ├── main.py
│   ├── auth.py
│   ├── crud.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── scheduler.py
│   ├── fake_generator.py
│   ├── alert_engine.py
│   ├── whatsapp_notifier.py
│   ├── rate_limiter.py
│   ├── exception_handlers.py
│   ├── json_logger.py
│   ├── seed_db.py
│   ├── init_db.sql
│   ├── migrations/
│   ├── data_sources/
│   │   ├── base.py
│   │   ├── fake_source.py
│   │   └── thingspeak_source.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── api.js
│   │   ├── pages/
│   │   └── styles/
│   ├── public/
│   ├── nginx.conf
│   ├── package.json
│   └── Dockerfile
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── docker-compose.yml
├── ws_auth_test.py
└── generate_test_tokens.py
```

### Key Components

- `backend/main.py`: API routes, health/metrics endpoints, WebSocket endpoint
- `backend/scheduler.py`: periodic vitals generation + escalation worker
- `backend/data_sources/`: pluggable source abstraction (`fake`, `thingspeak`)
- `frontend/src/pages/`: feature pages for operations and monitoring
- `ws_auth_test.py`: terminal-based WebSocket auth verification tool
- `generate_test_tokens.py`: helper for valid/expired JWT generation

## 5. Installation and Setup

## Prerequisites

- Python 3.12+ recommended
- Node.js 18+ and npm
- PostgreSQL
- Redis
- Optional: Docker Desktop

## Option A: Local Development

### 1) Clone

```bash
git clone <your-repo-url>
cd IoT_healthCare
```

### 2) Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3) Database seed (admin user)

```bash
cd backend
source venv/bin/activate
python seed_db.py
```

### 4) Frontend setup

```bash
cd frontend
npm install
```

### 5) Run services (three terminals)

Terminal 1:
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

Terminal 2:
```bash
cd backend
source venv/bin/activate
python scheduler.py
```

Terminal 3:
```bash
cd frontend
npm start
```

### 6) Access

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

## Option B: Docker Compose

Create root `.env` from `.env.example`, then run:

```bash
docker compose up -d --build
```

Access:
- Frontend (Nginx): `http://localhost`
- Backend API: `http://localhost:8000`

## 6. Environment Variables

Create `backend/.env` from `backend/.env.example`.

For Docker Compose, create root `.env` from `.env.example` for required container secrets.

### Required

```env
DATABASE_URL=postgresql://user:password@localhost:5432/patient_monitor
SECRET_KEY=<long-random-secret-at-least-32-chars>
ADMIN_PASSWORD=<strong-admin-password>
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATA_SOURCE=fake
CORS_ORIGINS=http://localhost,http://localhost:3000,http://localhost:5173
```

### Common Optional

```env
REDIS_URL=redis://localhost:6379/0
REDIS_REQUIRED=false
WS_CONNECTION_LIMIT=50
WS_MESSAGES_PER_MINUTE=120
WS_BROADCAST_MODE=event
SLA_THRESHOLD_SECONDS=300
MAX_ALERTS_PER_MINUTE=20
VITALS_RETENTION_DAYS=30
ENVIRONMENT=development
SERVICE_NAME=iot-healthcare
LOG_LEVEL=INFO
```

### ThingSpeak (if using real IoT source)

```env
DATA_SOURCE=thingspeak
THINGSPEAK_CHANNEL_ID=
THINGSPEAK_READ_API_KEY=
THINGSPEAK_TEMP_UNIT=F
THINGSPEAK_STALE_SECONDS=120
```

You can switch between `fake` and `thingspeak` at runtime from **Admin → System Status → Vitals Data Source** without restarting services.  
API endpoints:
- `GET /vitals/source` (admin)
- `PUT /vitals/source` (admin)

### WhatsApp (GREEN-API)

```env
WHATSAPP_ENABLED=true
GREEN_API_ID=your_id_instance
GREEN_API_TOKEN=your_api_token_instance
WHATSAPP_RECIPIENTS=919876543210,911234567890
```

### Frontend API Routing (production-friendly)

Frontend now defaults to same-origin proxy paths:

```env
REACT_APP_API_BASE_URL=/api
REACT_APP_WS_BASE_URL=
```

Set these in root `.env` before `docker compose up --build` if your API/WS endpoints differ.

### Repository Cleanup Note

Keep `backend/tests/` in the repository. Tests are part of production readiness and release safety; they are not deployed in runtime images.

## 7. Features

## Authentication and Access Control

- JWT authentication
- Role-based authorization (`ADMIN`, `DOCTOR`, `NURSE`)
- Admin-only staff registration endpoint
- Doctor and nurse self-registration flows

## Clinical Operations

- Hospital, doctor, nurse, and patient management
- Doctor/nurse assignment to patients
- Per-patient clinical chat thread
- Audit log tracking

## Real-Time Monitoring

- Continuous vitals generation/ingestion via scheduler
- Threshold-based alert engine
- Alert acknowledgement and escalation pipeline
- Authenticated WebSocket vitals stream
- Dashboard stats and patient vitals views

## Notification and Reliability

- WhatsApp notifications via GREEN-API
- Pause/resume alert delivery
- Alert acknowledgement via webhook processing
- Notification center endpoints

## Observability and Guardrails

- Health endpoints (`/health`, `/health/full`, service checks)
- Prometheus-compatible `/metrics`
- Rate limiting for login and API traffic
- Structured JSON logging + request IDs

## 8. API Documentation

Interactive API docs:
- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`

### Key Endpoints

| Method | Route | Purpose |
|---|---|---|
| POST | `/auth/login` | User login and JWT issuance |
| GET | `/auth/me` | Current authenticated user |
| POST | `/auth/register` | Admin-only user creation |
| POST | `/auth/register/doctor` | Doctor self-registration |
| POST | `/auth/register/nurse` | Nurse self-registration |
| GET | `/patients` | List patients |
| POST | `/patients` | Create patient |
| PATCH | `/patients/{id}/assign_doctor` | Assign doctor |
| PATCH | `/patients/{id}/assign_nurse` | Assign nurse |
| GET | `/vitals` | List vitals |
| GET | `/vitals/latest/{patient_id}` | Latest patient vital |
| GET | `/alerts` | List alerts |
| PATCH | `/alerts/{alert_id}/acknowledge` | Acknowledge alert |
| GET | `/dashboard/stats` | Dashboard aggregate counts |
| GET | `/patients/{id}/chat` | Fetch patient chat |
| POST | `/patients/{id}/chat` | Add patient chat message |
| GET | `/audit-logs` | Audit records |
| GET | `/notifications/my` | User notifications |
| PATCH | `/notifications/{id}/read` | Mark one notification read |
| POST | `/notifications/read-all` | Mark all notifications read |
| GET | `/whatsapp/config` | WhatsApp runtime config |
| POST | `/whatsapp/alerts/pause` | Pause WhatsApp alerts |
| POST | `/whatsapp/alerts/resume` | Resume WhatsApp alerts |
| POST | `/whatsapp/webhook` | Inbound WhatsApp webhook |
| GET | `/health/full` | Composite service health |
| GET | `/metrics` | Prometheus scrape endpoint |
| WS | `/ws/vitals` | Authenticated real-time vitals stream |

## 9. Authentication Flow

1. User logs in via `POST /auth/login` with username/password.
2. Backend validates credentials and returns a JWT.
3. Frontend stores token and includes `Authorization: Bearer <token>` for API calls.
4. Protected endpoints enforce `require_auth` and `require_role` checks.
5. WebSocket clients connect to `/ws/vitals` with token query param (`?token=...`).
6. Backend decodes JWT and resolves user by `sub` claim before allowing stream access.

## 10. Scalability Considerations

Current architecture is designed to scale incrementally:

- Modular backend boundaries (`auth`, `crud`, `data_sources`, `notifier`, `scheduler`)
- Separate worker process (`scheduler.py`) already decouples background workloads
- Redis-backed pub/sub for real-time fan-out
- Configurable WebSocket and rate-limit controls via environment variables
- PostgreSQL as primary system of record with migration scripts included
- Monitoring endpoint for metrics-based autoscaling signals

Potential next scaling steps:
- Move scheduler and notifier into dedicated worker services/queues
- Introduce read replicas for analytics-heavy queries
- Add caching layer for frequently read dashboard aggregates
- Front API gateway and load balancer for horizontal API scale
- Add async task queue (Celery/RQ) for notification retries and heavy jobs

## 11. Testing

## Automated

Backend tests:
```bash
cd backend
source venv/bin/activate
pytest -q
```

WebSocket auth security probe:
```bash
# Optional helper to print valid/expired tokens
python generate_test_tokens.py

# Probe scenarios: valid/missing/invalid/expired token
python ws_auth_test.py
```

## Manual

- Log in as admin and create clinical entities
- Start scheduler and verify vitals are generated every 10 seconds
- Confirm abnormal vitals create alerts
- Confirm acknowledgement updates alert status
- Verify dashboard updates and health endpoints
- Validate WhatsApp config and webhook integration (if credentials configured)

## 12. Deployment

## Local Production-Like Deployment

## 13. Runtime Troubleshooting (Live Updates / Docker Logs)

If you still see live vitals/alerts even when you did not run `docker compose up`, one of these is already running in the background:
- local backend (`uvicorn main:app`)
- local scheduler (`python scheduler.py`)
- previously started Docker containers

Use these checks:

```bash
docker compose ps
lsof -nP -iTCP:8000 -sTCP:LISTEN
ps -ax | grep -E "uvicorn main:app|python scheduler.py" | grep -v grep
```

If you run `docker compose up` without `-d`, logs from backend/scheduler are expected in the terminal (this includes generated vitals and alert events).

For normal use, prefer detached mode:

```bash
docker compose up -d --build
docker compose logs -f backend scheduler
```

If backend/scheduler repeatedly fail with PostgreSQL password errors after old volume reuse, either:

```bash
# Option A: reset postgres password inside DB container
docker exec iot_healthcare-db-1 sh -lc "psql -U postgres -d postgres -c \"ALTER USER postgres WITH PASSWORD '${POSTGRES_PASSWORD}';\""

# Option B: recreate all compose volumes (fresh DB)
docker compose down -v
docker compose up -d --build
```

Use Docker Compose:
```bash
docker compose up -d --build
```

### Hardened Production Deployment (recommended)

Use the production override so database/redis/backend are not exposed on host ports.

1) Create production env file:

```bash
cp .env.production.example .env
```

2) Set strong values in `.env`:
- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `CORS_ORIGINS` (your real domain)
- `GREEN_API_ID` / `GREEN_API_TOKEN` (if WhatsApp is enabled)

3) Deploy with base + production override:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

4) Validate:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -sS http://localhost/ -I
curl -sS http://localhost/api/health
```

5) View logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend scheduler frontend
```

This production mode additionally enables:
- internal-only DB/Redis/API ports
- secure auth cookie flag (`COOKIE_SECURE=true`)
- no-new-privileges + dropped Linux capabilities for app containers
- basic container log rotation

This launches:
- PostgreSQL
- Redis
- FastAPI backend
- Scheduler worker
- Frontend Nginx
- Backup sidecar

## Cloud Deployment Patterns

This codebase is container-ready and can be deployed on:
- AWS ECS/Fargate
- Azure Container Apps
- Google Cloud Run (split services)
- Render/Railway/Fly.io (multi-service setup)

Recommended production additions:
- Managed PostgreSQL and Redis
- TLS termination and secret manager
- CI/CD pipeline for build/test/deploy
- Centralized logs and metrics dashboards

## 13. Future Improvements

- Add frontend automated test suite (unit + E2E)
- Add refresh tokens and token revocation strategy
- Add tenant isolation for multi-hospital enterprise use
- Add asynchronous job queue for resilient notification retries
- Add stronger API versioning and backward compatibility policy
- Improve API base URL/config strategy for multi-environment frontend builds
- Add more granular authorization policies (resource-level RBAC)

## 14. Contributing

1. Fork the repository.
2. Create a feature branch.
3. Make focused changes with tests.
4. Run backend tests and smoke checks.
5. Open a pull request with clear description and impact.

Recommended before PR:
```bash
cd backend && pytest -q
cd frontend && npm run build
```

## 15. License

This project currently has no explicit license file.

Add a `LICENSE` file (for example MIT, Apache-2.0, or proprietary) before public/open-source distribution.
