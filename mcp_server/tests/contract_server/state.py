from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ContractState:
    user_id: int = 10
    employee_id: int = 25
    employee_code: str = "E0010"
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
    entries: list[dict[str, object]] = field(default_factory=list)
    idempotency: dict[str, tuple[str, dict[str, object]]] = field(
        default_factory=dict
    )
    post_count: int = 0
