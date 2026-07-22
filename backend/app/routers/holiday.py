from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.holiday_sync import list_holidays, sync_holidays_for_year

router = APIRouter()


@router.get("/api/holiday")
async def get_holiday(year: str = Query(..., description="조회하고자 하는 연도 (YYYY)"), db: Session = Depends(get_db)):
    try:
        rows = list_holidays(db, year)
        if not rows:
            await sync_holidays_for_year(db, year)
            rows = list_holidays(db, year)
        return [row.date for row in rows]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        print(f"공휴일 조회 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="공휴일 데이터를 불러오지 못했습니다.",
        )


@router.post("/api/holiday/sync")
async def sync_holiday(year: str = Query(..., description="동기화할 연도 (YYYY)"), db: Session = Depends(get_db)):
    try:
        changed = await sync_holidays_for_year(db, year)
        rows = list_holidays(db, year)
        return {
            "year": year,
            "changed": changed,
            "total": len(rows),
            "holidays": [
                {
                    "no": row.id,
                    "year": row.year,
                    "month": row.month,
                    "day": row.day,
                    "content": row.content,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ],
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        print(f"공휴일 동기화 실패: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="공휴일 동기화 중 오류가 발생했습니다.",
        )