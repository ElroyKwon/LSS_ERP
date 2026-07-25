from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lss_erp_mcp.confirmation import ConfirmationStore, ConfirmationUnavailable


def test_confirmation_expires() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    store = ConfirmationStore(ttl=timedelta(minutes=10), clock=lambda: now)
    token = store.put(
        user_id=10,
        week_start="2026-07-20",
        expected_version=3,
        proposal={"entries": []},
    )
    store.clock = lambda: now + timedelta(minutes=11)
    with pytest.raises(ConfirmationUnavailable):
        store.get(token)


def test_confirmation_detects_proposal_tampering() -> None:
    store = ConfirmationStore()
    token = store.put(
        user_id=10,
        week_start="2026-07-20",
        expected_version=3,
        proposal={"entries": []},
    )
    store._items[token].proposal["entries"].append({"project_id": 999})
    with pytest.raises(ConfirmationUnavailable, match="integrity"):
        store.get(token)


def test_confirmation_get_returns_detached_proposal_copy() -> None:
    store = ConfirmationStore()
    token = store.put(
        user_id=10,
        week_start="2026-07-20",
        expected_version=3,
        proposal={"entries": [{"project_id": 123}]},
    )

    returned = store.get(token)
    returned.proposal["entries"][0]["project_id"] = 999

    assert store.get(token).proposal["entries"][0]["project_id"] == 123


def test_consumed_confirmation_is_unavailable() -> None:
    store = ConfirmationStore()
    token = store.put(
        user_id=10,
        week_start="2026-07-20",
        expected_version=3,
        proposal={"entries": []},
    )
    store.consume(token)
    with pytest.raises(ConfirmationUnavailable):
        store.get(token)
