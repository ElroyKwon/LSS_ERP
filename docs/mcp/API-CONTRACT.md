# LSS ERP MCP REST Contract

## Authority and release state

The main developer's versioned backend OpenAPI document and returned SHA-256
are the integration authority. The local FastAPI stub is a database-free test
oracle, not the deployed API.

- State: `DEVELOPMENT/NOT-RELEASED`
- Local MCP surface: exactly seven tools
- ERP REST allowlist: exactly five method/path pairs
- Remote write tools: exactly one, disabled by default
- Real backend, PostgreSQL, OpenAPI, canary, and rollback: `NOT-RUN`

This is not a generic ERP bridge. Any capability outside this document requires
a separate inventory, data-minimization rule, scope, contract, threat review,
test Gate, and user approval.

## Trust boundary

```mermaid
flowchart LR
    WORKLOG["Personal worklog"] --> HOST["Approved AI host<br/>local interpretation"]
    HOST -->|"minimal structured facts"| MCP["Isolated mcp_server"]
    MCP -->|"HTTPS + bearer token"| API["ERP REST API"]
    API --> AUTH["Token AuthContext"]
    API --> DB[("PostgreSQL")]

    WORKLOG -. "raw text/path never sent" .-> API
    MCP -. "no vault access" .-> WORKLOG
    MCP -. "no DB account / DATABASE_URL" .-> DB
```

The backend derives `user_id` and `employee_id` from the validated token.
Client-provided `employee_id`, `user_id`, `approver_id`, `status`, or
`labor_type` authority fields must be rejected rather than ignored.

## REST allowlist

| Method | Path | Required scope | State effect |
|---|---|---|---|
| `GET` | `/api/auth/me` | `mcp:discover` | None; minimum token identity |
| `GET` | `/api/timesheets/week` | `timesheet:read:self` | None; server-bound self |
| `GET` | `/api/timesheets/entry-context` | `timesheet:read:self` | None; token-owner entry rules |
| `GET` | `/api/timesheets/projects` | `timesheet:read:self` | None; eligible project candidates |
| `POST` | `/api/timesheets/mcp-draft` | `timesheet:write:self:draft` | Own draft only |

All other method/path pairs are denied by the MCP REST client and must be
default-denied for an API token by the backend.

## Common response contract

- Success returns stable, versioned JSON and a correlation ID where applicable.
- `401`: missing, expired, revoked, or invalid token.
- `403`: client, scope, ownership, resource, endpoint, or protected-state denial.
- `404`: allowlisted resource not found without cross-user disclosure.
- `409`: stale version, duplicate logical row, or idempotency conflict.
- `422`: strict input validation failure.
- `429`: bounded retry metadata; no blind write retry.
- `5xx`: redacted error with correlation ID; no secret, SQL, or raw body.
- Redirects are rejected.
- Responses over the configured byte limit are rejected.
- Unknown response fields are rejected.

## Canonical daily entry

```json
{
  "work_date": "2026-07-20",
  "project_id": 123,
  "project_name": "MCP 개발",
  "project_source": "실행",
  "spg": "에너지",
  "hours": "8",
  "work_type": "실행 > 업무지원",
  "description": "MCP 안전 계약 개발"
}
```

Rules:

- `work_date` is inside the requested Monday-to-Sunday week.
- `hours` is `0.25..24` in quarter-hour increments.
- `project_source` is `실행`, `영업`, or `공통`.
- `실행` requires an eligible active `project_id`.
- `영업` and `공통` omit `project_id` and require `project_name`.
- `연차` is `project_id=null`, `project_name=연차`,
  `project_source=공통`, `work_type=공통 > 연차`.
- `description` maps to the existing ERP row note.
- The backend derives employee and labor type.

The backend adapter maps daily entries into the existing weekly
`mon_hours..sun_hours` row representation without redesigning the database
solely for MCP.

## `GET /api/timesheets/entry-context`

Request:

```text
GET /api/timesheets/entry-context?week_start=2026-07-20
```

Response:

```json
{
  "week_start": "2026-07-20",
  "week_end": "2026-07-26",
  "labor_type": "원가",
  "project_sources": ["실행", "영업", "공통"],
  "work_types": [
    "공통 > 연차",
    "공통 > 교육",
    "공통 > 행사",
    "공통 > 기타",
    "실행 > 업무지원"
  ],
  "daily_targets": [
    {
      "work_date": "2026-07-20",
      "target_hours": "8",
      "reason": "normal"
    }
  ]
}
```

The actual response contains exactly seven ordered `daily_targets`. Weekend,
holiday, leave-policy, or employee-calendar behavior is backend-owned and must
be evidenced. The request and response contain no employee selector.

The main developer must resolve and test the existing frontend/backend
work-type catalog drift, including `영업 > SHOP작업`, before declaring DTO
parity.

## `GET /api/timesheets/projects`

Request:

```text
GET /api/timesheets/projects?q=MCP&limit=20
```

Response:

```json
{
  "items": [
    {
      "project_id": 123,
      "project_code": "P-2026-001",
      "project_name": "MCP 개발",
      "project_source": "실행",
      "spg": "에너지",
      "active": true
    }
  ],
  "truncated": false
}
```

`project_id` may be `null` for a sales/common candidate only when the backend
can persist the returned `project_name` and `project_source` safely.

## Structured worklog input

The raw worklog and its path are not REST payloads. The approved AI host reads
them locally and calls the local MCP with facts such as:

```json
{
  "fact_id": "log-20260720-1",
  "work_date": "2026-07-20",
  "entry_kind": "project",
  "description": "MCP 안전 계약 개발",
  "hours": "8",
  "project_query": "MCP 개발",
  "work_type": "실행 > 업무지원"
}
```

`fact_id` is an opaque local correlation ID. It accepts only bounded
alphanumeric punctuation and cannot contain a path. The local prepare layer
rejects extra identity, status, raw-content, or authority fields.

The local `timesheet_prepare_from_worklog` tool:

- performs no POST;
- resolves only an unambiguous eligible candidate;
- never invents missing hours or work type;
- preserves unrelated current rows;
- returns daily/weekly totals and deterministic questions;
- accepts only explicitly approved coverage exception IDs;
- creates a confirmation only when blockers are cleared.

Worklog facts, question objects, candidate options, and accepted exception IDs
are not included in the ERP write body.

## `POST /api/timesheets/mcp-draft`

Request:

```json
{
  "week_start": "2026-07-20",
  "expected_version": 3,
  "entries": [
    {
      "work_date": "2026-07-20",
      "project_id": null,
      "project_name": "연차",
      "project_source": "공통",
      "spg": null,
      "hours": "8",
      "work_type": "공통 > 연차",
      "description": "연차"
    }
  ]
}
```

Required headers:

- `Authorization: Bearer <token>`; never recorded in evidence;
- `Idempotency-Key: <UUID>`;
- `X-Correlation-ID: <UUID>`.

Write invariants:

- self-only and draft-only;
- explicit expected version;
- employee/week uniqueness in PostgreSQL;
- project eligibility and source validation;
- backend-derived labor type;
- idempotency key and request hash enforced together;
- same key and hash replay the original result;
- same key with another hash returns `409`;
- uncertain timeout reconciled by readback before any same-key retry;
- version advances exactly once;
- mutation and audit commit in one transaction;
- submitted, approved, and rejected records are immutable;
- post-write readback must match the complete expanded entry proposal.

## MCP tool mapping

| MCP tool | REST call | Remote mutation |
|---|---|---|
| `erp_get_current_user` | `GET /api/auth/me` | No |
| `timesheet_get_week` | `GET /api/timesheets/week` | No |
| `timesheet_get_entry_context` | `GET /api/timesheets/entry-context` | No |
| `timesheet_search_projects` | `GET /api/timesheets/projects` | No |
| `timesheet_prepare_draft` | Read endpoints only; complete replacement | No |
| `timesheet_prepare_from_worklog` | Read endpoints only; merge-only | No |
| `timesheet_commit_draft` | `POST /api/timesheets/mcp-draft` | Yes; disabled by default |

Preparation does not grant write permission. Commit additionally requires an
unexpired confirmation, same token user, same week/version/proposal, one bound
idempotency key, and the separately approved canary-write Gate.
