"""Read-only schedule preparation over the strict Task 7 REST client.

Preparation never calls a schedule write method. It returns bounded,
content-redacted evidence and issues a local confirmation only when the
backend preflight and independent current read are coherent.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import cast
from typing import Callable

from pydantic import ValidationError

from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schedule_confirmation import (
    ScheduleConfirmation,
    ScheduleConfirmationStore,
    hash_schedule_proposal,
)
from lss_erp_mcp.schemas.schedule import (
    ScheduleAllDayProposal,
    ScheduleDetail,
    ScheduleMutationRequest,
    SchedulePreflightData,
    SchedulePreflightRequest,
    ScheduleProjection,
    ScheduleTimedProposal,
)


MAX_PREPARE_WEEKS = 64
_DRAFT_STATUS = "작성중"
_UNVERIFIED_WRITE_FIELDS = {
    "content",
    "type",
    "timesheet_project_id",
    "timesheet_project_name",
    "timesheet_project_source",
}
_CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_EVENT_ID_RE = re.compile(r"^[0-9a-v]{8,255}$")
_ETAG_RE = re.compile(r'^"[A-Za-z0-9._:-]{1,253}"$')


class SchedulePrepareError(ValueError):
    """Machine-safe local request validation failure."""


def _normalized_mutation(proposal: object) -> ScheduleMutationRequest:
    try:
        return ScheduleMutationRequest.model_validate(proposal)
    except ValidationError:
        raise SchedulePrepareError("invalid_schedule_proposal") from None


def _preflight_request(**values: object) -> SchedulePreflightRequest:
    try:
        return SchedulePreflightRequest.model_validate(values)
    except ValidationError:
        raise SchedulePrepareError("invalid_schedule_request") from None


def _desired_from_mutation(
    request: ScheduleMutationRequest,
) -> ScheduleAllDayProposal | ScheduleTimedProposal:
    if request.is_all_day:
        return ScheduleAllDayProposal(
            is_all_day=True,
            date=request.date,
            end_date=request.end_date,
            content=request.content,
        )
    return ScheduleTimedProposal(
        is_all_day=False,
        start_time=request.start_time,
        end_time=request.end_time,
        content=request.content,
    )


def _safe_item(item: object | None) -> dict[str, object] | None:
    """Return the bounded, non-content schedule projection for presentation."""
    if item is None:
        return None
    result: dict[str, object] = {
        "event_id": getattr(item, "event_id"),
        "category": getattr(item, "category"),
        "is_all_day": getattr(item, "is_all_day"),
        "schedule_kind": getattr(item, "schedule_kind"),
    }
    if getattr(item, "is_all_day"):
        result.update(
            {
                "start_date": getattr(item, "start_date").isoformat(),
                "end_date": getattr(item, "end_date").isoformat(),
            }
        )
    else:
        result.update(
            {
                "start_time": getattr(item, "start_time").isoformat(),
                "end_time": getattr(item, "end_time").isoformat(),
            }
        )
    return result


def _safe_after(
    request: ScheduleMutationRequest,
    projection: ScheduleProjection,
) -> dict[str, object]:
    result: dict[str, object] = {
        "category": request.category,
        "is_all_day": projection.is_all_day,
        "schedule_kind": request.schedule_kind,
    }
    if projection.is_all_day:
        result.update(
            {
                "start_date": projection.start_date.isoformat(),
                "end_date": projection.end_date.isoformat(),
            }
        )
    else:
        result.update(
            {
                "start_time": projection.start_time.isoformat(),
                "end_time": projection.end_time.isoformat(),
            }
        )
    return result


def _changed_fields(
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> list[str]:
    keys = set((before or {}).keys()) | set((after or {}).keys())
    return sorted(
        key
        for key in keys
        if (before or {}).get(key) != (after or {}).get(key)
    )


def _impact(
    *,
    action: str,
    normalized_proposal: dict[str, object],
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> dict[str, object]:
    if action == "DELETE":
        requested_write_fields = [
            "category",
            "event_id",
            "expected_etag",
        ]
    else:
        requested_write_fields = sorted(normalized_proposal)
    unverified_requested_fields = sorted(
        _UNVERIFIED_WRITE_FIELDS.intersection(requested_write_fields)
    )
    return {
        "kind": action.lower(),
        "visible_changed_fields": _changed_fields(before, after),
        "requested_write_fields": requested_write_fields,
        "unverified_requested_fields": unverified_requested_fields,
        "comparison_complete": not unverified_requested_fields,
    }


def _preflight_is_coherent(
    detail: ScheduleDetail,
    result: SchedulePreflightData,
) -> bool:
    owner_reasons = [
        reason
        for reason in result.denial_reasons
        if reason in {"legacy_owner_unbound", "owner_mismatch"}
    ]
    return (
        _safe_item(detail) == _safe_item(result.current)
        and detail.etag == result.etag
        and detail.owner_binding == result.owner_binding
        and detail.eligibility.denial_reasons == owner_reasons
    )


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _finish_prepare(
    store: ScheduleConfirmationStore,
    *,
    user_id: int,
    request: SchedulePreflightRequest,
    result: SchedulePreflightData,
    normalized_proposal: dict[str, object],
    coherent: bool,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> dict[str, object]:
    statuses = [
        {
            "week_start": item.week_start.isoformat(),
            "status": item.status,
        }
        for item in result.timesheet_statuses
    ]
    affected_weeks = [item.isoformat() for item in result.affected_weeks]
    locked_weeks = [
        item for item in statuses if item["status"] != _DRAFT_STATUS
    ]
    denial_reasons = list(result.denial_reasons)
    if not coherent:
        denial_reasons.append("preflight_state_changed")
    if (
        len(affected_weeks) > MAX_PREPARE_WEEKS
        or len(statuses) > MAX_PREPARE_WEEKS
    ):
        denial_reasons.append("preflight_evidence_too_large")
    denial_reasons = _dedupe(denial_reasons)
    can_commit = result.write_allowed and coherent and not denial_reasons

    proposal_hash = hash_schedule_proposal(normalized_proposal)
    confirmation_token = None
    if can_commit:
        confirmation_token = store.put(
            user_id=user_id,
            action=request.action,
            category=request.category,
            event_id=request.event_id,
            expected_etag=result.etag,
            proposal=normalized_proposal,
        )

    return {
        "action": request.action,
        "category": request.category,
        "event_id": request.event_id,
        "before": before,
        "after": after,
        "impact": _impact(
            action=request.action,
            normalized_proposal=normalized_proposal,
            before=before,
            after=after,
        ),
        "affected_weeks": affected_weeks[:MAX_PREPARE_WEEKS],
        "locked_weeks": locked_weeks[:MAX_PREPARE_WEEKS],
        "timesheet_statuses": statuses[:MAX_PREPARE_WEEKS],
        "expected_etag": result.etag,
        "denial_reasons": denial_reasons,
        "can_commit": can_commit,
        "proposal_hash": proposal_hash,
        "confirmation_token": confirmation_token,
    }


async def prepare_create(
    client: ERPClient,
    store: ScheduleConfirmationStore,
    *,
    proposal: dict[str, object],
) -> dict[str, object]:
    mutation = _normalized_mutation(proposal)
    desired = _desired_from_mutation(mutation)
    request = _preflight_request(
        action="CREATE",
        category=mutation.category,
        desired=desired,
    )
    normalized = mutation.model_dump(mode="json", exclude_none=True)
    user = await client.get_current_user()
    result = await client.preflight_schedule(request)
    return _finish_prepare(
        store,
        user_id=user.user_id,
        request=request,
        result=result,
        normalized_proposal=normalized,
        coherent=True,
        before=None,
        after=_safe_after(mutation, cast(ScheduleProjection, result.desired)),
    )


async def prepare_update(
    client: ERPClient,
    store: ScheduleConfirmationStore,
    *,
    event_id: str,
    proposal: dict[str, object],
) -> dict[str, object]:
    mutation = _normalized_mutation(proposal)
    desired = _desired_from_mutation(mutation)
    request = _preflight_request(
        action="UPDATE",
        category=mutation.category,
        event_id=event_id,
        desired=desired,
    )
    normalized = mutation.model_dump(mode="json", exclude_none=True)
    user = await client.get_current_user()
    detail = await client.get_schedule(event_id, category=mutation.category)
    result = await client.preflight_schedule(request)
    after = _safe_after(mutation, cast(ScheduleProjection, result.desired))
    after["event_id"] = event_id
    return _finish_prepare(
        store,
        user_id=user.user_id,
        request=request,
        result=result,
        normalized_proposal=normalized,
        coherent=_preflight_is_coherent(detail, result),
        before=_safe_item(detail),
        after=after,
    )


async def prepare_delete(
    client: ERPClient,
    store: ScheduleConfirmationStore,
    *,
    event_id: str,
    category: str,
) -> dict[str, object]:
    request = _preflight_request(
        action="DELETE",
        category=category,
        event_id=event_id,
    )
    user = await client.get_current_user()
    detail = await client.get_schedule(event_id, category=request.category)
    result = await client.preflight_schedule(request)
    return _finish_prepare(
        store,
        user_id=user.user_id,
        request=request,
        result=result,
        normalized_proposal={},
        coherent=_preflight_is_coherent(detail, result),
        before=_safe_item(detail),
        after=None,
    )


def _validated_commit_request(
    confirmation: ScheduleConfirmation,
) -> ScheduleMutationRequest | None:
    if confirmation.action != "CREATE" and (
        confirmation.event_id is None
        or not _EVENT_ID_RE.fullmatch(confirmation.event_id)
        or confirmation.expected_etag is None
        or not _ETAG_RE.fullmatch(confirmation.expected_etag)
    ):
        raise SchedulePrepareError("invalid_schedule_confirmation")
    if confirmation.action == "DELETE":
        if confirmation.proposal:
            raise SchedulePrepareError("invalid_schedule_proposal")
        return None
    mutation = _normalized_mutation(confirmation.proposal)
    if mutation.category != confirmation.category:
        raise SchedulePrepareError("invalid_schedule_proposal")
    return mutation


def _new_correlation_id(factory: Callable[[], str]) -> str:
    value = factory()
    if not isinstance(value, str) or not _CORRELATION_ID_RE.fullmatch(value):
        raise ValueError("invalid_correlation_id")
    return value


def derive_schedule_correlation_id(
    user_id: int,
    idempotency_key: str,
) -> str:
    """Derive the operator-recoverable correlation ID for one user/key pair."""
    if type(user_id) is not int or user_id < 1:
        raise ValueError("invalid_schedule_user_id")
    material = (
        f"lss-erp-schedule-correlation:v1\0{user_id}\0{idempotency_key}"
    ).encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return f"schedule_v1_{digest[:40]}"


def _release_pre_send(
    store: ScheduleConfirmationStore,
    confirmation_token: str,
    lease_id: str,
) -> None:
    try:
        store.release(confirmation_token, lease_id)
    except Exception:
        # Do not expose store internals. A failed release leaves the owner
        # lease fail-closed, so another caller cannot start a write.
        raise SchedulePrepareError("confirmation_release_failed") from None


def _consume_after_write_entry(
    store: ScheduleConfirmationStore,
    confirmation_token: str,
    lease_id: str,
) -> str:
    try:
        store.consume(confirmation_token, lease_id)
    except Exception:
        # The matching lease remains in-flight when finalization cannot be
        # proven. This is intentionally fail-closed and prevents replay.
        return "INFLIGHT_FAIL_CLOSED"
    return "CONSUMED"


def _reconciliation_result(
    *,
    action: str,
    event_id: str | None,
    correlation_id: str,
    idempotency_key: str,
    error_code: str,
    confirmation_finalization: str,
) -> dict[str, object]:
    return {
        "status": "RECONCILIATION_REQUIRED",
        "action": action,
        "event_id": event_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "replayed": False,
        "write_applied": None,
        "reconciliation_required": True,
        "error_code": error_code,
        "confirmation_finalization": confirmation_finalization,
    }


async def commit_schedule(
    client: ERPClient,
    store: ScheduleConfirmationStore,
    *,
    write_enabled: bool,
    confirmation_token: str,
    idempotency_key: str,
    correlation_id_factory: Callable[[], str] | None = None,
) -> dict[str, object]:
    """Send one confirmed mutation without retrying an uncertain outcome.

    The local owner lease is released only while the write is known not to
    have been called. Once a typed write method is entered, success and
    uncertainty both consume the confirmation so a second tool call cannot
    turn status reconciliation into an accidental forward retry.
    """
    if not write_enabled:
        raise PermissionError("schedule commit tool is disabled")

    confirmation = store.get(confirmation_token)
    user = await client.get_current_user()
    lease = store.claim(
        confirmation_token,
        idempotency_key,
        user_id=user.user_id,
        action=confirmation.action,
        category=confirmation.category,
        event_id=confirmation.event_id,
        expected_etag=confirmation.expected_etag,
        proposal=confirmation.proposal,
    )

    try:
        mutation = _validated_commit_request(lease.confirmation)
        correlation_id = _new_correlation_id(
            correlation_id_factory
            or (
                lambda: derive_schedule_correlation_id(
                    user.user_id,
                    idempotency_key,
                )
            )
        )
    except (ValueError, ValidationError):
        _release_pre_send(store, confirmation_token, lease.lease_id)
        raise

    try:
        if lease.confirmation.action == "CREATE":
            if mutation is None:
                raise AssertionError("CREATE mutation unexpectedly absent")
            write_result = await client.create_schedule(
                mutation,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            event_id = write_result.event_id
        elif lease.confirmation.action == "UPDATE":
            if mutation is None or lease.confirmation.event_id is None:
                raise AssertionError("UPDATE binding unexpectedly incomplete")
            if lease.confirmation.expected_etag is None:
                raise AssertionError("UPDATE etag unexpectedly absent")
            write_result = await client.update_schedule(
                lease.confirmation.event_id,
                mutation,
                etag=lease.confirmation.expected_etag,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            event_id = write_result.event_id
        else:
            if lease.confirmation.event_id is None:
                raise AssertionError("DELETE target unexpectedly absent")
            if lease.confirmation.expected_etag is None:
                raise AssertionError("DELETE etag unexpectedly absent")
            await client.delete_schedule(
                lease.confirmation.event_id,
                category=lease.confirmation.category,
                etag=lease.confirmation.expected_etag,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            event_id = lease.confirmation.event_id
    except asyncio.CancelledError:
        # The typed write boundary has been entered. Finalize fail-closed and
        # preserve task-cancellation semantics.
        _consume_after_write_entry(
            store,
            confirmation_token,
            lease.lease_id,
        )
        raise
    except ERPError as exc:
        # A transport failure after entering the typed client cannot prove
        # whether the backend accepted the operation. Never retry here.
        finalization = _consume_after_write_entry(
            store,
            confirmation_token,
            lease.lease_id,
        )
        return _reconciliation_result(
            action=lease.confirmation.action,
            event_id=lease.confirmation.event_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            error_code=exc.code,
            confirmation_finalization=finalization,
        )
    except Exception:
        # ValueError and every other unexpected exception after typed write
        # entry are potentially post-send. Never release for forward replay.
        finalization = _consume_after_write_entry(
            store,
            confirmation_token,
            lease.lease_id,
        )
        return _reconciliation_result(
            action=lease.confirmation.action,
            event_id=lease.confirmation.event_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            error_code="unexpected_schedule_write_failure",
            confirmation_finalization=finalization,
        )
    except BaseException:
        # Preserve process-level exceptions while making the local capability
        # non-replayable whenever possible.
        _consume_after_write_entry(
            store,
            confirmation_token,
            lease.lease_id,
        )
        raise

    finalization = _consume_after_write_entry(
        store,
        confirmation_token,
        lease.lease_id,
    )
    return {
        "status": "SUCCEEDED",
        "action": lease.confirmation.action,
        "event_id": event_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "replayed": False,
        "write_applied": True,
        "reconciliation_required": False,
        "confirmation_finalization": finalization,
    }


async def get_operation_status(
    client: ERPClient,
    correlation_id: str,
) -> dict[str, object]:
    """Fetch the backend journal result; this function never retries a write."""
    result = await client.get_schedule_operation(correlation_id)
    return result.model_dump(mode="json")
