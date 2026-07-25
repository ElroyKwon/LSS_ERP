# LSS ERP AI Timesheet Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an approved AI host turn local personal-worklog facts into a
complete, safely merged timesheet draft while the user handles only unresolved
exceptions and final approval.

**Architecture:** The AI host reads natural-language worklogs locally and sends
bounded structured facts over stdio. A new database-free MCP preparation lane
resolves eligible project candidates, preserves unrelated draft rows, calculates
coverage, and issues a confirmation only after blocking questions are resolved.
The main developer implements one self-read REST endpoint and the expanded
entry DTO in a separate backend/PostgreSQL branch.

**Tech Stack:** Python 3.12, Pydantic 2, MCP Python SDK, httpx, FastAPI contract
oracle, pytest, PostgreSQL 16 and Alembic in the main-developer lane.

---

## Scope and ownership

Current implementation:

- structured worklog facts;
- token-owner entry context;
- project/common/leave resolution;
- merge-only worklog preparation;
- daily/weekly totals and exception questions;
- confirmed draft commit with existing safety Gates;
- AI-oriented MCP metadata;
- local contract and regression evidence;
- main-developer backend handoff.

Deferred to separate Goals:

- transcript/audio ingestion;
- weekly narrative report;
- project mutation;
- Telegram;
- email;
- schedule;
- cross-employee or manager access;
- release deployment.

The local MCP lane must not edit backend models, migrations, authentication,
deployment, or database configuration. Backend steps in this plan are handoff
requirements for the main developer, not authorization for this branch to edit
those files.

## File map

| File | Responsibility |
|---|---|
| `mcp_server/src/lss_erp_mcp/schemas/timesheet.py` | Expanded ERP entry and entry-context DTO |
| `mcp_server/src/lss_erp_mcp/schemas/worklog.py` | Strict worklog facts and question DTO |
| `mcp_server/src/lss_erp_mcp/erp_client.py` | Five-path REST allowlist and context client |
| `mcp_server/src/lss_erp_mcp/tools/timesheets.py` | Existing reads, replace prepare, commit/readback |
| `mcp_server/src/lss_erp_mcp/tools/worklog.py` | Worklog resolution, safe merge, totals, questions |
| `mcp_server/src/lss_erp_mcp/server.py` | Seven MCP tools and annotations |
| `mcp_server/tests/contract_server/state.py` | Context/project contract-oracle state |
| `mcp_server/tests/contract_server/app.py` | New context response and richer project fixtures |
| `mcp_server/tests/unit/test_worklog_schema.py` | Strict fact/entry validation |
| `mcp_server/tests/unit/test_worklog_merge.py` | Deterministic merge and totals |
| `mcp_server/tests/integration/test_entry_context.py` | REST context read |
| `mcp_server/tests/integration/test_worklog_prepare.py` | End-to-end shadow prepare |
| `mcp_server/tests/protocol/test_stdio.py` | Seven-tool list and annotation contract |
| `docs/mcp/*.md` | Versioned contract, safety, verification, entrypoint, hand-back |
| `goals/*` | Goal scope/status and future separation |

### Task 1: Expanded strict schemas

**Files:**

- Modify: `mcp_server/src/lss_erp_mcp/schemas/timesheet.py`
- Create: `mcp_server/src/lss_erp_mcp/schemas/worklog.py`
- Create: `mcp_server/tests/unit/test_worklog_schema.py`

- [x] **Step 1: Write failing schema tests**

Add tests that require:

```python
def test_leave_fact_needs_no_project_query() -> None:
    fact = WorklogFact(
        fact_id="log-1",
        work_date=date(2026, 7, 20),
        entry_kind="leave",
        hours=Decimal("8"),
        description="연차",
    )
    assert fact.entry_kind == "leave"


def test_fact_rejects_path_like_fact_id() -> None:
    with pytest.raises(ValidationError, match="fact_id"):
        WorklogFact(
            fact_id=r"G:\vault\worklog.md",
            work_date=date(2026, 7, 20),
            entry_kind="project",
            description="개발",
        )


def test_expanded_entry_rejects_projectless_execution_row() -> None:
    with pytest.raises(ValidationError, match="project_id"):
        DraftEntry(
            work_date=date(2026, 7, 20),
            project_source="실행",
            project_name="MCP 개발",
            hours=Decimal("8"),
            work_type="실행 > 업무지원",
            description="개발",
        )
```

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit\test_worklog_schema.py -q
```

Expected: collection fails because `schemas.worklog` and expanded fields do not
exist.

- [x] **Step 3: Implement strict models**

Add these interfaces:

```python
EntryKind = Literal["project", "common", "leave", "non_project"]
ProjectSource = Literal["실행", "영업", "공통"]


class WorklogFact(StrictModel):
    fact_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    work_date: date
    entry_kind: EntryKind
    description: str = Field(min_length=1, max_length=300)
    hours: Decimal | None = Field(
        default=None,
        gt=0,
        le=24,
        multiple_of=Decimal("0.25"),
    )
    project_id: int | None = Field(default=None, gt=0)
    project_query: str | None = Field(default=None, min_length=1, max_length=100)
    project_name: str | None = Field(default=None, min_length=1, max_length=200)
    project_source: ProjectSource | None = None
    work_type: str | None = Field(default=None, min_length=1, max_length=200)


class ClarificationOption(StrictModel):
    value: str
    label: str


class ClarificationQuestion(StrictModel):
    question_id: str
    fact_id: str | None
    code: str
    prompt: str
    options: list[ClarificationOption] = []
```

Expand `DraftEntry` with optional `project_id`, optional `project_name`,
`project_source`, and optional `spg`. Add a model validator enforcing execution
project IDs and names for sales/common rows.

Add `DailyTarget` and `TimesheetEntryContext` with strict Monday/week matching,
allowed sources, work types, labor type, and exactly seven daily targets.

- [x] **Step 4: Run schema tests and full unit tests**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit -q
```

Expected: all unit tests pass.

- [x] **Step 5: Commit**

```powershell
git add mcp_server/src/lss_erp_mcp/schemas mcp_server/tests/unit/test_worklog_schema.py
git commit -m "feat: add strict AI worklog schemas"
```

### Task 2: Token-owner entry context

**Files:**

- Modify: `mcp_server/src/lss_erp_mcp/erp_client.py`
- Modify: `mcp_server/src/lss_erp_mcp/tools/timesheets.py`
- Modify: `mcp_server/tests/contract_server/state.py`
- Modify: `mcp_server/tests/contract_server/app.py`
- Create: `mcp_server/tests/integration/test_entry_context.py`
- Modify: `mcp_server/tests/contract/test_erp_client.py`

- [x] **Step 1: Write failing context tests**

```python
@pytest.mark.asyncio
async def test_entry_context_is_bound_to_requested_week() -> None:
    transport = httpx.ASGITransport(app=create_contract_app())
    async with ERPClient(
        base_url="http://testserver",
        token="test-token",
        transport=transport,
    ) as client:
        context = await client.get_entry_context(date(2026, 7, 20))
    assert context.week_start == date(2026, 7, 20)
    assert context.labor_type == "원가"
    assert len(context.daily_targets) == 7
    assert "공통 > 연차" in context.work_types


@pytest.mark.asyncio
async def test_context_response_for_another_week_is_rejected() -> None:
    async def mismatched_context(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "week_start": "2026-07-27",
                "week_end": "2026-08-02",
                "labor_type": "원가",
                "project_sources": ["실행", "영업", "공통"],
                "work_types": ["공통 > 연차"],
                "daily_targets": [
                    {
                        "work_date": f"2026-07-{day:02d}",
                        "target_hours": "8",
                        "reason": "normal",
                    }
                    for day in range(27, 32)
                ]
                + [
                    {
                        "work_date": "2026-08-01",
                        "target_hours": "0",
                        "reason": "weekend",
                    },
                    {
                        "work_date": "2026-08-02",
                        "target_hours": "0",
                        "reason": "weekend",
                    },
                ],
            },
        )

    async with ERPClient(
        base_url="https://erp.example.test",
        token="test-token",
        transport=httpx.MockTransport(mismatched_context),
    ) as client:
        with pytest.raises(ERPError, match="context week mismatch"):
            await client.get_entry_context(date(2026, 7, 20))
```

- [x] **Step 2: Run and verify RED**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\integration\test_entry_context.py mcp_server\tests\contract\test_erp_client.py -q
```

Expected: failures because the client method and endpoint do not exist.

- [x] **Step 3: Implement context client and oracle**

Add `("GET", "/api/timesheets/entry-context")` to `ALLOWLIST`.

Implement:

```python
async def get_entry_context(self, week_start: date) -> TimesheetEntryContext:
    data = await self._request(
        "GET",
        "/api/timesheets/entry-context",
        params={"week_start": week_start.isoformat()},
    )
    result = _validate_response(TimesheetEntryContext, data)
    if (
        result.week_start != week_start
        or result.week_end != week_start + timedelta(days=6)
    ):
        raise ERPError(
            "upstream_invalid_response",
            "ERP API context week mismatch",
            False,
        )
    return result
```

The contract oracle returns an eight-hour weekday target, zero-hour weekend
target, allowed work types copied from the current ERP route, the token-owner
labor type, and no editable employee identifier.

Add a `get_entry_context` tool helper that parses ISO date before HTTP.

- [x] **Step 4: Run context and contract tests**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\integration\test_entry_context.py mcp_server\tests\contract -q
```

Expected: all selected tests pass.

- [x] **Step 5: Commit**

```powershell
git add mcp_server/src/lss_erp_mcp/erp_client.py mcp_server/src/lss_erp_mcp/tools/timesheets.py mcp_server/tests/contract_server mcp_server/tests/contract mcp_server/tests/integration/test_entry_context.py
git commit -m "feat: add self timesheet entry context"
```

### Task 3: Worklog resolution and safe merge

**Files:**

- Create: `mcp_server/src/lss_erp_mcp/tools/worklog.py`
- Create: `mcp_server/tests/unit/test_worklog_merge.py`
- Create: `mcp_server/tests/integration/test_worklog_prepare.py`
- Modify: `mcp_server/tests/contract_server/state.py`
- Modify: `mcp_server/tests/contract_server/app.py`

- [x] **Step 1: Write failing deterministic merge tests**

```python
def test_merge_preserves_unrelated_existing_rows() -> None:
    current = [
        persisted_entry(
            entry_id=1,
            work_date="2026-07-20",
            project_id=123,
            description="기존 업무",
        )
    ]
    incoming = [
        draft_entry(
            work_date="2026-07-21",
            project_id=456,
            description="신규 업무",
        )
    ]
    merged, preserved = merge_entries(current, incoming)
    assert len(merged) == 2
    assert preserved == 1


def test_merge_replaces_only_same_semantic_row() -> None:
    current = [draft_entry(hours="4")]
    incoming = [draft_entry(hours="8")]
    merged, preserved = merge_entries(current, incoming)
    assert merged[0]["hours"] == "8"
    assert preserved == 0
```

- [x] **Step 2: Run and verify RED**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit\test_worklog_merge.py -q
```

Expected: import failure because `tools.worklog` does not exist.

- [x] **Step 3: Implement pure helpers**

Implement focused functions:

```python
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


def merge_entries(
    current: list[dict[str, object]],
    incoming: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int]:
    current_clean = [_without_entry_id(item) for item in current]
    current_counts = Counter(semantic_entry_key(item) for item in current_clean)
    incoming_groups: dict[
        tuple[object, ...],
        list[dict[str, object]],
    ] = defaultdict(list)
    for item in incoming:
        incoming_groups[semantic_entry_key(item)].append(item)

    merged: list[dict[str, object]] = []
    preserved = 0
    replaced: set[tuple[object, ...]] = set()
    for item in current_clean:
        key = semantic_entry_key(item)
        replacements = incoming_groups.get(key, [])
        if current_counts[key] == 1 and len(replacements) == 1:
            merged.append(replacements[0])
            replaced.add(key)
        else:
            merged.append(item)
            preserved += 1

    for key, items in incoming_groups.items():
        if key not in current_counts and key not in replaced:
            merged.extend(items)
    return sorted(merged, key=_sortable_entry_key), preserved


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


def _without_entry_id(entry: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in entry.items() if key != "entry_id"}


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
    query = str(fact.project_id) if fact.project_id is not None else fact.project_query
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
            if lowered in {item.project_code.casefold(), item.project_name.casefold()}
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
    current: list[dict[str, object]],
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
    current_counts = Counter(semantic_entry_key(item) for item in current)
    warnings.extend(
        "duplicate existing entry: "
        + "/".join(str(component) for component in key)
        for key, count in sorted(
            current_counts.items(),
            key=lambda item: repr(item[0]),
        )
        if count > 1
    )
    return warnings
```

Keep these helpers independent from HTTP and confirmation state.

- [x] **Step 4: Write failing resolution integration tests**

Cover:

- exact project ID resolution;
- unique project-query resolution;
- ambiguous project candidates;
- project not found;
- leave normalization;
- common/non-project resolution;
- missing hours;
- missing work type;
- existing-row preservation;
- daily/weekly totals;
- no POST during preparation.

The successful test must assert:

```python
assert result["mode"] == "merge"
assert result["preserved_entry_count"] == 1
assert result["daily_totals"]["2026-07-20"] == "8"
assert result["weekly_total_hours"] == "16"
assert result["clarification_questions"] == []
assert result["can_commit"] is True
assert state.post_count == 0
```

- [x] **Step 5: Run and verify resolution RED**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\integration\test_worklog_prepare.py -q
```

Expected: failures because `prepare_from_worklog` is missing.

- [x] **Step 6: Implement resolution**

Implement:

```python
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
    fact_ids = [fact.fact_id for fact in parsed_facts]
    if len(set(fact_ids)) != len(fact_ids):
        raise ValueError("fact_id values must be unique")
    week_end = parsed_week + timedelta(days=6)
    if parsed_week.weekday() != 0:
        raise ValueError("week_start must be Monday")
    if any(
        fact.work_date < parsed_week or fact.work_date > week_end
        for fact in parsed_facts
    ):
        raise ValueError("fact work_date must be within the requested week")

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
    coverage_questions = build_coverage_questions(
        context,
        daily_totals,
    )
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
    warnings = hard_blocking_warnings(
        current_entries,
        incoming,
        daily_totals,
    )
    if len(merged) > 50:
        warnings.append("merged proposal exceeds 50 entries")
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
            day.isoformat(): str(daily_totals.get(day.isoformat(), Decimal("0")))
            for day in (
                parsed_week + timedelta(days=offset)
                for offset in range(7)
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
```

Project selection is deterministic:

- exact ID first;
- one exact case-insensitive code/name match;
- otherwise one active candidate;
- otherwise a question with at most 20 options.

Question IDs use stable components, for example:

```python
f"fact:{fact.fact_id}:missing-hours"
f"fact:{fact.fact_id}:project-ambiguous"
f"coverage:{work_date.isoformat()}:below-target"
```

The confirmation proposal includes complete merged entries and sorted accepted
question IDs.

- [x] **Step 7: Run unit and integration tests**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\unit\test_worklog_merge.py mcp_server\tests\integration\test_worklog_prepare.py -q
```

Expected: all selected tests pass.

- [x] **Step 8: Commit**

```powershell
git add mcp_server/src/lss_erp_mcp/tools/worklog.py mcp_server/tests/unit/test_worklog_merge.py mcp_server/tests/integration/test_worklog_prepare.py mcp_server/tests/contract_server
git commit -m "feat: prepare timesheets from structured worklogs"
```

### Task 4: Commit compatibility with expanded entries

**Files:**

- Modify: `mcp_server/src/lss_erp_mcp/tools/timesheets.py`
- Modify: `mcp_server/tests/integration/test_commit.py`
- Modify: `mcp_server/tests/fault/test_commit_replay.py`
- Modify: `mcp_server/tests/contract/test_contract_stub.py`

- [x] **Step 1: Add expanded-entry commit regression tests**

Add a successful leave/common commit and a successful execution-project commit.
Assert exact readback of:

```python
{
    "project_id": None,
    "project_name": "연차",
    "project_source": "공통",
    "spg": None,
    "work_type": "공통 > 연차",
    "description": "연차",
}
```

Add a test that accepted exception IDs remain confirmation-bound but are absent
from the ERP write body.

- [x] **Step 2: Run and verify current generalized commit behavior**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\integration\test_commit.py mcp_server\tests\fault\test_commit_replay.py -q
```

Observed: the worklog-prepared confirmation path passed immediately because
Tasks 1 and 3 expanded the shared strict request/readback model without adding
a second commit implementation. No production-code change was required.

- [x] **Step 3: Confirm readback and confirmation handling**

`commit_draft` continues to build only this write request:

```python
DraftWriteRequest(
    week_start=confirmation.week_start,
    expected_version=confirmation.expected_version,
    entries=confirmation.proposal["entries"],
)
```

Do not forward `accepted_question_ids`, `fact_id`, project candidate lists, raw
text, or local correlation data to the backend.

Update semantic sorting/readback to include all canonical entry fields.

- [x] **Step 4: Run commit, fault, and contract tests**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\integration\test_commit.py mcp_server\tests\fault mcp_server\tests\contract -q
```

Expected: all selected tests pass.

- [x] **Step 5: Commit**

```powershell
git add mcp_server/src/lss_erp_mcp/tools/timesheets.py mcp_server/tests/integration/test_commit.py mcp_server/tests/fault mcp_server/tests/contract
git commit -m "test: verify expanded timesheet commit contract"
```

### Task 5: Seven AI-oriented MCP tools

**Files:**

- Modify: `mcp_server/src/lss_erp_mcp/server.py`
- Modify: `mcp_server/tests/protocol/test_stdio.py`

- [x] **Step 1: Write failing list and metadata tests**

Require exactly:

```python
{
    "erp_get_current_user",
    "timesheet_commit_draft",
    "timesheet_get_entry_context",
    "timesheet_get_week",
    "timesheet_prepare_draft",
    "timesheet_prepare_from_worklog",
    "timesheet_search_projects",
}
```

Assert the commit tool is not read only and is potentially destructive. Assert
the two preparation tools are read-only with no remote mutation. Assert the
worklog prepare description contains the structured-facts and no-hour-guessing
instructions.

- [x] **Step 2: Run and verify RED**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\protocol\test_stdio.py -q
```

Expected: tool-list and annotation failures.

- [x] **Step 3: Register tools and annotations**

Use `mcp.types.ToolAnnotations`. Example:

```python
@mcp.tool(
    title="업무일지에서 타임시트 초안 준비",
    description=(
        "로컬 AI가 업무일지 원문이나 경로가 아닌 구조화 사실만 전달합니다. "
        "시간을 추측하지 말고 반환된 예외 질문을 사용자에게 확인한 뒤, "
        "변경 내역과 일별·주간 합계를 보여주십시오."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def timesheet_prepare_from_worklog(
    week_start: str,
    facts: Annotated[
        list[WorklogFact],
        Field(min_length=1, max_length=100),
    ],
    ctx: Context[ServerSession, AppContext],
    accepted_question_ids: Annotated[
        list[str],
        Field(max_length=50),
    ] = [],
) -> dict[str, object]:
    app = ctx.request_context.lifespan_context
    return await prepare_from_worklog(
        app.client,
        app.confirmations,
        week_start=week_start,
        facts=[fact.model_dump(mode="json") for fact in facts],
        accepted_question_ids=accepted_question_ids,
    )
```

The commit tool remains disabled by configuration before it can claim the
confirmation. Metadata does not replace runtime enforcement.

- [x] **Step 4: Run protocol tests**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\protocol -q
```

Expected: stdio initialize/list/call tests pass.

- [x] **Step 5: Commit**

```powershell
git add mcp_server/src/lss_erp_mcp/server.py mcp_server/tests/protocol/test_stdio.py
git commit -m "feat: expose AI-oriented timesheet tools"
```

### Task 6: Safety, quality, and no-silent-deletion Gates

**Files:**

- Modify: `mcp_server/tests/security/test_isolation.py`
- Create: `mcp_server/tests/security/test_worklog_privacy.py`
- Modify: `mcp_server/tests/performance/test_local_budget.py`
- Create: `mcp_server/tests/integration/test_worklog_golden_cases.py`

- [x] **Step 1: Add failing safety and quality tests**

Require:

- path-like `fact_id` rejected;
- unknown identity and status fields rejected;
- no backend/ORM/DB driver or vault path references;
- no POST from either preparation tool;
- existing rows preserved when omitted from worklog facts;
- no confirmation for unresolved hours, project, work type, or coverage;
- accepted question IDs deterministic;
- common, leave, project, and non-project golden cases;
- bounded project queries and fact counts;
- preparation local overhead remains within the existing budget after removing
  contract-oracle network time from the measurement.

- [x] **Step 2: Run and verify RED**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\security mcp_server\tests\integration\test_worklog_golden_cases.py mcp_server\tests\performance -q
```

Expected: new tests fail until every Gate is enforced.

- [x] **Step 3: Apply minimal fixes**

Fix only behavior demonstrated by the failing tests. Do not add transcript,
weekly-report, Telegram, email, schedule, or manager features.

- [x] **Step 4: Run selected Gate suites**

Run:

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests\security mcp_server\tests\integration\test_worklog_golden_cases.py mcp_server\tests\performance -q
```

Expected: all selected tests pass with no warnings.

- [x] **Step 5: Commit**

```powershell
git add mcp_server/tests mcp_server/src
git commit -m "test: gate AI timesheet safety and quality"
```

### Task 7: Main-developer contract and Goal handoff

**Files:**

- Modify: `docs/mcp/API-CONTRACT.md`
- Modify: `docs/mcp/AI-SAFETY-BASELINE.md`
- Modify: `docs/mcp/AI-MAIN-DEVELOPER-ENTRYPOINT.md`
- Modify: `docs/mcp/EVIDENCE-HAND-BACK.md`
- Modify: `docs/mcp/GITHUB-ISSUE-HANDOFF.md`
- Modify: `docs/mcp/LOCAL-VERIFICATION.md`
- Modify: `docs/handoffs/2026-07-25-lss-erp-mcp-backend-db-token-handoff.md`
- Modify: `mcp_server/README.md`
- Modify: `goals/_INDEX.md`
- Modify: `goals/LSS-MCP-G0001/STATUS.md`
- Create: `goals/LSS-MCP-G0006/STATUS.md`
- Create: `goals/LSS-MCP-G0007/STATUS.md`
- Create: `goals/LSS-MCP-G0008/STATUS.md`
- Create: `goals/LSS-MCP-G0009/STATUS.md`
- Create: `goals/FUTURE-CAPABILITIES.md`

- [x] **Step 1: Update exact surface counts and schemas**

Document exactly seven tools and five endpoints. Include full request/response
examples for entry context, expanded entries, structured facts, preparation
questions, merge output, and commit.

- [x] **Step 2: Update main-developer ownership**

Require the main developer to implement:

- self-read entry context;
- execution/sales/common/leave mapping;
- token-owner labor type;
- expanded draft DTO;
- OpenAPI and PostgreSQL evidence;
- legacy UI regression;
- no write activation.

Keep every unverified real-system field as `NOT-RUN` or `UNKNOWN`.

- [x] **Step 3: Update Goal files**

Maintain exactly one active Goal, G0001. Record local implementation evidence
under G0006-G0008 without activating those Goals. Add future capability
separation for weekly report, transcript, project mutation, Telegram, email,
and schedule.

- [x] **Step 4: Self-review documents**

Run:

```powershell
rg -n "exactly five|five tools|four REST|5개 도구|4개 REST" docs mcp_server goals
rg -n "placeholder-marker|implement-later-marker|assume|blanket guarantee" docs/mcp docs/handoffs goals
```

Expected: no stale count outside clearly labeled historical evidence and no
placeholder that could be mistaken for reproduced proof.

- [x] **Step 5: Commit**

```powershell
git add docs mcp_server/README.md goals
git commit -m "docs: hand off AI timesheet backend contract"
```

### Task 8: Fresh verification and collaboration push

**Files:**

- Modify: `docs/mcp/LOCAL-VERIFICATION.md`
- Modify: `goals/LSS-MCP-G0001/STATUS.md`

- [x] **Step 1: Run the complete local test suite**

```powershell
.\mcp_server\.venv\Scripts\python.exe -m pytest mcp_server\tests -q
```

Expected: zero failures.

- [x] **Step 2: Run compile and dependency Gates**

```powershell
.\mcp_server\.venv\Scripts\python.exe -m compileall -q mcp_server\src mcp_server\tests
.\mcp_server\.venv\Scripts\python.exe -m pip_audit --progress-spinner off
```

Expected: exit code zero and zero known vulnerabilities in resolved published
dependencies. Keep the local unpublished-package caveat.

- [x] **Step 3: Run source isolation and secret scans**

```powershell
rg -n "DATABASE_URL|create_engine|sqlalchemy|backend\\.app|G:\\\\|_Obsidian" mcp_server/src
rg -n "(Bearer\\s+[A-Za-z0-9._-]{12,}|postgres(?:ql)?://|SECRET_KEY\\s*=|LSS_ERP_API_TOKEN\\s*=)" mcp_server docs goals
```

Expected: zero forbidden runtime and secret findings.

- [x] **Step 4: Reproduce stdio tool evidence**

Run the protocol test and, when available, MCP Inspector. Record the exact tool
count and result without exposing credentials.

- [x] **Step 5: Re-read requirements and record evidence**

Compare every design requirement to code, tests, and handoff documents. Update
local evidence only from this run. Do not convert backend/PostgreSQL/OpenAPI,
Credential Manager live, real API, canary, or rollback to PASS.

- [x] **Step 6: Final commit**

```powershell
git add docs/mcp/LOCAL-VERIFICATION.md goals/LSS-MCP-G0001/STATUS.md
git commit -m "docs: record AI timesheet verification"
```

- [x] **Step 7: Verify branch state and push**

```powershell
git status --short --branch
git log -1 --oneline
git push origin khlee-add-mcp
git rev-parse HEAD
git ls-remote --heads origin khlee-add-mcp
```

Expected: clean worktree and identical local/remote SHA. This is a development
collaboration push only.

## Main-developer backend execution checklist

The main developer creates or uses a separate backend working branch from the
pushed collaboration checkpoint and performs TDD for:

1. `GET /api/timesheets/entry-context`;
2. expanded MCP draft request mapping into the existing weekly row model;
3. execution-project eligibility;
4. sales/common/leave normalization;
5. token-owner labor type;
6. self-only, draft-only, state, version, and unique enforcement;
7. idempotency/audit atomicity;
8. OpenAPI export and SHA-256;
9. PostgreSQL migration and rollback evidence;
10. legacy UI regression.

The main developer returns evidence through `docs/mcp/EVIDENCE-HAND-BACK.md`.
That branch may not merge to `origin/main`, deploy, or activate real write
without G0009 PASS and a separate user approval.
