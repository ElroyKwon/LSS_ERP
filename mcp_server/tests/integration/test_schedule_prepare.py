from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from lss_erp_mcp.errors import ERPError
from lss_erp_mcp.schedule_confirmation import ScheduleConfirmationStore
from lss_erp_mcp.schemas.schedule import (
    OwnerBinding,
    ScheduleAllDayDetail,
    ScheduleAllDayItem,
    ScheduleAllDayProjection,
    ScheduleEligibility,
    SchedulePreflightData,
    TimesheetStatus,
)
from lss_erp_mcp.schemas.timesheet import CurrentUser
from lss_erp_mcp.tools.schedules import (
    SchedulePrepareError,
    prepare_create,
    prepare_delete,
    prepare_update,
)


EVENT_ID = "abcde123"
ETAG = '"etag-1"'


def mutation(*, content: str = "private meeting") -> dict[str, object]:
    return {
        "content": content,
        "type": "#123456",
        "category": "company",
        "is_all_day": True,
        "date": "2026-07-28",
        "end_date": "2026-07-28",
        "schedule_kind": "project",
    }


def current_detail(
    *,
    owner_state: str = "BOUND",
    write_allowed: bool = True,
    etag: str = ETAG,
    end_date: str = "2026-07-28",
) -> ScheduleAllDayDetail:
    reasons = []
    if owner_state == "LEGACY_OWNER_UNBOUND":
        reasons = ["legacy_owner_unbound"]
    elif owner_state == "OWNER_MISMATCH":
        reasons = ["owner_mismatch"]
    return ScheduleAllDayDetail.model_validate(
        {
            "event_id": EVENT_ID,
            "category": "company",
            "is_all_day": True,
            "schedule_kind": "project",
            "start_date": "2026-07-28",
            "end_date": end_date,
            "etag": etag,
            "owner_binding": {
                "state": owner_state,
                "write_allowed": write_allowed,
            },
            "eligibility": {
                "write_allowed": write_allowed,
                "denial_reasons": reasons,
            },
        }
    )


def preflight(
    action: str,
    *,
    write_allowed: bool = True,
    reasons: list[str] | None = None,
    owner_state: str = "BOUND",
    status: str = "작성중",
    etag: str | None = ETAG,
    current_end_date: str = "2026-07-28",
) -> SchedulePreflightData:
    denial_reasons = reasons or []
    if action == "CREATE":
        current = None
        event_id = None
        actual_etag = None
        owner = OwnerBinding(state="NOT_APPLICABLE", write_allowed=True)
    else:
        current = ScheduleAllDayItem(
            event_id=EVENT_ID,
            category="company",
            is_all_day=True,
            schedule_kind="project",
            start_date="2026-07-28",
            end_date=current_end_date,
        )
        event_id = EVENT_ID
        actual_etag = etag
        owner = OwnerBinding(
            state=owner_state,
            write_allowed=owner_state == "BOUND",
        )
    desired = None
    if action != "DELETE":
        desired = ScheduleAllDayProjection(
            is_all_day=True,
            start_date="2026-07-28",
            end_date="2026-07-28",
        )
    return SchedulePreflightData(
        action=action,
        category="company",
        event_id=event_id,
        current=current,
        desired=desired,
        owner_binding=owner,
        affected_weeks=["2026-07-27"],
        timesheet_statuses=[
            TimesheetStatus(week_start="2026-07-27", status=status)
        ],
        etag=actual_etag,
        write_allowed=write_allowed,
        denial_reasons=denial_reasons,
    )


class FakeClient:
    def __init__(
        self,
        result: SchedulePreflightData,
        *,
        detail: ScheduleAllDayDetail | None = None,
    ) -> None:
        self.result = result
        self.detail = detail or current_detail()
        self.calls: list[tuple[str, object]] = []
        self.write_calls = 0

    async def get_current_user(self) -> CurrentUser:
        self.calls.append(("get_current_user", None))
        return CurrentUser(
            user_id=7,
            employee_id=11,
            employee_code="E007",
            display_name="Test User",
            client_id="mcp-test",
            resource="erp",
            scopes=["schedule:read", "schedule:write"],
        )

    async def get_schedule(
        self,
        event_id: str,
        *,
        category: str,
    ) -> ScheduleAllDayDetail:
        self.calls.append(("get_schedule", (event_id, category)))
        return self.detail

    async def preflight_schedule(self, request):
        self.calls.append(
            ("preflight_schedule", request.model_dump(mode="json"))
        )
        return self.result

    async def create_schedule(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("prepare must not write")

    async def update_schedule(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("prepare must not write")

    async def delete_schedule(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("prepare must not write")


@pytest.mark.asyncio
async def test_prepare_create_uses_preflight_only_and_binds_normalized_request() -> None:
    client = FakeClient(preflight("CREATE"))
    store = ScheduleConfirmationStore(
        clock=lambda: datetime(2026, 7, 27, tzinfo=UTC),
        token_factory=lambda: "c" * 43,
    )

    result = await prepare_create(client, store, proposal=mutation())

    assert [name for name, _ in client.calls] == [
        "get_current_user",
        "preflight_schedule",
    ]
    assert client.write_calls == 0
    assert result["action"] == "CREATE"
    assert result["before"] is None
    assert result["after"] == {
        "category": "company",
        "is_all_day": True,
        "schedule_kind": "project",
        "start_date": "2026-07-28",
        "end_date": "2026-07-28",
    }
    assert result["affected_weeks"] == ["2026-07-27"]
    assert result["locked_weeks"] == []
    assert result["denial_reasons"] == []
    assert result["can_commit"] is True
    token = result["confirmation_token"]
    lease = store.claim(
        token,
        "idem-key-0001",
        user_id=7,
        action="CREATE",
        category="company",
        event_id=None,
        expected_etag=None,
        proposal=mutation(),
    )
    assert lease.confirmation.proposal == mutation()


@pytest.mark.asyncio
async def test_prepare_update_reads_current_preflight_and_binds_etag() -> None:
    client = FakeClient(preflight("UPDATE"))
    store = ScheduleConfirmationStore()

    result = await prepare_update(
        client,
        store,
        event_id=EVENT_ID,
        proposal=mutation(),
    )

    assert [name for name, _ in client.calls] == [
        "get_current_user",
        "get_schedule",
        "preflight_schedule",
    ]
    assert client.write_calls == 0
    assert result["expected_etag"] == ETAG
    assert result["before"]["event_id"] == EVENT_ID
    assert result["after"]["start_date"] == "2026-07-28"
    assert result["impact"]["visible_changed_fields"] == []
    assert result["impact"]["requested_write_fields"] == [
        "category",
        "content",
        "date",
        "end_date",
        "is_all_day",
        "schedule_kind",
        "type",
    ]
    assert result["impact"]["unverified_requested_fields"] == [
        "content",
        "type",
    ]
    assert result["impact"]["comparison_complete"] is False
    assert result["can_commit"] is True
    store.claim(
        result["confirmation_token"],
        "idem-key-0001",
        user_id=7,
        action="UPDATE",
        category="company",
        event_id=EVENT_ID,
        expected_etag=ETAG,
        proposal=mutation(),
    )


@pytest.mark.asyncio
async def test_prepare_delete_returns_bounded_deletion_impact() -> None:
    client = FakeClient(preflight("DELETE"))
    store = ScheduleConfirmationStore()

    result = await prepare_delete(
        client,
        store,
        event_id=EVENT_ID,
        category="company",
    )

    assert [name for name, _ in client.calls] == [
        "get_current_user",
        "get_schedule",
        "preflight_schedule",
    ]
    assert client.write_calls == 0
    assert result["before"]["event_id"] == EVENT_ID
    assert result["after"] is None
    assert result["impact"] == {
        "kind": "delete",
        "visible_changed_fields": [
            "category",
            "end_date",
            "event_id",
            "is_all_day",
            "schedule_kind",
            "start_date",
        ],
        "requested_write_fields": [
            "category",
            "event_id",
            "expected_etag",
        ],
        "unverified_requested_fields": [],
        "comparison_complete": True,
    }
    store.claim(
        result["confirmation_token"],
        "idem-key-0001",
        user_id=7,
        action="DELETE",
        category="company",
        event_id=EVENT_ID,
        expected_etag=ETAG,
        proposal={},
    )


@pytest.mark.asyncio
async def test_locked_week_returns_stable_denial_without_confirmation() -> None:
    client = FakeClient(
        preflight(
            "UPDATE",
            write_allowed=False,
            reasons=["timesheet_locked"],
            status="승인",
        )
    )

    result = await prepare_update(
        client,
        ScheduleConfirmationStore(),
        event_id=EVENT_ID,
        proposal=mutation(),
    )

    assert result["locked_weeks"] == [
        {"week_start": "2026-07-27", "status": "승인"}
    ]
    assert result["denial_reasons"] == ["timesheet_locked"]
    assert result["can_commit"] is False
    assert result["confirmation_token"] is None
    assert client.write_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_state", "reason"),
    [
        ("LEGACY_OWNER_UNBOUND", "legacy_owner_unbound"),
        ("OWNER_MISMATCH", "owner_mismatch"),
    ],
)
async def test_prepare_refuses_legacy_or_mismatched_owner(
    owner_state: str,
    reason: str,
) -> None:
    client = FakeClient(
        preflight(
            "UPDATE",
            write_allowed=False,
            reasons=[reason],
            owner_state=owner_state,
        ),
        detail=current_detail(
            owner_state=owner_state,
            write_allowed=False,
        ),
    )

    result = await prepare_update(
        client,
        ScheduleConfirmationStore(),
        event_id=EVENT_ID,
        proposal=mutation(),
    )

    assert result["denial_reasons"] == [reason]
    assert result["confirmation_token"] is None
    assert client.write_calls == 0


@pytest.mark.asyncio
async def test_incoherent_current_and_preflight_fail_closed() -> None:
    client = FakeClient(
        preflight("UPDATE", current_end_date="2026-07-29"),
        detail=current_detail(end_date="2026-07-28"),
    )

    result = await prepare_update(
        client,
        ScheduleConfirmationStore(),
        event_id=EVENT_ID,
        proposal=mutation(),
    )

    assert result["denial_reasons"] == ["preflight_state_changed"]
    assert result["can_commit"] is False
    assert result["confirmation_token"] is None


@pytest.mark.asyncio
async def test_invalid_proposal_fails_before_any_http_call() -> None:
    client = FakeClient(preflight("CREATE"))
    invalid = mutation()
    invalid["unknown"] = "not allowed"

    with pytest.raises(ValueError):
        await prepare_create(
            client,
            ScheduleConfirmationStore(),
            proposal=invalid,
        )

    assert client.calls == []
    assert client.write_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "proposal_value", "event_id", "category", "expected_code"),
    [
        (
            "create",
            {**mutation(), "content": "SECRET_CONTENT_" * 500},
            EVENT_ID,
            "company",
            "invalid_schedule_proposal",
        ),
        (
            "create",
            {**mutation(), "category": "SECRET_CATEGORY"},
            EVENT_ID,
            "company",
            "invalid_schedule_proposal",
        ),
        (
            "create",
            {**mutation(), "SECRET_FIELD": "SECRET_VALUE"},
            EVENT_ID,
            "company",
            "invalid_schedule_proposal",
        ),
        (
            "update",
            mutation(),
            "SECRET_EVENT",
            "company",
            "invalid_schedule_request",
        ),
        (
            "delete",
            None,
            EVENT_ID,
            "SECRET_CATEGORY",
            "invalid_schedule_request",
        ),
        (
            "delete",
            None,
            "SECRET_EVENT",
            "company",
            "invalid_schedule_request",
        ),
    ],
)
async def test_invalid_prepare_inputs_return_machine_safe_error_without_http(
    operation: str,
    proposal_value: dict[str, object] | None,
    event_id: str,
    category: str,
    expected_code: str,
) -> None:
    client = FakeClient(preflight("CREATE"))

    with pytest.raises(SchedulePrepareError) as caught:
        if operation == "create":
            await prepare_create(
                client,
                ScheduleConfirmationStore(),
                proposal=proposal_value,
            )
        elif operation == "update":
            await prepare_update(
                client,
                ScheduleConfirmationStore(),
                event_id=event_id,
                proposal=proposal_value,
            )
        else:
            await prepare_delete(
                client,
                ScheduleConfirmationStore(),
                event_id=event_id,
                category=category,
            )

    assert str(caught.value) == expected_code
    assert "SECRET" not in str(caught.value)
    assert client.calls == []
    assert client.write_calls == 0


@pytest.mark.asyncio
async def test_prepare_preserves_safe_erp_error() -> None:
    class FailingClient(FakeClient):
        async def preflight_schedule(self, request):
            self.calls.append(("preflight_schedule", request.action))
            raise ERPError(
                "upstream_unavailable",
                "ERP API request failed",
                True,
            )

    client = FailingClient(preflight("CREATE"))
    with pytest.raises(ERPError) as caught:
        await prepare_create(
            client,
            ScheduleConfirmationStore(),
            proposal=mutation(),
        )

    assert caught.value.code == "upstream_unavailable"
    assert str(caught.value) == (
        "upstream_unavailable: ERP API request failed"
    )


@pytest.mark.asyncio
async def test_prepare_output_does_not_echo_content_or_mutable_input() -> None:
    client = FakeClient(preflight("CREATE"))
    source = mutation(content="sensitive customer detail")

    result = await prepare_create(
        client,
        ScheduleConfirmationStore(),
        proposal=source,
    )
    source["date"] = "2030-01-01"
    rendered = repr(result)

    assert "sensitive customer detail" not in rendered
    assert "unverified_requested_fields" in rendered
    assert result["after"]["start_date"] == "2026-07-28"
    assert len(result["proposal_hash"]) == 64


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "raw_value"),
    [
        ("content", "private-content-only-change"),
        ("type", "#FEDCBA"),
        ("timesheet_project_id", 987654321),
        ("timesheet_project_name", "private-project-name"),
        ("timesheet_project_source", "공통"),
    ],
)
async def test_update_marks_redacted_or_unavailable_requested_fields_unverified(
    field: str,
    raw_value: object,
) -> None:
    client = FakeClient(preflight("UPDATE"))
    source = mutation()
    source[field] = raw_value

    result = await prepare_update(
        client,
        ScheduleConfirmationStore(),
        event_id=EVENT_ID,
        proposal=source,
    )

    assert result["impact"]["visible_changed_fields"] == []
    assert field in result["impact"]["requested_write_fields"]
    expected_unverified = {"content", "type"}
    if field.startswith("timesheet_project_"):
        expected_unverified.add(field)
    assert set(result["impact"]["unverified_requested_fields"]) == (
        expected_unverified
    )
    assert result["impact"]["comparison_complete"] is False
    assert str(raw_value) not in repr(result)


@pytest.mark.asyncio
async def test_create_impact_has_explicit_visible_and_unverified_semantics() -> None:
    result = await prepare_create(
        FakeClient(preflight("CREATE")),
        ScheduleConfirmationStore(),
        proposal=mutation(),
    )

    assert result["impact"] == {
        "kind": "create",
        "visible_changed_fields": [
            "category",
            "end_date",
            "is_all_day",
            "schedule_kind",
            "start_date",
        ],
        "requested_write_fields": [
            "category",
            "content",
            "date",
            "end_date",
            "is_all_day",
            "schedule_kind",
            "type",
        ],
        "unverified_requested_fields": ["content", "type"],
        "comparison_complete": False,
    }


@pytest.mark.asyncio
async def test_prepare_result_uses_defensive_nested_copies() -> None:
    response = preflight("CREATE")
    client = FakeClient(response)
    result = await prepare_create(
        client,
        ScheduleConfirmationStore(),
        proposal=deepcopy(mutation()),
    )

    result["affected_weeks"].append("2026-08-03")

    assert response.affected_weeks == [datetime(2026, 7, 27).date()]


@pytest.mark.asyncio
async def test_oversize_preflight_evidence_is_bounded_and_fails_closed() -> None:
    response = preflight("CREATE")
    base = datetime(2026, 1, 5).date()
    response.affected_weeks = [
        base + timedelta(days=7 * index) for index in range(65)
    ]
    response.timesheet_statuses = [
        TimesheetStatus(week_start=week, status="작성중")
        for week in response.affected_weeks
    ]

    result = await prepare_create(
        FakeClient(response),
        ScheduleConfirmationStore(),
        proposal=mutation(),
    )

    assert len(result["affected_weeks"]) == 64
    assert len(result["timesheet_statuses"]) == 64
    assert result["denial_reasons"] == ["preflight_evidence_too_large"]
    assert result["can_commit"] is False
    assert result["confirmation_token"] is None
