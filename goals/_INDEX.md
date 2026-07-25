# LSS ERP MCP Goal Index

| Goal | Purpose | Status | Owner |
|---|---|---|---|
| LSS-MCP-G0001 | Backend API contract and dependency baseline | ACTIVE | coordinator + main developer |
| LSS-MCP-G0002 | API token scope and default deny | PLANNED | main developer |
| LSS-MCP-G0003 | Timesheet self, state, version, unique | PLANNED | main developer |
| LSS-MCP-G0004 | Idempotency and audit transaction | PLANNED | main developer |
| LSS-MCP-G0005 | Isolated stdio MCP package and AI tool metadata | IMPLEMENTED/LOCAL-PASS | MCP implementer |
| LSS-MCP-G0006 | Self reads, entry context, and project candidates | IMPLEMENTED/LOCAL-PASS | MCP implementer |
| LSS-MCP-G0007 | Worklog facts, safe merge, totals, exception questions | IMPLEMENTED/LOCAL-PASS | MCP implementer |
| LSS-MCP-G0008 | Confirmed expanded-draft commit | IMPLEMENTED/LOCAL-PASS/DISABLED | MCP implementer |
| LSS-MCP-G0009 | Security, AI quality, fault, rollback, release gate | PLANNED/LOCAL-PARTIAL | coordinator |
| LSS-MCP-G0010 | Schedule capability | DEFERRED/NOT-RUN | separate approval |
| LSS-MCP-G0011 | Weekly narrative work report | DEFERRED/NOT-DESIGNED | separate approval |
| LSS-MCP-G0012 | Transcript and audio work intake | DEFERRED/NOT-DESIGNED | separate approval |
| LSS-MCP-G0013 | Project registration and information mutation | DEFERRED/NOT-DESIGNED | separate approval |
| LSS-MCP-G0014 | Telegram command intake and status reply | DEFERRED/NOT-DESIGNED | separate approval |
| LSS-MCP-G0015 | Company email ingestion and analysis | DEFERRED/NOT-DESIGNED | separate approval |
| LSS-MCP-G0016 | Manager and cross-employee functions | DEFERRED/NOT-DESIGNED | separate approval |

Rule: exactly one Goal may be ACTIVE.

`IMPLEMENTED/LOCAL-PASS` is evidence classification, not another active Goal.
G0001 remains the only `ACTIVE` Goal until the main-developer backend hand-back
is accepted.

Verified development checkpoints may be pushed only to
`origin/khlee-add-mcp`. They remain `DEVELOPMENT/NOT-RELEASED` until G0009
`COMPLETE/PASS` and separate user approval for `origin/main` release merge or
deployment. Main developers may branch from the collaboration branch or merge
it into a separate backend working branch for the requested hand-back.

Weekly report, transcript, project mutation, Telegram, email, and manager
functions are registered as inactive deferred Goals G0011 through G0016 and
summarized in `FUTURE-CAPABILITIES.md`. They are not implied by the current
seven-tool package.
