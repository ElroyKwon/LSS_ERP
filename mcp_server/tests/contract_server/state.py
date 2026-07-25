from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ContractState:
    user_id: int = 10
    employee_id: int = 25
    employee_code: str = "E0010"
    labor_type: str = "원가"
    scopes: set[str] = field(
        default_factory=lambda: {
            "mcp:discover",
            "timesheet:read:self",
            "timesheet:write:self:draft",
        }
    )
    week_start: date = date(2026, 7, 20)
    status: str = "작성중"
    version: int = 3
    version_increment: int = 1
    entries: list[dict[str, object]] = field(default_factory=list)
    projects: list[dict[str, object]] = field(
        default_factory=lambda: [
            {
                "project_id": 123,
                "project_code": "P-2026-001",
                "project_name": "MCP 개발",
                "project_source": "실행",
                "spg": "에너지",
                "active": True,
            }
        ]
    )
    idempotency: dict[str, tuple[str, dict[str, object]]] = field(
        default_factory=dict
    )
    post_count: int = 0
    readback_entries_override: list[dict[str, object]] | None = None
    forced_error_status: int | None = None
    forced_error_code: str = "forced_error"
    forced_error_retryable: bool = False
