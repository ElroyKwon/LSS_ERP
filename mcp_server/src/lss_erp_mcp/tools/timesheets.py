from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from lss_erp_mcp.confirmation import ConfirmationStore
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schemas.timesheet import DraftEntry, DraftWriteRequest


async def get_week(client: ERPClient, week_start: str) -> dict[str, object]:
    parsed = date.fromisoformat(week_start)
    return (await client.get_week(parsed)).model_dump(mode="json")


async def search_projects(
    client: ERPClient,
    query: str,
    limit: int = 20,
) -> dict[str, object]:
    return (await client.search_projects(query, limit)).model_dump(mode="json")


def entry_key(entry: dict[str, object]) -> tuple[object, ...]:
    return (
        entry["work_date"],
        entry["project_id"],
        entry["work_type"],
        entry["description"],
    )


def build_diff(
    current: list[dict[str, object]],
    proposed: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    current_map = {entry_key(item): item for item in current}
    proposed_map = {entry_key(item): item for item in proposed}
    added = [
        proposed_map[key] for key in proposed_map.keys() - current_map.keys()
    ]
    removed = [
        current_map[key] for key in current_map.keys() - proposed_map.keys()
    ]
    changed: list[dict[str, object]] = []
    for key in current_map.keys() & proposed_map.keys():
        before = current_map[key]
        after = proposed_map[key]
        if Decimal(str(before["hours"])) != Decimal(str(after["hours"])):
            changed.append({"before": before, "after": after})
    return {
        "added": sorted(added, key=entry_key),
        "changed": sorted(changed, key=lambda item: entry_key(item["after"])),
        "removed": sorted(removed, key=entry_key),
    }


async def prepare_draft(
    client: ERPClient,
    store: ConfirmationStore,
    *,
    week_start: str,
    entries: list[dict[str, object]],
) -> dict[str, object]:
    parsed_week = date.fromisoformat(week_start)
    user = await client.get_current_user()
    current = await client.get_week(parsed_week)
    proposed = [
        DraftEntry.model_validate(item).model_dump(mode="json")
        for item in entries
    ]

    unresolved: list[int] = []
    for project_id in sorted({int(item["project_id"]) for item in proposed}):
        result = await client.search_projects(str(project_id), 20)
        active_ids = {item.project_id for item in result.items if item.active}
        if project_id not in active_ids:
            unresolved.append(project_id)

    diff = build_diff(
        [item.model_dump(mode="json") for item in current.entries],
        proposed,
    )
    daily_total: dict[str, Decimal] = {}
    for item in proposed:
        day = str(item["work_date"])
        daily_total[day] = daily_total.get(day, Decimal("0")) + Decimal(
            str(item["hours"])
        )
    warnings = [
        f"{day} exceeds 24 hours"
        for day, total in sorted(daily_total.items())
        if total > Decimal("24")
    ]

    key_counts = Counter(entry_key(item) for item in proposed)
    for key, count in sorted(key_counts.items()):
        if count > 1:
            warnings.append(
                "duplicate proposed entry: "
                + "/".join(str(component) for component in key)
            )

    can_commit = (
        current.status == "작성중"
        and not unresolved
        and not warnings
    )
    confirmation_token = None
    if can_commit:
        confirmation_token = store.put(
            user_id=user.user_id,
            week_start=week_start,
            expected_version=current.version,
            proposal={"entries": proposed},
        )
    return {
        "week_start": week_start,
        "current_status": current.status,
        "current_version": current.version,
        "diff": diff,
        "unresolved_project_ids": unresolved,
        "warnings": warnings,
        "can_commit": can_commit,
        "confirmation_token": confirmation_token,
    }


async def commit_draft(
    client: ERPClient,
    store: ConfirmationStore,
    *,
    confirmation_token: str,
    idempotency_key: str,
) -> dict[str, object]:
    confirmation = store.get(confirmation_token)
    user = await client.get_current_user()
    if user.user_id != confirmation.user_id:
        raise PermissionError("confirmation user mismatch")

    request = DraftWriteRequest(
        week_start=confirmation.week_start,
        expected_version=confirmation.expected_version,
        entries=confirmation.proposal["entries"],
    )
    parsed_idempotency_key = UUID(idempotency_key)
    correlation_id = uuid4()
    saved = None
    for attempt in range(2):
        try:
            saved = await client.save_draft(
                request,
                idempotency_key=parsed_idempotency_key,
                correlation_id=correlation_id,
            )
            break
        except ERPError as exc:
            if attempt == 0 and exc.code == "upstream_timeout" and exc.retryable:
                continue
            raise
    if saved is None:
        raise RuntimeError("commit did not produce a result")

    persisted = await client.get_week(request.week_start)
    expected_entries = sorted(
        [item.model_dump(mode="json") for item in request.entries],
        key=entry_key,
    )
    actual_entries = sorted(
        [
            {
                key: value
                for key, value in item.model_dump(mode="json").items()
                if key != "entry_id"
            }
            for item in persisted.entries
        ],
        key=entry_key,
    )
    verified = (
        saved.week_start == request.week_start
        and persisted.week_start == request.week_start
        and saved.version == persisted.version
        and saved.status == "작성중"
        and persisted.status == "작성중"
        and expected_entries == actual_entries
    )
    if not verified:
        raise RuntimeError("verification_failed")

    store.consume(confirmation_token)
    return {
        "verified": True,
        "timesheet_id": saved.timesheet_id,
        "version": saved.version,
        "correlation_id": saved.correlation_id,
        "idempotency_replayed": saved.idempotency_replayed,
    }
