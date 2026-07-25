from __future__ import annotations

import sys

import pytest

from lss_erp_mcp import credential_cli
from lss_erp_mcp.config import McpSettings
from lss_erp_mcp.credentials import CredentialUnavailable, load_erp_token


class FakeKeyring:
    def __init__(self, value: str | None):
        self.value = value

    def get_password(self, service: str, name: str) -> str | None:
        return self.value


def settings(**overrides) -> McpSettings:
    values = {
        "environment": "production",
        "base_url": "https://erp.example.test",
        "credential_service": "LSS ERP MCP",
        "credential_name": "lss-erp-mcp-local",
    }
    values.update(overrides)
    return McpSettings(**values)


def test_missing_keyring_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LSS_ERP_API_TOKEN", raising=False)
    with pytest.raises(CredentialUnavailable):
        load_erp_token(settings(), FakeKeyring(None))


def test_keyring_token_is_used() -> None:
    assert load_erp_token(settings(), FakeKeyring("secret-token")) == "secret-token"


def test_env_token_is_not_allowed_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LSS_ERP_API_TOKEN", "env-secret")
    with pytest.raises(CredentialUnavailable):
        load_erp_token(settings(allow_env_token=True), FakeKeyring(None))


def test_env_token_requires_explicit_development_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LSS_ERP_API_TOKEN", "env-secret")
    development = settings(
        environment="development",
        base_url="http://127.0.0.1:8000",
        allow_env_token=True,
    )
    assert load_erp_token(development, FakeKeyring(None)) == "env-secret"


def test_credential_set_uses_hidden_prompt_and_never_prints_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stored: list[tuple[str, str, str]] = []
    monkeypatch.setenv("LSS_ERP_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("LSS_ERP_ENVIRONMENT", "development")
    monkeypatch.setattr(sys, "argv", ["lss-erp-mcp-credential", "set"])
    monkeypatch.setattr(
        credential_cli.getpass,
        "getpass",
        lambda _prompt: "hidden-token-value",
    )
    monkeypatch.setattr(
        credential_cli.keyring,
        "set_password",
        lambda service, name, value: stored.append((service, name, value)),
    )

    credential_cli.main()

    captured = capsys.readouterr()
    assert stored == [("LSS ERP MCP", "lss-erp-mcp-local", "hidden-token-value")]
    assert "hidden-token-value" not in captured.out
    assert captured.out.strip() == "Credential stored."
