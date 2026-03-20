# FastAPI Multi-Tenant RLS API

A production-grade multi-tenant REST API built with FastAPI, PostgreSQL Row-Level Security (RLS), and JWT authentication. Each tenant's data is strictly isolated at the database level — no application-layer filtering required.

---

## Table of Contents

- [Architecture Overview (HLD)](#architecture-overview-hld)
- [Detailed Design (LLD)](#detailed-design-lld)
- [Security Design](#security-design)
- [Threat Model](#threat-model)
- [RLS Design](#rls-design)
- [Data Model](#data-model)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Logging](#logging)
- [Make Targets](#make-targets)

---

## Architecture Overview (HLD)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client / Consumer                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS  (Authorization: Bearer <JWT>)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                          │
│                                                                 │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│   │  API Layer   │   │  Service     │   │   CRUD / ORM     │  │
│   │  (Routers)   │──▶│  Layer       │──▶│   (SQLAlchemy)   │  │
│   │              │   │  (Business   │   │                  │  │
│   │  /v1/auth    │   │   Logic)     │   │  crud/tenant.py  │  │
│   │  /v1/users   │   │              │   │  crud/user.py    │  │
│   │  /v1/tenants │   │  service/    │   │  crud/case.py    │  │
│   │  /v1/cases   │   │  auth.py     │   │                  │  │
│   └──────────────┘   │  case.py     │   └──────────────────┘  │
│                       └──────────────┘                          │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                   Dependency Layer                       │  │
│   │  deps/auth.py: get_principal → get_rls_session          │  │
│   │  • Decodes JWT → TokenClaims(user_id, tenant_id)        │  │
│   │  • Injects SET LOCAL app.tenant_id / app.user_id        │  │
│   └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Two separate DB roles
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
   ┌─────────────────────┐      ┌─────────────────────────────┐
   │  app_owner (DDL)    │      │  app_user (DML / runtime)   │
   │                     │      │                             │
   │  • Alembic runs as  │      │  • Application runs as      │
   │    app_owner        │      │    app_user                 │
   │  • Owns all tables  │      │  • Subject to RLS policies  │
   │  • CREATEDB priv.   │      │  • Cannot bypass RLS        │
   └─────────────────────┘      └─────────────────────────────┘
                │                             │
                └──────────────┬──────────────┘
                               ▼
                ┌──────────────────────────────┐
                │       PostgreSQL 16+          │
                │                              │
                │  ┌────────────────────────┐  │
                │  │  Row-Level Security    │  │
                │  │  FORCE RLS on:         │  │
                │  │  • cases               │  │
                │  │  • case_events         │  │
                │  │                        │  │
                │  │  Policy:               │  │
                │  │  tenant_id =           │  │
                │  │  app.tenant_id (GUC)   │  │
                │  └────────────────────────┘  │
                │                              │
                │  Tables: tenants, users,     │
                │          cases, case_events, │
                │          pings               │
                └──────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| RLS at database layer | Tenant isolation is guaranteed even if application logic has bugs |
| FORCE ROW LEVEL SECURITY | Applies RLS even to `app_owner` (table owner); prevents accidental bypass. Note: PostgreSQL superusers can still bypass RLS — application connections must never use superuser roles |
| Two DB roles | `app_owner` for DDL; `app_user` for DML — least-privilege runtime |
| Append-only `case_events` | DB triggers block UPDATE/DELETE; immutable audit trail |
| Idempotency keys on status updates | Clients can safely retry without double-processing |
| JWT carries `tenant_id` + `user_id` | No extra DB lookup required to establish tenant context |

---

## Detailed Design (LLD)

### Request Lifecycle (Authenticated Endpoint)

```
Client
  │
  │  POST /v1/cases/   {"status": "OPEN"}
  │  Authorization: Bearer eyJ...
  ▼
FastAPI Router (app/api/v1/cases.py)
  │
  ├─ Depends(get_principal)
  │     │  HTTPBearer extracts token
  │     │  decode_access_token() → TokenClaims{user_id, tenant_id}
  │     │  401 if missing/invalid/expired
  │     ▼
  ├─ Depends(get_rls_session)
  │     │  Opens SQLAlchemy Session (as app_user)
  │     │  SELECT set_config('app.tenant_id', '<uuid>', true)
  │     │  SELECT set_config('app.user_id', '<uuid>', true)
  │     │  Yields session (transaction-local GUC active; auto-reset on commit)
  │     ▼
  └─ create_case(case_in, db, principal)
        │
        ▼
     Service Layer (app/service/case.py)
        │  create_new_case(db, case_in, tenant_id, created_by)
        │
        ▼
     CRUD Layer (app/crud/case.py)
        │  INSERT INTO cases (id, tenant_id, created_by, status, ...)
        │  PostgreSQL checks: tenant_id = current_setting('app.tenant_id')
        │  INSERT blocked if tenant_id mismatch (RLS WITH CHECK)
        │
        ▼
     Response: CaseResponse{id, tenant_id, created_by, status, created_at}
```

### Layer Responsibilities

| Layer | Files | Responsibility |
|---|---|---|
| API | `app/api/v1/` | HTTP routing, request parsing, response serialization, error mapping |
| Service | `app/service/` | Business logic, orchestration, transaction boundaries |
| CRUD | `app/crud/` | Database queries, ORM model operations |
| Models | `app/models/` | SQLAlchemy ORM table definitions |
| Schemas | `app/schemas/` | Pydantic request/response models |
| Domain | `app/domain/` | Enums and domain types |
| Deps | `app/deps/` | FastAPI dependency injection (auth, sessions) |
| DB | `app/db/` | Session factories, connection setup |
| Core | `app/core/` | Config, JWT/password security utilities, logging setup |

### Transaction Design

- Each request gets one `Session` (connection) from the pool
- `get_rls_session` sets GUC vars (`app.tenant_id`, `app.user_id`) as **transaction-local** (`true`) before yielding
- **Dependency layer owns the transaction boundary** — `get_rls_session` and `get_db` call `db.commit()` on success or `db.rollback()` on exception after the route handler returns
- Service and CRUD layers call only `db.flush()` — never `db.commit()` — so all writes in a request are committed atomically
- Session is always closed in the `finally` block regardless of outcome

### Idempotency Flow (Status Update)

```
PATCH /v1/cases/{case_id}/status
  {"status": "APPROVED", "idempotency_key": "key-abc-123", "reason": "..."}
  │
  ├─ Look up existing case_event WHERE idempotency_key = 'key-abc-123'
  │     ├─ Found → return existing event (no-op, idempotent)
  │     └─ Not found → continue
  │
  ├─ UPDATE cases SET status = 'APPROVED'
  ├─ INSERT INTO case_events (event_type='STATUS_CHANGED', idempotency_key)
  │     └─ IntegrityError (unique violation) → race condition detected
  │           → two clients retried simultaneously; only one INSERT wins
  │           → SAVEPOINT rolled back (outer transaction with RLS context intact)
  │           → re-query existing event → return it
  └─ COMMIT (owned by get_rls_session dependency)
```

The `UNIQUE(tenant_id, case_id, idempotency_key)` constraint is the safety net for concurrent retries. If two clients send the same `idempotency_key` simultaneously, only one `INSERT` succeeds at the database level. The loser gets an `IntegrityError` — the service uses a **SAVEPOINT** (`db.begin_nested()`) so only the nested write is rolled back. The outer transaction (and its transaction-local RLS GUC values) remains intact, allowing the recovery query to execute correctly. No duplicate events are ever created.

---

## Security Design

### Authentication Flow

```
POST /v1/auth/register  →  creates tenant + admin user  →  returns JWT
POST /v1/auth/{slug}/login  →  verifies password  →  returns JWT

JWT payload:
  {
    "sub": "<user_id>",
    "user_id": "<user_id>",
    "tenant_id": "<tenant_id>",
    "exp": <unix_timestamp>
  }

All protected endpoints:
  Authorization: Bearer <JWT>
```

### Password Hashing

- Algorithm: **Argon2id** via `passlib[argon2]`
- Argon2id is memory-hard and resistant to GPU/ASIC brute-force attacks
- Passwords are never stored in plain text

### JWT

| Property | Value |
|---|---|
| Algorithm | HS256 |
| Library | `python-jose` |
| Signing key | `JWT_SECRET` env var |
| Expiry | `ACCESS_TOKEN_EXPIRE_MINUTES` env var |
| Claims | `sub`, `user_id`, `tenant_id`, `exp` |

### Database Role Separation

| Role | Used by | Privileges |
|---|---|---|
| `postgres` | Test setup only | Superuser — creates/drops test DBs |
| `app_owner` | Alembic migrations | DDL (CREATE TABLE, ALTER, etc.), CREATEDB |
| `app_user` | Application runtime | DML (SELECT, INSERT, UPDATE, DELETE) on owned tables; subject to RLS |

The `app_user` role cannot bypass RLS policies. Even if application code attempted a cross-tenant query, PostgreSQL would return zero rows (or block the write).

---

## Threat Model

This system is designed to resist tenant isolation failures at every layer. The table below maps potential attack surfaces to their mitigations:

| Layer | Risk | Mitigation |
|---|---|---|
| API | Missing tenant filter in query | DB-level RLS enforces it regardless |
| ORM / CRUD | Developer forgets `tenant_id` WHERE clause | RLS `USING` policy filters rows silently |
| SQL injection | Bypass application filters | Parameterized queries (SQLAlchemy ORM) + RLS as second line |
| Connection pooling | Stale `app.tenant_id` leaks to next request | Transaction-local GUCs (`set_config(..., true)`) are auto-reset on commit; no stale context can survive pool return |
| Superuser access | Bypass FORCE RLS | Application never connects as superuser; `app_user` is non-superuser |
| Audit trail tampering | DELETE/UPDATE case events | DB triggers block mutation; append-only enforced at database level |
| Token forgery | Fake `tenant_id` in JWT | JWT signed with `JWT_SECRET`; tampering causes signature verification failure |

**Defense in depth:** RLS is a hard database constraint, not an application convention. Even if application code is buggy or a developer makes a mistake, PostgreSQL will not return or accept cross-tenant rows.

---

## RLS Design

### Concept

PostgreSQL's Row-Level Security allows defining policies that filter which rows a role can see or modify. With `FORCE ROW LEVEL SECURITY`, the policies apply even to the table owner (`app_owner`), providing a hard guarantee.

> **Important:** PostgreSQL superusers can still bypass RLS regardless of `FORCE ROW LEVEL SECURITY`. In production environments, application connections must never use superuser roles. This system uses `app_user` (a non-superuser role) for all runtime queries.

### Context Injection

Every request sets two PostgreSQL configuration variables (GUCs) on the active connection:

```python
# In get_rls_session (app/deps/auth.py)
db.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(principal.tenant_id)})
db.execute(text("SELECT set_config('app.user_id', :uid, true)"),   {"uid": str(principal.user_id)})
```

PostgreSQL configuration variables (GUCs) are stored per connection. The `true` argument means the setting is **transaction-local** — it is automatically reset to its prior value when the transaction commits or rolls back. This is the correct mode for connection-pooled environments: after `get_rls_session` commits at the end of the request, the GUC values are cleared, so the connection can safely return to the pool without carrying stale tenant context.

### RLS Policies

```sql
-- cases table
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases FORCE ROW LEVEL SECURITY;

CREATE POLICY cases_tenant_isolation ON cases
  USING     (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

-- case_events table
ALTER TABLE case_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_events FORCE ROW LEVEL SECURITY;

CREATE POLICY case_events_tenant_isolation ON case_events
  USING     (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
```

- `USING` — filters rows on SELECT, UPDATE, DELETE
- `WITH CHECK` — blocks INSERT/UPDATE that would create cross-tenant rows
- `nullif(..., '')::uuid` — safe cast; returns NULL if GUC is unset, which matches no rows

### RLS Coverage

| Table | RLS Enabled | FORCE RLS | Policy |
|---|---|---|---|
| `tenants` | No | No | Public (no sensitive per-row data) |
| `users` | No | No | See note below |
| `cases` | Yes | Yes | `cases_tenant_isolation` |
| `case_events` | Yes | Yes | `case_events_tenant_isolation` |

**Why `tenants` and `users` do not use RLS:**

User registration and tenant creation must occur *before* any tenant context exists — there is no `app.tenant_id` GUC set at that point. If RLS were enabled on these tables, the `USING` policy would match nothing and registration would silently fail or block.

Identity tables (`tenants`, `users`) are therefore outside the RLS boundary. Access control for these tables is enforced at the application layer instead.

### Append-Only `case_events`

`case_events` is enforced as append-only at the database level via triggers:

```sql
CREATE OR REPLACE FUNCTION prevent_case_events_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'case_events is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER case_events_no_update
  BEFORE UPDATE ON case_events FOR EACH ROW
  EXECUTE FUNCTION prevent_case_events_mutation();

CREATE TRIGGER case_events_no_delete
  BEFORE DELETE ON case_events FOR EACH ROW
  EXECUTE FUNCTION prevent_case_events_mutation();
```

This ensures an immutable audit trail regardless of application logic.

### Connection Pool Safety

With session-scoped GUCs (`set_config(..., false)`), there would be a real risk in connection-pooled environments:

```
Request A → sets app.tenant_id = "tenant-A"  (session-scoped)
            commits, connection returned to pool

Request B → gets the same connection
            app.tenant_id is still "tenant-A" ← tenant leak!
```

This system eliminates that risk by using **transaction-local** GUCs (`set_config(..., true)`). When the dependency commits at the end of Request A, PostgreSQL automatically resets all transaction-local GUC values to their defaults. The connection returns to the pool clean — no tenant context remains.

```
Request A → sets app.tenant_id = "tenant-A"  (transaction-local)
            COMMIT → GUC auto-reset to default
            connection returned to pool

Request B → gets the same connection
            app.tenant_id = "" (unset) ← safe
            get_rls_session sets app.tenant_id = "tenant-B"
```

The application also uses `NullPool` in tests to guarantee complete connection isolation between test cases.

---

## Data Model

### Entity Relationship Diagram

```
┌──────────────────┐        ┌──────────────────────────┐
│     tenants      │        │          users           │
│──────────────────│        │──────────────────────────│
│ id (PK, UUID)    │◄───────│ id (PK, UUID)            │
│ name (str)       │  1:N   │ tenant_id (FK → tenants) │
│ slug (unique)    │        │ name (str)               │
│ created_at       │        │ email (str)              │
└──────────────────┘        │ password_hash (str)      │
                            │ role (enum)              │
                            │ created_at               │
                            │ updated_at               │
                            └──────────┬───────────────┘
                                       │
                            ┌──────────▼───────────────┐
                            │          cases           │
                            │──────────────────────────│
                            │ id (PK, UUID)            │
                            │ tenant_id (FK → tenants) │◄── RLS
                            │ created_by (FK → users)  │
                            │ status (enum)            │
                            │ created_at               │
                            │ updated_at               │
                            └──────────┬───────────────┘
                                       │
                            ┌──────────▼───────────────┐
                            │       case_events        │
                            │──────────────────────────│
                            │ id (PK, UUID)            │
                            │ case_id (FK → cases)     │◄── RLS + append-only
                            │ tenant_id (FK → tenants) │
                            │ actor_id (FK → users)    │
                            │ event_type (enum)        │
                            │ event_ts                 │
                            │ payload (JSONB)          │
                            │ idempotency_key (str)    │◄── unique per tenant+case
                            │ created_at               │
                            │ updated_at               │
                            └──────────────────────────┘
```

### Enums

**UserRole**
| Value | Description |
|---|---|
| `ADMIN` | Tenant administrator |
| `USER` | Standard user |
| `MANAGER` | Manager role |
| `SUPERVISOR` | Supervisor role |
| `PLATFORM_ADMIN` | Platform-level admin |
| `AUDITOR` | Read-only auditor |

**CaseStatus**
| Value | Description |
|---|---|
| `OPEN` | Case is open and active |
| `IN_REVIEW` | Case is under review |
| `APPROVED` | Case has been approved |
| `REJECTED` | Case has been rejected |

**CaseEventType**
| Value | Description |
|---|---|
| `CASE_CREATED` | Case was created |
| `EVIDENCE_COMPLETED` | Evidence collection completed |
| `SCREENING_COMPLETED` | Screening process completed |
| `APPROVED` | Case was approved |
| `STATUS_CHANGED` | Case status was changed |

### Key Constraints

| Table | Constraint | Purpose |
|---|---|---|
| `tenants` | `UNIQUE(slug)` | URL-safe tenant identifier |
| `users` | `UNIQUE(tenant_id, email)` | Email unique per tenant, not globally |
| `case_events` | `UNIQUE(tenant_id, case_id, idempotency_key)` | Idempotent event writes |

---

## API Reference

Base URL: `http://localhost:8000`

### Health

#### GET /health

Check API health status.

```bash
curl http://localhost:8000/health
```

**Response 200**
```json
{"status": "ok"}
```

---

### Authentication

#### POST /v1/auth/register

Register a new tenant and an admin user. Returns an access token.

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "admin_name": "Alice",
    "admin_email": "alice@acme.com",
    "admin_password": "supersecret123"
  }'
```

**Response 200**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error responses**
| Status | Reason |
|---|---|
| 400 | Duplicate email or invalid input |
| 422 | Missing required fields |

---

#### POST /v1/auth/{tenant_slug}/login

Authenticate a user within a tenant and obtain an access token.

```bash
curl -X POST http://localhost:8000/v1/auth/acme-corp/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@acme.com",
    "password": "supersecret123"
  }'
```

**Response 200**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error responses**
| Status | Reason |
|---|---|
| 400 | Wrong password or user not found |
| 403 | Tenant slug not found |
| 422 | Missing required fields |

---

### Tenants

#### GET /v1/tenants/{tenant_id}

Retrieve a tenant by its UUID.

```bash
curl http://localhost:8000/v1/tenants/550e8400-e29b-41d4-a716-446655440000
```

**Response 200**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "created_at": "2026-03-04T18:00:00Z"
}
```

**Error responses**
| Status | Reason |
|---|---|
| 404 | Tenant not found |

---

### Users

#### POST /v1/users/

Create a new user within the authenticated tenant. Requires a valid JWT.

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X POST http://localhost:8000/v1/users/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bob Smith",
    "email": "bob@acme.com",
    "password": "securepass456",
    "role": "USER"
  }'
```

**Response 200**
```json
{
  "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "name": "Bob Smith",
  "email": "bob@acme.com",
  "role": "USER",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-03-04T19:00:00Z"
}
```

**Error responses**
| Status | Reason |
|---|---|
| 400 | Duplicate email within tenant |
| 401 | Missing or invalid JWT |
| 422 | Missing required fields |

---

### Cases

All case endpoints require a valid JWT. Tenant isolation is enforced by RLS — users can only see and modify cases belonging to their own tenant.

#### POST /v1/cases/

Create a new case.

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X POST http://localhost:8000/v1/cases/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "OPEN"}'
```

**Response 200**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_by": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "status": "OPEN",
  "created_at": "2026-03-04T20:00:00Z"
}
```

**Request body**
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `status` | `CaseStatus` | No | `OPEN` | Initial status |

**Error responses**
| Status | Reason |
|---|---|
| 401 | Missing or invalid JWT |

---

#### GET /v1/cases/

List all cases for the authenticated tenant. Supports pagination.

```bash
curl "http://localhost:8000/v1/cases/?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

**Query parameters**
| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `limit` | `int` | `50` | 1–200 | Maximum number of cases to return |
| `offset` | `int` | `0` | ≥ 0 | Number of cases to skip |

**Response 200**
```json
[
  {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_by": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "status": "OPEN",
    "created_at": "2026-03-04T20:00:00Z"
  }
]
```

**Error responses**
| Status | Reason |
|---|---|
| 401 | Missing or invalid JWT |
| 422 | Invalid pagination parameters |

---

#### GET /v1/cases/{case_id}

Retrieve a specific case by ID. RLS ensures cross-tenant access returns 404.

```bash
curl http://localhost:8000/v1/cases/7c9e6679-7425-40de-944b-e07fc1f90ae7 \
  -H "Authorization: Bearer $TOKEN"
```

**Response 200**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_by": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "status": "OPEN",
  "created_at": "2026-03-04T20:00:00Z"
}
```

**Error responses**
| Status | Reason |
|---|---|
| 401 | Missing or invalid JWT |
| 404 | Case not found (or belongs to another tenant) |

---

#### PATCH /v1/cases/{case_id}/status

Update the status of a case. Uses idempotency key to safely handle retries.

```bash
curl -X PATCH \
  http://localhost:8000/v1/cases/7c9e6679-7425-40de-944b-e07fc1f90ae7/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "IN_REVIEW",
    "idempotency_key": "transition-open-to-review-001",
    "reason": "Starting review process"
  }'
```

**Response 200**
```json
{
  "case_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "new_status": "IN_REVIEW",
  "event_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
  "event_type": "STATUS_CHANGED"
}
```

**Request body**
| Field | Type | Required | Description |
|---|---|---|---|
| `status` | `CaseStatus` | Yes | New status |
| `idempotency_key` | `string` | Yes | Unique key per transition (safe to retry) |
| `reason` | `string` | No | Required if status is `APPROVED` or `REJECTED` |

**Error responses**
| Status | Reason |
|---|---|
| 401 | Missing or invalid JWT |
| 404 | Case not found |

---

#### POST /v1/cases/events

Append a raw event to a case.

```bash
curl -X POST http://localhost:8000/v1/cases/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "event_type": "EVIDENCE_COMPLETED",
    "idempotency_key": "evidence-done-001",
    "payload": {"documents": 3, "verified": true}
  }'
```

**Response 200**
```json
{
  "id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "case_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "actor_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "event_type": "EVIDENCE_COMPLETED",
  "event_ts": "2026-03-04T21:00:00Z",
  "payload": {"documents": 3, "verified": true}
}
```

**Error responses**
| Status | Reason |
|---|---|
| 401 | Missing or invalid JWT |

---

#### GET /v1/cases/{case_id}/events

List all events for a case.

```bash
curl http://localhost:8000/v1/cases/7c9e6679-7425-40de-944b-e07fc1f90ae7/events \
  -H "Authorization: Bearer $TOKEN"
```

**Response 200**
```json
[
  {
    "id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "case_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "actor_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "event_type": "CASE_CREATED",
    "event_ts": "2026-03-04T20:00:00Z",
    "payload": {}
  }
]
```

---

### Ping (Demo)

#### GET /v1/ping/

```bash
curl http://localhost:8000/v1/ping/
```

**Response 200**
```json
[{"id": 1, "message": "pong"}]
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- `make` (optional but recommended)

### 1. Clone and configure

```bash
git clone <repo-url>
cd rls-firstapi
cp .env.example .env   # edit with your values
```

### 2. Start the stack

```bash
make up
# or: sudo docker compose up -d --build

# For development (hot-reload enabled):
sudo docker compose --profile dev up -d --build
```

### 3. Run migrations

```bash
make dbup
# or: sudo docker compose run --rm api alembic upgrade head
```

### 4. One-time: Grant CREATEDB to app_owner

Required once per fresh database (enables isolated test DB creation):

```bash
make db-grant-createdb
# or: sudo docker compose exec db psql -U postgres -c "ALTER ROLE app_owner CREATEDB;"
```

### 5. Register a tenant and start using the API

```bash
# Register tenant + admin user
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Company",
    "admin_name": "Admin User",
    "admin_email": "admin@mycompany.com",
    "admin_password": "strongpassword123"
  }'

# Login (use the slug generated from your tenant name)
curl -X POST http://localhost:8000/v1/auth/my-company/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@mycompany.com", "password": "strongpassword123"}'

# Use the token
export TOKEN="<token from login response>"

# Create a case
curl -X POST http://localhost:8000/v1/cases/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "OPEN"}'
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | SQLAlchemy URL for `app_user` runtime connection (e.g. `postgresql+psycopg://app_user:pass@db:5432/appdb`) |
| `ALEMBIC_DATABASE_URL` | Yes | SQLAlchemy URL for `app_owner` migration connection |
| `JWT_SECRET` | Yes | JWT signing key (keep secret, min 32 chars recommended). `JWT_SECRET_KEY` and legacy `SECRET_KEY` are also accepted |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | JWT lifetime in minutes (e.g. `60`) |
| `CORS_ORIGINS` | No | Comma-separated list of allowed CORS origins (e.g. `http://localhost:3000,https://app.example.com`). Defaults to none |
| `LOG_LEVEL` | No | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Defaults to `INFO` |
| `LOG_JSON` | No | Set to `true` to emit structured JSON logs (recommended in production). Defaults to `false` (human-readable text) |
| `TEST_ADMIN_DATABASE_URL` | Test only | Superuser URL for creating/dropping test databases (e.g. `postgresql+psycopg://postgres:postgres@db:5432/postgres`) |

---

## Testing

### Test Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    pytest session                       │
│                                                         │
│  session-scoped fixtures (run once):                    │
│  ┌────────────────────────────────────────────────────┐ │
│  │  test_db_url                                       │ │
│  │    1. Create app_test_<random10> DB (as postgres)  │ │
│  │    2. alembic upgrade head (as app_owner)          │ │
│  │    3. yield test DB URL                            │ │
│  │    4. Drop test DB (teardown)                      │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────┐ │
│  │  TestSessionLocal                                  │ │
│  │    URL: app_user @ test DB (mirrors production)    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  per-test autouse fixtures:                             │
│  ┌────────────────────────────────────────────────────┐ │
│  │  override_get_db → redirects public DB dep         │ │
│  │  override_get_rls_session → injects principal,     │ │
│  │    sets app.tenant_id / app.user_id on connection  │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Why `app_user` in tests?**
`cases` and `case_events` have `FORCE ROW LEVEL SECURITY`. Even `app_owner` (table owner) cannot bypass RLS with FORCE. Runtime sessions must use `app_user` — exactly as in production — or all writes will fail with "new row violates row-level security policy".

### RLS Isolation Verified by Tests

The integration test suite explicitly validates tenant isolation at the database level:

- **Cross-tenant reads blocked** — a token from tenant A cannot retrieve cases belonging to tenant B; the RLS `USING` policy returns zero rows, producing a 404
- **Cross-tenant writes blocked** — inserting a row with a mismatched `tenant_id` is rejected by the RLS `WITH CHECK` policy
- **RLS policies confirmed present** — tests connect as `app_user` (not `app_owner`), which means any missing or misconfigured policy would immediately cause test failures

These tests run against a real PostgreSQL instance with full migrations applied, making them a reliable guard against RLS regressions.

### Test Structure

```
app/
├── tests/                          # Integration tests (real DB + RLS)
│   ├── conftest.py                 # DB lifecycle + FastAPI overrides
│   ├── test_smoke.py               # Health and basic connectivity
│   ├── test_auth.py                # Register + login flows
│   └── test_cases.py              # Case CRUD + RLS isolation + idempotency
│
├── core/tests/
│   └── test_security.py            # Unit: JWT + password hashing
│
├── utils/tests/
│   └── test_slug.py                # Unit: slug generation
│
└── service/tests/
    ├── test_auth.py                # Unit: register/login service layer
    └── test_case.py                # Unit: case service layer
```

### Running Tests

**All tests (integration + unit) via Docker:**
```bash
make test
```

**Unit tests only (no DB required, fast):**
```bash
make test-unit
```

**Integration tests only (requires running DB):**
```bash
make test-integration
```

**With coverage report:**
```bash
make test-cov
```

**First time setup** (run once on a fresh environment):
```bash
make db-grant-createdb   # grants CREATEDB to app_owner
make test                # runs all tests
```

---

## Project Structure

```
rls-firstapi/
├── app/
│   ├── api/
│   │   ├── health.py              # GET /health
│   │   └── v1/
│   │       ├── auth.py            # POST /auth/register, /auth/{slug}/login
│   │       ├── cases.py           # CRUD /cases, /cases/events
│   │       ├── tenant.py          # GET /tenants/{id}
│   │       ├── user.py            # POST /users/
│   │       └── ping.py            # GET /ping/
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── logging_config.py      # LoggingManager, LogSink ABC, get_logger()
│   │   ├── security.py            # JWT encode/decode, password hash/verify
│   │   └── tests/
│   │       └── test_security.py
│   ├── crud/
│   │   ├── case.py                # ORM queries for cases + events
│   │   ├── tenant.py              # ORM queries for tenants
│   │   ├── user.py                # ORM queries for users
│   │   └── ping.py
│   ├── db/
│   │   ├── public.py              # get_db (unauthenticated session, transaction owner)
│   │   ├── rls.py                 # RLS session utilities
│   │   └── session.py             # SessionLocal (app_user)
│   ├── deps/
│   │   └── auth.py                # get_principal (JWT decode), get_rls_session (RLS + transaction owner)
│   ├── domain/
│   │   ├── case_enum.py           # CaseStatus, CaseEventType
│   │   └── roles.py               # UserRole
│   ├── models/
│   │   ├── base.py                # DeclarativeBase
│   │   ├── case.py                # Case ORM model
│   │   ├── case_events.py         # CaseEvent ORM model
│   │   ├── tenant.py              # Tenant ORM model
│   │   └── user.py                # User ORM model
│   ├── schemas/
│   │   ├── auth.py                # TokenClaims, LoginRequest/Response, RegisterRequest/Response
│   │   ├── case.py                # CaseCreate, CaseResponse, CaseEventCreate, etc.
│   │   ├── tenant.py              # TenantResponse
│   │   └── user.py                # CreateUser, UserResponse
│   ├── service/
│   │   ├── auth.py                # register_tenant, login_tenant
│   │   ├── case.py                # create_new_case, update_case_status, etc.
│   │   └── tests/
│   │       ├── test_auth.py
│   │       └── test_case.py
│   ├── tests/                     # Integration tests
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_cases.py
│   │   └── test_smoke.py
│   └── utils/
│       ├── slug.py                # slugify, generate_unique_slug
│       └── tests/
│           └── test_slug.py
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 53184ca3391f_*.py      # Initial ping table
│       ├── 2a37263a67be_*.py      # Add tenants + users + RLS
│       ├── 5b6df6d193f9_*.py      # Add cases + case_events + RLS + triggers
│       ├── 4185f6f685eb_*.py      # DB role grants
│       └── f10adf536bc9_*.py      # Disable RLS on identity tables
├── app/db/init/
│   └── 001_roles.sql              # Creates app_owner, app_user roles (Docker init)
├── docker-compose.yml             # Services: db, api (prod), api-dev (--profile dev, hot-reload), test (profile)
├── Dockerfile
├── Makefile
├── pyproject.toml
├── .env                           # Production env vars (git-ignored)
└── .env.test                      # Test env vars (git-ignored)
```

---

## Logging

All logging is centralised through `app/core/logging_config.py`.

### LoggingManager

A singleton `logging_manager` is initialised once in `app/main.py` before any other import:

```python
from app.core.config import settings
from app.core.logging_config import logging_manager

logging_manager.setup(level=settings.LOG_LEVEL, json_format=settings.LOG_JSON)
```

Call `get_logger(__name__)` anywhere in the codebase to obtain a standard `logging.Logger` that routes through the manager:

```python
from app.core.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Case created", extra={"case_id": str(case.id)})
```

### Output formats

| `LOG_JSON` | Format | Use case |
|---|---|---|
| `false` (default) | Coloured, human-readable text (TTY-aware, colours stripped if not a TTY) | Local development |
| `true` | Structured JSON — one object per line with timestamp, level, logger, message, and any `extra` fields | Production / log aggregators (Datadog, Loki, CloudWatch, etc.) |

### Adding a third-party sink

`LogSink` is an abstract base class. Implement it and register it with `logging_manager.add_sink()` **after** calling `setup()`:

```python
import logging
from app.core.logging_config import LogSink, logging_manager

class DatadogSink(LogSink):
    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.ERROR:
            # forward to Datadog or any external platform
            datadog_client.send(record.getMessage())

logging_manager.add_sink(DatadogSink())
```

All log records — including those already written to the terminal — are forwarded to every registered sink. The terminal handler is always active regardless of whether sinks are configured.

---

## Make Targets

| Target | Description |
|---|---|
| `make up` | Build and start all services in detached mode |
| `make down` | Stop and remove containers |
| `make logs` | Follow API container logs |
| `make sh` | Open a shell in the API container |
| `make mig m="<name>"` | Generate an Alembic migration with the given name |
| `make dbup` | Apply all pending Alembic migrations |
| `make dbdown` | Downgrade one Alembic migration step |
| `make db-grant-createdb` | Grant CREATEDB privilege to app_owner (run once on fresh DB) |
| `make test` | Run all tests (unit + integration) in Docker |
| `make test-unit` | Run only unit tests (fast, no DB) |
| `make test-integration` | Run only integration tests (requires DB) |
| `make test-cov` | Run all tests with coverage report |

---

## Interactive API Docs

When the server is running, Swagger UI is available at:

```
http://localhost:8000/docs
```

ReDoc is available at:

```
http://localhost:8000/redoc
```
