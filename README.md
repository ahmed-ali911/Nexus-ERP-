# Sham ERP

Deployable ERP for food manufacturing/distribution companies in Kuwait.
Single codebase, deployed per-client via Docker (not multi-tenant SaaS).
Organizational hierarchy: **Company → Branch → Warehouse** — one deployment
can hold one or more Companies (legal entities).

Stack: FastAPI + PostgreSQL + React/TypeScript + Docker.

> **Status:** foundation skeleton only. No business modules, models, or
> logic yet — see "Current state" below.

## Structure

```
sham-erp/
├── backend/                 FastAPI app
│   ├── app/
│   │   ├── main.py          App entrypoint, GET /health
│   │   ├── core/            Cross-cutting infrastructure
│   │   │   ├── config.py    Settings loaded from env (.env)
│   │   │   ├── database.py  SQLAlchemy engine/session (Base, get_db)
│   │   │   ├── rbac.py      Role-based access control (placeholder)
│   │   │   └── audit.py     Audit trail (placeholder)
│   │   └── modules/         Business modules go here (empty for now)
│   ├── pyproject.toml       uv-managed deps; ruff + black configured
│   └── Dockerfile
├── frontend/                React + TypeScript (Vite)
│   ├── src/
│   │   ├── i18n/            i18next setup, en/ar locale files
│   │   ├── theme/           MUI theme + emotion cache, RTL/LTR aware
│   │   ├── App.tsx           Minimal shell proving bilingual RTL/LTR works
│   │   └── main.tsx
│   ├── package.json         Vite + MUI + i18next; eslint + prettier configured
│   └── eslint.config.js
├── database/
│   ├── alembic.ini          Alembic config (points at ../backend for models)
│   ├── migrations/          env.py, script.py.mako, versions/ (empty)
│   └── seed/                Seed data/scripts (empty for now)
├── deploy/
│   ├── on-prem/              Placeholder for on-prem deployment assets
│   └── hosted/                Placeholder for hosted deployment assets
├── docker-compose.yml       backend + postgres + redis
├── .env.example             Copy to .env before running
└── README.md
```

## Current state

- `backend/app/core/config.py` and `database.py` are functional (settings
  loading, SQLAlchemy engine/session) — this is infrastructure wiring, not
  business logic.
- `backend/app/core/rbac.py` and `audit.py` are empty placeholders — no
  permission model or change-tracking exists yet.
- `backend/app/modules/` is empty — this is where business modules (e.g.
  sales, inventory) will live, one subpackage each.
- `database/migrations/versions/` is empty — no models exist yet, so there
  is nothing to migrate.
- `frontend/` has a working bilingual (AR/EN) shell with RTL/LTR switching
  (MUI theme direction + emotion RTL cache + i18next), but no screens beyond
  a placeholder proving the toggle works.
- `deploy/on-prem/` and `deploy/hosted/` are empty except for README
  placeholders.

## Running it

1. Copy the env file and adjust values (DB credentials, secret key, default
   currency/locale, company name):

   ```
   cp .env.example .env
   ```

2. Start backend + Postgres + Redis:

   ```
   docker-compose up --build
   ```

3. Confirm the backend is up and can reach Postgres:

   ```
   curl http://localhost:8000/health
   # {"status":"ok"}
   ```

   Postgres is exposed on `localhost:5432` and Redis on `localhost:6379`
   for local tooling. The backend container only starts once both
   dependencies report healthy (see `healthcheck` in `docker-compose.yml`).

4. Frontend runs separately (not yet part of docker-compose):

   ```
   cd frontend
   npm install
   npm run dev
   ```

   Open the printed local URL — you'll see a placeholder screen with an
   AR/EN toggle that flips text direction (RTL/LTR) live.

## Database migrations (Alembic)

No models exist yet, so there's nothing to generate. Once the first module
adds models under `backend/app/modules/<module>/models.py`, import them in
`database/migrations/env.py` and run, from `database/`:

```
alembic revision --autogenerate -m "add <module> tables"
alembic upgrade head
```

Alembic reads `DATABASE_URL` from the same `.env`-driven settings as the
backend (via `app.core.config.settings`), so migrations always target the
same database the app connects to.

## Next step

This is Step 1 (skeleton only). No business modules, models, or module
logic have been added. Review this foundation before we scaffold the first
module.
