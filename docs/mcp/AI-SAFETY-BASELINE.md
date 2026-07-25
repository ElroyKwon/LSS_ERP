# LSS ERP MCP AI Safety Baseline

## Purpose and claim boundary

This document records the safety controls required before an AI host may use
the LSS ERP MCP. It is an evidence baseline, not a blanket guarantee that the
system is safe.

- Current state: `DEVELOPMENT/NOT-RELEASED`
- Current local evidence: database-free MCP lane only
- Main-developer evidence: `WAITING`
- Real API, PostgreSQL, canary, and rollback: `NOT-RUN`

The current MCP does **not** expose every ERP API. It exposes exactly five MCP
tools over four allowlisted REST endpoints:

| MCP tool | Purpose | Remote write |
|---|---|---|
| `erp_get_current_user` | Return minimum identity bound to the API token | No |
| `timesheet_get_week` | Read the token owner's requested week | No |
| `timesheet_search_projects` | Search the minimum active-project view | No |
| `timesheet_prepare_draft` | Build a local diff and expiring confirmation | No |
| `timesheet_commit_draft` | Save the token owner's draft after all write Gates | Yes; disabled by default |

Any additional ERP function or endpoint requires a new inventory, scope,
contract, threat review, tests, and release Goal. It must not be inferred from
this branch.

## Identity and authorization invariant

The MCP client never chooses the employee whose data is accessed. The backend
must derive `user_id` and `employee_id` from the validated API token and bind
them to one `AuthContext`.

```mermaid
sequenceDiagram
    participant AI as Approved AI host
    participant MCP as Isolated mcp_server
    participant API as ERP REST API
    participant AUTH as Token/AuthContext
    participant DB as PostgreSQL

    AI->>MCP: Call one allowlisted tool
    MCP->>API: HTTPS + bearer token
    API->>AUTH: Validate hash, expiry, revocation, client, resource, scope
    AUTH-->>API: Server-derived user_id and employee_id
    API->>DB: Query or mutate rows owned by that employee
    DB-->>API: Minimum allowed result
    API-->>MCP: Strict response + correlation_id
    MCP-->>AI: Strict tool result

    Note over AI,MCP: employee_id/user_id/status are not authority inputs
    Note over MCP,DB: MCP has no DB account or DATABASE_URL
```

Required token constraints:

- raw token returned only once at issuance and never stored in Git;
- database stores token hash and prefix, not the raw token;
- `client_id=lss-erp-mcp-local`;
- `resource=lss-erp-api`;
- default scope is empty and unregistered token endpoints return `403`;
- allowed scopes are only `mcp:discover`, `timesheet:read:self`, and
  `timesheet:write:self:draft`;
- expired, revoked, invalid, or inactive-user tokens return `401`;
- JWT role/menu privileges are never unioned into API-token scopes;
- API requests do not accept `employee_id`, `user_id`, `approver_id`, or
  `status` as authority.

## Safety control matrix

| Risk | Required control | Local evidence in this branch | Main developer or joint proof still required |
|---|---|---|---|
| AI accesses another employee | Server derives identity from token; self-only endpoints; strict schemas reject extra identity fields | Contract oracle, strict Pydantic models, same-user confirmation check | Real `AuthContext`, IDOR tests, deployed OpenAPI |
| Broad ERP access | Four-method/path REST allowlist; three explicit scopes; default deny | REST client allowlist and contract/error tests | Backend endpoint mapping and unregistered-path `403` |
| Direct database bypass | Separate stdio process; no backend, ORM, DB driver, account, or `DATABASE_URL` | Import isolation test and banned-reference scan | Deployment configuration review |
| Unapproved write | Write disabled by default; prepare is local/no-write; expiring confirmation required | Prepare/commit integration and confirmation tests | Approved canary configuration and operator evidence |
| Cross-user or stale confirmation | Confirmation bound to user, week, version, proposal hash, and one idempotency key | Integrity, expiry, mismatch, and concurrent-claim tests | Backend self/state/version enforcement |
| Duplicate or uncertain write | Expected version, idempotency key, response-loss readback, exact post-write verification | Fault/replay/concurrency tests against contract oracle | PostgreSQL unique, single transaction, real response-loss test |
| Protected record modification | Only `작성중 → 작성중`; submitted/approved/rejected immutable | Local prepare rejects non-draft state | Backend protected-state tests |
| Secret or business-content leak | Credential Manager, redacted telemetry, no raw body/vault path, no stdout diagnostics | Credential loader, redaction, secret scan, stdio tests | Live Credential Manager and deployed log inspection |
| SSRF or response abuse | Origin-only base URL, HTTPS outside loopback, redirects rejected, response-size bound | Configuration, SSRF, client contract tests | Development endpoint and network policy evidence |
| Unsafe release inference | Collaboration push is not release approval; kill switch, revoke, rollback Gates | State and handoff documents | G0009 joint PASS and separate user approval |

## Evidence classification

### Verified locally

- 70 database-free unit, contract, integration, protocol, security, fault, and
  performance tests pass.
- Official MCP SDK stdio initialize/list/call passes.
- MCP Inspector lists exactly five tools.
- MCP source has zero backend/ORM/DB-driver imports and banned runtime
  references.
- Secret-pattern scan reports zero findings.
- Dependency audit reports zero known vulnerabilities in resolved
  dependencies; the local unpublished package is not a PyPI audit target.
- Write confirmation is integrity-bound, expiring, single in-flight, and
  permanently bound to one idempotency key.
- A response lost after a possible write is reconciled by readback before any
  same-key retry.

### Not yet verified

- token-to-`AuthContext` behavior in the real backend;
- PostgreSQL migrations, uniqueness, and transaction atomicity;
- real default-deny, IDOR, protected-state, and audit behavior;
- live Windows Credential Manager use;
- development API read-only integration;
- one-user draft canary;
- token revocation, backend rollback, and legacy UI recovery.

No AI or developer may convert these items from `NOT-RUN` or `UNKNOWN` to
`PASS` without reproduced command output and identifiable artifacts.

## Main developer acceptance work

The main developer must return the following before the local safety claims can
be extended to the real system:

1. exact backend branch and commit SHA;
2. non-production PostgreSQL 16 lane identity;
3. Alembic upgrade and downgrade evidence;
4. token hash/expiry/revocation/client/resource/scope default-deny tests;
5. token-derived self-only and protected-state authorization tests;
6. employee/week duplicate preflight and unique-constraint evidence;
7. idempotency, request-hash, mutation, and audit single-transaction tests;
8. normal plus 401/403/404/409/422/429/5xx contract results;
9. deployed OpenAPI artifact and SHA-256;
10. credential-free development base URL and Credential Manager target name;
11. token revoke `401`, rollback, and legacy UI smoke evidence;
12. every remaining blocker and `UNKNOWN`.

Use `docs/mcp/EVIDENCE-HAND-BACK.md`; do not include token values, database
credentials, connection strings, authorization headers, raw request bodies, or
personal paths.

## Release decision

A main developer may branch from or merge `origin/khlee-add-mcp` into a
separate backend working branch to perform the requested implementation. That
does not authorize merging into `origin/main`, deploying to a real server, or
enabling real ERP writes.

Release merge, deployment, and real write activation require G0009
`COMPLETE/PASS` plus separate user approval.
