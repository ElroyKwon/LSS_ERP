# LSS-MCP-G0003 Status

- status: PLANNED/NOT-RUN
- owner: main developer
- dependency: G0002 PASS

## Goal

Enforce token-derived self access, draft-only mutation, expected version,
employee/week uniqueness, and canonical entry validation.

Expanded entries must support execution, sales, common, and annual leave while
the backend derives employee and labor type.

## Done-When

- client identity, status, approver, and labor-type selectors are rejected;
- submitted, approved, and rejected rows are immutable;
- stale version and duplicate employee/week writes return `409`;
- daily-to-weekly ERP row mapping preserves all canonical entry fields;
- frontend/backend work-type parity is evidenced.
