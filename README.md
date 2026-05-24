# Breathe ESG — Emissions Data Ingestion & Review Platform

A Django REST + React prototype for Breathe ESG's Tech Intern Assignment.

## Live Demo

> Coming soon — see submission email for deployed URL

**Demo credentials:**
- Analyst: `analyst / demo1234`
- Admin: `admin / admin1234`

---

## What this does

Ingests emission activity data from three source types, normalizes it into a unified data model, and provides an analyst review dashboard where records can be flagged, approved, and tracked before audit lock.

| Source | Format | Scope |
|--------|--------|-------|
| SAP MB51 fuel movements | CSV flat file | Scope 1 |
| Utility portal billing export | CSV portal download | Scope 2 |
| Concur expense report | CSV expense export | Scope 3 |

---

## Quick start (local)

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_demo
python manage.py runserver 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Architecture

```
backend/                 # Django REST API
  breathe_esg/           # Django project settings
  emissions/
    models.py            # Core data models
    views.py             # API views
    parsers/
      sap_parser.py      # SAP MB51 CSV parser
      utility_parser.py  # Utility portal CSV parser
      travel_parser.py   # Concur expense CSV parser
    normalizers/
      emission_factors.py  # DEFRA 2023 factors
  users/                 # Auth views (JWT)

frontend/               # React + Vite SPA
  src/
    pages/
      DashboardPage.jsx  # Summary metrics + charts
      RecordsPage.jsx    # Data grid + review workflow
      IngestPage.jsx     # File upload + sample CSVs
      JobsPage.jsx       # Ingestion job history
    api/client.js        # Axios API client
```

---

## Deliverable documents

| Document | Description |
|----------|-------------|
| [MODEL.md](MODEL.md) | Data model design and rationale |
| [DECISIONS.md](DECISIONS.md) | Ambiguities resolved and PM questions |
| [TRADEOFFS.md](TRADEOFFS.md) | Three things deliberately not built |
| [SOURCES.md](SOURCES.md) | Real-world format research per source |

---

## Deployment

This app is structured for Railway, Render, or Fly.io:

**Backend**: Django + gunicorn, SQLite dev / Postgres in production via `DATABASE_URL` env var.

**Frontend**: Deploy as static site. Set `VITE_API_BASE_URL` env var if backend is on a different domain.

See [backend/build.sh](backend/build.sh) and [backend/Procfile](backend/Procfile).
