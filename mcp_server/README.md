# LSS ERP MCP

This is an isolated MCP stdio process for the LSS ERP REST contract. It has no
database dependency and must not receive a database account, `DATABASE_URL`,
backend `SECRET_KEY`, or backend imports.

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

The write tool is disabled by default. `LSS_ERP_CANARY_WRITE=true` is not
ordinary configuration: it may be set only for a separately approved canary
after the backend and read-only integration Gates pass.

## Verify

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests -q
.\mcp_server\.venv\Scripts\python.exe -m compileall -q mcp_server\src mcp_server\tests
.\mcp_server\.venv\Scripts\python.exe -m pip_audit --progress-spinner off
```

See `docs/mcp/AI-MAIN-DEVELOPER-ENTRYPOINT.md` for ownership and integration
boundaries and `docs/mcp/LOCAL-VERIFICATION.md` for the evidence classification.
