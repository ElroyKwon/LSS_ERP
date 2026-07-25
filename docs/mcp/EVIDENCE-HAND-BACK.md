# LSS ERP MCP Main Developer Evidence Hand-Back

Copy this template into the main developer's result. Replace values only with
reproduced evidence. Keep unresolved fields as `NONE`, `NOT-RUN`, or
`UNKNOWN`.

```yaml
branch: khlee-add-mcp
backend_commit: NONE
postgresql_test_lane:
  identity: NONE
  non_production_proof: NOT-RUN
alembic_revision:
  before: NONE
  applied: NONE
  rollback_target: NONE
openapi:
  source: NONE
  sha256: NONE
dependency_audit:
  command: NONE
  result: NOT-RUN
tests:
  backend_contract:
    command: NONE
    result: NOT-RUN
  backend_security:
    command: NONE
    result: NOT-RUN
  postgresql_integration:
    command: NONE
    result: NOT-RUN
  migration_upgrade:
    command: NONE
    result: NOT-RUN
  migration_downgrade:
    command: NONE
    result: NOT-RUN
  legacy_ui_smoke:
    command: NONE
    result: NOT-RUN
duplicates:
  employee_week:
    query_id: NONE
    count: UNKNOWN
  parking:
    query_id: NONE
    count: UNKNOWN
development_api:
  base_url: NONE
  credential_service: LSS ERP MCP
  credential_target: NONE
  token_value: FORBIDDEN
rollback:
  write_tool_disabled: NOT-RUN
  token_revoke_401: NOT-RUN
  command: NONE
  result: NOT-RUN
  final_data_state: UNKNOWN
  final_migration_state: UNKNOWN
blockers: []
unknowns:
  - Replace only with reproduced evidence
```

## Required attachments

- exact commands and summarized output;
- backend commit diff or file list;
- redacted duplicate preflight output;
- OpenAPI artifact hash output;
- migration current/upgrade/downgrade output;
- backend and legacy UI test output;
- redacted canary and rollback correlation IDs, if separately approved and run.

## Forbidden content

Do not place a token, authorization header, database URL, database account,
`SECRET_KEY`, raw request body, SQL containing personal data, personal
worklog, or vault path in this file or its attachments.
