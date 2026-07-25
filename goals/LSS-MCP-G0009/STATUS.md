# LSS-MCP-G0009 Status

- status: PLANNED/LOCAL-PARTIAL
- owner: coordinator + main developer
- active_goal: false
- release_state: DEVELOPMENT/NOT-RELEASED

## Locally covered

- strict unit, contract, integration, protocol, security, fault, and
  performance tests;
- worklog privacy and no-silent-deletion checks;
- project/common/leave/non-project golden cases;
- deterministic questions and exact expanded-entry readback.

## Still required

- PostgreSQL and Alembic evidence;
- deployed OpenAPI hash;
- real token/AuthContext/default-deny/IDOR tests;
- real entry-context and DTO parity;
- representative worklog shadow review;
- one-user canary only after separate approval;
- token revoke, backend/migration/data rollback, and legacy UI smoke;
- independent review of all reproduced evidence.

No release merge, deployment, or real write is authorized.
