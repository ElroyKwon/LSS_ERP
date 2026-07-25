# LSS-MCP-G0004 Status

- status: PLANNED/NOT-RUN
- owner: main developer
- dependency: G0003 PASS

## Goal

Commit mutation, idempotency record, request hash, correlation data, and audit
evidence in one PostgreSQL transaction.

## Done-When

- same key and hash replay exactly once;
- same key and different hash returns `409`;
- timeout before and after mutation has deterministic recovery;
- audit and data are atomic and redacted;
- rollback result is reproduced.
