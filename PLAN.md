# Plan: `taken` — Python Backend API for Duty Scheduling

## Context

US Basketball Amsterdam (~125 members, 12 teams, ~126 home games/season) needs a backend API service to manage duty assignments (referee, table official, hall duty) for home games. The club website (Next.js on Vercel, `usbasketball/usbasketball`) will consume this API for members to view their duty assignments.

### Domain Summary

- **Season**: Sept–May container for all data
- **12 teams**: D1–D6 (dames), H1–H6 (heren), levels 1 (highest) to 6 (lowest)
- **~125 members**, each on a primary team, some on a secondary team (bankspeler)
- **~126 home games** at a multi-court venue (Veld 1–3)
- **Duty types**: zaaldienst (1/timeslot, from ~15-member pool), scheids-1/2 (referee, needs diploma), tafel-1/2/3 (table official)
- **Balance formula**: `korting + single_duties + (double_duties × 2)` — goal is equal across all members
- **Double duty**: duty NOT adjacent (same day, within 150min) to member's own game → counts 2×
- **NBB games** (H1, H2, D1): federation referees provided, no club refs needed
- **D6 members**: cannot referee
- **Tafel-3**: only for higher-level games (24-sec shot clock)
- **External data**: foys.io API provides game schedules

---

## Tech Stack

| Layer             | Choice                                             | Why                                                                                                           |
| ----------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Language**      | Python 3.13                                        | Optimization library ecosystem                                                                                |
| **Framework**     | FastAPI                                            | Async, auto OpenAPI docs, Pydantic validation, Vercel-compatible                                              |
| **ORM**           | SQLAlchemy 2.0                                     | Standard Python ORM, mature PostgreSQL support                                                                |
| **Migrations**    | Alembic                                            | Standard companion to SQLAlchemy                                                                              |
| **Validation**    | Pydantic v2                                        | Built into FastAPI, type-safe request/response models                                                         |
| **Database**      | PostgreSQL on Neon                                 | Native types, Vercel Marketplace, free tier                                                                   |
| **Optimization**  | Google OR-Tools (CP-SAT)                           | Constraint satisfaction + optimization solver — ideal for duty assignment                                     |
| **Auth (admin)**  | JWT Bearer tokens (`python-jose`)                  | Board member login with password                                                                              |
| **Auth (public)** | API key + Auth0 token verification (`PyJWKClient`) | Dual protection: API key validates the caller is the website, Auth0 token validates the user is a club member |
| **Testing**       | pytest + httpx                                     | Standard Python testing                                                                                       |
| **Deploy**        | Vercel (Fluid Compute)                             | Same platform as website                                                                                      |

---

## Project Structure

```
taken/
  api/
    index.py                    # Vercel entry point — mounts FastAPI app
  app/
    __init__.py
    main.py                     # FastAPI app factory, router registration
    config.py                   # Settings via pydantic-settings (env vars)
    dependencies.py             # Shared FastAPI dependencies (db session, auth)
    db/
      __init__.py
      engine.py                 # SQLAlchemy engine + session factory (Neon)
      models.py                 # SQLAlchemy ORM models (10 tables)
    routers/
      __init__.py
      auth.py                   # POST /auth/login
      seasons.py                # CRUD /seasons
      members.py                # CRUD /seasons/{sid}/members
      games.py                  # CRUD /seasons/{sid}/games
      games_sync.py             # POST /seasons/{sid}/games/sync (foys.io)
      assignments.py            # CRUD /seasons/{sid}/assignments
      generate.py               # POST /seasons/{sid}/assignments/generate
      zaaldienst.py             # GET/PUT /seasons/{sid}/zaaldienst
      balance.py                # GET /seasons/{sid}/balance
      config.py                 # GET/PUT /seasons/{sid}/config
      audit.py                  # GET /seasons/{sid}/audit
      export.py                 # GET /seasons/{sid}/export
      publish.py                # POST /seasons/{sid}/publish
      public.py                 # GET /public/schema (API-key + Auth0 auth)
    schemas/                    # Pydantic request/response models
      season.py
      member.py
      game.py
      assignment.py
      balance.py
      public.py
    engine/
      __init__.py
      solver.py                 # OR-Tools CP-SAT assignment solver
      constraints.py            # Hard constraints (eligibility rules)
      scoring.py                # Soft constraint weights (balance, adjacency)
      balancer.py               # Balance calculation
      types.py                  # Engine data classes
    services/
      __init__.py
      foys.py                   # foys.io API client + sync logic
      team_mapping.py           # Team code ↔ name mapping
      timeslot.py               # Adjacency calculation
      excel_export.py           # .xlsx generation (openpyxl)
      validation.py             # Season validation checks
    middleware/
      __init__.py
      auth.py                   # JWT verification for admin routes
      api_key.py                # API key verification for public routes
      auth0.py                  # Auth0 token verification for public routes
  alembic/                      # Migration files
    versions/
    env.py
  alembic.ini
  tests/
    conftest.py                 # Fixtures: test DB, client, seed data
    test_auth.py
    test_seasons.py
    test_members.py
    test_games.py
    test_assignments.py
    test_engine.py              # Solver + optimizer tests
    test_balance.py
    test_sync.py
    test_public.py
  requirements.txt
  pyproject.toml
  vercel.json
  .python-version               # 3.13
```

---

## Database Schema (PostgreSQL via SQLAlchemy)

TODO

---

## Assignment Engine — OR-Tools CP-SAT Solver

### Why OR-Tools instead of greedy

The duty assignment is a **constraint satisfaction + optimization problem**:

- **Hard constraints**: member can't be assigned during own game, must have diploma for referee duty, D6 can't referee, one person per duty slot, etc.
- **Soft objective**: minimize balance variance across all members (fair distribution)

OR-Tools' CP-SAT (Constraint Programming - Satisfiability) solver is purpose-built for this. Instead of greedily picking candidates one-at-a-time and hoping for a good global result, CP-SAT considers **all assignments simultaneously** and finds an optimal (or near-optimal) solution.

### Model Design (`app/engine/solver.py`)

**Decision variables:**

```python
# For each (game, duty_type, member) triple: binary variable
# assign[g, d, m] = 1 if member m is assigned duty d on game g
assign = {}
for game in games:
    for duty in game.required_duties:
        for member in eligible_members(game, duty):
            assign[game.id, duty, member.id] = model.NewBoolVar(...)
```

**Hard constraints:**

1. Each duty slot filled by exactly 1 member: `sum(assign[g, d, :]) == 1`
2. Member not assigned during own game (primary + secondary team)
3. Member assigned at most once per timeslot: `sum(assign[games_in_ts, :, m]) <= 1`
4. Referee duties require diploma != "nee"
5. D6 members excluded from referee duties
6. NBB games get no club referees
7. Zaaldienst only from zaaldienst pool members

**Soft objectives (minimized):**

1. **Balance variance**: For each member, compute their total effective balance. Minimize `max_balance - min_balance` (minimax) or `sum of squared deviations` from mean.
2. **Double duty penalty**: Prefer assignments adjacent to member's own game (weight: high)
3. **Same-team concentration**: Penalize >N members from same team in one timeslot (weight: medium)
4. **Diploma matching**: Prefer E-level referees for high-level games (weight: low)

**Implementation approach:**

```python
from ortools.sat.python import cp_model

def solve_assignments(season_data: SeasonData) -> AssignmentPlan:
    model = cp_model.CpModel()

    # Create variables
    # Add hard constraints
    # Define objective (weighted sum of soft penalties)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30  # time limit
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return extract_assignments(solver, assign)
    else:
        # Fallback to greedy if solver fails
        return greedy_fallback(season_data)
```

**Expected performance:** CP-SAT can handle problems with ~50,000 binary variables efficiently. Our problem: ~126 games × ~5 duties × ~100 eligible members ≈ 63,000 variables. With constraint propagation reducing the effective search space, this should solve in well under 30 seconds.

### Zaaldienst handling

Zaaldienst is per-timeslot (not per-game), so it's modeled separately:

```python
# For each (timeslot, zaaldienst_member) pair
zaal[ts, m] = model.NewBoolVar(...)
# Exactly 1 per timeslot
sum(zaal[ts, :]) == 1
```

---

## API Endpoints

All admin routes require `Authorization: Bearer <jwt>`. Public routes require both `x-api-key` and Auth0 token.

### Auth

```
POST /auth/login       { password: str }              → { token, expires_at }
```

### Seasons

```
GET    /seasons                                        → Season[]
POST   /seasons         { name: str }                  → Season
GET    /seasons/active                                 → Season | null
GET    /seasons/{sid}                                  → Season
PUT    /seasons/{sid}   { name?, is_active? }          → Season
DELETE /seasons/{sid}                                  → { ok }
```

### Members

```
GET    /seasons/{sid}/members                          → Member[]
POST   /seasons/{sid}/members  { first_name, team, primary_team, ... }  → Member
PUT    /seasons/{sid}/members/{mid}  { ... }           → Member
DELETE /seasons/{sid}/members/{mid}                    → { ok }
```

### Games

```
GET    /seasons/{sid}/games                            → Game[]
POST   /seasons/{sid}/games  { home_team_code, away_team_name, date, start_time, ... }  → Game
PUT    /seasons/{sid}/games/{gid}  { ... }             → Game
DELETE /seasons/{sid}/games/{gid}                      → { ok }
POST   /seasons/{sid}/games/sync  { preview?: bool, resolutions?: [...] }  → SyncResult
```

### Assignments

```
GET    /seasons/{sid}/assignments?game_id=X            → Assignment[]
POST   /seasons/{sid}/assignments  { game_id, member_id, duty_type }  → Assignment
PUT    /seasons/{sid}/assignments/{aid}  { member_id }  → Assignment
DELETE /seasons/{sid}/assignments/{aid}                → { ok }
POST   /seasons/{sid}/assignments/generate             → GenerateResult
```

### Zaaldienst

```
GET    /seasons/{sid}/zaaldienst                       → ZaaldienstEntry[]
PUT    /seasons/{sid}/zaaldienst/{tsid}  { member_id }  → { ok }
```

### Balance

```
GET    /seasons/{sid}/balance                          → MemberBalance[]
GET    /seasons/{sid}/balance/{mid}                    → MemberBalanceDetail
```

### Config, Audit, Export, Publish

```
GET    /seasons/{sid}/config                           → dict
PUT    /seasons/{sid}/config/{key}  { value }          → { ok }
GET    /seasons/{sid}/audit?entity_type=X&limit=N      → AuditEntry[]
GET    /seasons/{sid}/export                           → .xlsx file
POST   /seasons/{sid}/publish                          → { ok, published_at }
```

### Public (for website) — requires both API key + Auth0 token

```
GET    /public/schema                                  → PublicSchema
GET    /public/schema?team=H3                          → PublicSchema (filtered)
```

**Dual auth on public routes:**

1. `x-api-key` header — validates the caller is the club website (not a random client)
2. `Authorization: Bearer <auth0_token>` — the website forwards the user's Auth0 JWT; the taken API verifies it against Auth0's JWKS endpoint (`https://<AUTH0_DOMAIN>/.well-known/jwks.json`) to confirm the user is an authenticated club member

The taken API needs these env vars for Auth0 verification:

```
AUTH0_DOMAIN=<your-auth0-domain>.auth0.com
AUTH0_AUDIENCE=<your-api-audience>    # or the website's client ID
```

Implementation in `app/middleware/auth0.py`:

```python
from jwt import PyJWKClient
import jwt

jwks_client = PyJWKClient(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")

async def verify_auth0_token(token: str) -> dict:
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=AUTH0_AUDIENCE,
        issuer=f"https://{AUTH0_DOMAIN}/"
    )
```

Response shape for `/public/schema`:

```json
{
  "season_name": "2025-2026",
  "published_at": "2026-01-15T10:30:00Z",
  "games": [
    {
      "id": 1,
      "home_team_code": "H3",
      "home_team_name": "U.S. - MSE-3",
      "away_team_name": "Klipperstars - MSE-1",
      "date": "2025-10-05",
      "start_time": "14:00",
      "field_name": "Veld 2",
      "is_cancelled": false,
      "zaaldienst": "D2, Sanne",
      "assignments": [
        {
          "duty_type": "scheids-1",
          "member_display_id": "H4, Keje",
          "is_double": false
        },
        {
          "duty_type": "tafel-1",
          "member_display_id": "D3, Lisa",
          "is_double": true
        }
      ]
    }
  ],
  "balances": [
    {
      "display_id": "H3, Keje",
      "team": "H3",
      "effective_balance": 4.5,
      "scheids_duties": 2,
      "tafel_duties": 1,
      "zaaldienst": 0,
      "korting": 0.5
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Project Setup + Foundation

- Initialize Python project: `pyproject.toml`, `requirements.txt`, `.python-version`
- Set up FastAPI app with health check endpoint
- Configure SQLAlchemy 2.0 + Neon PostgreSQL connection
- Define **minimal** SQLAlchemy models needed for sync: `seasons`, `teams`, `games`, `timeslots`, `game_timeslots`, `sync_log`
- Set up Alembic, create initial migration
- Implement JWT auth (`POST /auth/login`)
- Implement basic seasons CRUD (`POST /seasons`, `GET /seasons/active`)
- Implement `services/team_mapping.py` (needed by sync for team code normalization)
- Configure `vercel.json` for Python Fluid Compute
- Deploy to Vercel, provision Neon via Marketplace

**Deliverable:** Deployed API with auth and season creation, ready for sync.

### Phase 2: foys.io Sync

- Implement `services/foys.py` — API client, normalization, diff computation
- Implement `services/timeslot.py` — timeslot find-or-create, adjacency calculation
- Implement `POST /seasons/{sid}/games/sync` with preview/apply pattern
- Handle conflict resolution for manually-edited games
- Implement `GET /seasons/{sid}/games` (read-only, to verify synced data)
- Write tests for sync flow

**Deliverable:** Can create a season, sync games from foys.io, and view the synced games.

### Phase 3: Remaining Models + Core CRUD

- Define remaining SQLAlchemy models: `members`, `assignments`, `balance_adjustments`, `config`, `audit_log`
- Create Alembic migration for the new tables
- Define Pydantic schemas for all entities
- Implement members CRUD router
- Implement full games CRUD (create/update/delete, extending the GET from Phase 2)
- Implement config and audit routers
- Implement automatic timeslot creation/linking when games are created manually
- Write integration tests for all CRUD routes

**Deliverable:** Full CRUD for all entities with audit trail.

### Phase 4: Assignment Engine (OR-Tools CP-SAT)

- Implement `engine/constraints.py` — eligibility rules as functions
- Implement `engine/scoring.py` — soft constraint weights
- Implement `engine/solver.py` — CP-SAT model with all constraints and objectives
- Implement `engine/balancer.py` — balance calculation
- Implement `POST /seasons/{sid}/assignments/generate`
- Implement `GET /seasons/{sid}/balance`
- Implement zaaldienst routes
- Implement assignment CRUD (manual overrides)
- Write engine tests with realistic data

**Deliverable:** Optimal duty assignment generation.

### Phase 5: Public API + Publish

- Implement API-key middleware (`app/middleware/api_key.py`)
- Implement Auth0 token verification middleware (`app/middleware/auth0.py`) — verifies user JWT against Auth0 JWKS
- Combine both as dependencies on public routes (both must pass)
- Implement `GET /public/schema`
- Implement `POST /seasons/{sid}/publish`
- Implement `services/validation.py` — constraint violation checks
- Write tests for public API (mock both API key and Auth0 token verification)

**Deliverable:** Website can fetch and display duty schedule. Endpoint is protected by both API key (service-level) and Auth0 token (user-level).

### Phase 6: Export + Polish

- Add CORS for website domain
- Add rate limiting on public endpoints
- API documentation (auto-generated by FastAPI at `/docs`)
- Error monitoring (Sentry)

**Deliverable:** Production-ready API.

---

## Deployment Configuration

### `vercel.json`

```json
{
  "rewrites": [{"source": "/(.*)", "destination": "/api/index"}]
}
```

### `api/index.py`

```python
from app.main import app  # FastAPI instance

# Vercel expects a WSGI/ASGI app at module level
```

### Environment Variables

```
DATABASE_URL=postgres://...     # Auto-provisioned by Neon
ADMIN_PASSWORD=<bcrypt hash>
JWT_SECRET=<random 256-bit hex>
API_KEY=<for website integration>
AUTH0_DOMAIN=<tenant>.auth0.com # For verifying user tokens from the website
AUTH0_AUDIENCE=<api-audience>   # Auth0 API identifier or client ID
FOYS_FEDERATION_ID=52cfa65e-9782-4a81-ab35-e2f981fcb7a9
FOYS_HOME_ORG_ID=2f1e5e8e-e2c5-4d8b-9d21-1584bc6c8d5a
```

---

## Verification

1. **Each phase**: pytest integration tests (seed DB, call endpoint, assert response)
2. **Phase 4 (engine)**: Test with realistic data (125 members, 126 games), verify:
   - Zero hard constraint violations
   - Balance standard deviation across members
   - All duty slots filled (or warnings for impossible slots)
   - Completes in <30 seconds
3. **Phase 5**: Test from website repo — fetch `/public/schema`, verify data renders on `/takenschema` page
4. **Manual**: FastAPI auto-docs at `/docs` for interactive testing
