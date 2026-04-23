# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SST Platform — Sistema de Seguridad y Salud en el Trabajo. A compliance and training management system for Colombian workplace safety regulations. Two separate apps:

- **Backend**: `sst-backend/` — FastAPI + PostgreSQL + SQLAlchemy
- **Frontend**: `sst-frontend/` — React 19 + TypeScript + Material-UI 7

---

## Commands

### Backend

```bash
# Development server (from sst-backend/)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Migrations
alembic upgrade head                                      # Apply all migrations
alembic revision -m "description"                        # New manual migration
alembic revision --autogenerate -m "description"         # Auto-detect changes (verify output before applying)
alembic downgrade -1                                     # Roll back one step
python migrate.py check                                  # Check migration status

# Tests
pytest
pytest tests/test_auth.py                                # Single file
pytest --cov=app                                         # With coverage
```

### Frontend

```bash
# From sst-frontend/
npm start           # Dev server on port 3000
npm run build       # Production build
npm test            # Run tests
npm run lint        # ESLint check
npm run lint:fix    # Auto-fix lint errors
npm run type-check  # TypeScript type checking only
```

---

## Backend Architecture

### Entry Point & Routing

`app/main.py` assembles the app: CORS, TrustedHost middleware, three APSchedulers (reinduction, occupational exams, course reminders), static file mounts, and a `lifespan` context that starts/stops schedulers.

All API routes are registered via `app/api/__init__.py` → `api_router`, with prefix `/api/v1`. There are 52 route modules under `app/api/`.

### Database Layer

- `app/database.py` — `SessionLocal` factory, `get_db()` dependency (injected into every route that needs DB).
- `app/models/` — 41 SQLAlchemy models. Import order matters: models must be imported before `create_tables()` runs.
- Alembic migrations live in `alembic/versions/`. **Never use `create_tables()` in production to create schema** — always use Alembic. `create_tables()` exists for test setup.
- Autogenerate migrations (`--autogenerate`) sometimes miss enum changes; write those manually following the pattern in existing migrations (e.g., `106e441ffcc4_make_course_id_nullable_in_certificates.py`).

### Auth & Roles

- JWT (HS256) via `python-jose`. Access token: 120 min, refresh token: 30 days.
- `app/dependencies.py` — `get_current_active_user()`, `has_role_or_custom()`, `require_admin()`, etc.
- Four fixed roles: `admin`, `trainer` (capacitador), `supervisor`, `employee`. Additionally, users can have a `custom_role_id` pointing to dynamically-defined permissions.
- `has_role_or_custom(user, ["admin", "trainer"])` is the idiomatic check — always prefer it over direct role comparisons.
- Account lockout after repeated failed logins (tracked in `User` model).

### Schema / Validation

- Pydantic v2 schemas in `app/schemas/`. Response schemas use `model_config = ConfigDict(from_attributes=True)` (not `class Config`).
- `Optional` fields default to `None`; required fields have no default.
- Some endpoints bypass Pydantic via `JSONResponse` (raw dict) — these are marked with `/direct/` prefix and exist to avoid serialization issues with complex nested data.

### File Storage

Local filesystem under `uploads/`, `certificates/`, `medical_reports/`, `attendance_lists/`. Optionally mirrored to Contabo S3 (`USE_CONTABO_STORAGE=true`). Always use the storage service abstraction, not direct file writes.

### AI Integration

Claude (Anthropic) and Perplexity APIs are used for legal matrix analysis and interactive lesson generation. Keys: `CLAUDE_API_KEY`, `PERPLEXITY_API_KEY`. Model defaults: `claude-sonnet-4-6`, `sonar`.

---

## Frontend Architecture

### API Client

`src/services/api.ts` — single Axios instance. Base URL from `REACT_APP_API_URL` (falls back to `http://localhost:8000/api/v1`). Two interceptors:
1. **Request**: injects `Authorization: Bearer <token>` from `localStorage`.
2. **Response**: on 401, clears `localStorage` and redirects to `/login`.

Timeout is 120 seconds (PDF generation endpoints can be slow).

### Routing & Auth

React Router v7. Protected routes check `localStorage` for token. Role-based redirects happen at the layout level — each role (`admin`, `trainer`, `supervisor`, `employee`) lands on a different dashboard.

### State Management

No Redux. State is local (`useState`) or shared via React Context (`src/contexts/`). Server data is fetched directly in `useEffect` / `useCallback` — no SWR or React Query.

### Types

Central type definitions in `src/types/index.ts`. All interfaces matching backend schemas live here. When changing backend schemas, update the corresponding interfaces in this file.

### Environment

Runtime config via `window._env_` (production Docker injection) with fallback to `process.env`. Config helper at `src/config/env.ts`. Required: `REACT_APP_API_URL`.

---

## Key Patterns

### Adding a new feature end-to-end

1. **Migration**: write manually in `alembic/versions/`, run `alembic upgrade head`.
2. **Model**: add/modify in `app/models/`, import in `app/models/__init__.py` if needed.
3. **Schema**: add Pydantic schemas in `app/schemas/`.
4. **CRUD/service**: business logic in `app/api/<feature>.py` (this project inlines CRUD logic in route functions — no separate `crud/` layer).
5. **Router**: register in `app/api/__init__.py`.
6. **Frontend types**: update `src/types/index.ts`.
7. **Frontend page**: add/update in `src/pages/`.

### Enum columns in migrations

Alembic autogenerate does NOT detect PostgreSQL enum value additions. Write the migration manually using `op.execute("ALTER TYPE ...")` — see existing migrations like `068250d6256f` or `765bc47` as reference.

### Evaluations without a course

`evaluation.course_id` is nullable. When `course_id IS NULL`, the evaluation is standalone. All JOIN queries against `courses` must use `outerjoin`. Employees see standalone (course-less, published) evaluations in addition to course-linked ones via `EvaluationAssignment` records.

---

## Required Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | JWT signing secret |
| `REACT_APP_API_URL` | ✅ | Backend URL for frontend |
| `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` | For email | Password reset, certificates |
| `CLAUDE_API_KEY` | For AI features | Legal matrix, interactive lessons |
| `CONTABO_*` | For S3 storage | Set `USE_CONTABO_STORAGE=true` |
