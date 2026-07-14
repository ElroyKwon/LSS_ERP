from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..mcp.tools import call_tool, list_tools
from ..utils.auth import get_current_user

router = APIRouter(prefix="/api", tags=["AI Assistant"])


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


def _select_tool(message: str, context: ChatContext) -> tuple[str, dict[str, Any]]:
    text = message.lower()
    filters = context.filters or {}
    if "타임시트" in message or "미제출" in message or "제출" in message or context.route == "/timesheet":
        args: dict[str, Any] = {}
        if filters.get("week_start"):
            args["week_start"] = filters["week_start"]
        if "미제출" in message or "미작성" in message:
            args["status"] = "미작성"
        elif "작성중" in message:
            args["status"] = "작성중"
        elif "승인" in message:
            args["status"] = "승인"
        elif "반려" in message:
            args["status"] = "반려"
        return "get_timesheet_team_status", args
    if "의견" in message or "답변" in message or context.route == "/opinion-listening":
        return "list_waiting_opinions", {"limit": 10}
    if "프로젝트" in message or "pjt" in text or "pj-" in text or context.route == "/execution/projects":
        query = message
        for token in ["프로젝트", "검색", "찾아", "찾아줘", "요약", "알려줘"]:
            query = query.replace(token, " ")
        return "search_projects", {"query": query.strip(), "limit": 10}
    return "get_operational_summary", {"week_start": filters.get("week_start")}


def _summarize_tool_result(tool_name: str, result: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[str]]:
    if tool_name == "get_timesheet_team_status":
        counts = result.get("counts", {})
        rows = result.get("rows", [])
        missing = [row for row in rows if row.get("status") == "미작성"]
        answer = (
            f"{result.get('week_start')} ~ {result.get('week_end')} 타임시트 현황입니다. "
            f"총 {len(rows)}명, 총 입력 시간 {result.get('total_hours', 0)}h입니다. "
            f"상태별 건수는 " + ", ".join(f"{k} {v}명" for k, v in counts.items()) + "입니다."
        )
        if missing:
            names = ", ".join(row["employee_name"] for row in missing[:8])
            answer += f" 미작성자는 {names}" + (" 외 추가 인원이 있습니다." if len(missing) > 8 else "입니다.")
        cards = [{
            "title": "타임시트 현황",
            "metric": f"{len(rows)}명",
            "description": f"미작성 {counts.get('미작성', 0)}명 · 제출 {counts.get('제출', 0)}명 · 승인 {counts.get('승인', 0)}명",
            "items": rows[:8],
        }]
        return answer, cards, ["미제출자만 다시 보여줘", "승인된 타임시트만 요약해줘", "이번 주 운영 요약"]

    if tool_name == "list_waiting_opinions":
        items = result.get("items", [])
        answer = f"답변 대기 의견은 총 {result.get('total_waiting', 0)}건입니다."
        if items:
            answer += " 최근 대기 항목은 " + ", ".join(item["title"] for item in items[:5]) + "입니다."
        cards = [{
            "title": "의견 청취 답변 대기",
            "metric": f"{result.get('total_waiting', 0)}건",
            "description": "관리자 답변이 아직 등록되지 않은 의견입니다.",
            "items": items,
        }]
        return answer, cards, ["첫 번째 의견 답변 초안 작성", "답변 대기 목록 다시 조회", "운영 요약"]

    if tool_name == "search_projects":
        items = result.get("items", [])
        answer = f"프로젝트 검색 결과 {len(items)}건을 찾았습니다."
        if items:
            answer += " 상위 결과는 " + ", ".join(
                f"{item.get('project_no') or '-'} {item.get('project_name')}" for item in items[:5]
            ) + "입니다."
        cards = [{
            "title": "프로젝트 검색",
            "metric": f"{len(items)}건",
            "description": f"검색어: {result.get('query') or '최근 프로젝트'}",
            "items": items,
        }]
        return answer, cards, ["이 프로젝트 투입시간 요약", "계약금액 큰 순서로 설명", "운영 요약"]

    summary = result
    ts_counts = summary.get("timesheet", {}).get("counts", {})
    waiting = summary.get("opinions", {}).get("total_waiting", 0)
    active_projects = summary.get("projects", {}).get("active_count", 0)
    answer = (
        "ERP 운영 요약입니다. "
        f"타임시트는 미작성 {ts_counts.get('미작성', 0)}명, 제출 {ts_counts.get('제출', 0)}명, 승인 {ts_counts.get('승인', 0)}명입니다. "
        f"답변 대기 의견은 {waiting}건이고, 진행 중으로 분류되는 프로젝트는 {active_projects}건입니다."
    )
    cards = [
        {
            "title": "타임시트",
            "metric": f"미작성 {ts_counts.get('미작성', 0)}명",
            "description": f"{summary.get('timesheet', {}).get('week_start')} ~ {summary.get('timesheet', {}).get('week_end')}",
            "items": [],
        },
        {
            "title": "의견 청취",
            "metric": f"{waiting}건",
            "description": "답변 대기 의견",
            "items": summary.get("opinions", {}).get("items", []),
        },
        {
            "title": "프로젝트",
            "metric": f"{active_projects}건",
            "description": "진행 중 프로젝트 추정",
            "items": summary.get("projects", {}).get("recent", []),
        },
    ]
    return answer, cards, ["미제출 타임시트 조회", "답변 대기 의견 보여줘", "프로젝트 검색"]


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
