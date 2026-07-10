import os
import re
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / "google_calendar.env")

router = APIRouter(
    prefix="/api/schedules",
    tags=["Schedules"]
)

class ScheduleCreate(BaseModel):
    content: str
    date: str
    type: str
    category: Optional[str] = "company"
    user_name: str

SCOPES = ['https://www.googleapis.com/auth/calendar']

env_credentials_dir = os.getenv("GOOGLE_CUSTOM_CREDENTIALS_DIR")
FILE_NAME_WORK = os.getenv("GOOGLE_CUSTOM_KEY_WORK_NAME")
HARDCODED_COMPANY_ID = os.getenv("GOOGLE_CUSTOM_CALENDAR_COMPANY_ID")
FILE_NAME_REFRESH = os.getenv("GOOGLE_CUSTOM_KEY_REFRESH_NAME")
HARDCODED_REFRESH_CALENDAR_ID = os.getenv("GOOGLE_CUSTOM_CALENDAR_REFRESH_ID")

if env_credentials_dir:
    CREDENTIALS_DIR = str((BASE_DIR / env_credentials_dir).resolve())
else:
    CREDENTIALS_DIR = None

_google_services_cache: Dict[str, Tuple[any, str]] = {}


def get_calendar_config_and_service(category: str):
    if category in _google_services_cache:
        return _google_services_cache[category]

    if not CREDENTIALS_DIR:
        raise HTTPException(
            status_code=500,
            detail="환경 변수 'GOOGLE_CUSTOM_CREDENTIALS_DIR'이 정의되지 않았습니다."
        )

    if category == "refresh":
        json_path = os.path.join(CREDENTIALS_DIR, FILE_NAME_REFRESH or "")
        calendar_id = HARDCODED_REFRESH_CALENDAR_ID
    else:
        json_path = os.path.join(CREDENTIALS_DIR, FILE_NAME_WORK or "")
        calendar_id = HARDCODED_COMPANY_ID
        
    if not json_path or not os.path.exists(json_path):
        raise HTTPException(
            status_code=500, 
            detail=f"인증에 필요한 구글 JSON 키 파일이 경로에 없습니다: {json_path}"
        )
        
    creds = service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    
    _google_services_cache[category] = (service, calendar_id)
    return service, calendar_id


@router.get("")
def get_schedules(category: str = Query("company", description="company 또는 refresh")):
    try:
        service, target_calendar_id = get_calendar_config_and_service(category)
        
        events_result = service.events().list(
            calendarId=target_calendar_id,
            maxResults=250,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        google_events = events_result.get('items', [])
        
        formatted_schedules = []
        for event in google_events:
            start_info = event.get('start', {})
            event_date = start_info.get('date') or start_info.get('dateTime', '')[:10]
            
            raw_summary = event.get('summary', '제목 없음')
            content = raw_summary
            user_name = ""  
            
            if raw_summary.startswith("[") and "]" in raw_summary:
                try:
                    match = re.match(r"^\[(.*?)\]\s*(.*)$", raw_summary)
                    if match:
                        user_name = match.group(1).strip()
                        content = match.group(2).strip()
                except Exception:
                    pass
            
            desc = event.get('description', '')
            schedule_type = "success" 
            
            if "유형:" in desc:
                try:
                    raw_type = desc.split("유형:")[1].split("(")[0].strip()
                    if raw_type in ["정상", "업무", "success"]:
                        schedule_type = "success"
                    elif raw_type in ["경고", "warning"]:
                        schedule_type = "warning"
                    elif raw_type in ["중요", "error", "야근"]:
                        schedule_type = "error"
                    elif raw_type in ["진행중", "processing"]:
                        schedule_type = "processing"
                    elif raw_type in ["기타", "default"]:
                        schedule_type = "default"
                    else:
                        schedule_type = raw_type
                except Exception:
                    pass

            formatted_schedules.append({
                "id": event.get('id'),
                "content": content,          
                "user_name": user_name,      
                "date": event_date,
                "type": schedule_type
            })
            
        return formatted_schedules

    except HttpError as he:
        print(f"\n=== GOOGLE CALENDAR API HTTP ERROR ({category}) ===")
        print(f"Status Code: {he.resp.status}, Reason: {he.content}")
        raise HTTPException(status_code=he.resp.status, detail="구글 캘린더 API 연동 중 오류 발생")
    except Exception as e:
        print(f"\n=== GOOGLE CALENDAR FETCH ERROR ({category}) ===")
        traceback.print_exc()
        print("==================================================\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구글 ({category}) 일정 불러오기 실패 원인: {str(e)}"
        )


@router.post("")
def create_schedule(payload: ScheduleCreate):
    try:
        service, target_calendar_id = get_calendar_config_and_service(payload.category)
        
        start_date_str = payload.date
        dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date_str = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        
        display_summary = f"[{payload.user_name}] {payload.content}"
        
        event = {
            'summary': display_summary,
            'description': f"유형: {payload.type} (사내 Timesheet 시스템 연동 - 등록자: {payload.user_name})",
            'start': {
                'date': start_date_str,
                'timeZone': 'Asia/Seoul',
            },
            'end': {
                'date': end_date_str,
                'timeZone': 'Asia/Seoul',
            },
        }
        
        google_result = service.events().insert(calendarId=target_calendar_id, body=event).execute()
        
        return {
            "status": "success",
            "id": google_result.get('id')
        }
        
    except HttpError as he:
        print(f"\n=== GOOGLE CALENDAR API HTTP ERROR ({payload.category}) ===")
        print(f"Status Code: {he.resp.status}, Reason: {he.content}")
        raise HTTPException(status_code=he.resp.status, detail="구글 캘린더 쓰기 권한이 없거나 API 오류가 발생했습니다.")
    except Exception as e:
        print(f"\n=== GOOGLE CALENDAR INSERT ERROR ({payload.category}) ===")
        traceback.print_exc()
        print("==================================================\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"구글 API ({payload.category}) 전송 실패 원인: {str(e)}"
        )