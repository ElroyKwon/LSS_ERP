from __future__ import annotations

import os
from typing import Protocol

import keyring

from .config import McpSettings


class KeyringReader(Protocol):
    def get_password(self, service: str, name: str) -> str | None: ...


class CredentialUnavailable(RuntimeError):
    pass


def load_erp_token(
    settings: McpSettings,
    reader: KeyringReader = keyring,
) -> str:
    token = reader.get_password(
        settings.credential_service,
        settings.credential_name,
    )
    if token:
        return token
    if (
        settings.environment.lower() in {"development", "test"}
        and settings.allow_env_token
    ):
        env_token = os.getenv("LSS_ERP_API_TOKEN")
        if env_token:
            return env_token
    raise CredentialUnavailable("ERP API credential is unavailable")
