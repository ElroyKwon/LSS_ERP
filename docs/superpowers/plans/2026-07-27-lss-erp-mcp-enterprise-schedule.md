# LSS ERP MCP Enterprise Schedule Implementation Plan

> **Execution note:** Use `test-driven-development` for every behavior change
> and `verification-before-completion` before any completion, commit, or push
> claim. Execute on the existing `khlee-add-mcp` branch. Do not create another
> branch or worktree unless the user changes this decision.

**Goal:** Add safe enterprise schedule read/prepare/confirmed-write MCP tools
without rewriting the existing schedule workflow or changing the calendar UI.

**Architecture:** The standalone local-stdio MCP remains a strict REST client.
The backend adds scoped read/preflight/status contracts, an operation journal,
and an Employee-before-Timesheet mutation-lock protocol. Existing schedule CRUD
gains bounded MCP-context hooks plus shared locking around Timesheet
synchronization for deterministic event IDs, immutable ownership,
timesheet-state checks, `etag`, audit, and reconciliation.

The selected concurrency **option 1** is the database row-lock protocol
documented in `docs/mcp/SCHEDULE-MUTATION-LOCKING.md`. It is separate from the
overall integration-option numbering retained in the design document.

**Tech stack:** Python, FastAPI, SQLAlchemy, Alembic, Google Calendar API,
MCP Python SDK v1, httpx, Pydantic v2, pytest.

**Design source:**
`docs/superpowers/specs/2026-07-27-lss-erp-mcp-enterprise-schedule-design.md`

## Execution Checkpoint — 2026-07-27 Task 11 Local Verification

**Status:** `LOCAL-IMPLEMENTATION-PASS / TASKS-1-11-LOCAL-PASS /
TASK-12-EXTERNAL-GATES-NOT-RUN /
TASK-13-COMMIT-PUSH-PASS / WRITE-DISABLED /
POSTGRESQL-ROW-LOCK-RUNTIME-NOT-RUN`

- Tasks 1 through 5 were implemented with TDD and passed independent
  specification and code-quality/security review.
- Task 6 now includes strict update/delete reconciliation plus the reviewed
  missing-row refinement: all participating writers acquire
  `Employee(id) FOR UPDATE` before affected
  `Timesheet(week_start,id) FOR UPDATE`.
- Schedule writers treat their first scope read as seed IDs, re-query current
  local/linked scope under all parent locks, and union UPDATE desired weeks.
  A newly discovered Employee rolls back and restarts the DB-only acquisition
  at most three times; MCP reloads its durable operation row after each restart.
  Persistent churn fails closed as `timesheet_scope_unstable` without a Google
  write.
- Timesheet save/submit/approve/reject and ordinary schedule
  create/update/delete participate in the shared order; MCP paths reuse their
  existing acquisition rather than double-locking.
- `uq_timesheets_employee_week_start` and Alembic `20260727_0016` provide the
  final database invariant. The migration fails closed when duplicates exist
  and does not delete or merge data.
- Task 6 local implementation passed both final independent specification and
  code-quality review. Its PostgreSQL row-lock runtime claim remains outside
  the local SQLite/static evidence boundary.
- Task 7 passed its final independent review. Its local evidence is:
  - Task 7 unit/contract: `158 passed`;
  - Task 7 plus existing SSRF protection: `163 passed`;
  - complete local MCP suite: `266 passed`;
  - MCP compileall, `git diff --check`, and the unchanged Calendar frontend
    check: exit `0`.
- SQLite proves model uniqueness, SQL construction, and route call order only.
  PostgreSQL migration execution and lock contention remain `NOT-RUN`.
- Task 8 passed final independent specification and code-quality review:
  - focused confirmation/prepare tests: `54 passed`;
  - complete local MCP suite: `320 passed`;
  - MCP compileall, `git diff --check`, and the unchanged Calendar frontend
    check: exit `0`.
- Task 9 is implemented with TDD and passed final independent specification
  (`PASS`) and code-quality/security (`Ready=Yes`) review after correction of
  the exception/redaction/document boundaries:
  - RED: two expected collection errors for the missing commit/status helpers;
  - Task 7 schema/client focused tests: `158 passed`;
  - Task 8 confirmation/prepare focused tests: `54 passed`;
  - Task 9 commit/config/protocol/replay focused tests: `38 passed`;
  - complete local MCP suite: `351 passed`;
  - MCP compileall, `git diff --check`, and unchanged Calendar frontend:
    exit `0`;
  - exactly fourteen registered tools: seven existing timesheet and seven
    schedule tools;
  - schedule write gate is independent, default false, and exact-lowercase;
  - definite success and potentially-sent failure consume the matching owner
    lease; safe pre-send validation failure releases only the matching lease;
  - timeout is attempted once and returns
    `RECONCILIATION_REQUIRED` with correlation evidence for the read-only
    status tool;
  - every exception after typed-write entry is potentially sent; cancellation
    and unexpected exceptions attempt matching-lease consumption, while
    consume failure is returned as `INFLIGHT_FAIL_CLOSED`;
  - pre-send release failure is fixed-code and fail-closed;
  - correlation is deterministically recoverable from the persisted
    authenticated `user_id` plus idempotency key and is separated across users;
  - FastMCP argument validation keeps the strict schema but redacts rejected
    input values to `invalid_tool_arguments`; unknown top-level arguments are
    rejected before tool code or gate evaluation.
- Task 10 contract-stub/fault-matrix implementation passed final independent
  specification (`PASS`) and code-quality/security (`Ready=Yes`) review:
  - initial RED: `14 failed, 1 passed`;
  - correction RED: `13 failed, 11 passed`;
  - owner-denial replay regression RED: `2 failed`;
  - final Task 10 focused suite: `28 passed`;
  - complete non-real-API/non-canary MCP suite: `379 passed`;
  - owner denial is not durably replayed because real backend owner evidence is
    resolved before the operation claim commit; mutable timesheet denial is
    stored and replayed exactly after the durable claim;
  - operation status and idempotency are separated by authenticated user;
  - operation result/error fields use field and value allowlists;
  - CREATE/UPDATE/DELETE revalidate current owner/timesheet evidence before
    mutation, while exact replay precedes mutable-state checks.
- Task 11 synchronized the REST contract, safety baseline, local verification,
  apply/rollback, evidence hand-back, main-developer entrypoint, standalone MCP
  README, schedule locking contract, and confirmation/prepare contract.
  Current local evidence is:
  - backend schedule suite: `124 passed, 102 warnings`;
  - Task 10 contract/security/performance slice: `28 passed`;
  - complete non-real-API/non-canary MCP suite: `379 passed`;
  - MCP and backend compileall: exit `0`;
  - MCP and backend `pip check`: no broken requirements;
  - MCP `pip-audit`: no known vulnerabilities;
  - backend `pip-audit`: `FAIL`, 30 findings across 7 packages in the unchanged
    main-branch backend dependency lane; main-developer remediation required;
  - MCP runtime DB/ORM/Google SDK scan: zero findings;
  - broad personal-path/secret scan: intentional test guard and documentation
    placeholder only, no literal runtime secret/personal path;
  - `git diff --check`: exit `0`, line-ending conversion warnings only;
  - Calendar frontend baseline diff: exit `0`, no output.
- Task 12 prerequisites were not provided, so PostgreSQL migration rehearsal
  and contention, external backend integration/runtime, real API and Google
  canary, deployment, and rollback remain `NOT-RUN`.
- Task 13 local commit and collaboration-branch push passed on 2026-07-28 after
  review remediation. Implementation commit:
  `8a5b1ed11c68bc2edbc7feb23686106b9f8e3954`.
- The branch remains `DEVELOPMENT/NOT-RELEASED`. Next gate: provide the
  isolated Task 12 environment/authority; `origin/main` merge, deployment, and
  production writes remain unauthorized.

## 0. Fixed Scope and Entry Gate

Expected baseline:

```text
repository: D:\_Project\LSS_ERP
branch: khlee-add-mcp
local HEAD: b9c0c1bced40397b713efb4497a1e5ea9f947be7
origin/khlee-add-mcp: b9c0c1bced40397b713efb4497a1e5ea9f947be7
expected planning-session changes:
  ?? docs/superpowers/specs/2026-07-27-lss-erp-mcp-enterprise-schedule-design.md
  ?? docs/superpowers/plans/2026-07-27-lss-erp-mcp-enterprise-schedule.md
```

Allowed behavior change:

- schedule MCP read, prepare, commit, and operation-status capabilities;
- backend enforcement required only for API-token MCP schedule requests;
- ordinary calendar UI/JWT behavior remains compatible.

Stop immediately if:

- the branch or baseline changed and the diff has not been reviewed;
- `frontend/src/views/CalendarView.vue` must be modified;
- implementation requires copying the existing CRUD flow into `mcp_server`;
- implementation requires direct MCP DB/ORM/Google credential access;
- the existing schedule CRUD must be moved or rewritten substantially;
- production credentials, DB, or calendar are the only way to make a test pass.

No commit or push is authorized by this planning session. The commit commands
below are execution checkpoints for the next session and require user
authorization before running.

## Task 1: Re-establish the Baseline and Freeze Existing Behavior

**Files:**

- Create: `backend/requirements-dev.txt`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/schedule/test_schedule_characterization.py`
- Read only: `backend/app/routers/schedule.py`
- Read only: `frontend/src/views/CalendarView.vue`

### Step 1: Verify the exact entry state

Run:

```powershell
Set-Location D:\_Project\LSS_ERP
git status --short --branch
git rev-parse HEAD
git rev-parse origin/khlee-add-mcp
git rev-list --left-right --count origin/main...HEAD
```

Expected: branch `khlee-add-mcp`, local/remote SHA `b9c0c1b...`, `0 37`
against `origin/main`, and only the two approved untracked planning documents
listed above. Any other worktree change must be inspected before implementation.

If different, inspect `git log --oneline --decorate -10` and
`git diff --stat b9c0c1b...HEAD`; do not overwrite or reset.

### Step 2: Add a backend test dependency file

`backend/requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8.3,<10
pytest-asyncio>=0.24,<2
```

Do not modify production `backend/requirements.txt` for pytest.

### Step 3: Write characterization tests before hooks

Cover:

- JWT/ordinary call path builds the same Google event body;
- create returns `{"status": "success", "id": ...}`;
- update and delete still use display-name ownership in the ordinary path;
- normal calls do not require MCP headers;
- create compensation delete remains invoked after DB-side failure;
- update compensation retains the existing branch behavior;
- `CalendarView.vue` is outside the implementation write set.

Use fake Google request/service objects and an isolated SQLite session. Do not
use a live Google calendar and do not mock application results without
exercising the real schedule functions.

### Step 4: Run the characterization suite

```powershell
.\backend\venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_schedule_characterization.py -q
```

Expected: PASS before production changes. If the existing code cannot be
characterized, record the exact blocker and stop.

### Step 5: Record the checkpoint

Proposed commit after authorization:

```powershell
git add backend/requirements-dev.txt backend/tests/conftest.py backend/tests/schedule/test_schedule_characterization.py
git commit -m "test(mcp): characterize existing schedule workflow"
```

## Task 2: Add API-token Schedule Scope Enforcement

**Files:**

- Create: `backend/app/utils/mcp_schedule_auth.py`
- Create: `backend/tests/schedule/test_mcp_schedule_auth.py`
- Modify: `backend/app/utils/auth.py` only if a token lookup helper must be
  reused without changing `get_current_user` behavior

### Step 1: Write failing scope tests

Cases:

- `schedule:read` allows MCP list/detail only;
- `schedule:write` allows preflight and write context;
- missing scope returns `403 missing_scope`;
- expired/revoked token returns `401`;
- JWT UI user remains accepted by existing `get_current_user`;
- API-token identity comes from `ApiToken.user_id`, never request input;
- scope list is normalized and default-deny.

Run:

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_auth.py -q
```

Expected: FAIL because scoped schedule principal does not exist.

### Step 2: Implement the smallest separate principal dependency

Create an immutable context containing:

- `user`;
- `api_token_id`;
- normalized scopes;
- client/token prefix safe for audit;
- whether the request is an MCP schedule request.

Do not change the return type or normal behavior of `get_current_user`.

### Step 3: Re-run tests

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_auth.py backend\tests\schedule\test_schedule_characterization.py -q
```

Expected: PASS.

### Step 4: Proposed authorized commit

```powershell
git add backend/app/utils/mcp_schedule_auth.py backend/app/utils/auth.py backend/tests/schedule
git commit -m "feat(mcp): enforce schedule token scopes"
```

## Task 3: Add the Durable Operation Journal

**Files:**

- Create: `backend/app/models/mcp_schedule.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260727_0015_mcp_schedule_operations.py`
- Modify: `backend/app/utils/schema.py`
- Create: `backend/tests/schedule/test_mcp_schedule_operation_model.py`

The migration must revise `20260724_0014`.

### Step 1: Write failing model and uniqueness tests

Test:

- required fields and state values;
- unique `(user_id, idempotency_key)`;
- unique `correlation_id`;
- same key/same request replay lookup;
- same key/different request conflict;
- redacted result/error JSON only;
- SQLite development schema and PostgreSQL migration definitions agree.

### Step 2: Run the focused RED test

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_operation_model.py -q
```

Expected: FAIL because model/table do not exist.

### Step 3: Implement additive model, migration, and development schema

Create `mcp_schedule_operations`; do not add columns to
`calendar_schedules`.

Allowed statuses:

```text
IN_PROGRESS
SUCCEEDED
FAILED
RECONCILIATION_REQUIRED
MANUAL_REVIEW
```

### Step 4: Verify model and migration syntax

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_operation_model.py -q
Set-Location D:\_Project\LSS_ERP\backend
.\venv\Scripts\python.exe -m alembic heads
.\venv\Scripts\python.exe -m alembic history
Set-Location D:\_Project\LSS_ERP
```

Migration upgrade/downgrade against PostgreSQL remains `NOT-RUN` until an
approved isolated DB is available.

### Step 5: Proposed authorized commit

```powershell
git add backend/app/models backend/app/utils/schema.py backend/alembic/versions/20260727_0015_mcp_schedule_operations.py backend/tests/schedule
git commit -m "feat(mcp): add schedule operation journal"
```

## Task 4: Add Read, Detail, Preflight, and Status Contracts

**Files:**

- Create: `backend/app/routers/mcp_schedule.py`
- Create: `backend/app/services/mcp_schedule_control.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/schedule/test_mcp_schedule_contract.py`
- Create: `backend/tests/schedule/test_mcp_schedule_preflight.py`

### Step 1: Write failing endpoint contract tests

Required routes:

```text
GET  /api/mcp/schedules
GET  /api/mcp/schedules/{event_id}
POST /api/mcp/schedules/preflight
GET  /api/mcp/schedules/operations/{correlation_id}
```

Test:

- object response envelope;
- date/category/result-limit validation;
- exact scope requirements;
- event ID validation;
- detail includes owner-binding state, Google `etag`, and eligibility;
- preflight performs no DB or Google mutation;
- operation status is visible only to its owner;
- response size and free-text redaction boundaries.

### Step 2: Run RED

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_contract.py backend\tests\schedule\test_mcp_schedule_preflight.py -q
```

Expected: 404/import failures.

### Step 3: Implement additive router and service

Use the existing `CalendarSchedule` data and existing Google service factory.
Do not duplicate create/update/delete orchestration.

Preflight calculates:

- current and desired normalized state;
- immutable owner binding;
- affected current and desired weeks;
- timesheet statuses;
- current `etag`;
- `write_allowed` and stable denial reasons.

### Step 4: Re-run contract and characterization suites

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule -q
```

Expected: PASS and no characterization regression.

### Step 5: Proposed authorized commit

```powershell
git add backend/app/routers/mcp_schedule.py backend/app/services/mcp_schedule_control.py backend/app/main.py backend/tests/schedule
git commit -m "feat(mcp): add schedule read and preflight API"
```

## Task 5: Add Deterministic Create and Immutable Ownership Hooks

**Files:**

- Modify: `backend/app/routers/schedule.py`
- Modify: `backend/app/services/mcp_schedule_control.py`
- Create: `backend/tests/schedule/test_mcp_schedule_create.py`
- Create: `backend/tests/schedule/test_mcp_schedule_idempotency.py`

### Step 1: Write failing create-control tests

Test:

- normal UI event body remains byte-equivalent as a Python mapping;
- MCP create requires `schedule:write`;
- deterministic event ID uses valid lower base32hex characters;
- same owner/category/key/payload yields the same event ID;
- different payload with the same key returns `idempotency_conflict`;
- event private properties use token-derived IDs;
- event body owner input cannot be spoofed;
- submitted/approved destination week blocks before Google insert;
- response-loss replay observes the deterministic event and does not insert a
  second event;
- result and correlation are stored without secrets.

### Step 2: Run RED

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_create.py backend\tests\schedule\test_mcp_schedule_idempotency.py -q
```

Expected: FAIL because create hooks do not exist.

### Step 3: Add only hook calls to existing create flow

The normal path must remain:

```text
build event -> Google insert -> schedule upsert -> timesheet sync -> DB commit
```

The MCP hook may:

- validate/claim the operation before the Google call;
- supply `event["id"]`;
- add private extended properties;
- record success/failure/reconciliation state.

Do not move the existing flow into a new duplicate function.

### Step 4: Run focused and characterization tests

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_create.py backend\tests\schedule\test_mcp_schedule_idempotency.py backend\tests\schedule\test_schedule_characterization.py -q
```

Expected: PASS.

### Step 5: Proposed authorized commit

```powershell
git add backend/app/routers/schedule.py backend/app/services/mcp_schedule_control.py backend/tests/schedule
git commit -m "feat(mcp): guard schedule creation"
```

## Task 6: Add Strict Schedule Concurrency, Namespace Locking, and Reconciliation

**Files:**

- Modify: `backend/app/routers/schedule.py`
- Modify: `backend/app/routers/timesheet.py`
- Modify: `backend/app/models/timesheet.py`
- Modify: `backend/app/services/mcp_schedule_control.py`
- Create: `backend/app/services/timesheet_locking.py`
- Create: `backend/alembic/versions/20260727_0016_unique_timesheet_employee_week.py`
- Create: `backend/tests/schedule/test_mcp_schedule_update_delete.py`
- Create: `backend/tests/schedule/test_mcp_schedule_faults.py`
- Create: `backend/tests/schedule/test_timesheet_locking.py`
- Create: `backend/tests/schedule/test_schedule_scope_revalidation.py`
- Modify: `backend/tests/schedule/test_schedule_characterization.py`

### Step 1: Write failing update/delete tests

Test:

- matching immutable owner is accepted;
- display-name-only legacy event returns `legacy_owner_unbound`;
- immutable owner mismatch returns `owner_mismatch`;
- missing or stale `If-Match` returns `stale_event`;
- Google update/delete request receives `If-Match`;
- submitted/approved affected weeks block before the Google call;
- same-key replay returns stored result;
- Google success plus DB failure becomes
  `RECONCILIATION_REQUIRED` when not deterministically compensated;
- delete readback 404 is interpreted only with DB/journal evidence;
- conflicting evidence becomes `MANUAL_REVIEW`;
- ordinary UI characterization remains unchanged.

### Step 2: Run RED

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule\test_mcp_schedule_update_delete.py backend\tests\schedule\test_mcp_schedule_faults.py -q
```

Expected: FAIL.

### Step 3: Add minimal update/delete hooks

Use the Google request object's headers for `If-Match`. Preserve private
extended properties on update. Do not infer immutable ownership from the
summary.

Never automatically retry an uncertain update/delete. Persist the state and
return the correlation ID for `schedule_operation_status`.

### Step 4: Run all backend schedule tests

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule -q
```

Expected: PASS.

### Step 5: Correct locking, replay, and compensation review findings

**Additional files:**

- Create: `docs/mcp/SCHEDULE-MUTATION-LOCKING.md`
- Modify: `docs/superpowers/specs/2026-07-27-lss-erp-mcp-enterprise-schedule-design.md`
- Modify: `backend/tests/schedule/test_mcp_schedule_create.py`
- Modify: `backend/tests/schedule/test_mcp_schedule_update_delete.py`
- Modify: `backend/tests/schedule/test_mcp_schedule_idempotency.py`
- Create: `backend/tests/schedule/test_schedule_scope_revalidation.py`

- [x] Add RED tests proving that an event observed from a prior create is
  never compensation-deleted when local reconstruction fails.
- [x] Add a RED test proving stored `SUCCEEDED` create replay remains stable
  after the timesheet becomes locked.
- [x] Add a RED two-call invalid-update test proving the same machine code and
  correlation behavior.
- [x] Add RED cases proving only the exact literal `true` enables
  `MCP_SCHEDULE_WRITE_ENABLED`.
- [x] Add RED lock-contract tests proving Employee-before-Timesheet ordering,
  deterministic affected-row ordering, missing-week namespace locking, and
  SQLAlchemy `FOR UPDATE` construction before the Google test double runs.
- [x] Add RED ordinary and MCP UPDATE/DELETE tests that inject seed scope A
  before the parent lock and actual scope B afterwards, then prove B is locked
  before local or Google mutation and UPDATE still unions desired weeks.
- [x] Re-query current CalendarSchedule and TimesheetEntry-linked scope while
  all seed Employee locks are held. Treat the pre-lock scope as seed IDs only.
- [x] If revalidation discovers a new Employee ID, roll back before child/local/
  Google mutation, expand and sort the parent set, reload the committed MCP
  operation row, and restart with a hard bound of three DB-only attempts.
- [x] Fail persistent churn closed as `timesheet_scope_unstable`; prove exact
  MCP replay preserves the original correlation/code with zero Google writes.
- [x] Add RED UPDATE and DELETE locked-week tests proving the first rejection
  and exact replay both return `timesheet_locked` with the original
  `X-Correlation-ID`, with zero Google writes.
- [x] Add RED stored-create tests proving `FAILED` and `MANUAL_REVIEW` return
  their stored code/state/correlation with zero Google calls, and proving
  unavailable `RECONCILIATION_REQUIRED` readback preserves its stored evidence
  and correlation with zero Google writes.
- [x] Commit the operation claim, then open the locked mutation transaction;
  on success, hold its Employee and Timesheet row locks through Google, local
  synchronization, journal finalization to `SUCCEEDED`, and the final commit.
- [x] On failure, roll back the locked mutation transaction first and treat
  that final rollback as the lock-release boundary. Only then use a separate
  recovery transaction to persist bounded `FAILED`,
  `RECONCILIATION_REQUIRED`, or `MANUAL_REVIEW` evidence and the original
  correlation ID. After rollback, allow no new forward Google mutation and no
  local schedule/timesheet mutation. CREATE may perform bounded deterministic
  readback and ownership-proven current-invocation compensation under the
  normative guard. DELETE may perform one bounded read-only `GET` to classify
  404/present/conflicting DB+journal evidence, but never retries delete or
  compensates. UPDATE has no automatic readback, retry, or compensation unless
  separately designed. The recovery transaction writes journal evidence only
  and must not assume the locks still exist.
- [x] Track `insert_attempted_by_current_invocation` separately from
  `reconcile_observed`; allow compensation only for the former.
- [x] Resolve exact stored replay before mutable preflight. Return terminal
  non-success state/correlation without a Google call; allow only one bounded
  read-only deterministic-event observation for stored CREATE `IN_PROGRESS` or
  `RECONCILIATION_REQUIRED`, never a forward retry.
- [x] Validate MCP schedule time ordering with a stable allowlisted code before
  durable claim.
- [x] Add the named `uq_timesheets_employee_week_start` model invariant and
  Alembic `0016` duplicate preflight that fails closed without deleting rows.
- [x] Make timesheet save/submit/approve/reject and ordinary schedule
  create/update/delete participate in the same parent-before-child order,
  re-read locked state, and avoid double-locking MCP calls.
- [x] Prove a failed DELETE performs one delete and one bounded recovery `GET`,
  while exact replay performs neither again.
- [x] Document that SQLite verifies query construction and model uniqueness
  only and that actual
  PostgreSQL contention remains `POSTGRESQL-ROW-LOCK-RUNTIME-NOT-RUN`.

Run RED/GREEN focused tests:

```powershell
.\backend\venv\Scripts\python.exe -m pytest `
  backend\tests\schedule\test_mcp_schedule_create.py `
  backend\tests\schedule\test_mcp_schedule_idempotency.py `
  backend\tests\schedule\test_mcp_schedule_update_delete.py `
  backend\tests\schedule\test_mcp_schedule_faults.py `
  backend\tests\schedule\test_timesheet_locking.py `
  backend\tests\schedule\test_schedule_characterization.py `
  backend\tests\schedule\test_schedule_scope_revalidation.py -q
```

Then run the complete schedule suite and static checks:

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule -q
.\backend\venv\Scripts\python.exe -m compileall -q backend\app backend\tests
git diff --check
```

Expected: all local tests PASS. This does not prove PostgreSQL runtime
contention; keep that external Gate `NOT-RUN`.

### Step 6: Proposed authorized commit

```powershell
git add backend/app/models/timesheet.py backend/app/routers/schedule.py backend/app/routers/timesheet.py backend/app/services/mcp_schedule_control.py backend/app/services/timesheet_locking.py backend/alembic/versions/20260727_0016_unique_timesheet_employee_week.py backend/tests/schedule docs/mcp/SCHEDULE-MUTATION-LOCKING.md docs/superpowers
git commit -m "feat(mcp): guard schedule update and delete"
```

## Task 7: Add Standalone MCP Schedule Schemas and REST Client

**Files:**

- Create: `mcp_server/src/lss_erp_mcp/schemas/schedule.py`
- Modify: `mcp_server/src/lss_erp_mcp/schemas/__init__.py`
- Modify: `mcp_server/src/lss_erp_mcp/erp_client.py`
- Create: `mcp_server/tests/unit/test_schedule_schema.py`
- Create: `mcp_server/tests/contract/test_schedule_erp_client.py`

### Step 1: Write failing schema/client tests

Validate:

- category allowlist;
- bounded date range and result limit;
- exact all-day versus timed fields;
- event ID lower base32hex and length;
- operation action enum;
- `etag`, correlation, confirmation, and status types;
- no unknown fields;
- static allowlist for fixed routes;
- dedicated validated path builders for event/correlation IDs;
- no arbitrary URL, query, redirect, or path traversal;
- list response must use the new object envelope, not accept an arbitrary JSON
  list;
- write headers are generated by the client, not passed through unchecked.

### Step 2: Run RED

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit\test_schedule_schema.py mcp_server\tests\contract\test_schedule_erp_client.py -q
```

Expected: import/method failures.

### Step 3: Implement schemas and dedicated client methods

Add only typed methods:

- `list_schedules`
- `get_schedule`
- `preflight_schedule`
- `create_schedule`
- `update_schedule`
- `delete_schedule`
- `get_schedule_operation`

Do not broaden `_request` into a generic dynamic URL client.

### Step 4: Re-run tests

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit\test_schedule_schema.py mcp_server\tests\contract\test_schedule_erp_client.py mcp_server\tests\security\test_ssrf.py -q
```

Expected: PASS.

### Step 4.1: Implemented Task 7 contract and local evidence

The standalone adapter now keeps schedule traffic inside seven typed client
methods. It does not expose a caller-selected method, URL, query string, or
header dictionary:

- MCP list, detail, preflight, and operation status use strict object-envelope
  models. The list `count` must equal the number of items, and every response
  rejects unknown fields.
- Post-schema binding checks prove the response belongs to the request: list
  category/start/limit, detail event/category, update result event, preflight
  action/category/event/current/desired, and operation correlation/meta are
  compared with the original typed inputs. A mismatch becomes the same safe
  `upstream_invalid_response` used for schema drift.
- Owner and eligibility evidence cannot merely be individually well-typed.
  `OwnerBinding` enforces the backend authority mapping: `BOUND` and
  `NOT_APPLICABLE` mean owner-level `write_allowed: true`;
  `LEGACY_OWNER_UNBOUND` and `OWNER_MISMATCH` mean `false`.
- Detail responses reject `NOT_APPLICABLE`, which the backend never emits for
  detail. Detail eligibility must exactly mirror owner authority: `BOUND` has
  no denial, while legacy-unbound and owner-mismatch have their exact matching
  denial and remain non-writable.
- Preflight uses `NOT_APPLICABLE` only for CREATE and forbids it for
  UPDATE/DELETE. Top-level `write_allowed` is true exactly when
  `denial_reasons` is empty. Owner denials must match the binding, and any
  reported timesheet status other than `작성중` requires
  `timesheet_locked` and a false decision. `employee_not_found` remains a
  conservative backend fact because an empty status list alone cannot prove
  whether the employee exists.
- Denial reasons are a unique, bounded backend allowlist:
  `legacy_owner_unbound`, `owner_mismatch`, `employee_not_found`, and
  `timesheet_locked`. Unknown or duplicate reasons are schema drift.
- Operation status evidence is state-coherent: `IN_PROGRESS` is empty;
  `SUCCEEDED` has matching status, event, and correlation evidence,
  `write_applied: true`, no error, and never
  `reconciliation_required: true`; each terminal non-success status has
  matching bounded error code/status/correlation evidence and no success
  result. Valid fixtures cover all five backend states.
- Stable FastAPI string error codes and a bounded `X-Correlation-ID` response
  header are normalized into `ERPError`. Schedule routes accept only the
  lowercase machine-code grammar and the status-route correlation grammar;
  invalid values are discarded. Schedule error messages are generic and
  details are empty so upstream free text cannot cross the adapter. Legacy
  timesheet error handling remains unchanged.
- Create, update, and delete continue to use the legacy `/api/schedules`
  routes, but the client generates `X-LSS-MCP-Schedule`,
  `Idempotency-Key`, `X-Correlation-ID`, and the update/delete `If-Match`
  headers. Callers cannot pass arbitrary headers through these methods.
- The same policy is enforced below the typed methods in `_request`: each
  schedule route has an exact kwargs, header, query, and JSON-body shape.
  Direct low-level calls cannot override `Authorization`, add identity/custom
  headers, alter or omit MCP control headers, inject authority/body fields, or
  switch to a different request encoding.
- The required legacy `user_name` body field is generated as an empty
  presentation value. Schedule authority remains the bearer-token identity;
  no caller-selected owner ID or name crosses the typed MCP request boundary.
- Fixed routes are listed explicitly. Event and operation paths are built only
  by dedicated validators: Google event IDs are lower base32hex with length
  8-255, and correlation IDs are bounded URL-safe identifiers. Embedded query
  strings, absolute URLs, extra path segments, and traversal input fail before
  transport.
- Category, action, operation status, `etag`, correlation, confirmation,
  all-day/timed shapes, bounded write/list-query ranges, and result limit 1-100
  are Pydantic contract types. CREATE, UPDATE, and DELETE use exact mutually
  exclusive field shapes. Security-relevant booleans and integers reject
  coercion.
  The success envelope accepts only the exact boolean `true`, not numeric `1`
  or the string `"true"`, for both Python and decoded JSON input.
  Either list date bound may be supplied independently; when both exist they
  must be ordered and no more than 31 days apart.
- The 31-day duration cap applies to list query intervals and proposed/write
  states, not to already stored response/current items. Ordered, timezone-aware
  legacy schedules may span longer periods. Preflight week/status evidence has
  no invented item-count cap; `max_response_bytes` remains the transport bound.

Local TDD evidence from 2026-07-27:

- pre-change MCP baseline: `108 passed`;
- RED: `2 errors during collection` for the missing schedule schema and path
  builders;
- quality-hardening RED: `16 failed, 31 passed` for transport bypass, exact
  action/scalar shapes, and canonical error evidence;
- final envelope-strictness RED: `2 failed, 51 passed` for Python/JSON numeric
  `1` coercion into the success literal;
- response-binding/legacy-read RED: `44 failed, 61 passed` for request mismatch,
  operation-state coherence, and long existing schedule compatibility;
- authority/status-coherence RED: `26 failed, 132 passed` for contradictory
  owner mappings, detail/preflight write decisions, denial codes, timesheet
  lock evidence, and incomplete or contradictory successful-operation facts;
- Task 7 unit/contract GREEN: `158 passed`;
- Task 7 plus existing SSRF protection: `163 passed`;
- complete local MCP suite: `266 passed`;
- `compileall`, `git diff --check`, and the unchanged Calendar frontend check:
  exit `0`.

These results prove only the local schema, request-construction, transport
guard, and mock-response contracts. Backend/Google integration, real API
identity/scope checks, schedule writes, deployment, and canary execution remain
`NOT-RUN`.

### Step 5: Proposed authorized commit

```powershell
git add mcp_server/src/lss_erp_mcp/schemas/schedule.py mcp_server/src/lss_erp_mcp/schemas/__init__.py mcp_server/src/lss_erp_mcp/erp_client.py mcp_server/tests/unit/test_schedule_schema.py mcp_server/tests/contract/test_schedule_erp_client.py docs/superpowers/plans/2026-07-27-lss-erp-mcp-enterprise-schedule.md
git commit -m "feat(mcp): add schedule REST contract"
```

## Task 8: Add Schedule Preparation and Confirmation

**Task 8 checkpoint -- 2026-07-27**

**Status:** `IMPLEMENTED / LOCAL-FOCUSED-PASS /
FINAL-SPEC-AND-QUALITY-REVIEW-PENDING / WRITE-NOT-REGISTERED`

- Added a separate bounded `ScheduleConfirmationStore`; the existing
  timesheet `confirmation.py` and `ConfirmationStore` are unchanged.
- Confirmation binds authenticated user, action, category, optional event,
  expected `etag`, canonical Task 7 proposal hash, expiry, and one permanent
  strict Task 7 idempotency key. A claim returns a defensive immutable lease;
  only its matching lease ID can release or consume the token. Wrong, missing,
  stale, colliding, or over-capacity lease attempts fail closed. The default
  token and lease factories are cryptographically random; deterministic
  injection is test-only.
- TTL never revokes an active owner lease. Purge/read/retry preserve its
  token, key, and lease and return `confirmation_commit_in_progress`; an
  expired active item still counts toward bounded capacity. The matching owner
  can consume after TTL or release and deterministically remove the expired
  token.
- CREATE uses authenticated identity plus typed preflight. UPDATE and DELETE
  also read the typed current event and require event/owner/etag/projection
  coherence before a token is issued.
- Prepare returns a bounded content-redacted before/after/impact view,
  affected/status/locked weeks, stable denial reasons, proposal hash, and an
  optional token. Impact separates definitely different visible fields from
  requested field names whose current values are unavailable or redacted.
  `comparison_complete=false` prevents content-only, color-only, or supplied
  project-field UPDATEs from being misread as no-op comparisons. Raw values
  remain absent. Prepare never calls an ERP schedule write method.
- Local invalid proposal/request inputs return fixed machine-safe errors with
  no rejected value and zero HTTP. Safe ERP errors remain unchanged. A naive
  injected clock fails with a fixed error instead of a runtime comparison
  exception.
- Detailed state-machine and result contract:
  `docs/mcp/SCHEDULE-CONFIRMATION-AND-PREPARE.md`.
- TDD RED evidence: exactly `2` collection errors because both new
  implementation modules were absent.
- Review-correction RED evidence: exactly `8 failed / 26 passed` for the old
  ambiguous impact shape.
- Quality-correction RED evidence after the import scaffold: exactly
  `28 failed / 23 passed` for missing safe errors, strict idempotency, owner
  leases, and aware-clock handling.
- Final TTL-concurrency RED evidence: exactly `3 failed / 51 passed` for
  automatic active-owner loss at expiry.
- Focused GREEN evidence: `54 passed`.
- Full standalone MCP evidence: `320 passed`.
- Python compile, `git diff --check`, and
  `CalendarView.vue` diff against
  `b9c0c1bced40397b713efb4497a1e5ea9f947be7`: exit 0. Diff checking emitted
  only existing LF-to-CRLF working-copy warnings.
- Task 8 passed final specification and code-quality review. Task 9 is now
  implemented separately and pending its own reviews. All external
  runtime/write/deployment gates remain `NOT-RUN`; commit/push later passed as
  Task 13 at implementation commit `8a5b1ed`.

**Files:**

- Create: `mcp_server/src/lss_erp_mcp/schedule_confirmation.py`
- Create: `mcp_server/src/lss_erp_mcp/tools/schedules.py`
- Modify: `mcp_server/src/lss_erp_mcp/tools/__init__.py`
- Create: `mcp_server/tests/unit/test_schedule_confirmation.py`
- Create: `mcp_server/tests/integration/test_schedule_prepare.py`

### Step 1: Write failing confirmation tests

Bind confirmation to:

- authenticated user ID;
- action;
- category;
- event ID when applicable;
- expected `etag`;
- normalized proposal hash;
- expiry;
- one strict Task 7 idempotency key;
- one owner lease for the active claim.

Test TTL, tamper detection, cross-user/action reuse, changed proposal,
invalid idempotency non-poisoning, concurrent claim, wrong/missing/stale lease,
owner release/consume, lease format/collision/capacity, aware clock, and
defensive copies.

### Step 2: Write failing prepare-tool tests

For create/update/delete:

- read current state/preflight through the ERP client;
- return before/after and impact diff;
- expose locked weeks and stable denial reasons;
- convert local invalid proposal/request values to fixed machine-safe errors
  before HTTP without leaking rejected values;
- create no ERP/Google mutation;
- refuse legacy owner writes;
- issue a confirmation only when preflight is eligible.

### Step 3: Run RED

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit\test_schedule_confirmation.py mcp_server\tests\integration\test_schedule_prepare.py -q
```

Expected: FAIL.

### Step 4: Implement without modifying timesheet confirmation

Keep `confirmation.py` and its `ConfirmationStore` unchanged. Schedule
confirmation is a separate type because its identity, action, event, and
`etag` bindings differ.

### Step 5: Re-run tests

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit\test_schedule_confirmation.py mcp_server\tests\integration\test_schedule_prepare.py -q
```

Expected: PASS.

### Step 6: Proposed authorized commit

```powershell
git add mcp_server/src/lss_erp_mcp/schedule_confirmation.py mcp_server/src/lss_erp_mcp/tools/schedules.py mcp_server/src/lss_erp_mcp/tools/__init__.py mcp_server/tests
git commit -m "feat(mcp): prepare schedule changes safely"
```

## Task 9: Register Seven Schedule Tools and Dual Write Gates

**Files:**

- Modify: `mcp_server/src/lss_erp_mcp/config.py`
- Modify: `mcp_server/src/lss_erp_mcp/server.py`
- Modify: `mcp_server/src/lss_erp_mcp/tools/schedules.py`
- Create: `mcp_server/tests/integration/test_schedule_commit.py`
- Create: `mcp_server/tests/fault/test_schedule_commit_replay.py`
- Modify: `mcp_server/tests/unit/test_config.py`
- Modify: `mcp_server/tests/protocol/test_stdio.py`

### Step 1: Write failing write-gate and tool tests

Tools:

```text
schedule_list
schedule_get
schedule_prepare_create
schedule_prepare_update
schedule_prepare_delete
schedule_commit
schedule_operation_status
```

Test:

- read/prepare/status annotations are read-only;
- commit is destructive and idempotent;
- `LSS_ERP_SCHEDULE_CANARY_WRITE` defaults false;
- timesheet `canary_write` remains independent;
- commit rejects missing/expired/changed confirmation;
- commit generates correlation and idempotency headers;
- commit does not auto-retry timeout;
- uncertain outcome returns `RECONCILIATION_REQUIRED`;
- replay retrieves stored result/status;
- successful commit consumes confirmation;
- failed pre-send validation releases it safely.
- Task 9 commit must retain the `ScheduleConfirmationLease` returned by claim
  and pass its matching `lease_id` to release or consume; token-only cleanup is
  forbidden.
- Task 9 must finish that matching lease even when confirmation TTL elapses
  during an active commit. Another prepare/read/retry cannot evict it.

### Step 2: Run RED

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\integration\test_schedule_commit.py mcp_server\tests\fault\test_schedule_commit_replay.py mcp_server\tests\protocol\test_stdio.py -q
```

Expected: missing tools/settings.

### Step 3: Implement and register tools

Extend `AppContext` with a separate schedule confirmation store and schedule
write flag. Do not change the behavior of the existing seven timesheet tools.

Implementation contract:

- `schedule_commit` accepts only confirmation token and idempotency key; it
  obtains action/category/event/etag/proposal from the bounded Task 8 store;
- the local gate is checked before confirmation lookup or any HTTP call;
- current token-bound user identity is read before the owner lease is claimed;
- all stored proposal, key, and generated correlation values are validated
  before entering a typed Task 7 write method;
- the production correlation material is the versioned prefix
  `lss-erp-schedule-correlation:v1`, NUL, decimal authenticated `user_id`, NUL,
  and UTF-8 idempotency key; the ID is `schedule_v1_` plus the first 40
  hexadecimal SHA-256 characters, so the host can recover it after a
  lost/cancelled stdio response without resending and different users cannot
  collide merely by choosing the same key;
- safe pre-send validation failure releases the exact returned `lease_id`;
- failure of that pre-send release returns only
  `confirmation_release_failed` and leaves the lease fail-closed;
- success attempts to consume that lease and returns
  `confirmation_finalization`;
- every exception after write-method entry, including `ERPError`, `ValueError`,
  unexpected exceptions, and cancellation, is potentially sent and attempts
  to consume the lease to block a forward replay;
- an `ERPError` or unexpected ordinary exception returns
  `RECONCILIATION_REQUIRED` with the generated correlation ID; cancellation
  and process-level exceptions finalize fail-closed and are re-raised;
- consume failure never masks success or uncertainty and reports
  `confirmation_finalization=INFLIGHT_FAIL_CLOSED`;
- FastMCP validation responses expose only `invalid_tool_arguments`, not
  rejected values or Pydantic `input_value`, without weakening input schemas;
- top-level schemas publish `additionalProperties=false`, and runtime rejects
  unknown arguments before tool code or write-gate evaluation;
- `schedule_operation_status` is the only replay path and performs a read-only
  backend journal lookup; it never retries CREATE, UPDATE, or DELETE.

### Step 4: Re-run focused tests

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\integration\test_schedule_commit.py mcp_server\tests\fault\test_schedule_commit_replay.py mcp_server\tests\protocol\test_stdio.py mcp_server\tests\unit\test_config.py -q
```

Expected: PASS with fourteen total registered tools.

### Step 5: Proposed authorized commit

```powershell
git add mcp_server/src/lss_erp_mcp/config.py mcp_server/src/lss_erp_mcp/server.py mcp_server/src/lss_erp_mcp/tools/schedules.py mcp_server/tests
git commit -m "feat(mcp): expose confirmed schedule tools"
```

## Task 10: Extend the DB-free Contract Stub and Fault Matrix

**Files:**

- Modify: `mcp_server/tests/contract_server/app.py`
- Modify: `mcp_server/tests/contract_server/state.py`
- Create: `mcp_server/tests/contract/test_schedule_contract_stub.py`
- Create: `mcp_server/tests/security/test_schedule_security.py`
- Create: `mcp_server/tests/performance/test_schedule_local_budget.py`

### Step 1: Add failing contract-stub cases

The stub models contract state only. It does not copy backend ORM or Google
integration code.

Cover:

- read/detail/preflight/status;
- scope denial;
- locked timesheet;
- legacy/mismatched owner;
- stale `etag`;
- same-key replay;
- different-payload conflict;
- response loss after observable create;
- update/delete partial failure;
- reconciliation and manual-review states;
- oversized response and secret redaction.

### Step 2: Run RED

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\contract\test_schedule_contract_stub.py mcp_server\tests\security\test_schedule_security.py mcp_server\tests\performance\test_schedule_local_budget.py -q
```

Expected: FAIL.

### Step 3: Implement contract state and handlers

No database dependency, Google SDK, credential files, or personal vault paths.

### Step 4: Run complete local MCP suite

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests -m "not real_api and not canary_write" -q
```

Expected: all prior 108 tests plus new schedule tests PASS. Record the new
exact count; do not predict it in documentation.

### Step 5: Proposed authorized commit

```powershell
git add mcp_server/tests
git commit -m "test(mcp): cover schedule faults and security"
```

## Task 11: Documentation, Static Safety, and Local Verification

**Files:**

- Modify: `mcp_server/README.md`
- Modify: `docs/mcp/API-CONTRACT.md`
- Modify: `docs/mcp/AI-SAFETY-BASELINE.md`
- Modify: `docs/mcp/LOCAL-VERIFICATION.md`
- Modify: `docs/mcp/APPLY-AND-ROLLBACK.md`
- Modify: `docs/mcp/EVIDENCE-HAND-BACK.md`
- Modify: `docs/mcp/AI-MAIN-DEVELOPER-ENTRYPOINT.md`
- Modify: this plan and design only if implementation differs for an
  evidence-backed reason

### Step 1: Document exact operational boundaries

State separately:

- local implementation;
- backend unit/contract evidence;
- Alembic upgrade/downgrade evidence;
- real API read-only;
- Google test-calendar canary;
- deployment;
- commit;
- push.

Do not call local tests operational completion.

### Step 2: Run compile and dependency checks

```powershell
.\mcp_server\.venv\Scripts\python.exe -m compileall -q mcp_server\src mcp_server\tests
.\backend\venv\Scripts\python.exe -m compileall -q backend\app backend\tests
.\mcp_server\.venv\Scripts\python.exe -m pip check
.\backend\venv\Scripts\python.exe -m pip check
```

### Step 3: Run isolation and secret scans

```powershell
rg -n "DATABASE_URL|create_engine|SessionLocal|sqlalchemy|googleapiclient|service_account" mcp_server\src
rg -n "G:\\\\내 드라이브|_Obsidian|token_hash|Authorization:" mcp_server\src mcp_server\tests docs\mcp
git diff --check
```

Expected:

- no DB/ORM/Google SDK imports in `mcp_server/src`;
- no personal vault path or literal secret;
- `git diff --check` exit 0.

### Step 4: Run complete local suites

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule -q
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests -m "not real_api and not canary_write" -q
```

Record exact pass/fail/skip counts.

### Step 5: Verify frontend protection

```powershell
git diff --exit-code b9c0c1bced40397b713efb4497a1e5ea9f947be7 -- frontend/src/views/CalendarView.vue
```

Expected: exit 0 and no output.

### Step 6: Proposed authorized documentation commit

```powershell
git add mcp_server/README.md docs/mcp docs/superpowers
git commit -m "docs(mcp): hand off enterprise schedule controls"
```

## Task 12: Isolated Integration and Canary Gates

Do not execute this task unless all prerequisites are explicitly provided and
approved:

- isolated PostgreSQL test environment;
- current backend schema snapshot;
- migration/rollback authority;
- test user and exact-scope API token;
- dedicated Google test calendar;
- backend schedule write flag enabled only in that environment.

### Step 1: Migration rehearsal

```powershell
Set-Location D:\_Project\LSS_ERP\backend
.\venv\Scripts\python.exe -m alembic current
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m alembic downgrade 20260727_0015
.\venv\Scripts\python.exe -m alembic upgrade 20260727_0016
.\venv\Scripts\python.exe -m alembic downgrade 20260724_0014
.\venv\Scripts\python.exe -m alembic upgrade head
Set-Location D:\_Project\LSS_ERP
```

Expected: schema/data preservation and repeatable upgrade.

### Step 2: Real API read-only

Run only marked real-API schedule tests with write flags false. Verify
identity, exact scopes, list/detail/preflight/status, and no mutations.

### Step 3: Canary write matrix

Use disposable test-calendar events only:

- create;
- exact replay;
- update;
- stale `etag`;
- delete;
- submitted/approved timesheet block;
- response loss;
- DB failure after Google side effect;
- reconciliation/status.

Every created event must be recorded and deleted. If cleanup is uncertain,
stop and report exact event IDs and correlation IDs.

### Step 4: Rollback rehearsal

Disable both write flags, revoke the test token, remove canary events, roll
back the migration if required, and prove the original calendar UI path still
works.

## Task 13: Final Review, Commit, and Push Gate

### Step 1: Re-read the user-approved scope

Confirm:

- same `khlee-add-mcp` branch;
- no schedule workflow rewrite;
- no frontend change;
- standalone MCP REST-only;
- minimum hooks only;
- default write disabled.

### Step 2: Inspect the full diff

```powershell
git status --short
git diff --stat
git diff -- backend/app/routers/schedule.py
git diff -- frontend/src/views/CalendarView.vue
git diff --check
```

Any unplanned file or broad schedule-router rewrite is a stop condition.

### Step 3: Run fresh final verification

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests\schedule -q
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests -m "not real_api and not canary_write" -q
.\mcp_server\.venv\Scripts\python.exe -m compileall -q mcp_server\src mcp_server\tests
.\backend\venv\Scripts\python.exe -m compileall -q backend\app backend\tests
git diff --check
git status --short --branch
```

### Step 4: Request commit/push authorization if not already explicit

Report:

- files changed;
- exact test counts;
- NOT-RUN external gates;
- residual risks;
- proposed commit list;
- target `origin/khlee-add-mcp`.

Do not commit or push without authorization.

### Step 5: Push after authorization only

```powershell
git push origin khlee-add-mcp
git rev-parse HEAD
git ls-remote --heads origin khlee-add-mcp
git status --short --branch
```

Completion evidence requires local and remote SHA equality and a clean
worktree. A successful push is not operational canary completion.

## Next-session First Command Block

```powershell
Set-Location D:\_Project\LSS_ERP
Get-Content -Raw docs\superpowers\specs\2026-07-27-lss-erp-mcp-enterprise-schedule-design.md
Get-Content -Raw docs\superpowers\plans\2026-07-27-lss-erp-mcp-enterprise-schedule.md
git status --short --branch
git rev-parse HEAD
git rev-parse origin/khlee-add-mcp
```

Tasks 1 through 10 passed final specification and code-quality/security review;
Task 11 passed fresh local verification. Task 12 external runtime evidence
remains `NOT-RUN`. Task 13 local commit and collaboration-branch push passed at
implementation commit `8a5b1ed`; release merge and deployment remain
unauthorized.
