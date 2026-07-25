from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from .confirmation import ConfirmationStore
from .config import McpSettings
from .credentials import load_erp_token
from .erp_client import ERPClient
from .schemas.timesheet import DraftEntry
from .tools.identity import get_current_user
from .tools.timesheets import get_week, prepare_draft, search_projects


@dataclass
class AppContext:
    client: ERPClient
    confirmations: ConfirmationStore


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    settings = McpSettings()
    token = load_erp_token(settings)
    async with ERPClient(
        base_url=str(settings.base_url),
        token=token,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        write_timeout_seconds=settings.write_timeout_seconds,
        pool_timeout_seconds=settings.pool_timeout_seconds,
        max_response_bytes=settings.max_response_bytes,
    ) as client:
        yield AppContext(
            client=client,
            confirmations=ConfirmationStore(),
        )


mcp = FastMCP("LSS ERP", lifespan=lifespan, log_level="WARNING")


@mcp.tool()
async def erp_get_current_user(
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Return the minimum identity bound to the configured ERP API token."""
    return await get_current_user(ctx.request_context.lifespan_context.client)


@mcp.tool()
async def timesheet_get_week(
    week_start: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Read the configured user's timesheet week without side effects."""
    return await get_week(ctx.request_context.lifespan_context.client, week_start)


@mcp.tool()
async def timesheet_search_projects(
    query: str,
    ctx: Context[ServerSession, AppContext],
    limit: int = 20,
) -> dict[str, object]:
    """Search active projects through the minimum timesheet contract."""
    return await search_projects(
        ctx.request_context.lifespan_context.client,
        query,
        limit,
    )


@mcp.tool()
async def timesheet_prepare_draft(
    week_start: str,
    entries: list[DraftEntry],
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Build a local diff and confirmation token without writing ERP."""
    app = ctx.request_context.lifespan_context
    return await prepare_draft(
        app.client,
        app.confirmations,
        week_start=week_start,
        entries=[entry.model_dump(mode="json") for entry in entries],
    )


def run() -> None:
    mcp.run(transport="stdio")
