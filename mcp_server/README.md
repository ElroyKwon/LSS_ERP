# LSS ERP MCP

This is an isolated MCP stdio process for the LSS ERP REST contract. It has no
database dependency and must not receive a database account, `DATABASE_URL`,
backend `SECRET_KEY`, or backend imports.

The current package exposes fourteen tools: the existing seven
timesheet-focused tools and seven enterprise-schedule read/prepare/confirmed
commit/status tools. All transport remains behind a fixed typed REST
allowlist; this is not a generic ERP API bridge. See
`docs/mcp/AI-SAFETY-BASELINE.md` for the token-derived identity, least
privilege, write Gate, evidence, and non-claim boundaries. The schedule
confirmation, owner-lease, dual-gate, uncertainty, and status-only replay
contract is documented in
`docs/mcp/SCHEDULE-CONFIRMATION-AND-PREPARE.md`. The selected concurrency
option—Employee namespace row locking before globally ordered Timesheet row
locking—is documented separately, with transaction, retry, and recovery
boundaries, in `docs/mcp/SCHEDULE-MUTATION-LOCKING.md`.

## Development setup

```powershell
py -3.12 -m venv mcp_server\.venv
.\mcp_server\.venv\Scripts\python.exe -m pip install -e "mcp_server[dev]"
```

## Required runtime configuration

Set a credential-free ERP API origin:

```powershell
$env:LSS_ERP_BASE_URL = 'https://development-erp.example.invalid'
```

Production and staging require HTTPS. Development HTTP is limited to loopback.
Store the API token interactively in Windows Credential Manager:

```powershell
.\mcp_server\.venv\Scripts\lss-erp-mcp-credential.exe set
```

The default service and target names are `LSS ERP MCP` and
`lss-erp-mcp-local`. Do not put the token in shell history, Git, Markdown, or
MCP host configuration.

## Run

```powershell
.\mcp_server\.venv\Scripts\lss-erp-mcp.exe
```

The process uses stdio transport. Do not write diagnostic text to stdout
because stdout carries MCP protocol messages.

For AI-assisted timesheets, the approved host reads a personal worklog locally
and calls `timesheet_prepare_from_worklog` with minimal structured facts. Do
not send raw worklog text, a vault path, an employee selector, or a guessed
duration. The tool preserves unrelated draft rows and returns focused questions
plus daily/weekly totals before a commit can be requested.

`timesheet_prepare_draft` is a complete-replacement compatibility tool. Omitted
rows become removals, so an AI host must not use it for a partial worklog.

Both write surfaces are disabled independently by default.
`LSS_ERP_CANARY_WRITE=true` enables only the timesheet commit tool.
`LSS_ERP_SCHEDULE_CANARY_WRITE=true` enables only local schedule commit and
accepts only the exact lowercase literal; the backend still independently
requires `MCP_SCHEDULE_WRITE_ENABLED=true`. Neither setting is ordinary
configuration: it may be enabled only for a separately approved canary after
the backend and read-only integration Gates pass. An uncertain schedule write
is never retried automatically; use `schedule_operation_status` with the
returned correlation ID. The default correlation is deterministically derived
from the authenticated numeric `user_id` plus idempotency key, so it can also
be recovered after a cancelled or lost stdio response without resending the
mutation and cannot collide merely because different users chose the same key.
Persist both values before commit.

Schedule confirmations and owner leases are bounded process-local state, not a
durable queue or operation journal. Restart removes them. Any exception after
the typed write method is entered is treated as potentially sent; the MCP
consumes the matching lease or leaves it `INFLIGHT_FAIL_CLOSED` if finalization
cannot be proven. A restart or cancellation never authorizes blind resubmission:
recover the correlation and query the backend journal. If journal evidence is
missing or conflicting, stop for manual review.

Strict MCP input validation is retained. Rejected arguments return the fixed
`invalid_tool_arguments` boundary and do not reflect free text, unknown owner
fields, or Pydantic `input_value` details to the client. Tool schemas publish
`additionalProperties=false`; unknown top-level fields are rejected before
tool code or write-gate evaluation.

## Verify

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests -q
.\mcp_server\.venv\Scripts\python.exe -m compileall -q mcp_server\src mcp_server\tests
.\mcp_server\.venv\Scripts\python.exe -m pip_audit --progress-spinner off
```

See `docs/mcp/AI-MAIN-DEVELOPER-ENTRYPOINT.md` for ownership and integration
boundaries and `docs/mcp/LOCAL-VERIFICATION.md` for the evidence classification.

The local test suite does not prove PostgreSQL row-lock contention, a real ERP
transport, Google Calendar, deployed process restart/cancellation, canary
writes, rollback, release merge, or deployment. The reviewed implementation
was committed and pushed only to the development collaboration branch; all
external/runtime/release gates remain `NOT-RUN`.
