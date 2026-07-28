from __future__ import annotations

from datetime import date
from ipaddress import ip_address
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LSS_ERP_",
        extra="forbid",
        case_sensitive=False,
    )

    environment: str = "production"
    base_url: AnyHttpUrl
    credential_service: str = "LSS ERP MCP"
    credential_name: str = "lss-erp-mcp-local"
    allow_env_token: bool = False
    connect_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    read_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    write_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    pool_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    max_response_bytes: int = Field(default=65536, ge=1024, le=1048576)
    real_api_week_start: date | None = None
    real_api_test_project_id: int | None = None
    real_api_test_work_type: str | None = None
    canary_write: bool = False
    schedule_canary_write: bool = False

    @field_validator("schedule_canary_write", mode="before")
    @classmethod
    def require_exact_schedule_write_gate(cls, value: object) -> object:
        if isinstance(value, bool):
            return value
        if value == "true":
            return True
        if value == "false":
            return False
        raise ValueError(
            "schedule canary write requires exact lowercase true or false"
        )

    @model_validator(mode="after")
    def validate_origin(self) -> "McpSettings":
        parsed = urlsplit(str(self.base_url))
        if parsed.username or parsed.password:
            raise ValueError("base URL must be a credential-free origin")
        if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("base URL must be a credential-free origin")

        environment = self.environment.lower()
        if environment in {"production", "prod", "staging"} and parsed.scheme != "https":
            raise ValueError("production and staging require HTTPS")

        if parsed.scheme == "http":
            host = parsed.hostname or ""
            is_loopback = host == "localhost"
            if not is_loopback:
                try:
                    is_loopback = ip_address(host).is_loopback
                except ValueError:
                    is_loopback = False
            if not is_loopback:
                raise ValueError("development HTTP is limited to loopback")
        return self
