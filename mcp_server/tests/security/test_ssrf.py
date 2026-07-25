from __future__ import annotations

import pytest

from lss_erp_mcp.erp_client import ERPClient


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:pass@erp.example.test",
        "https://erp.example.test/api",
        "https://erp.example.test?target=other",
        "https://erp.example.test#fragment",
    ],
)
def test_client_rejects_non_origin_base_urls(base_url: str) -> None:
    with pytest.raises(ValueError, match="origin"):
        ERPClient(base_url=base_url, token="test-token")


def test_client_rejects_empty_token() -> None:
    with pytest.raises(ValueError, match="token"):
        ERPClient(base_url="https://erp.example.test", token="")
