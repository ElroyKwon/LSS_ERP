from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from lss_erp_mcp.confirmation import ConfirmationStore
from lss_erp_mcp.erp_client import ERPClient
from lss_erp_mcp.schemas.timesheet import (
    DraftEntry,
    ProjectItem,
    TimesheetEntryContext,
)
from lss_erp_mcp.schemas.worklog import (
    ClarificationOption,
    ClarificationQuestion,
    WorklogFact,
)
from lss_erp_mcp.tools.timesheets import build_diff


def semantic_entry_key(entry: dict[str, object]) -> tuple[object, ...]:
    return (
        entry["work_date"],
        entry.get("project_source"),
        entry.get("project_id"),
        entry.get("project_name"),
        entry["work_type"],
        entry["description"],
    )


def _sortable_entry_key(entry: dict[str, object]) -> tuple[str, ...]:
    return tuple(
        "" if component is None else str(component)
        for component in semantic_entry_key(entry)
    )


def _without_entry_id(entry: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in entry.items() if key != "entry_id"}


def merge_entries(
    current: list[dict[str, object]],
    incoming: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int]:
    merged = {
        semantic_entry_key(_without_entry_id(item)): _without_entry_id(item)
        for item in current
    }
    incoming_keys = {semantic_entry_key(item) for item in incoming}
    preserved = len(set(merged) - incoming_keys)
    for item in incoming:
        merged[semantic_entry_key(item)] = item
    return sorted(merged.values(), key=_sortable_entry_key), preserved


def calculate_totals(
    entries: list[dict[str, object]],
) -> tuple[dict[str, Decimal], Decimal]:
    totals: dict[str, Decimal] = {}
    for entry in entries:
        work_date = str(entry["work_date"])
        totals[work_date] = totals.get(work_date, Decimal("0")) + Decimal(
            str(entry["hours"])
        )
    return dict(sorted(totals.items())), sum(totals.values(), Decimal("0"))


def _question(
    *,
    question_id: str,
    fact_id: str | None,
    code: str,
    prompt: str,
    options: list[tuple[str, str]] | None = None,
) -> ClarificationQuestion:
    return ClarificationQuestion(
        question_id=question_id,
        fact_id=fact_id,
        code=code,
        prompt=prompt,
        options=[
            ClarificationOption(value=value, label=label)
            for value, label in (options or [])[:20]
        ],
    )


def _project_option(item: ProjectItem) -> tuple[str, str]:
    value = (
        str(item.project_id)
        if item.project_id is not None
        else item.project_code or item.project_name
    )
    label = " ".join(
        part for part in (item.project_code, item.project_name) if part
    )
    return value, label


async def _resolve_project(
    client: ERPClient,
    fact: WorklogFact,
) -> tuple[ProjectItem | None, ClarificationQuestion | None]:
    query = (
        str(fact.project_id)
        if fact.project_id is not None
        else fact.project_query
    )
    if not query:
        return None, _question(
            question_id=f"fact:{fact.fact_id}:missing-project",
            fact_id=fact.fact_id,
            code="missing_project",
            prompt="이 업무를 연결할 프로젝트가 필요합니다.",
        )
    result = await client.search_projects(query, 20)
    active = [item for item in result.items if item.active]
    if fact.project_id is not None:
        matches = [item for item in active if item.project_id == fact.project_id]
    else:
        lowered = query.casefold()
        matches = [
            item
            for item in active
            if lowered
            in {
                item.project_code.casefold(),
                item.project_name.casefold(),
            }
        ]
        if not matches and len(active) == 1:
            matches = active
    if len(matches) == 1:
        return matches[0], None
    code = "project_not_found" if not active else "project_ambiguous"
    return None, _question(
        question_id=f"fact:{fact.fact_id}:{code.replace('_', '-')}",
        fact_id=fact.fact_id,
        code=code,
        prompt=(
            "일치하는 활성 프로젝트가 없습니다."
            if not active
            else "연결할 프로젝트를 선택해야 합니다."
        ),
        options=[_project_option(item) for item in active],
    )


async def resolve_facts(
    client: ERPClient,
    context: TimesheetEntryContext,
    facts: list[WorklogFact],
) -> tuple[list[DraftEntry], list[ClarificationQuestion]]:
    resolved: list[DraftEntry] = []
    questions: list[ClarificationQuestion] = []
    for fact in facts:
        fact_questions: list[ClarificationQuestion] = []
        if fact.hours is None:
            fact_questions.append(
                _question(
                    question_id=f"fact:{fact.fact_id}:missing-hours",
                    fact_id=fact.fact_id,
                    code="missing_hours",
                    prompt="이 업무의 작업시간이 필요합니다.",
                )
            )

        if fact.entry_kind == "leave":
            project_id = None
            project_name = "연차"
            project_source = "공통"
            spg = None
            work_type = "공통 > 연차"
        elif fact.entry_kind == "project":
            project, project_question = await _resolve_project(client, fact)
            if project_question is not None:
                fact_questions.append(project_question)
                project_id = None
                project_name = None
                project_source = "실행"
                spg = None
            else:
                assert project is not None
                project_id = project.project_id
                project_name = project.project_name
                project_source = project.project_source
                spg = project.spg
            work_type = fact.work_type
        else:
            project_id = None
            project_name = fact.project_name
            project_source = "공통"
            spg = None
            work_type = fact.work_type
            if not project_name:
                fact_questions.append(
                    _question(
                        question_id=f"fact:{fact.fact_id}:missing-common-name",
                        fact_id=fact.fact_id,
                        code="missing_common_name",
                        prompt="공통 또는 비프로젝트 업무의 표시 이름이 필요합니다.",
                    )
                )

        if not work_type:
            fact_questions.append(
                _question(
                    question_id=f"fact:{fact.fact_id}:missing-work-type",
                    fact_id=fact.fact_id,
                    code="missing_work_type",
                    prompt="이 업무의 작업유형이 필요합니다.",
                    options=[(value, value) for value in context.work_types],
                )
            )
        elif work_type not in context.work_types:
            fact_questions.append(
                _question(
                    question_id=f"fact:{fact.fact_id}:invalid-work-type",
                    fact_id=fact.fact_id,
                    code="invalid_work_type",
                    prompt="ERP에서 허용하는 작업유형을 선택해야 합니다.",
                    options=[(value, value) for value in context.work_types],
                )
            )

        if fact_questions:
            questions.extend(fact_questions)
            continue
        resolved.append(
            DraftEntry(
                work_date=fact.work_date,
                project_id=project_id,
                project_name=project_name,
                project_source=project_source,
                spg=spg,
                hours=fact.hours,
                work_type=work_type,
                description=fact.description,
            )
        )
    return resolved, questions


def build_coverage_questions(
    context: TimesheetEntryContext,
    daily_totals: dict[str, Decimal],
) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    for target in context.daily_targets:
        day = target.work_date.isoformat()
        actual = daily_totals.get(day, Decimal("0"))
        if actual == target.target_hours:
            continue
        relation = "below" if actual < target.target_hours else "above"
        questions.append(
            _question(
                question_id=f"coverage:{day}:{relation}-target",
                fact_id=None,
                code=f"{relation}_daily_target",
                prompt=(
                    f"{day} 합계 {actual}시간이 기준 "
                    f"{target.target_hours}시간과 다릅니다. "
                    "누락 업무를 보완하거나 이 예외를 승인해 주십시오."
                ),
                options=[("accept", "이 일별 합계를 예외로 승인")],
            )
        )
    return questions


def hard_blocking_warnings(
    incoming: list[dict[str, object]],
    daily_totals: dict[str, Decimal],
) -> list[str]:
    warnings = [
        f"{day} exceeds 24 hours"
        for day, total in sorted(daily_totals.items())
        if total > Decimal("24")
    ]
    counts = Counter(semantic_entry_key(item) for item in incoming)
    warnings.extend(
        "duplicate worklog entry: "
        + "/".join(str(component) for component in key)
        for key, count in sorted(counts.items(), key=lambda item: repr(item[0]))
        if count > 1
    )
    return warnings


async def prepare_from_worklog(
    client: ERPClient,
    store: ConfirmationStore,
    *,
    week_start: str,
    facts: list[dict[str, object]],
    accepted_question_ids: list[str],
) -> dict[str, object]:
    if not 1 <= len(facts) <= 100:
        raise ValueError("facts must contain between 1 and 100 items")
    if len(accepted_question_ids) > 50:
        raise ValueError("accepted_question_ids may contain at most 50 items")
    parsed_week = date.fromisoformat(week_start)
    parsed_facts = [WorklogFact.model_validate(item) for item in facts]
    week_end = parsed_week + timedelta(days=6)
    if parsed_week.weekday() != 0:
        raise ValueError("week_start must be Monday")
    if any(
        fact.work_date < parsed_week or fact.work_date > week_end
        for fact in parsed_facts
    ):
        raise ValueError("fact work_date must be within the requested week")
    if len(set(accepted_question_ids)) != len(accepted_question_ids):
        raise ValueError("accepted_question_ids must not contain duplicates")

    user, current, context = await asyncio.gather(
        client.get_current_user(),
        client.get_week(parsed_week),
        client.get_entry_context(parsed_week),
    )
    resolved, fact_questions = await resolve_facts(
        client,
        context,
        parsed_facts,
    )
    current_entries = [
        _without_entry_id(item.model_dump(mode="json"))
        for item in current.entries
    ]
    incoming = [item.model_dump(mode="json") for item in resolved]
    merged, preserved = merge_entries(current_entries, incoming)
    daily_totals, weekly_total = calculate_totals(merged)
    coverage_questions = build_coverage_questions(context, daily_totals)
    coverage_ids = {item.question_id for item in coverage_questions}
    accepted = set(accepted_question_ids)
    unknown_accepted = accepted - coverage_ids
    if unknown_accepted:
        raise ValueError(
            "accepted_question_ids contains an unknown or non-coverage question"
        )
    questions = [
        *fact_questions,
        *[
            item
            for item in coverage_questions
            if item.question_id not in accepted
        ],
    ]
    warnings = hard_blocking_warnings(incoming, daily_totals)
    can_commit = (
        current.status == "작성중"
        and bool(merged)
        and not questions
        and not warnings
    )
    confirmation_token = None
    if can_commit:
        confirmation_token = store.put(
            user_id=user.user_id,
            week_start=week_start,
            expected_version=current.version,
            proposal={
                "entries": merged,
                "accepted_question_ids": sorted(accepted),
            },
        )
    return {
        "mode": "merge",
        "week_start": week_start,
        "current_status": current.status,
        "current_version": current.version,
        "proposal_entries": merged,
        "diff": build_diff(current_entries, merged),
        "preserved_entry_count": preserved,
        "daily_totals": {
            day.isoformat(): str(
                daily_totals.get(day.isoformat(), Decimal("0"))
            )
            for day in (
                parsed_week + timedelta(days=offset) for offset in range(7)
            )
        },
        "weekly_total_hours": str(weekly_total),
        "daily_targets": [
            item.model_dump(mode="json") for item in context.daily_targets
        ],
        "clarification_questions": [
            item.model_dump(mode="json") for item in questions
        ],
        "warnings": warnings,
        "can_commit": can_commit,
        "confirmation_token": confirmation_token,
    }
