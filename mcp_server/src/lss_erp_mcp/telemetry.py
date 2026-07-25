from __future__ import annotations

import json
import logging


_ALLOWED_FIELDS = frozenset(
    {
        "operation",
        "correlation_id",
        "http_status",
        "duration_ms",
        "retry_count",
        "result_category",
    }
)


def log_event(logger: logging.Logger, **fields: object) -> None:
    """Log operational metadata while discarding secrets and business content."""
    safe_fields = {
        name: value
        for name, value in fields.items()
        if name in _ALLOWED_FIELDS and value is not None
    }
    logger.info(json.dumps(safe_fields, ensure_ascii=False, sort_keys=True))
