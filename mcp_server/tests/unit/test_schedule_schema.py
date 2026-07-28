from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from lss_erp_mcp.schemas.schedule import (
    CorrelationId,
    EventId,
    OwnerBinding,
    ScheduleAllDayDetail,
    ScheduleAllDayItem,
    ScheduleAllDayProposal,
    ScheduleAllDayProjection,
    ScheduleCategory,
    ScheduleConfirmationToken,
    ScheduleEnvelope,
    ScheduleEligibility,
    ScheduleListRequest,
    ScheduleMutationRequest,
    ScheduleOperation,
    ScheduleOperationData,
    ScheduleOperationStatus,
    SchedulePreflightRequest,
    SchedulePreflightData,
    ScheduleTimedItem,
    ScheduleTimedProposal,
    ScheduleTimedProjection,
)


def test_schedule_category_is_an_exact_allowlist() -> None:
    adapter = TypeAdapter(ScheduleCategory)

    assert adapter.validate_python("company") == "company"
    assert adapter.validate_python("refresh") == "refresh"
    with pytest.raises(ValidationError):
        adapter.validate_python("personal")


def test_list_request_has_a_bounded_date_range_and_limit() -> None:
    valid = ScheduleListRequest(
        category="company",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 9, 1),
        limit=100,
    )

    assert valid.limit == 100
    with pytest.raises(ValidationError, match="date range"):
        ScheduleListRequest(
            category="company",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 9, 2),
        )
    with pytest.raises(ValidationError, match="date range"):
        ScheduleListRequest(
            category="company",
            start_date=date(2026, 8, 2),
            end_date=date(2026, 8, 1),
        )
    with pytest.raises(ValidationError, match="limit"):
        ScheduleListRequest(category="company", limit=101)


def test_list_request_allows_either_date_bound_independently() -> None:
    start_only = ScheduleListRequest(
        category="company",
        start_date=date(2026, 8, 1),
    )
    end_only = ScheduleListRequest(
        category="company",
        end_date=date(2026, 8, 31),
    )

    assert start_only.start_date == date(2026, 8, 1)
    assert start_only.end_date is None
    assert end_only.start_date is None
    assert end_only.end_date == date(2026, 8, 31)


def test_all_day_proposal_requires_only_date_fields() -> None:
    proposal = ScheduleAllDayProposal(
        is_all_day=True,
        date=date(2026, 8, 1),
        end_date=date(2026, 9, 1),
        content="bounded proposal text",
    )

    assert proposal.end_date - proposal.date == timedelta(days=31)
    with pytest.raises(ValidationError):
        ScheduleAllDayProposal.model_validate(
            {
                "is_all_day": True,
                "date": "2026-08-01",
                "end_date": "2026-08-01",
                "start_time": "2026-08-01T09:00:00+09:00",
            }
        )
    with pytest.raises(ValidationError, match="date range"):
        ScheduleAllDayProposal(
            is_all_day=True,
            date=date(2026, 8, 1),
            end_date=date(2026, 9, 2),
        )


def test_timed_proposal_requires_only_ordered_timezone_aware_fields() -> None:
    proposal = ScheduleTimedProposal(
        is_all_day=False,
        start_time=datetime(2026, 8, 1, 9, tzinfo=timezone(timedelta(hours=9))),
        end_time=datetime(2026, 8, 1, 17, tzinfo=timezone(timedelta(hours=9))),
    )

    assert proposal.end_time > proposal.start_time
    with pytest.raises(ValidationError):
        ScheduleTimedProposal.model_validate(
            {
                "is_all_day": False,
                "start_time": "2026-08-01T09:00:00+09:00",
                "end_time": "2026-08-01T17:00:00+09:00",
                "date": "2026-08-01",
            }
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        ScheduleTimedProposal(
            is_all_day=False,
            start_time=datetime(2026, 8, 1, 9),
            end_time=datetime(2026, 8, 1, 17),
        )
    with pytest.raises(ValidationError, match="after"):
        ScheduleTimedProposal(
            is_all_day=False,
            start_time=datetime(2026, 8, 1, 17, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    "model,payload,unexpected",
    [
        (
            ScheduleAllDayItem,
            {
                "event_id": "a23456789bcdefg",
                "category": "company",
                "is_all_day": True,
                "schedule_kind": "출장",
                "start_date": "2026-08-01",
                "end_date": "2026-08-01",
            },
            {"start_time": "2026-08-01T09:00:00+09:00"},
        ),
        (
            ScheduleTimedItem,
            {
                "event_id": "a23456789bcdefg",
                "category": "company",
                "is_all_day": False,
                "schedule_kind": "출장",
                "start_time": "2026-08-01T09:00:00+09:00",
                "end_time": "2026-08-01T17:00:00+09:00",
            },
            {"start_date": "2026-08-01"},
        ),
    ],
)
def test_schedule_items_have_exact_time_shapes(model, payload, unexpected) -> None:
    assert model.model_validate(payload).event_id == "a23456789bcdefg"
    with pytest.raises(ValidationError):
        model.model_validate(payload | unexpected)


@pytest.mark.parametrize(
    "value",
    [
        "A23456789bcdefg",
        "a234567w",
        "a234567",
        "a" * 256,
        "../a23456789",
    ],
)
def test_event_id_requires_lower_base32hex_and_bounded_length(value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(EventId).validate_python(value)


def test_action_status_correlation_and_confirmation_are_typed() -> None:
    assert TypeAdapter(ScheduleOperation).validate_python("CREATE") == "CREATE"
    assert (
        TypeAdapter(ScheduleOperationStatus).validate_python("MANUAL_REVIEW")
        == "MANUAL_REVIEW"
    )
    assert TypeAdapter(CorrelationId).validate_python("corr-valid_001") == "corr-valid_001"
    assert (
        TypeAdapter(ScheduleConfirmationToken).validate_python("a" * 32)
        == "a" * 32
    )

    for adapter, invalid in [
        (TypeAdapter(ScheduleOperation), "PATCH"),
        (TypeAdapter(ScheduleOperationStatus), "DONE"),
        (TypeAdapter(CorrelationId), "../corr-id"),
        (TypeAdapter(ScheduleConfirmationToken), "short"),
    ]:
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)


def test_preflight_action_fields_and_extra_fields_are_strict() -> None:
    request = SchedulePreflightRequest(
        action="UPDATE",
        category="company",
        event_id="a23456789bcdefg",
        desired=ScheduleAllDayProposal(
            date=date(2026, 8, 1),
            end_date=date(2026, 8, 1),
        ),
    )

    assert request.action == "UPDATE"
    with pytest.raises(ValidationError, match="event_id"):
        SchedulePreflightRequest(
            action="CREATE",
            category="company",
            event_id="a23456789bcdefg",
            desired=request.desired,
        )
    with pytest.raises(ValidationError, match="event_id"):
        SchedulePreflightRequest(
            action="UPDATE",
            category="company",
            desired=request.desired,
        )
    with pytest.raises(ValidationError, match="desired"):
        SchedulePreflightRequest(
            action="DELETE",
            category="company",
            event_id="a23456789bcdefg",
            desired=request.desired,
        )
    with pytest.raises(ValidationError):
        SchedulePreflightRequest.model_validate(
            {
                "action": "CREATE",
                "category": "company",
                "desired": {
                    "is_all_day": True,
                    "date": "2026-08-01",
                    "end_date": "2026-08-01",
                },
                "user_id": 999,
            }
        )


@pytest.mark.parametrize(
    "model,payload",
    [
        (
            ScheduleListRequest,
            {"category": "company", "limit": "10"},
        ),
        (
            ScheduleAllDayProposal,
            {
                "is_all_day": 1,
                "date": date(2026, 8, 1),
                "end_date": date(2026, 8, 1),
            },
        ),
        (
            ScheduleTimedProposal,
            {
                "is_all_day": 0,
                "start_time": datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
                "end_time": datetime(2026, 8, 1, 17, tzinfo=timezone.utc),
            },
        ),
        (
            ScheduleMutationRequest,
            {
                "content": "Customer visit",
                "type": "#722ed1",
                "category": "company",
                "is_all_day": 1,
                "date": date(2026, 8, 1),
                "end_date": date(2026, 8, 1),
            },
        ),
        (
            ScheduleMutationRequest,
            {
                "content": "Customer visit",
                "type": "#722ed1",
                "category": "company",
                "is_all_day": True,
                "date": date(2026, 8, 1),
                "end_date": date(2026, 8, 1),
                "timesheet_project_id": True,
            },
        ),
        (
            ScheduleAllDayItem,
            {
                "event_id": "a23456789bcdefg",
                "category": "company",
                "is_all_day": 1,
                "schedule_kind": "출장",
                "start_date": date(2026, 8, 1),
                "end_date": date(2026, 8, 1),
            },
        ),
    ],
)
def test_security_relevant_scalars_reject_bool_and_integer_coercion(
    model,
    payload,
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def _success_envelope_payload(success: object) -> dict[str, object]:
    return {
        "success": success,
        "data": {},
        "error": None,
        "meta": {
            "correlation_id": "corr-valid_001",
            "timestamp": "2026-07-27T00:00:00Z",
        },
    }


@pytest.mark.parametrize("mode", ["python", "json"])
@pytest.mark.parametrize("invalid", [1, "true"])
def test_schedule_envelope_success_rejects_coerced_truth(
    mode: str,
    invalid: object,
) -> None:
    payload = _success_envelope_payload(invalid)

    with pytest.raises(ValidationError):
        if mode == "python":
            ScheduleEnvelope[dict[str, object]].model_validate(payload)
        else:
            ScheduleEnvelope[dict[str, object]].model_validate_json(
                json.dumps(payload)
            )


@pytest.mark.parametrize("mode", ["python", "json"])
def test_schedule_envelope_success_accepts_exact_true(mode: str) -> None:
    payload = _success_envelope_payload(True)

    if mode == "python":
        result = ScheduleEnvelope[dict[str, object]].model_validate(payload)
    else:
        result = ScheduleEnvelope[dict[str, object]].model_validate_json(
            json.dumps(payload)
        )

    assert result.success is True


@pytest.mark.parametrize(
    "model,payload",
    [
        (
            ScheduleAllDayItem,
            {
                "event_id": "a23456789bcdefg",
                "category": "company",
                "is_all_day": True,
                "schedule_kind": "출장",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        ),
        (
            ScheduleTimedItem,
            {
                "event_id": "a23456789bcdefg",
                "category": "company",
                "is_all_day": False,
                "schedule_kind": "출장",
                "start_time": "2026-01-01T09:00:00+09:00",
                "end_time": "2026-03-31T17:00:00+09:00",
            },
        ),
        (
            ScheduleAllDayProjection,
            {
                "is_all_day": True,
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        ),
        (
            ScheduleTimedProjection,
            {
                "is_all_day": False,
                "start_time": "2026-01-01T09:00:00+09:00",
                "end_time": "2026-03-31T17:00:00+09:00",
            },
        ),
    ],
)
def test_legacy_response_ranges_may_exceed_write_window(model, payload) -> None:
    assert model.model_validate(payload).is_all_day is payload["is_all_day"]


def _preflight_payload(action: str) -> dict[str, object]:
    current = {
        "event_id": "a23456789bcdefg",
        "category": "company",
        "is_all_day": True,
        "schedule_kind": "출장",
        "start_date": "2026-08-03",
        "end_date": "2026-08-03",
    }
    desired = {
        "is_all_day": True,
        "start_date": "2026-08-10",
        "end_date": "2026-08-10",
    }
    return {
        "action": action,
        "category": "company",
        "event_id": None if action == "CREATE" else "a23456789bcdefg",
        "current": None if action == "CREATE" else current,
        "desired": None if action == "DELETE" else desired,
        "owner_binding": {
            "state": "NOT_APPLICABLE" if action == "CREATE" else "BOUND",
            "write_allowed": True,
        },
        "affected_weeks": ["2026-08-03"],
        "timesheet_statuses": [],
        "etag": None if action == "CREATE" else '"etag-safe"',
        "write_allowed": True,
        "denial_reasons": [],
    }


@pytest.mark.parametrize(
    "state,write_allowed",
    [
        ("BOUND", True),
        ("NOT_APPLICABLE", True),
        ("LEGACY_OWNER_UNBOUND", False),
        ("OWNER_MISMATCH", False),
    ],
)
def test_owner_binding_accepts_only_the_backend_authority_mapping(
    state: str,
    write_allowed: bool,
) -> None:
    binding = OwnerBinding.model_validate(
        {"state": state, "write_allowed": write_allowed}
    )

    assert binding.write_allowed is write_allowed


@pytest.mark.parametrize(
    "state,write_allowed",
    [
        ("BOUND", False),
        ("NOT_APPLICABLE", False),
        ("LEGACY_OWNER_UNBOUND", True),
        ("OWNER_MISMATCH", True),
    ],
)
def test_owner_binding_rejects_contradictory_write_authority(
    state: str,
    write_allowed: bool,
) -> None:
    with pytest.raises(ValidationError):
        OwnerBinding.model_validate(
            {"state": state, "write_allowed": write_allowed}
        )


def _detail_payload(
    state: str = "BOUND",
    *,
    owner_write_allowed: bool = True,
    eligibility_write_allowed: bool = True,
    denial_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "event_id": "a23456789bcdefg",
        "category": "company",
        "is_all_day": True,
        "schedule_kind": "출장",
        "start_date": "2026-08-03",
        "end_date": "2026-08-03",
        "etag": '"etag-safe"',
        "owner_binding": {
            "state": state,
            "write_allowed": owner_write_allowed,
        },
        "eligibility": {
            "write_allowed": eligibility_write_allowed,
            "denial_reasons": denial_reasons or [],
        },
    }


@pytest.mark.parametrize(
    "state,write_allowed,denial_reasons",
    [
        ("BOUND", True, []),
        ("LEGACY_OWNER_UNBOUND", False, ["legacy_owner_unbound"]),
        ("OWNER_MISMATCH", False, ["owner_mismatch"]),
    ],
)
def test_detail_eligibility_exactly_matches_owner_authority(
    state: str,
    write_allowed: bool,
    denial_reasons: list[str],
) -> None:
    detail = ScheduleAllDayDetail.model_validate(
        _detail_payload(
            state,
            owner_write_allowed=write_allowed,
            eligibility_write_allowed=write_allowed,
            denial_reasons=denial_reasons,
        )
    )

    assert detail.eligibility.write_allowed is write_allowed


@pytest.mark.parametrize(
    "payload",
    [
        _detail_payload("NOT_APPLICABLE"),
        _detail_payload(
            "BOUND",
            eligibility_write_allowed=False,
            denial_reasons=["employee_not_found"],
        ),
        _detail_payload(
            "LEGACY_OWNER_UNBOUND",
            owner_write_allowed=False,
            eligibility_write_allowed=False,
            denial_reasons=[],
        ),
        _detail_payload(
            "OWNER_MISMATCH",
            owner_write_allowed=False,
            eligibility_write_allowed=False,
            denial_reasons=["legacy_owner_unbound"],
        ),
    ],
)
def test_detail_rejects_non_authoritative_eligibility(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ScheduleAllDayDetail.model_validate(payload)


@pytest.mark.parametrize(
    "denial_reasons",
    [
        ["unknown_reason"],
        ["timesheet_locked", "timesheet_locked"],
    ],
)
def test_eligibility_reasons_are_bounded_to_unique_backend_codes(
    denial_reasons: list[str],
) -> None:
    with pytest.raises(ValidationError):
        ScheduleEligibility.model_validate(
            {"write_allowed": False, "denial_reasons": denial_reasons}
        )


@pytest.mark.parametrize("action", ["CREATE", "UPDATE", "DELETE"])
def test_preflight_data_accepts_exact_action_shapes(action: str) -> None:
    assert SchedulePreflightData.model_validate(_preflight_payload(action)).action == action


@pytest.mark.parametrize(
    "action,field,value",
    [
        ("CREATE", "event_id", "a23456789bcdefg"),
        ("CREATE", "current", _preflight_payload("UPDATE")["current"]),
        ("CREATE", "etag", '"etag-safe"'),
        ("CREATE", "desired", None),
        ("UPDATE", "event_id", None),
        ("UPDATE", "current", None),
        ("UPDATE", "etag", None),
        ("UPDATE", "desired", None),
        ("DELETE", "event_id", None),
        ("DELETE", "current", None),
        ("DELETE", "etag", None),
        ("DELETE", "desired", _preflight_payload("UPDATE")["desired"]),
    ],
)
def test_preflight_data_rejects_incoherent_action_shapes(
    action: str,
    field: str,
    value: object,
) -> None:
    payload = _preflight_payload(action)
    payload[field] = value

    with pytest.raises(ValidationError):
        SchedulePreflightData.model_validate(payload)


@pytest.mark.parametrize(
    "action,state,owner_write_allowed,denial_reasons,timesheet_statuses",
    [
        ("CREATE", "NOT_APPLICABLE", True, [], []),
        ("CREATE", "NOT_APPLICABLE", True, ["employee_not_found"], []),
        (
            "UPDATE",
            "LEGACY_OWNER_UNBOUND",
            False,
            ["legacy_owner_unbound"],
            [],
        ),
        (
            "DELETE",
            "OWNER_MISMATCH",
            False,
            ["owner_mismatch"],
            [],
        ),
        (
            "UPDATE",
            "BOUND",
            True,
            ["timesheet_locked"],
            [{"week_start": "2026-08-03", "status": "제출"}],
        ),
    ],
)
def test_preflight_accepts_backend_authority_and_lock_evidence(
    action: str,
    state: str,
    owner_write_allowed: bool,
    denial_reasons: list[str],
    timesheet_statuses: list[dict[str, str]],
) -> None:
    payload = _preflight_payload(action)
    payload["owner_binding"] = {
        "state": state,
        "write_allowed": owner_write_allowed,
    }
    payload["denial_reasons"] = denial_reasons
    payload["write_allowed"] = not denial_reasons
    payload["timesheet_statuses"] = timesheet_statuses

    parsed = SchedulePreflightData.model_validate(payload)

    assert parsed.write_allowed is (not denial_reasons)


@pytest.mark.parametrize(
    "action,state,owner_write_allowed,write_allowed,denial_reasons,timesheet_statuses",
    [
        ("CREATE", "BOUND", True, True, [], []),
        ("UPDATE", "NOT_APPLICABLE", True, True, [], []),
        ("UPDATE", "BOUND", True, True, ["employee_not_found"], []),
        ("UPDATE", "BOUND", True, False, [], []),
        ("UPDATE", "LEGACY_OWNER_UNBOUND", False, False, [], []),
        (
            "UPDATE",
            "OWNER_MISMATCH",
            False,
            False,
            ["legacy_owner_unbound"],
            [],
        ),
        (
            "UPDATE",
            "BOUND",
            True,
            True,
            [],
            [{"week_start": "2026-08-03", "status": "제출"}],
        ),
        (
            "UPDATE",
            "BOUND",
            True,
            False,
            ["timesheet_locked"],
            [{"week_start": "2026-08-03", "status": "작성중"}],
        ),
    ],
)
def test_preflight_rejects_contradictory_authority_or_lock_evidence(
    action: str,
    state: str,
    owner_write_allowed: bool,
    write_allowed: bool,
    denial_reasons: list[str],
    timesheet_statuses: list[dict[str, str]],
) -> None:
    payload = _preflight_payload(action)
    payload["owner_binding"] = {
        "state": state,
        "write_allowed": owner_write_allowed,
    }
    payload["write_allowed"] = write_allowed
    payload["denial_reasons"] = denial_reasons
    payload["timesheet_statuses"] = timesheet_statuses

    with pytest.raises(ValidationError):
        SchedulePreflightData.model_validate(payload)


def _operation_payload(status: str) -> dict[str, object]:
    if status == "IN_PROGRESS":
        result: dict[str, object] = {}
        error: dict[str, object] = {}
    elif status == "SUCCEEDED":
        result = {
            "status": "SUCCEEDED",
            "event_id": "a23456789bcdefg",
            "correlation_id": "corr-valid_001",
            "etag": '"etag-safe"',
            "write_applied": True,
        }
        error = {}
    else:
        result = {}
        error = {
            "code": "operation_failed",
            "status": status,
            "correlation_id": "corr-valid_001",
            "http_status": 409,
        }
    return {
        "correlation_id": "corr-valid_001",
        "status": status,
        "event_id": "a23456789bcdefg",
        "result": result,
        "error": error,
    }


@pytest.mark.parametrize(
    "status",
    [
        "IN_PROGRESS",
        "SUCCEEDED",
        "FAILED",
        "RECONCILIATION_REQUIRED",
        "MANUAL_REVIEW",
    ],
)
def test_operation_data_accepts_backend_redacted_state_shapes(status: str) -> None:
    assert ScheduleOperationData.model_validate(_operation_payload(status)).status == status


@pytest.mark.parametrize(
    "status,section,field,value",
    [
        ("IN_PROGRESS", "result", "status", "SUCCEEDED"),
        ("SUCCEEDED", "result", "status", None),
        ("SUCCEEDED", "result", "correlation_id", None),
        ("SUCCEEDED", "result", "write_applied", None),
        ("SUCCEEDED", "result", "write_applied", False),
        ("SUCCEEDED", "result", "reconciliation_required", True),
        ("SUCCEEDED", "error", "code", "operation_failed"),
        ("SUCCEEDED", "result", "event_id", "b23456789bcdefg"),
        ("SUCCEEDED", "result", "correlation_id", "corr-other_001"),
        ("FAILED", "result", "status", "SUCCEEDED"),
        ("FAILED", "error", "code", None),
        ("FAILED", "error", "status", "MANUAL_REVIEW"),
        ("FAILED", "error", "correlation_id", "corr-other_001"),
    ],
)
def test_operation_data_rejects_incoherent_nested_evidence(
    status: str,
    section: str,
    field: str,
    value: object,
) -> None:
    payload = _operation_payload(status)
    nested = dict(payload[section])
    if value is None:
        nested.pop(field, None)
    else:
        nested[field] = value
    payload[section] = nested

    with pytest.raises(ValidationError):
        ScheduleOperationData.model_validate(payload)
