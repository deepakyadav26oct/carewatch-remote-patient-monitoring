# CareWatch – AI-Assisted Remote Patient Monitoring (AS-03)

> **Simulated data only. Decision support, not a medical device. Alerts flag readings for clinical review and never replace medical judgment.**

```
Simulator ──► FastAPI ──► PostgreSQL
                │  └──► Detection (threshold · baseline z-score · trend · Isolation Forest)
                └──► WebSocket ──► Dashboard (frontend/index.html)
```

## Folders
| Path | What it is |
|---|---|
| `backend/` | FastAPI app (`app/main.py`), detection engine, simulator, auth, tests, Dockerfile |
| `database/schema.sql` | PostgreSQL tables + demo seed (optional: the API creates tables itself on startup) |
| `frontend/` | `index.html` + `config.js` (set `CAREWATCH_API` to your API URL; empty = built-in demo mode) |
| `render.yaml` | One-click Render blueprint (API + PostgreSQL) |
| `docker-compose.yml` | Local run with PostgreSQL |

## Run locally
```bash
# Option A: Docker (API + PostgreSQL)
docker compose up --build            # API on http://localhost:8000/docs

# Option B: plain Python (uses SQLite automatically)
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000/docs
pytest                               # 10 tests

# Frontend
cd frontend && python -m http.server 8080    # open http://localhost:8080
# edit frontend/config.js ->  window.CAREWATCH_API = "http://localhost:8000";
```
Demo logins (password `demo123`): `dr.rao` (physician), `nurse.sen` (nurse, read-only), `admin`. **Change `DEMO_PASSWORD` before any real use.**

## Endpoints (JWT required except `/health`, `/auth/login`, `/vitals`)
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | form: username, password. Rate-limited |
| GET | `/auth/me` | current user |
| GET | `/patients` | latest vitals, risk, active alert count |
| GET | `/patients/{id}` | profile, thresholds, risk factors (audit-logged) |
| GET | `/patients/{id}/vitals?hours=&limit=` | history for charts |
| POST | `/vitals` | ingest a reading; header `X-API-Key: SIMULATOR_KEY` |
| GET | `/alerts?status=&severity=&patient_id=` | alerts center |
| POST | `/alerts/{id}/acknowledge` | physician / admin only |
| GET | `/model/stats` | readings processed, alerts per layer |
| POST | `/simulate/deteriorate/{id}` | physician / admin; needs `SIMULATE=true` |
| WS | `/ws/live?token=` | live readings, risk updates, alerts |

## Detection layers
1. **Threshold** – outside configurable range (per-patient overrides in `patients.thresholds`).
2. **Baseline anomaly** – last 3 readings vs the patient's own previous 35 (|z| > 3).
3. **Trend** – slope of last 12 readings (e.g. steady SpO₂ fall).
4. **ML** – per-patient Isolation Forest on a rolling window, retrained every 30 readings.

Risk score 0–100: stable < 15, watch 15–39, high ≥ 40. Same alert is not repeated within 60 s; alerts auto-resolve once readings normalise.

## Environment variables
`DATABASE_URL`, `JWT_SECRET`, `SIMULATOR_KEY`, `FRONTEND_URL` (CORS, comma-separated), `SIMULATE` (true/false), `TOKEN_MINUTES`, `RETAIN_HOURS`, `DEMO_PASSWORD`. See `backend/.env.example`.

## Security notes
bcrypt password hashes, short-lived JWT, role-based access, audit log (login, patient views, acknowledgements), CORS restricted via `FRONTEND_URL`, input validation (Pydantic), login rate limit. Before real use you would also need TLS everywhere, secret management, proper user management and a clinical/regulatory review.
