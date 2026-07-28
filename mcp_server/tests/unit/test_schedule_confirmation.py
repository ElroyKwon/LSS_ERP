from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from lss_erp_mcp.schedule_confirmation import (
    ScheduleConfirmationStore,
    ScheduleConfirmationUnavailable,
)


NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
EVENT_ID = "abcde123"
ETAG = '"etag-1"'


def proposal(*, content: str = "private meeting") -> dict[str, object]:
    return {
        "content": content,
        "type": "#123456",
        "category": "company",
        "is_all_day": True,
        "date": "2026-07-28",
        "end_date": "2026-07-28",
        "schedule_kind": "project",
    }


def put_update(
    store: ScheduleConfirmationStore,
    *,
    value: dict[str, object] | None = None,
) -> str:
    return store.put(
        user_id=7,
        action="UPDATE",
        category="company",
        event_id=EVENT_ID,
        expected_etag=ETAG,
        proposal=value or proposal(),
    )


def claim_update(
    store: ScheduleConfirmationStore,
    token: str,
    *,
    idempotency_key: str = "idem-key-0001",
    user_id: int = 7,
    action: str = "UPDATE",
    category: str = "company",
    event_id: str | None = EVENT_ID,
    expected_etag: str | None = ETAG,
    value: dict[str, object] | None = None,
):
    return store.claim(
        token,
        idempotency_key,
        user_id=user_id,
        action=action,
        category=category,
        event_id=event_id,
        expected_etag=expected_etag,
        proposal=value or proposal(),
    )


def test_confirmation_binds_all_authority_fields_and_one_key() -> None:
    store = ScheduleConfirmationStore(
        clock=lambda: NOW,
        token_factory=lambda: "a" * 43,
        lease_factory=lambda: "l" * 43,
    )
    token = put_update(store)

    lease = claim_update(store, token)
    item = lease.confirmation

    assert token == "a" * 43
    assert lease.lease_id == "l" * 43
    assert item.user_id == 7
    assert item.action == "UPDATE"
    assert item.category == "company"
    assert item.event_id == EVENT_ID
    assert item.expected_etag == ETAG
    assert item.proposal == proposal()
    assert len(item.proposal_hash) == 64
    assert item.expires_at == NOW + timedelta(minutes=10)


def test_expired_confirmation_is_removed() -> None:
    now = [NOW]
    store = ScheduleConfirmationStore(clock=lambda: now[0])
    token = put_update(store)
    now[0] += timedelta(minutes=10)

    with pytest.raises(ScheduleConfirmationUnavailable, match="unavailable"):
        store.get(token)
    with pytest.raises(ScheduleConfirmationUnavailable, match="unavailable"):
        store.get(token)


@pytest.mark.parametrize("tampered_value", ["tampered", object()])
def test_tampered_stored_proposal_fails_integrity_and_is_removed(
    tampered_value: object,
) -> None:
    store = ScheduleConfirmationStore(clock=lambda: NOW)
    token = put_update(store)
    store._items[token].proposal["content"] = tampered_value

    with pytest.raises(ScheduleConfirmationUnavailable, match="integrity"):
        store.get(token)
    with pytest.raises(ScheduleConfirmationUnavailable, match="unavailable"):
        store.get(token)


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("user_id", 8),
        ("action", "DELETE"),
        ("category", "refresh"),
        ("event_id", "fffff123"),
        ("expected_etag", '"etag-2"'),
        ("value", proposal(content="changed")),
    ],
)
def test_claim_rejects_cross_binding_or_changed_proposal(
    override: str,
    value: object,
) -> None:
    store = ScheduleConfirmationStore(clock=lambda: NOW)
    token = put_update(store)
    kwargs = {override: value}

    with pytest.raises(ScheduleConfirmationUnavailable, match="mismatch"):
        claim_update(store, token, **kwargs)

    # A mismatched attempt cannot poison the authorized idempotency binding.
    lease = claim_update(store, token, idempotency_key="idem-key-authorized")
    assert lease.confirmation.user_id == 7


def test_claim_is_single_inflight_even_with_concurrent_callers() -> None:
    store = ScheduleConfirmationStore(clock=lambda: NOW)
    token = put_update(store)

    def attempt() -> str:
        try:
            claim_update(store, token)
        except ScheduleConfirmationUnavailable as exc:
            return str(exc)
        return "claimed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: attempt(), range(2)))

    assert sorted(results) == [
        "claimed",
        "confirmation_commit_in_progress",
    ]


def test_release_allows_same_key_but_not_a_different_key() -> None:
    lease_ids = iter(["l" * 43, "m" * 43])
    store = ScheduleConfirmationStore(
        clock=lambda: NOW,
        lease_factory=lambda: next(lease_ids),
    )
    token = put_update(store)
    first = claim_update(store, token)
    store.release(token, first.lease_id)

    second = claim_update(store, token)
    assert second.confirmation.event_id == EVENT_ID
    store.release(token, second.lease_id)
    with pytest.raises(ScheduleConfirmationUnavailable, match="idempotency"):
        claim_update(store, token, idempotency_key="idem-key-0002")


def test_consume_is_one_time_and_clears_claim_state() -> None:
    store = ScheduleConfirmationStore(clock=lambda: NOW)
    token = put_update(store)
    lease = claim_update(store, token)
    store.consume(token, lease.lease_id)

    with pytest.raises(ScheduleConfirmationUnavailable, match="unavailable"):
        store.get(token)


def test_put_get_and_claim_use_defensive_proposal_copies() -> None:
    store = ScheduleConfirmationStore(clock=lambda: NOW)
    source = proposal()
    token = put_update(store, value=source)
    source["content"] = "caller mutation"

    first = store.get(token)
    first.proposal["content"] = "returned mutation"
    second = claim_update(store, token).confirmation

    assert second.proposal["content"] == "private meeting"


@pytest.mark.parametrize(
    "idempotency_key",
    [
        "",
        "short",
        "x" * 129,
        "../abcde",
        7,
        True,
    ],
)
def test_invalid_idempotency_key_cannot_bind_or_claim(
    idempotency_key: object,
) -> None:
    store = ScheduleConfirmationStore(clock=lambda: NOW)
    token = put_update(store)

    with pytest.raises(ValueError, match="invalid_idempotency_key"):
        claim_update(store, token, idempotency_key=idempotency_key)

    assert store._idempotency_bindings == {}
    assert store._inflight == {}
    lease = claim_update(store, token, idempotency_key="valid-key-0001")
    assert lease.confirmation.user_id == 7


def test_only_matching_lease_can_release_or_consume_claim() -> None:
    lease_ids = iter(["l" * 43, "m" * 43])
    store = ScheduleConfirmationStore(
        clock=lambda: NOW,
        lease_factory=lambda: next(lease_ids),
    )
    token = put_update(store)
    first = claim_update(store, token)

    for wrong_lease in (None, "w" * 43):
        with pytest.raises(
            ScheduleConfirmationUnavailable,
            match="lease mismatch",
        ):
            store.release(token, wrong_lease)
        with pytest.raises(
            ScheduleConfirmationUnavailable,
            match="lease mismatch",
        ):
            store.consume(token, wrong_lease)
    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="confirmation_commit_in_progress",
    ):
        claim_update(store, token)

    store.release(token, first.lease_id)
    second = claim_update(store, token)
    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="lease mismatch",
    ):
        store.release(token, first.lease_id)
    with pytest.raises(ScheduleConfirmationUnavailable, match="idempotency"):
        claim_update(store, token, idempotency_key="other-key-0001")

    store.consume(token, second.lease_id)
    with pytest.raises(ScheduleConfirmationUnavailable, match="unavailable"):
        store.get(token)


def test_claim_lease_uses_defensive_confirmation_copy() -> None:
    store = ScheduleConfirmationStore(clock=lambda: NOW)
    token = put_update(store)

    lease = claim_update(store, token)
    lease.confirmation.proposal["content"] = "lease caller mutation"

    assert store.get(token).proposal["content"] == "private meeting"


def test_bad_or_colliding_generated_lease_fails_closed() -> None:
    invalid = ScheduleConfirmationStore(
        clock=lambda: NOW,
        lease_factory=lambda: "bad lease",
    )
    invalid_token = put_update(invalid)
    with pytest.raises(RuntimeError, match="secure confirmation lease"):
        claim_update(invalid, invalid_token)
    assert invalid._idempotency_bindings == {}
    assert invalid._inflight == {}

    colliding = ScheduleConfirmationStore(
        clock=lambda: NOW,
        lease_factory=lambda: "l" * 43,
    )
    first_token = put_update(colliding)
    second_token = put_update(colliding, value=proposal(content="second"))
    claim_update(colliding, first_token)
    with pytest.raises(RuntimeError, match="secure confirmation lease"):
        claim_update(
            colliding,
            second_token,
            value=proposal(content="second"),
        )


def test_lease_history_has_a_per_confirmation_capacity() -> None:
    lease_ids = iter(["l" * 43, "m" * 43])
    store = ScheduleConfirmationStore(
        clock=lambda: NOW,
        lease_factory=lambda: next(lease_ids),
        max_leases_per_confirmation=1,
    )
    token = put_update(store)
    first = claim_update(store, token)
    store.release(token, first.lease_id)

    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="lease capacity",
    ):
        claim_update(store, token)


def test_expired_active_claim_survives_purge_get_and_claim_until_owner_consumes() -> None:
    now = [NOW]
    store = ScheduleConfirmationStore(
        clock=lambda: now[0],
        ttl=timedelta(seconds=1),
        max_items=1,
    )
    token = put_update(store)
    now[0] += timedelta(milliseconds=900)
    owner = claim_update(store, token)
    bound_key = store._idempotency_bindings[token]
    now[0] += timedelta(milliseconds=100)

    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="^confirmation_commit_in_progress$",
    ):
        store.get(token)
    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="^confirmation_commit_in_progress$",
    ):
        claim_update(store, token)
    with pytest.raises(
        ScheduleConfirmationUnavailable,
        match="capacity",
    ):
        put_update(store, value=proposal(content="unrelated"))

    for wrong_lease in (None, "w" * 43):
        with pytest.raises(
            ScheduleConfirmationUnavailable,
            match="lease mismatch",
        ):
            store.release(token, wrong_lease)
        with pytest.raises(
            ScheduleConfirmationUnavailable,
            match="lease mismatch",
        ):
            store.consume(token, wrong_lease)
    assert store._items[token].proposal["content"] == "private meeting"
    assert store._idempotency_bindings[token] == bound_key
    assert store._inflight[token] == owner.lease_id

    store.consume(token, owner.lease_id)

    assert store._items == {}
    assert store._idempotency_bindings == {}
    assert store._inflight == {}
    assert store._lease_history == {}


def test_owner_release_after_ttl_cleans_expired_claim_and_stale_lease_cannot() -> None:
    now = [NOW]
    lease_ids = iter(["l" * 43, "m" * 43])
    store = ScheduleConfirmationStore(
        clock=lambda: now[0],
        ttl=timedelta(seconds=1),
        lease_factory=lambda: next(lease_ids),
    )
    token = put_update(store)
    first = claim_update(store, token)
    store.release(token, first.lease_id)
    owner = claim_update(store, token)
    now[0] += timedelta(seconds=1)

    for stale_lease in (None, first.lease_id, "w" * 43):
        with pytest.raises(
            ScheduleConfirmationUnavailable,
            match="lease mismatch",
        ):
            store.release(token, stale_lease)
        with pytest.raises(
            ScheduleConfirmationUnavailable,
            match="lease mismatch",
        ):
            store.consume(token, stale_lease)
    assert store._inflight[token] == owner.lease_id

    store.release(token, owner.lease_id)

    assert token not in store._items
    assert token not in store._idempotency_bindings
    assert token not in store._inflight
    assert token not in store._lease_history
    with pytest.raises(ScheduleConfirmationUnavailable, match="unavailable"):
        store.get(token)
    with pytest.raises(ScheduleConfirmationUnavailable, match="unavailable"):
        claim_update(store, token)


def test_naive_injected_clock_fails_with_fixed_error() -> None:
    store = ScheduleConfirmationStore(
        clock=lambda: datetime(2026, 7, 27, 12, 0),
    )

    with pytest.raises(
        ValueError,
        match="confirmation_clock_not_timezone_aware",
    ):
        put_update(store)

    assert store._items == {}


def test_store_rejects_invalid_limits_and_bounded_capacity() -> None:
    with pytest.raises(ValueError, match="TTL"):
        ScheduleConfirmationStore(ttl=timedelta(0))
    with pytest.raises(ValueError, match="max_items"):
        ScheduleConfirmationStore(max_items=0)
    with pytest.raises(ValueError, match="max_proposal_bytes"):
        ScheduleConfirmationStore(max_proposal_bytes=0)

    store = ScheduleConfirmationStore(
        clock=lambda: NOW,
        max_items=1,
        max_proposal_bytes=256,
    )
    put_update(store)
    with pytest.raises(ScheduleConfirmationUnavailable, match="capacity"):
        put_update(store)


def test_store_rejects_oversize_proposal_and_bad_generated_token() -> None:
    oversized = proposal(content="x" * 500)
    store = ScheduleConfirmationStore(
        clock=lambda: NOW,
        max_proposal_bytes=128,
    )
    with pytest.raises(ValueError, match="proposal"):
        put_update(store, value=oversized)

    invalid_token_store = ScheduleConfirmationStore(
        clock=lambda: NOW,
        token_factory=lambda: "bad token",
    )
    with pytest.raises(RuntimeError, match="secure confirmation token"):
        put_update(invalid_token_store)


def test_expired_items_are_swept_before_capacity_check() -> None:
    now = [NOW]
    store = ScheduleConfirmationStore(
        clock=lambda: now[0],
        ttl=timedelta(seconds=1),
        max_items=1,
    )
    first = put_update(store)
    now[0] += timedelta(seconds=1)

    second = put_update(store, value=deepcopy(proposal(content="second")))

    assert first != second
    assert store.get(second).proposal["content"] == "second"
