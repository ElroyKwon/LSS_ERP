from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations
from pydantic import Field

from .confirmation import ConfirmationStore
from .config import McpSettings
from .credentials import load_erp_token
from .erp_client import ERPClient
from .schemas.timesheet import DraftEntry
from .schemas.worklog import WorklogFact
from .tools.identity import get_current_user
from .tools.timesheets import (
    commit_draft,
    get_entry_context,
    get_week,
    prepare_draft,
    search_projects,
)
from .tools.worklog import prepare_from_worklog


@dataclass
class AppContext:
    client: ERPClient
    confirmations: ConfirmationStore
    write_enabled: bool


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    settings = McpSettings()
    token = load_erp_token(settings)
    async with ERPClient(
        base_url=str(settings.base_url),
        token=token,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        write_timeout_seconds=settings.write_timeout_seconds,
        pool_timeout_seconds=settings.pool_timeout_seconds,
        max_response_bytes=settings.max_response_bytes,
    ) as client:
        yield AppContext(
            client=client,
            confirmations=ConfirmationStore(),
            write_enabled=settings.canary_write,
        )


mcp = FastMCP("LSS ERP", lifespan=lifespan, log_level="WARNING")


@mcp.tool(
    title="ERP 연결 본인 확인",
    description="설정된 ERP API 토큰에 서버가 연결한 최소 본인 정보를 조회합니다.",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def erp_get_current_user(
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Return the minimum identity bound to the configured ERP API token."""
    return await get_current_user(ctx.request_context.lifespan_context.client)


@mcp.tool(
    title="본인 주간 타임시트 조회",
    description="본인의 지정 주차 타임시트와 기존 행을 변경 없이 조회합니다.",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def timesheet_get_week(
    week_start: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Read the configured user's timesheet week without side effects."""
    return await get_week(ctx.request_context.lifespan_context.client, week_start)


@mcp.tool(
    title="본인 타임시트 입력 기준 조회",
    description=(
        "본인의 노무구분, 허용 업무유형, 프로젝트 출처와 일별 기준시간을 "
        "지정 주차 기준으로 조회합니다."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def timesheet_get_entry_context(
    week_start: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Return token-owner entry rules and daily targets for one week."""
    return await get_entry_context(
        ctx.request_context.lifespan_context.client,
        week_start,
    )


@mcp.tool(
    title="타임시트 프로젝트 후보 검색",
    description="본인 타임시트에 사용할 수 있는 활성 프로젝트 후보만 검색합니다.",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def timesheet_search_projects(
    query: Annotated[str, Field(max_length=100)],
    ctx: Context[ServerSession, AppContext],
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
) -> dict[str, object]:
    """Search active projects through the minimum timesheet contract."""
    return await search_projects(
        ctx.request_context.lifespan_context.client,
        query,
        limit,
    )


@mcp.tool(
    title="전체 타임시트 교체안 준비",
    description=(
        "전달된 행을 주간 타임시트 전체 교체안으로 비교합니다. 생략한 기존 행은 "
        "삭제안이 되므로 부분 업무일지에는 사용하지 말고, 완성된 전체 표에만 "
        "사용하십시오. ERP에는 아직 쓰지 않습니다."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def timesheet_prepare_draft(
    week_start: str,
    entries: Annotated[
        list[DraftEntry],
        Field(min_length=1, max_length=50),
    ],
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Build a local diff and confirmation token without writing ERP."""
    app = ctx.request_context.lifespan_context
    return await prepare_draft(
        app.client,
        app.confirmations,
        week_start=week_start,
        entries=[entry.model_dump(mode="json") for entry in entries],
    )


@mcp.tool(
    title="업무일지에서 타임시트 초안 준비",
    description=(
        "로컬 AI가 업무일지 원문이나 경로가 아닌 구조화 사실만 전달합니다. "
        "시간을 추측하지 말고 반환된 예외 질문을 사용자에게 확인한 뒤, "
        "변경 내역과 일별·주간 합계를 보여주십시오. 기존의 관련 없는 행은 "
        "보존하며 ERP에는 아직 쓰지 않습니다."
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
    ]
    | None = None,
) -> dict[str, object]:
    """Prepare a merge-only draft from minimal structured worklog facts."""
    app = ctx.request_context.lifespan_context
    return await prepare_from_worklog(
        app.client,
        app.confirmations,
        week_start=week_start,
        facts=[fact.model_dump(mode="json") for fact in facts],
        accepted_question_ids=accepted_question_ids or [],
    )


@mcp.tool(
    title="확인된 본인 타임시트 초안 저장",
    description=(
        "직전에 준비·확인된 본인 작성중 초안만 저장하고 재조회로 검증합니다. "
        "canary 쓰기 Gate는 기본 비활성화입니다."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def timesheet_commit_draft(
    confirmation_token: str,
    idempotency_key: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    """Commit one confirmed draft only when the canary write Gate is enabled."""
    app = ctx.request_context.lifespan_context
    if not app.write_enabled:
        raise PermissionError("timesheet commit tool is disabled")
    return await commit_draft(
        app.client,
        app.confirmations,
        confirmation_token=confirmation_token,
        idempotency_key=idempotency_key,
    )


def run() -> None:
    mcp.run(transport="stdio")
