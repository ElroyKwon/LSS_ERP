# LSS-MCP-G0002 Status

- status: PLANNED/NOT-RUN
- owner: main developer
- dependency: G0001 hand-back accepted

## Goal

Implement API-token hash, expiry, revocation, client/resource binding, the
minimum three scopes, and default deny for every unregistered endpoint.

The new `GET /api/timesheets/entry-context` uses
`timesheet:read:self`; it does not add a broader scope.

## Done-When

- missing, invalid, expired, revoked, and inactive-user tokens return `401`;
- wrong client, resource, scope, or endpoint returns `403`;
- JWT role/menu permissions are not unioned into API-token permissions;
- exact commands and PostgreSQL-backed evidence are returned.
