import pytest

from lss_erp_mcp.config import McpSettings


def test_production_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        McpSettings(
            environment="production",
            base_url="http://erp.example.test",
            credential_service="LSS ERP MCP",
            credential_name="lss-erp-mcp-local",
        )


def test_development_http_requires_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        McpSettings(
            environment="development",
            base_url="http://192.0.2.10:8000",
            credential_service="LSS ERP MCP",
            credential_name="lss-erp-mcp-local",
        )


def test_development_allows_loopback_http() -> None:
    settings = McpSettings(
        environment="development",
        base_url="http://127.0.0.1:8000",
        credential_service="LSS ERP MCP",
        credential_name="lss-erp-mcp-local",
    )
    assert str(settings.base_url).rstrip("/") == "http://127.0.0.1:8000"


def test_base_url_must_be_an_origin_without_path() -> None:
    with pytest.raises(ValueError, match="origin"):
        McpSettings(
            environment="production",
            base_url="https://erp.example.test/api",
            credential_service="LSS ERP MCP",
            credential_name="lss-erp-mcp-local",
        )


def test_base_url_must_not_contain_credentials() -> None:
    with pytest.raises(ValueError, match="credential-free"):
        McpSettings(
            environment="production",
            base_url="https://user:pass@erp.example.test",
            credential_service="LSS ERP MCP",
            credential_name="lss-erp-mcp-local",
        )
