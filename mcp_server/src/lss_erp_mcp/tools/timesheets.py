from __future__ import annotations

from datetime import date

from lss_erp_mcp.erp_client import ERPClient


async def get_week(client: ERPClient, week_start: str) -> dict[str, object]:
    parsed = date.fromisoformat(week_start)
    return (await client.get_week(parsed)).model_dump(mode="json")


async def search_projects(
    client: ERPClient,
    query: str,
    limit: int = 20,
) -> dict[str, object]:
    return (await client.search_projects(query, limit)).model_dump(mode="json")
