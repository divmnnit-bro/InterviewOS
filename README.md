# InterviewOS

Interview scheduling and recruitment coordination for campus placement drives.
Coordinators describe a drive (a time window and an ordered list of rounds); candidates and interviewers
submit availability; an OR-Tools CP-SAT solver proposes a conflict-free schedule; the coordinator reviews and
publishes it; candidates can self-book; interviewers submit scored feedback; and pass/fail decisions move
candidates through the rounds. When something breaks after publication (an interviewer falls ill, a room
closes), Ripple Rescue repairs the schedule with the fewest possible changes.

> **Design principle:** the solver proposes, an independent checker verifies, the database saves safely
> (and refuses double bookings on its own), and notifications follow afterwards.

**Contents:** [Architecture](#architecture) · [Quick start](#quick-start) · [Configuration](#configuration) ·
[Migrations](#database-migrations) · [Testing](#testing) · [Benchmarks](#scheduler-benchmarks) ·
[How a drive runs](#how-a-drive-runs-end-to-end) · [How it stays correct](#how-it-stays-correct) ·
[API reference](#api-reference) · [Implemented vs planned](#implemented-features-vs-planned-extensions) ·
[Production notes](#production-notes) · [Troubleshooting](#troubleshooting)

---

## Architecture

```
 client ──HTTP/JSON──▶  app/api/routes     ◀── auth, role checks, request/response schemas (Pydantic)
                              │
                              ▼
                        app/services       ◀── transactions, row locks, version checks, audit events, notifications
                         │         │
                         ▼         ▼
              app/scheduler      app/models + app/db ──▶ PostgreSQL 16
        (pure logic, no I/O)         (SQLAlchemy 2.0)       exclusion constraints (btree_gist) block double booking
   CP-SAT solver · greedy plan · verify · explain · rescue
```

| Layer | Path | Responsibility |
|---|---|---|
| Frontend (SPA) | `frontend/src/` | React 18, TypeScript strict, TailwindCSS, TanStack Query, React Router v6, GSAP animations, Lucide icons |
| API | `backend/app/api/routes/` | One module per area. Roles are re-read from the database on every request, not trusted from the token |
| Schemas | `backend/app/schemas/` | Pydantic v2 request and response models |
| Services | `backend/app/services/` | Scheduling, booking, rescue, evaluations, pipeline, notifications, `.ics`. Services decide when to commit |
| Scheduler | `backend/app/scheduler/` | **No database, web or auth imports.** Plain dataclasses in, a proposed schedule out |
| Models / DB | `backend/app/models/`, `backend/app/db/` | 14 tables, enums stored as their lowercase values |
| Migrations | `backend/alembic/versions/` | `0001` to `0006` |
| Scripts | `backend/app/scripts/` | `seed_demo`, `create_coordinator`, `run_notifications` |
| Benchmarks | `backend/benchmarks/` | Scale benchmark for the scheduler |
| Tests | `backend/tests/`, `frontend/src/test/` | Backend pure-logic/API tests and Frontend Vitest/Playwright tests |

Stack: React 18, Vite 6, TypeScript strict, TailwindCSS, TanStack Query, GSAP, Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, psycopg 3, Pydantic 2, OR-Tools CP-SAT, PostgreSQL 16.

### Dependency and licensing review (2026-10-27)

No new runtime dependency was needed for these changes. The versions below are the upstream releases checked on this date, not a request to upgrade the app. Existing major versions stay in place because the current frontend build and backend tests pass; Python requirements are minimum ranges rather than a complete lockfile, so deployment should use a resolved, tested environment.

| Dependency | Upstream release checked | Upstream project / maintainer | License and decision |
|---|---:|---|---|
| React (app uses 18.x) | 19.3.1 | React Team | MIT; keep the existing major version for this change |
| FastAPI (`>=0.115`) | 0.161.1 | FastAPI project | MIT; no upgrade needed for these routes |
| Pydantic (`>=2.8`) | 2.13.x stable line | Pydantic project | MIT; keep v2 schemas |
| OR-Tools (`>=9.10`) | 9.15 | Google OR-Tools | Apache-2.0; keep the existing CP-SAT integration |
| PostgreSQL (Compose uses 16) | 16 remains supported | PostgreSQL Global Development Group | PostgreSQL License; keep the configured major version |
| pytest (`>=8.0`) | 9.1.1 | pytest-dev | MIT; keep the tested range |
| FullCalendar | Not installed | FullCalendar project | Standard is MIT; Premium resource timelines require a paid commercial license, so keep the existing custom scheduling views |

The Python lower bounds are in `backend/requirements.txt`; the frontend lockfile records exact npm resolutions. Upstream release, license, support, and pricing details: [React releases and license](https://github.com/facebook/react/releases), [FastAPI releases and license](https://github.com/fastapi/fastapi), [Pydantic releases and license](https://github.com/pydantic/pydantic), [OR-Tools releases and license](https://github.com/google/or-tools), [PostgreSQL release support](https://www.postgresql.org/support/versioning/) and [license](https://www.postgresql.org/about/licence/), [pytest releases and license](https://github.com/pytest-dev/pytest), and [FullCalendar licensing and pricing](https://fullcalendar.io/license).

---

## Quick start

### Option A: Docker Compose (Full Stack)

Prerequisite: Docker with the Compose plugin (`docker compose version`).

```bash
docker compose up --build            # Starts PostgreSQL, Backend API (:8000), and Production Frontend (:3000)
```

- **Frontend App**: <http://localhost:3000>
- **Backend API**: <http://localhost:8000> (interactive docs at `/docs`, health check at `/health`)

Seed demo data with ready-to-use accounts, rooms, drive, stages, and availability:

```bash
docker compose exec backend python -m app.scripts.seed_demo
```

Demo Credentials:
- **Coordinator**: `coordinator@interviewos.dev` / `Password123!`
- **Interviewers**: `sarah.chen@interviewos.dev` / `Password123!`, `marcus.vance@interviewos.dev` / `Password123!`
- **Candidates**: `alice.walker@example.com` / `Password123!`, `bob.martinez@example.com` / `Password123!`

---

### Option B: Native Development (Backend + Frontend)

#### 1. Backend

Prerequisites: Python 3.12+ and PostgreSQL 16 (e.g. `docker compose up -d postgres`).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate                      # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                           # Windows: copy .env.example .env
alembic upgrade head                           # creates every table and enables btree_gist
python -m app.scripts.seed_demo                # seeds coordinator, interviewers, candidates, rooms, drive
uvicorn app.main:app --port 8000 --reload      # http://localhost:8000
```

#### 2. Frontend

Prerequisites: Node.js 20+ / 22+.

```bash
cd frontend
npm install
npm run dev                                    # http://localhost:5173
```

- Unit & integration tests: `npm test`
- Type checking: `npm run typecheck`
- Linter: `npm run lint`
- Production bundle: `npm run build`

Useful Docker Compose commands:
```bash
docker compose up -d postgres                 # database only (to run the API and tests natively)
docker compose --profile worker up            # also run the notification delivery worker
docker compose logs -f backend                # follow the API logs
docker compose down                           # stop (the database volume is kept)
docker compose down -v                        # stop AND delete the database volume
```

The Compose file is a **development & production** setup: it mounts `./backend` for hot reload when developing and serves the compiled frontend with Nginx SPA fallback. Settings can be overridden from `.env` next to `docker-compose.yml`.

---

## Configuration

Read from environment variables or `backend/.env` (environment variables win). Defaults are in `backend/app/core/config.py`.

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | Anything other than `development` makes a strong `SECRET_KEY` mandatory |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/interviewos` | Must use the `psycopg` (v3) driver |
| `SECRET_KEY` | `dev-only-insecure-secret-change-me` | Signs login tokens and booking links. Outside `development` the app **refuses to start** unless it is 32+ characters and not the dev value. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` | `HS256` / `60` | Login token settings |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_ECHO` | `10` / `20` / `false` | Connection pool and SQL logging |
| `SCHEDULER_MAX_TIME_LIMIT_SECONDS` | `60` | Upper bound on the solver time a client may request |
| `SCHEDULER_MAX_WORKERS` | `8` | Upper bound on CP-SAT search workers a client may request |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Frontend origins allowed to call the API, comma-separated. Empty disables CORS |
| `SMTP_HOST` / `SMTP_FROM` | unset | Optional email alerts. Email rows are queued only when both are set; configure TLS or SSL and credentials below if the SMTP server requires them |
| `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` | `587` / unset / unset | Optional SMTP connection settings; secrets belong in environment configuration, never source control |
| `SMTP_USE_SSL` / `SMTP_STARTTLS` / `SMTP_TIMEOUT_SECONDS` | `false` / `true` / `10` | Encrypted SMTP transport and connection timeout |


Docker Compose only: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` (host port, default 5432),
`BACKEND_PORT` (host port, default 8000), `WATCHFILES_FORCE_POLLING`.

---

## Database migrations

Alembic reads the connection string from `DATABASE_URL` (see `alembic/env.py`), so there is one source of truth.
Run these from `backend/`, or prefix with `docker compose exec backend` when using Compose.

```bash
alembic upgrade head              # apply everything (the container does this on every start)
alembic current                   # which revision the database is at
alembic history --verbose         # list revisions
alembic downgrade -1              # undo the latest revision
alembic upgrade head --sql        # print the SQL instead of running it
alembic check                     # fail if the models and the migrations have drifted apart
alembic revision --autogenerate -m "describe the change"   # after editing a model
```

| Revision | Adds |
|---|---|
| `0001` | Initial schema, `btree_gist`, the exclusion constraints that block double booking |
| `0002` | `room_availabilities`, `recruitment_drives.timezone` (what "a day" means for daily limits) |
| `0003` | Per-drive scheduling rules: slot grid, interviewer rest, minimum gap between rounds |
| `0004` | `evaluations.recommendation` (`strong_hire`, `hire`, `no_hire`, `strong_no_hire`) |
| `0005` | AI interview kits, background-job tracking, advanced scheduling quality and analytics support |
| `0006` | Structured MCQs and competency coverage on saved AI interview kits |

`0001` runs `CREATE EXTENSION IF NOT EXISTS btree_gist`, which needs a PostgreSQL role allowed to create extensions
(the `postgres` superuser in the Compose database is). On managed PostgreSQL, enable `btree_gist` first.

---

## Testing

All commands run from `backend/` (or prefix with `docker compose exec backend`). The suite has three kinds of test:

| Kind | Files | Needs PostgreSQL? |
|---|---|---|
| Pure logic | `tests/scheduler/`, `tests/test_pipeline_rules.py`, `tests/test_ics.py`, `tests/test_security.py`, `tests/test_models.py` | No |
| API and constraints | `tests/api/`, `tests/test_db_constraints.py` | Yes, migrated to head. Each test runs in a transaction that is rolled back |
| **Race conditions** | `tests/test_booking_race.py` | Yes. Uses several real connections and **commits real rows**, then deletes them |

```bash
pytest tests/scheduler tests/test_pipeline_rules.py tests/test_ics.py \
       tests/test_security.py tests/test_models.py        # no database needed
pytest                                                    # everything, including the race tests
pytest tests/test_booking_race.py -v                      # only the concurrency tests
pytest tests/api/test_evaluations_api.py -k advance       # a single area
```

**Use a separate test database.** The tests connect to whatever `DATABASE_URL` points at, and the race tests commit
rows, so do not point them at a database with data you care about:

```bash
docker compose exec postgres createdb -U postgres interviewos_test

# bash
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/interviewos_test
# PowerShell:  $env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/interviewos_test"

alembic upgrade head
pytest
```

Inside Compose, pass the URL for one command instead (host name `postgres`):

```bash
T=postgresql+psycopg://postgres:postgres@postgres:5432/interviewos_test
docker compose exec -e DATABASE_URL=$T backend alembic upgrade head
docker compose exec -e DATABASE_URL=$T backend pytest
```

### Frontend Testing & Verification

All frontend checks run from `frontend/`:

| Kind | Command | Status |
|---|---|---|
| Vitest Unit & Integration | `npm test` | **35 passed (100%)** across 8 test suites |
| TypeScript strict type check | `npm run typecheck` | **0 errors** (`tsc --noEmit`) |
| ESLint code quality & hooks | `npm run lint` | **0 errors** (ESLint 9 + typescript-eslint) |
| Production Build | `npm run build` | **Clean build** in 3.06s with route code-splitting |
| Playwright E2E Story | `npm run e2e` | Automated end-to-end demo lifecycle spec |

```bash
cd frontend
npm test                 # Run all 35 unit/integration tests
npm run typecheck        # Strict TypeScript verification
npm run lint             # ESLint rules & React hooks validation
npm run build            # Production bundle with manual vendor chunking
```

---

## 5-Minute Demo Script & Screenshot Catalog

- **Complete 5-Minute Demo Script**: See [docs/DEMO_SCRIPT.md](file:///c:/Users/Victus/Downloads/InterviewOS-main/docs/DEMO_SCRIPT.md) for exact click-by-click instructions, demo account credentials, and voiceover cues across Coordinator setup, Solver run, Candidate self-booking, Interviewer evaluation, Pipeline advance, and Ripple Rescue disruption repair.
- **Visual Tour & Screenshot Catalog**: See [docs/SCREENSHOTS.md](file:///c:/Users/Victus/Downloads/InterviewOS-main/docs/SCREENSHOTS.md) for UI breakdowns and descriptions of each screen (F1 through F8).

---

## Scheduler benchmarks

`backend/benchmarks/benchmark_scheduler.py` compares the CP-SAT solver with the greedy first-fit plan that seeds it
(and that is returned if the solver runs out of time). It needs no database.

```bash
cd backend
python benchmarks/benchmark_scheduler.py                    # all tiers, both methods
python benchmarks/benchmark_scheduler.py --tier large --workers 4 --time-limit 60
python benchmarks/benchmark_scheduler.py --methods greedy   # greedy only (fast)
python benchmarks/benchmark_scheduler.py --json results.json

docker compose run --rm --no-deps backend python benchmarks/benchmark_scheduler.py   # inside Compose
```

| Tier | Candidates | Interviewers | Rounds | Rooms | Days | Character |
|---|---|---|---|---|---|---|
| `small` | 10 | 5 | 2 | 2 | 2 | comfortable |
| `medium` | 50 | 20 | 3 | 5 | 3 | heavily loaded |
| `large` | 160 | 40 | 3 | 10 | 3 | oversubscribed stress test |

Every candidate is scheduled for **all** of the tier's rounds in one run (chained in order), which is harder than the
API's normal one-round-at-a-time use. Data is generated from `--seed`, so both methods see identical input. The
`large` tier deliberately holds more interview time than its rooms can supply (at the default seed the greedy baseline
alone places about three quarters), so it shows how well each method uses the capacity that exists.

The output has three tables: **match rate, speed and validity** (interviews and candidates placed, wall-clock time,
solver status, and whether the independent checker accepted the schedule); **quality and memory** (the busiest
interviewer's load, the average start time, peak memory); and **CP-SAT minus greedy** per tier.

How to read it:

- `Valid` must be `yes` in every row. The script exits with status 1 if any run failed or any schedule breaks a constraint.
- `Time` covers validation, preparation and solving. CP-SAT will usually spend close to its whole time limit on the big
  tiers; `feasible` there is normal (valid, but not proven optimal).
- When both methods place everyone, CP-SAT's value shows in the *quality* columns (more even load, earlier starts), not in the match rate.
- `Peak MB` is the whole process including the interpreter and OR-Tools, so it is the figure to size a container limit by.
  Each run happens in a fresh subprocess so one run's peak does not inflate the next; `--no-isolate` disables that.
- Results depend on the machine. Run it on the hardware you will deploy to, and raise `--workers` there.

---

## How a drive runs end to end

1. **Set up (coordinator).** `POST /users` for interviewers (with `skills` and daily `capacity`) and candidates, `POST /rooms`,
   `POST /drives`, then `POST /drives/{id}/stages` for each round (duration, panel size, required skills, pass rule).
   Move the drive to `collecting_availability` with `PATCH /drives/{id}`.
2. **Availability.** `PUT /users/{id}/availability` for each interviewer and candidate (the person themself or a coordinator).
   Rooms with no availability windows are open for the whole drive. Enrol candidates with `POST /drives/{id}/candidates`.
3. **Schedule.** `POST /drives/{id}/schedule/propose` solves and saves a pending proposal (anything that did not fit comes back
   with reasons; `POST .../schedule/explain` adds verified fixes). Review it, then `POST .../schedule/publish` with the
   `expected_version` you saw.
4. **Self-booking (optional).** `POST /drives/{id}/booking-links` issues signed links; a candidate opens `GET /booking/{token}`,
   picks a slot and confirms with `POST /booking/{token}/confirm`. Calendar files come from the `.ics` endpoints.
5. **When something breaks.** `POST /drives/{id}/rescue/preview`, then `/rescue/apply` with the previewed version.
6. **Feedback and decisions.** Panelists `POST /interviews/{id}/evaluations`; the coordinator `advance`s or `reject`s each candidate;
   `GET /drives/{id}/pipeline` shows every candidate in every round. Then schedule the next round by proposing again.

---

## How it stays correct

**Double booking is impossible at the database level.** PostgreSQL exclusion constraints (they need `btree_gist`) reject
overlapping active bookings even when two requests arrive at the same instant:

- `interviews`: no two active interviews may share a room, and none may share a candidate, at overlapping times.
  Ranges are half-open, so back-to-back sessions are allowed.
- `panel_assignments`: no interviewer may be in two overlapping active interviews. The table keeps a copy of the
  interview's slot, kept correct by a composite foreign key with `ON UPDATE CASCADE`.
- Cancelled and no-show interviews free their slot (their panel rows are set inactive).

**The scheduler** (`app/scheduler`) is pure logic. Hard constraints: availability of candidate, interviewers and room;
skills; room seats panel plus candidate; no double booking (existing bookings included); interviewer rest buffer;
interviewer daily capacity (per local day in the drive's timezone); round order with a minimum gap.
Soft preferences (`Weights`): schedule as many as possible (always wins), earlier is better, even interviewer load,
smallest adequate room. A quick greedy plan is handed to CP-SAT as a starting hint and is returned as-is
(`status: heuristic`) if the solver cannot finish in time, so a big drive never comes back empty. Anything left out
is reported with a reason code (`ReasonCode`): structural reasons are exact; `capacity_contention` means it fits alone
but lost to other demand. `verify()` is an independent checker that shares no code with the solver and is run before
anything is saved.

**Propose and publish** (`app/services/scheduling.py`). Each active candidate is scheduled for their current round, unless they
already have a live interview for it. Interviewers and rooms are shared across drives, so *every* interview occupying a
slot in the drive window is passed to the solver as an existing booking. The solve runs with no transaction open.
A proposal is saved only if `verify()` finds no violations. Saving and publishing lock the drive row and compare-and-swap
`schedule_version`, so a stale proposal gets a 409 instead of overwriting newer work.

**Self-booking** (`app/services/booking.py`). The idempotency key is hashed with the candidate id; the candidate's enrolment row
is locked; room and panel are chosen and the panel's rows are locked in sorted order; then everything is re-read and re-checked
with the independent checker before inserting. A pending proposal holds its slots against self-booking, and a candidate who
self-books has their proposed interview dropped at publish. Booking links are signed with the app key but carry `typ=booking`,
so they cannot act as logins, and login tokens cannot open booking links.

**Notifications** are written after the booking commits and never fail it. `run_notifications` creates any that were missed
(for example after a crash between commit and notify) and retries pending or failed rows with backoff, up to 5 attempts,
using `FOR UPDATE SKIP LOCKED`, so several workers are safe. In-app alerts work without external configuration. Optional email alerts use Python's standard-library SMTP client only when both `SMTP_HOST` and `SMTP_FROM` are configured; a delivery failure never rolls back a booking.

**Ripple Rescue** (`app/services/rescue.py`, `app/scheduler/rescue.py`). Priority: keep every interview scheduled, then change as
little as possible. A candidate-visible change (time or room) costs far more than a panel swap, and small time shifts beat big
ones. Apply requires `expected_version` (409 `stale_schedule_version`) and, if sent, `plan_fingerprint` (409 `plan_changed`);
it checks nothing moved underneath the plan, then applies moves, cancellations, the `schedule.rescue` audit event and the
version bump in one transaction. Moves go through unique parking slots so a chain of moves never trips the exclusion
constraints midway. Started or `locked` interviews never move. A deactivated room or suspended interviewer is detected as
an implicit disruption. Notifications are created after the commit.

**Evaluations and pipeline** (`app/services/evaluations.py`, `pipeline.py`). Only an active panel member can submit (a coordinator
must name the member in `on_behalf_of`); the interview must have started; a panelist can revise until the candidate's result for the
round is recorded; colleagues' feedback is hidden until you submit your own; the audit log records the submission, not the text.
A decision must name the candidate's current round. *Advance* is refused (409 `decision_blocked`) if there is no interview, a panelist
has not submitted, or the average score is below the round's `min_score`; `override: true` with a reason of at least 10 characters
bypasses that and is audited. *Reject* sets `rejected` and cancels the candidate's interviews that have not started.

**Audit log.** These actions are recorded in `audit_events`: `schedule.propose`, `schedule.discard`, `schedule.publish`, `schedule.rescue`,
`booking.confirm`, `evaluation.submit`, `evaluation.update`, `pipeline.advance`, `pipeline.reject`.


---

## API reference

Routes are mounted at the root (no `/api/v1` prefix). Interactive documentation with every field is at `/docs`.
Authenticated routes need `Authorization: Bearer <token>`. Errors raised by the service layer look like
`{"error": "<code>", "message": "...", "details": ...}`; authentication, permission and validation errors
(401, 403, 404 from route code, 422) use FastAPI's standard `{"detail": ...}`.

**Meta and auth**

| Endpoint | Who | Notes |
|---|---|---|
| `GET /health` | public | Liveness only; does not touch the database |
| `POST /auth/login` | public | JSON `{email, password}`, returns a bearer token |
| `POST /auth/register` | public | Always creates a **candidate** |
| `GET /auth/me` | signed in | |
| `POST /users` | coordinator | Create an interviewer (`skills`, `capacity`, `department`), candidate (`roll_number`, `branch`) or coordinator |

**Drives, stages, enrolment** (all coordinator-only)

| Endpoint | Notes |
|---|---|
| `POST /drives`, `GET /drives`, `GET /drives/{id}`, `PATCH /drives/{id}` | Title, description, window, timezone, slot grid, interviewer rest, round gap and `status`. Window, timezone and stages are locked once a schedule is published |
| `POST/GET /drives/{id}/stages`, `PATCH/DELETE /drives/{id}/stages/{stage_id}` | Duration, panel size, required skills, pass rule |
| `POST/GET /drives/{id}/candidates`, `DELETE /drives/{id}/candidates/{candidate_id}` | Enrol (`{"candidate_ids": [...]}`) or withdraw; withdrawing keeps history |

**Rooms and availability**

| Endpoint | Who | Notes |
|---|---|---|
| `POST /rooms`, `GET /rooms`, `PATCH /rooms/{id}` | coordinator | |
| `GET/PUT /rooms/{id}/availability` | coordinator | No windows = open the whole drive; with windows, usable only inside them |
| `GET/PUT /users/{id}/availability` | owner or coordinator | `PUT` replaces all windows |

**Scheduling** (coordinator-only)

| Endpoint | Notes |
|---|---|
| `POST /drives/{id}/schedule/propose` | Optional body overrides `slot_minutes`, `interviewer_buffer_minutes`, `min_round_gap_minutes`, `time_limit_seconds` (default 20), `workers` for one run. Solves, verifies, saves as `proposed`, replacing the previous pending proposal. Returns `schedule_version` and anything unscheduled with reasons |
| `GET /drives/{id}/schedule/proposal`, `DELETE ...` | View or discard the pending proposal |
| `POST /drives/{id}/schedule/publish` | Body `{"expected_version": n}`. Compare-and-swap, then `proposed` becomes `scheduled`. 409 if the schedule moved on |
| `POST /drives/{id}/schedule/explain` | Read-only. Explains every candidate left out, with **verified** fixes (each re-solved on a relaxed copy) |

**Self-booking, calendar, notifications**

| Endpoint | Who | Notes |
|---|---|---|
| `POST /drives/{id}/booking-links` | coordinator | Signed expiring links (`ttl_hours`, default 72) for candidates who still need a slot; reports who was skipped and why |
| `GET /booking/{token}` | link holder | Free slots now (`limit`, `after`) or the existing booking |
| `POST /booking/{token}/confirm` | link holder | Body `{"start": ...}` and a required `Idempotency-Key` header (8 to 64 characters). 201 created, 200 replay, 409 `slot_unavailable`, 422 if the key was used for a different slot |
| `GET /booking/{token}/ics`, `GET /interviews/{id}/ics` | link holder / candidate, panelist or coordinator | RFC 5545 file; `SEQUENCE` follows the interview version so calendars update |
| `GET /notifications`, `POST /notifications/{id}/read` | signed in | Your own in-app notifications |

**Ripple Rescue** (coordinator-only)

| Endpoint | Notes |
|---|---|
| `POST /drives/{id}/rescue/preview` | Body `{"disruptions": [{"kind": "interviewer_out" \| "room_out" \| "candidate_out", "resource_id", "start_time", "end_time"}]}`. Returns `moves`, `dropped`, `needs_manual`, who to notify, `schedule_version`, `plan_fingerprint`. Writes nothing |
| `POST /drives/{id}/rescue/apply` | Same body plus `expected_version` and optional `plan_fingerprint`. Recomputes and applies atomically; a repair with nothing to change returns `applied: false` |

**Evaluations and pipeline**

| Endpoint | Who | Notes |
|---|---|---|
| `POST /interviews/{id}/evaluations` | panelist, or coordinator with `on_behalf_of` | Rubric ratings (0 to 10), optional overall `score` (default: mean of the rubric), feedback, `recommendation`. 201 first time, 200 when revising |
| `GET /interviews/{id}/evaluations` | panelist, coordinator | Panelists see colleagues' feedback only after submitting their own |
| `POST /drives/{id}/candidates/{cid}/advance` | coordinator | Body `{stage_id, notes?, override?, override_reason?}` |
| `POST /drives/{id}/candidates/{cid}/reject` | coordinator | Same body; no evidence needed |
| `GET /drives/{id}/pipeline` | coordinator | Per-round counts and every candidate's state; `?status=` filters the candidate list |

---

## Implemented features vs planned extensions

### Implemented (stages 1 to 8, plus packaging)

| Stage | Area | Where |
|---|---|---|
| 1 | Database layer: 14 models, Alembic `0001`, DB-level double-booking protection | `app/models`, `alembic/` |
| 2 | Auth (scrypt passwords, JWT), role checks; drive, stage and room APIs | `app/api/routes/auth.py`, `drives.py`, `rooms.py` |
| 3 | Availability for candidates, interviewers and rooms; candidate enrolment | `rooms.py`, `drives.py` |
| 4 | CP-SAT scheduler core with hard constraints, soft preferences, independent checker, greedy hint/fallback | `app/scheduler` |
| 5 | Propose, review and publish with schedule-version compare-and-swap and audit events | `app/services/scheduling.py`, `routes/schedule.py` |
| 6 | Self-booking links, idempotent confirmation, `.ics` export, in-app notifications with retries | `services/booking.py`, `notifications.py`, `ics.py` |
| 7 | Conflict explanations with verified fixes; Ripple Rescue preview and apply | `scheduler/explain.py`, `rescue.py`, `services/rescue.py` |
| 8 | Evaluations, feedback access control, pass/fail rules, pipeline overview | `services/evaluations.py`, `pipeline.py` |
| 9 | Dockerfile, Compose stack, scheduler benchmarks, this documentation | `backend/Dockerfile`, `docker-compose.yml`, `backend/benchmarks/` |

### Frontend Status (F1–F8 Fully Implemented)

All frontend requirements specified across F1 through F8 are fully implemented and integrated with the FastAPI backend:

**Frontend Implementation Status (F1–F8 Complete):**
- **F1: Foundation & Auth**: Typed API client with 401 interceptor, role-based routing guards, AppShell with mobile drawer & desktop sidebar, 30s notification polling, and complete design system.
- **F2: Coordinator Setup**: People, Rooms, and Drives directories; stages builder with pass rules and locked-field safeguards; candidate batch enrolment and withdrawal.
- **F3: Availability Matrix**: 7-day interactive week calendar with hour grid, window overlap auto-merging, drive-window background boundary clipping, whole-drive room availability banner, and interviewer profile card.
- **F4: Scheduling Console**: Dual timeline views (by Room & by Interviewer) with 30-min block scaling, CP-SAT solver run, daily workload counters vs capacity, explain unscheduled drawer with verified fixes, compare-and-swap publish with 409 stale version detection, and .ics invitation downloads.
- **F5: Candidate Area & Self-Booking**: Coordinator booking links generator with TTL, public self-booking page (`/book/:token`) with local timezone day-grouping, idempotent confirmation (`Idempotency-Key` header), conflict handling, and Candidate Dashboard with strict score isolation.
- **F6: Interviewer Area**: My Interviews agenda with authenticated .ics downloads, unbiased unrated criteria (0–10), live average score, backend-aligned recommendations, per-interviewer pending-feedback state, start-time submission gating, and anti-anchoring colleague feedback lock.
- **F7: Pipeline & Ripple Rescue**: Kanban board per stage, Candidate Dossier modal, progression decisions (Advance/Reject) with audited override justification, and Ripple Rescue disruption console (disruption form, before/after move diff, collateral vs direct impact categorization, atomic apply with version fingerprint).
- **F8: Production Polish & Containerization**: Multi-stage Dockerfile with Nginx SPA fallback, `docker-compose.yml` frontend service, demo database seed script (`backend/app/scripts/seed_demo.py`), route code-splitting, bundle optimization, and Playwright end-to-end demo story.

**Backend gaps / planned extensions:**
- Interviewer skills and daily capacity can be set only when the user is created (`POST /users`); there is no endpoint to edit them later.
- Only the `min_score` pass rule is implemented; unsupported rule types are rejected at stage creation/update and cannot silently pass a candidate.
- Email delivery is optional and uses standard-library SMTP when configured; without `SMTP_HOST` and `SMTP_FROM`, only in-app notifications are queued.
- Automatic drive status transitions to `in_progress` and `completed` as rounds start and end.
- Rate limiting on public booking links and login endpoints.

The coordinator dashboard uses database-backed counts, interview schedules, recent audit action labels, interviewer workload, and stage conversion. Its activity feed deliberately omits audit details and free-text feedback. AI interview kits are saved as drafts; coordinators can edit and save question text, MCQs, answer keys, and competency coverage before using them. Raw job descriptions are used only in local deterministic generation and are not forwarded to external AI providers.

---

## Free Render preview

The root `render.yaml` Blueprint defines the frontend static site, Docker API and private PostgreSQL 16 database. All compute and database resources are set to Render's **Free** plan; preview environments are disabled, and the AI provider stays deterministic so the deploy makes no OpenAI API calls. No paid plan or API key is configured.

To publish it, connect this repository in Render and create a Blueprint from `render.yaml`. Render will build both services, run Alembic migrations at API startup, and wire the frontend URL to the API. The frontend URL shown on the Render dashboard is the live app link.

This is a temporary preview: Render Free web services sleep after 15 minutes without traffic and can take about a minute to wake. The 1 GB Free Postgres database expires after 30 days; Render provides a 14-day upgrade grace period before deleting it, and Free Postgres has no backups. Export any data you need before expiry. The Blueprint itself only selects Free plans; Render account-level usage/billing settings remain managed in the Render dashboard.
## Production notes

Build and run the image without the development mount and without `--reload`:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"   # keep it: every instance must share it
export DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/interviewos"        # your real credentials and host

docker build -t interviewos-backend ./backend
docker run -d --name interviewos-backend -p 8000:8000 \
  -e ENVIRONMENT=production -e SECRET_KEY -e DATABASE_URL \
  interviewos-backend
docker run -d --name interviewos-notifications --no-healthcheck \
  -e ENVIRONMENT=production -e SECRET_KEY -e DATABASE_URL \
  interviewos-backend python -m app.scripts.run_notifications
```

- The container applies `alembic upgrade head` and then starts Uvicorn; if the migration fails the container exits instead of serving
  an unmigrated schema. Run **one** API replica, or run migrations as a separate release step, so two containers never migrate at once.
- Keep the same `SECRET_KEY` on every instance, or logins and booking links break across restarts and replicas.
- Put a TLS-terminating proxy in front. Booking links are bearer credentials in a URL; keep them out of access logs.
- The image runs as an unprivileged user and its `HEALTHCHECK` calls `/health`.
- `.dockerignore` keeps `.env` and virtualenvs out of the image; never bake secrets into it.
- Size memory from the benchmark's `Peak MB` for your largest expected drive, and set `workers` and `time_limit_seconds` per request
  within `SCHEDULER_MAX_WORKERS` and `SCHEDULER_MAX_TIME_LIMIT_SECONDS`.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `SECRET_KEY must be set to a random value...` on start | `ENVIRONMENT` is not `development` and the key is short or the dev default. Set a real key |
| `port is already allocated` on 5432 or 8000 | Set `POSTGRES_PORT` or `BACKEND_PORT` in a root `.env`, or stop the other service |
| `--reload` ignores edits (Docker Desktop on macOS or Windows) | Set `WATCHFILES_FORCE_POLLING=true` |
| Many tests `skipped` | PostgreSQL is unreachable or not migrated. Start it, run `alembic upgrade head`, run again |
| `type "..." does not exist` or missing column in tests | The test database is behind. `alembic upgrade head` against that database |
| `permission denied to create extension "btree_gist"` | Enable the extension as a superuser first, then run the migration |
| Backend container restarts in a loop | `docker compose logs backend`; usually a failed migration or a bad `DATABASE_URL` (use host `postgres`, not `localhost`, inside Compose) |

