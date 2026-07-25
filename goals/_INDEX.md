# LSS ERP MCP Goal Index

| Goal | Purpose | Status | Owner |
|---|---|---|---|
| LSS-MCP-G0001 | Backend API contract and dependency baseline | ACTIVE | coordinator + main developer |
| LSS-MCP-G0002 | API token scope and default deny | PLANNED | main developer |
| LSS-MCP-G0003 | Timesheet self, state, version, unique | PLANNED | main developer |
| LSS-MCP-G0004 | Idempotency and audit transaction | PLANNED | main developer |
| LSS-MCP-G0005 | Isolated stdio MCP package | PLANNED | MCP implementer |
| LSS-MCP-G0006 | Read-only REST tools | PLANNED | MCP implementer |
| LSS-MCP-G0007 | Local prepare and diff | PLANNED | MCP implementer |
| LSS-MCP-G0008 | Confirmed draft commit | PLANNED | MCP implementer |
| LSS-MCP-G0009 | Security, fault, performance, rollback, release gate | PLANNED | coordinator |

Rule: exactly one Goal may be ACTIVE.

Verified development checkpoints may be pushed only to
`origin/khlee-add-mcp`. They remain `DEVELOPMENT/NOT-RELEASED` until G0009
`COMPLETE/PASS` and separate user approval for `origin/main` release merge or
deployment. Main developers may branch from the collaboration branch or merge
it into a separate backend working branch for the requested hand-back.
