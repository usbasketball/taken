# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

`taken` is a Python FastAPI backend for duty scheduling at US Basketball Amsterdam (~125 members, ~12 teams, ~126 home games/season). It manages assignment of referee, table official, and hall duty (zaaldienst) roles to members per game, enforcing eligibility rules and optimizing for fairness. A companion Next.js website (separate repo) consumes the public API.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Run dev server
uvicorn app.application:app --reload

# Run all tests
pytest

# Run a single test file
pytest tests/test_sync.py

# Run a single test by name
pytest tests/test_sync.py::test_sync_preview_returns_diff

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
alembic downgrade -1
```

Interactive API docs when running locally: `http://localhost:8000/docs`

> **Alembic note:** `alembic.ini` intentionally has a blank `sqlalchemy.url`. `alembic/env.py` reads `DATABASE_URL` directly from the environment.

## Architecture

### Request Flow

```
Vercel → api/index.py (re-exports app) → app/main.py (router registration)
       → routers/ → services/ → db/models.py (SQLAlchemy ORM)
```

### Key Design Points

**Auth (two-tier):**

- Admin routes: HS256 JWT via `require_auth()` dependency (`app/middleware/auth.py`), injected per-route with `Depends()` — not global middleware
- `verify_password` accepts plain text if `ADMIN_PASSWORD` doesn't start with `$2b$`/`$2a$` (intentional for local dev; default: `"changeme"`)
- Public routes: Auth0 JWT (`Authorization: Bearer <auth0_token>`), verified against Auth0's JWKS endpoint

**Database:**

- Production: PostgreSQL via Neon. Both `app/db/engine.py` and `alembic/env.py` independently rewrite `postgres://` → `postgresql://` and append `sslmode=require` for `neon.tech` URLs — keep these in sync.
- Tests: in-memory SQLite with `StaticPool` (required so all connections share the same in-memory DB). The engine factory branches on `url.startswith("sqlite")` to skip PostgreSQL-only pool settings.

**foys.io sync (two-step):**

- `POST /seasons/{sid}/games/sync?preview=true` — returns diff (added/updated/removed/conflicts) without writing
- `POST /seasons/{sid}/games/sync?preview=false` — applies the diff; conflicts default to "keep local" unless overridden per `external_id` with `action: "overwrite"`

**Timeslots:** A `Timeslot` is a unique `(season_id, date, start_time)`. Games link via `GameTimeslot` (many-to-many). Two games are "adjacent" if within 150 minutes on the same day, affecting duty balance counting.

**Tests:** All tests use per-function in-memory SQLite; `get_db` is overridden via `app.dependency_overrides`. External foys.io HTTP calls are mocked with `unittest.mock.patch`.

### Configuration (`app/config.py`, pydantic-settings)

| Variable                                  | Purpose                                   |
| ----------------------------------------- | ----------------------------------------- |
| `DATABASE_URL`                            | Defaults to `sqlite:///./test.db` locally |
| `ADMIN_PASSWORD`                          | Plain text (dev) or bcrypt hash (prod)    |
| `JWT_SECRET`                              | HS256 signing key                         |
| `AUTH0_DOMAIN` / `AUTH0_AUDIENCE`         | Verifies website user JWTs                |
| `FOYS_FEDERATION_ID` / `FOYS_HOME_ORG_ID` | foys.io defaults (hardcoded)              |

## Implementation Status

This is a mid-build project. Phases 1–2 are complete:

- Phase 1: auth, seasons CRUD, DB engine, ORM models, Alembic migration
- Phase 2: foys.io sync service, games listing, timeslot management

**Phases 3–6 not yet implemented:** members/assignments/balance/solver routers, OR-Tools CP-SAT solver (`app/engine/`), Excel export, Auth0/API key middleware, public endpoints.

The canonical architecture plan (full API spec, DB schema, solver design) is in `PLAN.md`.

### Planned Solver (Phase 4)

OR-Tools CP-SAT with ~63,000 binary decision variables (126 games × 5 duties × 100 eligible members), 30-second time limit, falling back to greedy on timeout.

## Deployment

Vercel: `vercel.json` rewrites all traffic to `/api/index.py`. Test files are excluded from the function bundle via `excludeFiles`.
