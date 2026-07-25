# LSS ERP MCP Main Developer AI Entrypoint

## Start here

This branch is a collaboration checkpoint for development only. A main
developer may branch from it or merge it into a separate backend working
branch. It is not approval to merge into `origin/main`, deploy, or enable real
ERP writes.

1. Check out `khlee-add-mcp` and record `git rev-parse HEAD`.
2. Read `goals/_INDEX.md` and `goals/LSS-MCP-G0001/STATUS.md`.
3. Read
   `docs/handoffs/2026-07-25-lss-erp-mcp-backend-db-token-handoff.md`.
4. Read
   `docs/superpowers/specs/2026-07-25-lss-erp-ai-timesheet-automation-design.md`.
5. Read
   `docs/superpowers/plans/2026-07-25-lss-erp-ai-timesheet-automation.md`.
6. Read `docs/mcp/API-CONTRACT.md`.
7. Read `docs/mcp/AI-SAFETY-BASELINE.md`.
8. Read `docs/mcp/APPLY-AND-ROLLBACK.md`.
9. Implement only the main-developer-owned backend and PostgreSQL lane.
10. Return reproduced evidence using
   `docs/mcp/EVIDENCE-HAND-BACK.md`.

Do not replace `NONE`, `NOT-RUN`, or `UNKNOWN` with an assumption.

## Working-branch integration

Use one of these development-only flows:

```powershell
git fetch origin
git switch -c main-dev-mcp-backend origin/khlee-add-mcp
git rev-parse HEAD
```

Or merge the collaboration branch into an existing separate backend working
branch after reviewing `git diff origin/main...origin/khlee-add-mcp`.

Do not merge directly into `origin/main`. Return the exact working-branch SHA
with the evidence hand-back. Release integration remains gated by G0009 and a
separate user approval.

## Ownership

| Lane | Owner | Scope |
|---|---|---|
| Backend and database | Main developer | PostgreSQL, Alembic, token hash and scope, `AuthContext`, REST endpoints, audit, idempotency, development and actual-server application, rollback |
| Isolated MCP | MCP lane | Database-free contract stub, REST client, stdio tools, local confirmation, unit/contract/protocol/security/fault/performance tests |
| Joint Gate | Both | Real API read-only, separately approved one-user canary, rollback reproduction, G0009 decision |

The current package exposes exactly seven timesheet-focused MCP tools over five
REST endpoints. The new local lane accepts minimal structured worklog facts,
preserves unrelated existing rows, and asks deterministic exception questions.
It does not read a vault path or send raw worklog text to ERP. It does not
expose every ERP API. Additional ERP capabilities require separate scope,
contract, threat, and test Goals.

G0011 through G0016 are already registered as inactive
`DEFERRED/NOT-DESIGNED` Goals for weekly reports, transcript/audio intake,
project mutation, Telegram commands, company email analysis, and
manager/cross-employee functions. Do not implement or add them to the REST
allowlist during the current G0001 backend hand-back.

The isolated MCP lane must not edit backend models, migrations, authentication
middleware, deployment files, or database configuration. The main developer
must not add direct database access to `mcp_server/`.

## Non-negotiable boundaries

- Do not give the MCP process `DATABASE_URL`, a database account, `SECRET_KEY`,
  or backend imports.
- Do not put a token, connection string, raw request body, or personal vault
  path in Git, Markdown, test output, screenshots, or chat.
- Do not use SQLite-only evidence to accept PostgreSQL migration behavior.
- Preserve the existing legacy `/api/mcp` read contract and keep its write
  surface at zero.
- Do not modify submitted, approved, or rejected timesheets through MCP.
- Treat `mcp_server/tests/contract_server/` as a local test oracle, not as the
  deployed API authority.
- Keep the write tool disabled until a separate user approval and the
  documented canary prerequisites are satisfied.
- Do not merge into `origin/main` or deploy because this branch exists. Its
  release state is `DEVELOPMENT/NOT-RELEASED`.

## Backend work expected

1. Identify a non-production PostgreSQL 16 test lane.
2. Run employee/week and parking duplicate preflight queries.
3. Add and test the minimum schema constraints and token/scope model.
4. Implement the five REST endpoints in `API-CONTRACT.md`, including the
   token-owner `entry-context` read.
5. Map expanded daily entries to the existing weekly ERP rows for execution,
   sales, common, and leave without accepting an employee or labor-type
   selector.
6. Resolve the existing frontend/backend work-type catalog drift, including
   `영업 > SHOP작업`, with regression evidence.
7. Prove authentication, ownership, protected-state, version, idempotency,
   audit, and rollback behavior.
8. Export the deployed development OpenAPI document and calculate SHA-256.
9. Return a credential-free development API base URL and the Windows
   Credential Manager target name only.

Stop and report evidence if duplicates exist, the target could be production,
the backend commit cannot be identified, or a required test is unavailable.

## Required hand-back

- backend commit SHA and branch;
- PostgreSQL test-lane identity proving non-production use;
- Alembic revision;
- OpenAPI SHA-256;
- dependency audit command and output;
- backend contract, security, PostgreSQL integration, migration
  upgrade/downgrade, and legacy UI test output;
- entry-context, expanded DTO mapping, work-type parity, and execution/sales/
  common/leave regression output;
- employee/week and parking duplicate preflight counts;
- development API base URL without credentials;
- Credential Manager service and target names without the token value;
- rollback command and reproduced result;
- all remaining blockers and `UNKNOWN` items.

## Local MCP verification

The MCP lane evidence is summarized in `docs/mcp/LOCAL-VERIFICATION.md`.
Reproduce it from the repository root:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests -q
.\mcp_server\.venv\Scripts\python.exe -m compileall -q mcp_server\src mcp_server\tests
.\mcp_server\.venv\Scripts\python.exe -m pip_audit --progress-spinner off
```

These local results do not prove Credential Manager live integration,
PostgreSQL behavior, a deployed REST contract, or real-server rollback.
