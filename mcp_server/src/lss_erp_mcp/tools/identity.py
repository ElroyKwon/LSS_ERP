from __future__ import annotations

from lss_erp_mcp.erp_client import ERPClient


async def get_current_user(client: ERPClient) -> dict[str, object]:
    return (await client.get_current_user()).model_dump(mode="json")
