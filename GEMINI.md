# IoT Healthcare Patient Monitor - Project Context

## Project Overview
This project is a full-stack healthcare monitoring platform designed to track patient vitals in near real-time, detect risk conditions, and notify care teams. It helps hospitals and clinics automate vital capture, generate alerts, and provide visibility into patient states.

### Tech Stack
- **Frontend:** React 19, React Router v7, Axios, Chart.js (react-chartjs-2), react-scripts.
- **Backend:** Python (FastAPI), SQLAlchemy ORM, Pydantic, python-jose (JWT), bcrypt, slowapi (rate limiting), Redis client, httpx.
- **Database & Data:** PostgreSQL 16, Redis 7 (pub/sub & rate-limiter).
- **Infrastructure & Monitoring:** Docker + Docker Compose, Nginx, Prometheus, Grafana.

### Architecture
A modular monolith backend with a separate scheduler worker process.
- **React SPA** communicates with **FastAPI** (API + WebSocket).
- **PostgreSQL** handles persistent storage.
- **Redis** handles pub/sub for real-time vitals and rate limiting.
- **Scheduler Worker** writes vitals/alerts to DB and publishes vitals to Redis.

## Building and Running

### Prerequisites
- Python 3.12+
- Node.js 18+ and npm
- PostgreSQL and Redis
- Docker Desktop (Optional)

### Local Development Setup
1. **Backend:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   # Make sure to set SECRET_KEY in .env
   python seed_db.py
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
2. **Scheduler (runs in separate terminal):**
   ```bash
   cd backend
   source venv/bin/activate
   python scheduler.py
   ```
3. **Frontend (runs in separate terminal):**
   ```bash
   cd frontend
   npm install
   npm start
   ```

### Docker Compose
Create root `.env` from `.env.example`, then run:
```bash
docker compose up -d --build
```
- Access Frontend at `http://localhost`
- Access Backend API at `http://localhost:8000`

## Testing
- **Backend Tests:** 
  ```bash
  cd backend
  source venv/bin/activate
  pytest -q
  ```
- **WebSocket Auth Testing:** `python ws_auth_test.py` (use `python generate_test_tokens.py` to generate tokens).

## Development Conventions
- **Code Organization:** Backend is modularized into `main.py` (routes), `crud.py`, `models.py` (SQLAlchemy), `schemas.py` (Pydantic), `scheduler.py` (periodic worker). The frontend is organized using a `src/pages/` pattern for features.
- **Authentication:** JWT-based authentication with roles (`ADMIN`, `DOCTOR`, `NURSE`). WebSockets are authenticated via JWT tokens passed in the query string (`?token=...`).
- **Dependencies:** Managed via `requirements.txt` for the backend and `package.json` for the frontend.
- **Testing:** Include pytest-based tests for backend changes. Maintain `backend/tests/` to ensure production readiness.
- **Configuration:** Environment variables are used to manage secrets and system configs (via `.env` files).
