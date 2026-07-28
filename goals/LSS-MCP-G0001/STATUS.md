# LSS-MCP-G0001 Status

- status: ACTIVE
- code_baseline: khlee-add-mcp@8a5b1ed
- design_commit: 3b4f001
- remote_main_at_first_push: 8cb295c
- remote_main_overlap: NONE (frontend ProjectsView only)
- owner: coordinator
- backend_owner: main developer
- local_database: UNAVAILABLE
- execution_model: parallel backend handoff and database-free MCP lane
- collaboration_push: GRANTED
- collaboration_remote_checkpoint: PUSHED (8a5b1ed)
- github_issue_registration: MANUAL-PENDING
- github_issue_draft: docs/mcp/GITHUB-ISSUE-HANDOFF.md
- ai_safety_baseline: docs/mcp/AI-SAFETY-BASELINE.md
- release_merge_deploy: NOT-GRANTED
- release_state: DEVELOPMENT/NOT-RELEASED
- parallel_local_lane: IMPLEMENTED/LOCAL-PASS/WRITE-DISABLED
- local_code_checkpoint: 8a5b1ed
- local_timesheet_checkpoint: PASS (108 passed historical focused package)
- local_schedule_backend_pytest: PASS (124 passed)
- local_mcp_pytest: PASS (379 passed)
- local_compileall: PASS
- local_banned_runtime_refs: PASS (0)
- local_dependency_audit: PASS (0 known vulnerabilities; local unpublished package skipped)
- local_mcp_sdk_stdio: PASS
- local_mcp_sdk_tools_list: PASS (7 tools and annotations)
- local_mcp_inspector_tools_list: PASS (exactly 7 tools)
- local_mermaid_docs: PASS (13/13 rendered)
- credential_manager_live: NOT-RUN
- backend_handback: WAITING
- postgresql_and_alembic: NOT-RUN
- deployed_real_api: NOT-RUN
- real_erp_read_and_write: NOT-RUN
- canary_and_rollback: NOT-RUN
- exposed_mcp_scope: exactly 14 tools over 12 fixed REST method/path pairs
- ai_timesheet_scope: structured worklog facts, self entry context, safe merge,
  exception questions, daily/weekly totals, confirmed own-draft commit
- personal_worklog_raw_text_or_path: FORBIDDEN
- future_weekly_report_transcript_telegram_email_project_mutation: DEFERRED
- all_erp_api_access: NOT-IN-SCOPE

## Done-When

- Backend dependency and contract test evidence received.
- PostgreSQL 16 test database identified as non-production.
- SEC-20 and SEC-21 resolved with regression evidence.
- Legacy `/api/mcp` read contract frozen and write surface remains zero.
- Normal, 401, 403, 409, and 422 contracts are fixed.
- No unclassified P0 risk remains.

## Local Evidence Boundary

The database-free MCP implementation, enterprise-schedule controls, and local
test oracle are pushed for main-developer collaboration, but they do not
complete G0001. G0001 remains the only `ACTIVE` Goal until the backend
dependency, PostgreSQL, migration, contract, security, and legacy UI evidence
is returned and accepted.

Reproduction commands and explicit non-claims are recorded in
`docs/mcp/LOCAL-VERIFICATION.md`.

## Stop Conditions

- Production-like database target.
- Missing backend commit SHA.
- SQLite-only migration acceptance.
- Secret or database credential placed in Git or Markdown.
- Backend reports PASS without command output.
