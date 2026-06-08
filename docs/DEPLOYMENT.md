# LSS ERP Deployment Notes

## Target Runtime

- Production target: Ubuntu server.
- Public access will use an assigned domain over HTTPS.
- FastAPI serves the built Vue SPA from `frontend/dist` in the current single-service layout.
- Keep production secrets in `backend/.env`; do not commit that file.

## Required Production Environment

Set these values in `backend/.env` on the Ubuntu server:

```env
DATABASE_URL=postgresql+pg8000://<user>:<password>@<host>:5432/<database>
SECRET_KEY=<strong-random-secret-at-least-32-chars>
DEBUG=false
API_DOCS_ENABLED=false
ALLOWED_ORIGINS=https://<production-domain>
NTS_BUSINESS_STATUS_SERVICE_KEY=<data-go-kr-key>
POSTAL_SERVICE_KEY=<epost-key>
```

When local development also needs Vite, include local origins:

```env
ALLOWED_ORIGINS=https://<production-domain>,http://localhost:5173,http://localhost:3000
```

## Deployment Checklist

1. Install Python, Node.js LTS, PostgreSQL, and reverse proxy such as Nginx.
2. Create the PostgreSQL database and production DB user.
3. Place `backend/.env` on the server with production values.
4. Build frontend with `npm run build` from `frontend`.
5. Run FastAPI with a process manager such as systemd and Uvicorn.
6. Put Nginx in front of Uvicorn and terminate HTTPS at Nginx.
7. Set DNS for the assigned domain to the Ubuntu server.
8. Set `API_DOCS_ENABLED=false` unless public API docs are intentionally required.
9. Test login, company registration, NTS status lookup, and postal lookup after deployment.

## External API Notes

- NTS business status uses `https://api.odcloud.kr/api/nts-businessman/v1/status`.
- EPost postal lookup uses `retrieveNewAdressAreaCdSearchAllService/getNewAddressListAreaCdSearchAll`.
- If an external service key is missing, expired, or rejected, the frontend shows a dedicated popup.
- Admin users can update external API keys from that popup; the backend writes the new value to `backend/.env` and updates the running process settings.

## Current Operational Constraints

- Schema bootstrap currently runs on app startup through `Base.metadata.create_all()` plus `ensure_master_columns()`. This is convenient for development, but Alembic migrations should be used before production data becomes critical.
- `frontend/dist` is served by FastAPI. If traffic grows, serving static assets directly from Nginx is preferable.
