# LSS ERP MCP Main Developer Evidence Hand-Back

Copy this template into the main developer's result. Replace values only with
reproduced evidence. Keep unresolved fields as `NONE`, `NOT-RUN`, or
`UNKNOWN`.

```yaml
source_branch: khlee-add-mcp
backend_working_branch: NONE
backend_commit: NONE
postgresql_test_lane:
  identity: NONE
  non_production_proof: NOT-RUN
alembic_revisions:
  before: NONE
  schedule_operation_journal: 20260727_0015
  timesheet_employee_week_unique: 20260727_0016
  current_after_upgrade: NONE
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
  schedule_contract:
    command: NONE
    result: NOT-RUN
  schedule_lock_contention:
    employee_namespace_before_timesheet: NOT-RUN
    missing_timesheet_header: NOT-RUN
    concurrent_schedule_vs_timesheet_writer: NOT-RUN
    scope_restart_and_bound: NOT-RUN
  entry_context_contract:
    command: NONE
    result: NOT-RUN
  expanded_timesheet_dto:
    command: NONE
    result: NOT-RUN
  work_type_catalog_parity:
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
authorization:
  token_identity_to_auth_context: NOT-RUN
  client_identity_fields_rejected: NOT-RUN
  self_only_idor_denied: NOT-RUN
  unregistered_endpoint_default_deny: NOT-RUN
  protected_state_write_denied: NOT-RUN
  jwt_and_api_token_privileges_not_unionized: NOT-RUN
  entry_context_has_no_employee_selector: NOT-RUN
  labor_type_is_server_derived: NOT-RUN
  schedule_read_scope: NOT-RUN
  schedule_write_scope: NOT-RUN
  schedule_operation_user_isolation: NOT-RUN
  legacy_owner_unbound_denied: NOT-RUN
  owner_mismatch_denied: NOT-RUN
  stale_etag_denied: NOT-RUN
timesheet_mapping:
  execution_project: NOT-RUN
  sales_project: NOT-RUN
  common_work: NOT-RUN
  annual_leave: NOT-RUN
  existing_unmentioned_rows_preserved: NOT-RUN
  daily_weekly_totals_match_legacy_ui: NOT-RUN
schedule_mapping:
  list_detail_preflight_status: NOT-RUN
  create_exact_replay: NOT-RUN
  update_if_match: NOT-RUN
  delete_if_match: NOT-RUN
  locked_timesheet_no_google_write: NOT-RUN
  response_loss_reconciliation: NOT-RUN
  partial_failure_manual_review: NOT-RUN
token_policy:
  raw_token_stored_in_database: FORBIDDEN
  client_id: lss-erp-mcp-local
  resource: lss-erp-api
  default_scope_empty: NOT-RUN
  exact_scopes:
    - mcp:discover
    - timesheet:read:self
    - timesheet:write:self:draft
    - schedule:read
    - schedule:write
  expiry_and_revoke_401: NOT-RUN
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
google_test_calendar:
  identity: NONE
  dedicated_non_production_proof: NOT-RUN
  created_event_ids: []
  unresolved_event_ids: []
rollback:
  timesheet_write_tool_disabled: NOT-RUN
  schedule_mcp_write_tool_disabled: NOT-RUN
  schedule_backend_write_disabled: NOT-RUN
  token_revoke_401: NOT-RUN
  test_calendar_cleanup: NOT-RUN
  command: NONE
  result: NOT-RUN
  final_schedule_state: UNKNOWN
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
- PostgreSQL Employee-before-Timesheet contention output, including an absent
  target-week Timesheet header and a concurrent schedule/timesheet writer;
- backend and legacy UI test output;
- entry-context and expanded execution/sales/common/leave DTO test output;
- frontend/backend work-type catalog parity evidence, including
  `영업 > SHOP작업`;
- token-derived identity, self-only, default-deny, scope, and protected-state
  security test output;
- schedule list/detail/preflight/status, owner/etag, exact replay, response-loss,
  and partial-failure test output;
- redacted canary event/correlation IDs and rollback evidence, if separately
  approved and run.

## Forbidden content

Do not place a token, authorization header, database URL, database account,
`SECRET_KEY`, raw request body, SQL containing personal data, personal
worklog, or vault path in this file or its attachments.
