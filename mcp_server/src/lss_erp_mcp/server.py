from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from .confirmation import ConfirmationStore
from .config import McpSettings
from .credentials import load_erp_token
from .erp_client import ERPClient
from .schedule_confirmation import ScheduleConfirmationStore
from .schemas.schedule import ScheduleMutationRequest
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
from .tools.schedules import (
    commit_schedule,
    get_operation_status,
    prepare_create,
    prepare_delete,
    prepare_update,
)
from .tools.worklog import prepare_from_worklog


class RedactingFastMCP(FastMCP):
    """Preserve strict schemas without reflecting rejected values to clients."""

    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.inputSchema["additionalProperties"] = False
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
    ) -> object:
        tool = self._tool_manager.get_tool(name)
        if tool is not None:
            properties = tool.parameters.get("properties", {})
            allowed = set(properties) if isinstance(properties, dict) else set()
            if set(arguments) - allowed:
                raise ToolError(
                    f"Error executing tool {name}: invalid_tool_arguments"
                ) from None
        try:
            return await super().call_tool(name, arguments)
        except ToolError as exc:
            if isinstance(exc.__cause__, ValidationError):
                raise ToolError(
                    f"Error executing tool {name}: invalid_tool_arguments"
                ) from None
            raise


@dataclass
class AppContext:
    client: ERPClient
    confirmations: ConfirmationStore
    write_enabled: bool
    schedule_confirmations: ScheduleConfirmationStore
    schedule_write_enabled: bool


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
            schedule_confirmations=ScheduleConfirmationStore(),
            schedule_write_enabled=settings.schedule_canary_write,
        )


mcp = RedactingFastMCP("LSS ERP", lifespan=lifespan, log_level="WARNING")


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


_SCHEDULE_READ_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


@mcp.tool(
    title="Enterprise schedule list",
    description="Read a bounded company or refresh schedule range.",
    annotations=_SCHEDULE_READ_ANNOTATIONS,
)
async def schedule_list(
    ctx: Context[ServerSession, AppContext],
    category: str = "company",
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> dict[str, object]:
    result = await ctx.request_context.lifespan_context.client.list_schedules(
        category=category,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return result.model_dump(mode="json")


@mcp.tool(
    title="Enterprise schedule detail",
    description="Read one schedule with owner, etag, and eligibility evidence.",
    annotations=_SCHEDULE_READ_ANNOTATIONS,
)
async def schedule_get(
    event_id: str,
    ctx: Context[ServerSession, AppContext],
    category: str = "company",
) -> dict[str, object]:
    result = await ctx.request_context.lifespan_context.client.get_schedule(
        event_id,
        category=category,
    )
    return result.model_dump(mode="json")


@mcp.tool(
    title="Prepare schedule creation",
    description=(
        "Prepare a content-redacted creation review and optional confirmation. "
        "This tool does not write."
    ),
    annotations=_SCHEDULE_READ_ANNOTATIONS,
)
async def schedule_prepare_create(
    proposal: ScheduleMutationRequest,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    app = ctx.request_context.lifespan_context
    return await prepare_create(
        app.client,
        app.schedule_confirmations,
        proposal=proposal.model_dump(mode="json", exclude_none=True),
    )


@mcp.tool(
    title="Prepare schedule update",
    description=(
        "Prepare a content-redacted update review and optional confirmation. "
        "This tool does not write."
    ),
    annotations=_SCHEDULE_READ_ANNOTATIONS,
)
async def schedule_prepare_update(
    event_id: str,
    proposal: ScheduleMutationRequest,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    app = ctx.request_context.lifespan_context
    return await prepare_update(
        app.client,
        app.schedule_confirmations,
        event_id=event_id,
        proposal=proposal.model_dump(mode="json", exclude_none=True),
    )


@mcp.tool(
    title="Prepare schedule deletion",
    description=(
        "Prepare a content-redacted deletion review and optional confirmation. "
        "This tool does not write."
    ),
    annotations=_SCHEDULE_READ_ANNOTATIONS,
)
async def schedule_prepare_delete(
    event_id: str,
    category: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    app = ctx.request_context.lifespan_context
    return await prepare_delete(
        app.client,
        app.schedule_confirmations,
        event_id=event_id,
        category=category,
    )


@mcp.tool(
    title="Commit confirmed schedule mutation",
    description=(
        "Commit one exact confirmed mutation when the independent local "
        "schedule write gate and the backend write gate are both enabled."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def schedule_commit(
    confirmation_token: str,
    idempotency_key: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    app = ctx.request_context.lifespan_context
    return await commit_schedule(
        app.client,
        app.schedule_confirmations,
        write_enabled=app.schedule_write_enabled,
        confirmation_token=confirmation_token,
        idempotency_key=idempotency_key,
    )


@mcp.tool(
    title="Schedule operation status",
    description=(
        "Read the backend operation journal by correlation ID without "
        "retrying a schedule write."
    ),
    annotations=_SCHEDULE_READ_ANNOTATIONS,
)
async def schedule_operation_status(
    correlation_id: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, object]:
    return await get_operation_status(
        ctx.request_context.lifespan_context.client,
        correlation_id,
    )


def run() -> None:
    mcp.run(transport="stdio")
