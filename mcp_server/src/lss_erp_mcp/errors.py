from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ERPError(RuntimeError):
    code: str
    message: str
    retryable: bool
    status_code: int | None = None
    correlation_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
