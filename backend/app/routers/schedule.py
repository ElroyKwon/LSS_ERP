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
    date: Optional[str] = None
    type: str
    category: Optional[str] = "company"
    user_name: str
    is_all_day: Optional[bool] = True
    start_time: Optional[str] = None
    end_time: Optional[str] = None

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
            orderBy='startTime',
            timeZone='Asia/Seoul'
        ).execute()
        
        google_events = events_result.get('items', [])
        
        formatted_schedules = []
        for event in google_events:
            start_info = event.get('start', {})
            is_all_day = 'date' in start_info
            
            if is_all_day:
                event_date = start_info.get('date')
                start_date = event_date
                start_time = None
                end_time = None
                
                # Google Calendar all-day end date is exclusive, so subtract 1 day
                end_date_str = event.get('end', {}).get('date', start_date)
                try:
                    dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                    end_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
                except Exception:
                    end_date = start_date
            else:
                date_time_str = start_info.get('dateTime', '')
                event_date = date_time_str[:10] if date_time_str else ''
                start_date = event_date
                start_time = date_time_str.replace('T', ' ')[:19] if date_time_str else None
                
                end_time_str = event.get('end', {}).get('dateTime', '')
                end_time = end_time_str.replace('T', ' ')[:19] if end_time_str else None
                end_date = end_time_str[:10] if end_time_str else event_date
            
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
                "type": schedule_type,
                "is_all_day": is_all_day,
                "start_time": start_time,
                "end_time": end_time,
                "start_date": start_date,
                "end_date": end_date
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
        
        display_summary = f"[{payload.user_name}] {payload.content}"
        
        if payload.is_all_day:
            start_date_str = payload.date
            if not start_date_str:
                raise HTTPException(status_code=400, detail="종일 일정은 date 필드가 필요합니다.")
            dt = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date_str = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
            
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
        else:
            if not payload.start_time or not payload.end_time:
                raise HTTPException(status_code=400, detail="시간 지정 일정은 start_time과 end_time 필드가 필요합니다.")
            start_dt = datetime.strptime(payload.start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(payload.end_time, "%Y-%m-%d %H:%M:%S")
            
            event = {
                'summary': display_summary,
                'description': f"유형: {payload.type} (사내 Timesheet 시스템 연동 - 등록자: {payload.user_name})",
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'Asia/Seoul',
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
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