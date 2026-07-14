from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..mcp.tools import call_tool, list_tools
from ..utils.auth import get_current_user

router = APIRouter(prefix="/api", tags=["AI Assistant"])

PROJECT_STATUSES = ("미진행", "진행중", "완료")


class ChatContext(BaseModel):
    route: str | None = None
    menu: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str


class AiChatRequest(BaseModel):
    message: str
    context: ChatContext = Field(default_factory=ChatContext)
    history: list[ChatMessage] = Field(default_factory=list)


class McpJsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


def _week_bounds(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - timedelta(days=1)


def _timesheet_period_args(normalized: str, filters: dict[str, Any]) -> dict[str, Any]:
    today = date.today()
    args: dict[str, Any] = {}
    if any(token in normalized for token in ["지난달", "전월"]):
        first_this_month, _ = _month_bounds(today)
        previous_month_day = first_this_month - timedelta(days=1)
        start, end = _month_bounds(previous_month_day)
        args["period_start"] = str(start)
        args["period_end"] = str(end)
        args["period_label"] = "지난달"
    elif any(token in normalized for token in ["이번달", "금월", "이번월"]):
        start, end = _month_bounds(today)
        args["period_start"] = str(start)
        args["period_end"] = str(end)
        args["period_label"] = "이번달"
    elif any(token in normalized for token in ["지난주", "전주"]):
        start, end = _week_bounds(today - timedelta(days=7))
        args["week_start"] = str(start)
        args["period_label"] = "지난주"
    elif filters.get("week_start"):
        args["week_start"] = filters["week_start"]
    return args


def _select_tool(message: str, context: ChatContext) -> tuple[str, dict[str, Any]]:
    text = message.lower()
    normalized = "".join(message.split())
    filters = context.filters or {}
    if (
        "타임시트" in message
        or any(token in normalized for token in ["미제출", "미작성", "작성중", "작성자", "작성인원", "저장", "저장인원", "입력자", "입력인원", "제출자"])
        or context.route == "/timesheet"
    ):
        args = _timesheet_period_args(normalized, filters)
        if any(token in normalized for token in ["미제출", "미작성", "안낸", "안냈"]):
            args["status"] = "미작성"
        elif any(token in normalized for token in ["작성중", "작성자", "작성인원", "작성한", "입력자", "입력인원", "입력한", "저장자", "저장인원", "저장한", "저장된", "제출자", "제출만", "제출한"]):
            args["status"] = "작성중"
        return "get_timesheet_team_status", args
    if "의견" in message or "답변" in message or context.route == "/opinion-listening":
        args: dict[str, Any] = {}
        if any(token in normalized for token in ["답변완료", "완료의견", "답변된"]):
            args["status"] = "answered"
        elif any(token in normalized for token in ["전체의견", "의견전체", "모든의견"]):
            args["status"] = "all"
        else:
            args["status"] = "waiting"
        if any(token in normalized for token in ["첨부있는", "첨부파일", "첨부있"]):
            args["has_attachments"] = True
        query = message
        for token in ["의견", "청취", "답변", "대기", "완료", "전체", "목록", "보여줘", "알려줘", "검색", "첨부", "있는", "만", "다시"]:
            query = query.replace(token, " ")
        query = query.strip()
        if query:
            args["query"] = query
        return "list_waiting_opinions", args
    if "프로젝트" in message or "pjt" in text or "pj-" in text or context.route == "/execution/projects":
        args: dict[str, Any] = {}
        for status in PROJECT_STATUSES:
            if status in normalized:
                args["status"] = status
                break
        if any(token in normalized for token in ["진행프로젝트", "진행중인프로젝트"]):
            args["status"] = "진행중"
        if any(token in normalized for token in ["금액큰", "계약금액큰", "큰순", "금액순", "계약금액순"]):
            args["order_by"] = "amount_desc"
        elif any(token in normalized for token in ["금액작은", "작은순"]):
            args["order_by"] = "amount_asc"
        elif any(token in normalized for token in ["종료일", "계약종료", "마감"]):
            args["order_by"] = "end_date"
        query = message
        for token in [
            "프로젝트", "검색", "찾아", "찾아줘", "요약", "알려줘", "보여줘",
            "해줘", "현황", "최근", "목록", "리스트", "다시",
            "진행중", "미진행", "완료", "계약금액", "금액", "큰", "작은", "순서", "순",
        ]:
            query = query.replace(token, " ")
        query = query.strip()
        if query:
            args["query"] = query
        return "search_projects", args
    return "get_operational_summary", _timesheet_period_args(normalized, filters)


def _summarize_tool_result(tool_name: str, result: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[str]]:
    if tool_name == "get_timesheet_team_status":
        counts = result.get("counts", {})
        all_counts = result.get("all_counts") or counts
        rows = result.get("rows", [])
        status_filter = result.get("status_filter")
        period_start = result.get("period_start") or result.get("week_start")
        period_end = result.get("period_end") or result.get("week_end")
        period_unit = result.get("period_unit", "주")
        missing = [row for row in rows if row.get("status") == "미작성"]
        if status_filter:
            answer = (
                f"{period_start} ~ {period_end} "
                f"{status_filter} 상태 타임시트 직원은 {len(rows)}명입니다. "
                f"해당 {period_unit} {status_filter} 입력 시간은 {result.get('total_hours', 0)}h입니다."
            )
            if rows:
                names = ", ".join(row["employee_name"] for row in rows[:20])
                answer += f" 대상자는 {names}" + (" 외 추가 인원이 있습니다." if len(rows) > 20 else "입니다.")
        else:
            status_text = ", ".join(f"{k} {v}명" for k, v in counts.items()) or "해당 없음"
            answer = (
                f"{period_start} ~ {period_end} 타임시트 현황입니다. "
                f"총 {len(rows)}명, 해당 {period_unit} 입력 시간 {result.get('total_hours', 0)}h입니다. "
                f"상태별 건수는 {status_text}입니다."
            )
            if missing:
                names = ", ".join(row["employee_name"] for row in missing[:20])
                answer += f" 미작성자는 {names}" + (" 외 추가 인원이 있습니다." if len(missing) > 20 else "입니다.")
        description = (
            f"{status_filter} 필터 적용 · 전체 미작성 {all_counts.get('미작성', 0)}명 · 작성중 {all_counts.get('작성중', 0)}명"
            if status_filter
            else f"미작성 {counts.get('미작성', 0)}명 · 작성중 {counts.get('작성중', 0)}명"
        )
        cards = [{
            "title": "타임시트 현황",
            "metric": f"{len(rows)}명",
            "description": description,
            "items": rows,
        }]
        suggestions = ["지난주 작성인원 보여줘", "지난주 미작성인원 보여줘", "이번달 타임시트 현황 보여줘"]
        return answer, cards, suggestions

    if tool_name == "list_waiting_opinions":
        items = result.get("items", [])
        status_filter = result.get("status_filter", "waiting")
        status_label = {"waiting": "답변 대기", "answered": "답변 완료", "all": "전체"}.get(status_filter, "의견 청취")
        answer = f"{status_label} 의견은 총 {result.get('total_count', 0)}건입니다."
        if items:
            answer += " 최근 대기 항목은 " + ", ".join(item["title"] for item in items[:5]) + "입니다."
        elif result.get("query"):
            answer += f" 검색어 '{result.get('query')}'에 해당하는 항목은 없습니다."
        cards = [{
            "title": "의견 청취",
            "metric": f"{result.get('total_count', 0)}건",
            "description": f"{status_label} · 전체 대기 {result.get('total_waiting', 0)}건 · 답변 완료 {result.get('total_answered', 0)}건",
            "items": items,
        }]
        return answer, cards, ["답변 대기 의견 다시 보여줘", "답변 완료 의견 보여줘", "첨부 있는 의견만 보여줘"]

    if tool_name == "search_projects":
        items = result.get("items", [])
        status_filter = result.get("status_filter")
        total_count = result.get("total_count", len(items))
        order_label = {
            "recent": "최근 수정순",
            "amount_desc": "계약금액 큰 순",
            "amount_asc": "계약금액 작은 순",
            "end_date": "계약 종료일순",
        }.get(result.get("order_by"), "최근 수정순")
        answer = f"프로젝트 검색 결과 {total_count}건을 찾았습니다."
        if status_filter:
            answer += f" 상태는 {status_filter}, 정렬은 {order_label}입니다."
        if items:
            answer += " 상위 결과는 " + ", ".join(
                f"{item.get('project_no') or '-'} {item.get('project_name')}" for item in items[:5]
            ) + "입니다."
        elif result.get("query"):
            answer += f" 검색어 '{result.get('query')}'에 해당하는 프로젝트는 없습니다."
        cards = [{
            "title": "프로젝트 검색",
            "metric": f"{total_count}건",
            "description": f"{status_filter or '전체 상태'} · {order_label} · 계약금액 합계 {result.get('total_contract_amount', 0):,.0f}",
            "items": items,
        }]
        return answer, cards, ["진행중 프로젝트 보여줘", "계약금액 큰 프로젝트 보여줘", "완료 프로젝트 보여줘"]

    summary = result
    ts_counts = summary.get("timesheet", {}).get("counts", {})
    ts_rows = summary.get("timesheet", {}).get("rows", [])
    waiting = summary.get("opinions", {}).get("total_waiting", 0)
    answered = summary.get("opinions", {}).get("total_answered", 0)
    active_projects = summary.get("projects", {}).get("active_count", 0)
    project_amount = summary.get("projects", {}).get("total_contract_amount", 0)
    answer = (
        "ERP 운영 요약입니다. "
        f"타임시트는 미작성 {ts_counts.get('미작성', 0)}명, 작성중 {ts_counts.get('작성중', 0)}명입니다. "
        f"답변 대기 의견은 {waiting}건, 답변 완료 의견은 {answered}건입니다. "
        f"진행 중 프로젝트는 {active_projects}건이고 계약금액 합계는 {project_amount:,.0f}입니다."
    )
    cards = [
        {
            "title": "타임시트",
            "metric": f"미작성 {ts_counts.get('미작성', 0)}명",
            "description": f"{summary.get('timesheet', {}).get('period_start')} ~ {summary.get('timesheet', {}).get('period_end')}",
            "items": ts_rows,
        },
        {
            "title": "프로젝트",
            "metric": f"{active_projects}건",
            "description": f"진행중 프로젝트 · 계약금액 합계 {project_amount:,.0f}",
            "items": summary.get("projects", {}).get("recent", []),
        },
        {
            "title": "의견 청취",
            "metric": f"{waiting}건",
            "description": "답변 대기 의견",
            "items": summary.get("opinions", {}).get("items", []),
        },
    ]
    return answer, cards, ["지난주 미작성인원 보여줘", "답변 대기 의견 보여줘", "진행중 프로젝트 보여줘"]


@router.get("/ai/tools")
def get_ai_tools(_=Depends(get_current_user)):
    return {"tools": list_tools()}


@router.post("/ai/chat")
def chat_with_assistant(
    payload: AiChatRequest,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    if not payload.message.strip():
        raise HTTPException(status_code=422, detail="메시지를 입력하세요.")
    tool_name, arguments = _select_tool(payload.message, payload.context)
    try:
        tool_result = call_tool(tool_name, arguments, db, current)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    answer, cards, suggestions = _summarize_tool_result(tool_name, tool_result)
    return {
        "answer": answer,
        "tool_calls": [{"name": tool_name, "arguments": arguments}],
        "cards": cards,
        "suggestions": suggestions,
        "raw": tool_result,
    }


@router.post("/mcp")
def mcp_json_rpc(
    payload: McpJsonRpcRequest,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    try:
        if payload.method == "tools/list":
            return {"jsonrpc": "2.0", "id": payload.id, "result": {"tools": list_tools()}}
        if payload.method == "tools/call":
            name = payload.params.get("name")
            arguments = payload.params.get("arguments") or {}
            result = call_tool(name, arguments, db, current)
            return {
                "jsonrpc": "2.0",
                "id": payload.id,
                "result": {
                    "content": [{"type": "text", "text": str(result)}],
                    "structuredContent": result,
                    "isError": False,
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": payload.id,
            "error": {"code": -32601, "message": f"Unsupported MCP method: {payload.method}"},
        }
    except KeyError as exc:
        return {
            "jsonrpc": "2.0",
            "id": payload.id,
            "error": {"code": -32602, "message": str(exc)},
        }


@router.get("/mcp/tools")
def get_mcp_tools(_=Depends(get_current_user)):
    return {"tools": list_tools()}
