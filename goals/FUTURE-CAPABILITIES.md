# LSS ERP MCP Future Capability Separation

These are registered deferred Goals, not implemented features and not implied
by the current seven-tool MCP package. Each Goal has an inactive `STATUS.md`
under `goals/LSS-MCP-G00xx/`.

| Goal | Capability | Current state | Required new boundary |
|---|---|---|---|
| G0011 | Weekly narrative work report | DEFERRED/NOT-DESIGNED | report source, factual grounding, approval, persistence |
| G0012 | Transcript/audio work intake | DEFERRED/NOT-DESIGNED | transcription provider, consent, retention, raw-content minimization |
| G0013 | Project registration and information mutation | DEFERRED/NOT-DESIGNED | field ownership, duplicate detection, approval, rollback |
| G0014 | Telegram command intake | DEFERRED/NOT-DESIGNED | sender binding, command confirmation, replay protection, audit |
| G0015 | Company email analysis | DEFERRED/NOT-DESIGNED | mailbox authority, privacy, retention, employee separation, action approval |
| G0016 | Manager and cross-employee functions | DEFERRED/NOT-DESIGNED | role/scope, purpose limitation, least privilege, access review |

The next implementation remains the current worklog-to-own-timesheet lane.
Future Goals must not be activated or added to the REST allowlist until their
own user approval and security design exist.
