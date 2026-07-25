from __future__ import annotations

import json
import logging

import pytest

from lss_erp_mcp.telemetry import log_event


def test_telemetry_drops_secret_and_business_content_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "lss_erp_secret_canary"
    with caplog.at_level(logging.INFO):
        log_event(
            logging.getLogger("test"),
            operation="timesheet_get_week",
            result_category="success",
            correlation_id="corr-safe",
            Authorization=f"Bearer {secret}",
            raw_token=secret,
            description=secret,
            worklog=secret,
            vault_path=secret,
        )

    assert secret not in caplog.text
    payload = json.loads(caplog.records[0].message)
    assert payload == {
        "correlation_id": "corr-safe",
        "operation": "timesheet_get_week",
        "result_category": "success",
    }
