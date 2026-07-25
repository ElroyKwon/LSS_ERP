# LSS ERP MCP Main Developer AI Entrypoint

## Start here

This branch is a collaboration checkpoint for development only. It is not
approval to merge, deploy, or enable real ERP writes.

1. Check out `khlee-add-mcp` and record `git rev-parse HEAD`.
2. Read
   `docs/handoffs/2026-07-25-lss-erp-mcp-backend-db-token-handoff.md`.
3. Read `docs/mcp/API-CONTRACT.md`.
4. Read `docs/mcp/APPLY-AND-ROLLBACK.md`.
5. Implement only the main-developer-owned backend and PostgreSQL lane.
6. Return reproduced evidence using
   `docs/mcp/EVIDENCE-HAND-BACK.md`.

Do not replace `NONE`, `NOT-RUN`, or `UNKNOWN` with an assumption.

## Ownership

| Lane | Owner | Scope |
|---|---|---|
| Backend and database | Main developer | PostgreSQL, Alembic, token hash and scope, `AuthContext`, REST endpoints, audit, idempotency, development and actual-server application, rollback |
| Isolated MCP | MCP lane | Database-free contract stub, REST client, stdio tools, local confirmation, unit/contract/protocol/security/fault/performance tests |
| Joint Gate | Both | Real API read-only, separately approved one-user canary, rollback reproduction, G0009 decision |

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
- Do not merge or deploy because this branch exists. Its release state is
  `DEVELOPMENT/NOT-RELEASED`.

## Backend work expected

1. Identify a non-production PostgreSQL 16 test lane.
2. Run employee/week and parking duplicate preflight queries.
3. Add and test the minimum schema constraints and token/scope model.
4. Implement the four REST endpoints in `API-CONTRACT.md`.
5. Prove authentication, ownership, protected-state, version, idempotency,
   audit, and rollback behavior.
6. Export the deployed development OpenAPI document and calculate SHA-256.
7. Return a credential-free development API base URL and the Windows
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
