from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Holiday

HOLIDAY_API_URL = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getHoliDeInfo"


def _normalize_year(year: str | int) -> str:
    value = str(year).strip()
    if len(value) != 4 or not value.isdigit():
        raise ValueError("year must be YYYY")
    return value


def _apply_statutory_overrides(holidays: list[dict[str, str]], year: str) -> list[dict[str, str]]:
    if int(year) >= 2026:
        has_constitution_day = any(
            item["year"] == year and item["month"] == "07" and item["day"] == "17"
            for item in holidays
        )
        if not has_constitution_day:
            holidays.append({"year": year, "month": "07", "day": "17", "content": "제헌절"})
    return holidays


def list_holidays(db: Session, year: str | int) -> list[Holiday]:
    target_year = _normalize_year(year)
    return (
        db.query(Holiday)
        .filter(Holiday.year == target_year)
        .order_by(Holiday.year.asc(), Holiday.month.asc(), Holiday.day.asc(), Holiday.content.asc())
        .all()
    )


async def fetch_public_holidays(year: str | int) -> list[dict[str, str]]:
    target_year = _normalize_year(year)
    service_key = settings.holiday_service_key
    if not service_key:
        return _apply_statutory_overrides([], target_year)

    params = {
        "solYear": target_year,
        "numOfRows": "100",
        "_type": "json",
        "ServiceKey": service_key,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(HOLIDAY_API_URL, params=params, timeout=10.0)
        response.raise_for_status()

    body = response.json().get("response", {}).get("body", {})
    items = body.get("items", {}).get("item", [])
    if not items:
        return _apply_statutory_overrides([], target_year)
    if isinstance(items, dict):
        items = [items]

    holidays: list[dict[str, str]] = []
    for item in items:
        if item.get("isHoliday") != "Y":
            continue
        locdate = str(item.get("locdate", ""))
        if len(locdate) != 8 or not locdate.isdigit():
            continue
        holidays.append({
            "year": locdate[0:4],
            "month": locdate[4:6],
            "day": locdate[6:8],
            "content": str(item.get("dateName") or "공휴일").strip() or "공휴일",
        })
    return _apply_statutory_overrides(holidays, target_year)


def upsert_holidays(db: Session, holidays: Iterable[dict[str, str]]) -> int:
    changed = 0
    now = datetime.now()
    for item in holidays:
        row = (
            db.query(Holiday)
            .filter(
                Holiday.year == item["year"],
                Holiday.month == item["month"],
                Holiday.day == item["day"],
            )
            .first()
        )
        if row:
            if row.content != item["content"]:
                row.content = item["content"]
                row.updated_at = now
                changed += 1
            continue
        db.add(Holiday(
            year=item["year"],
            month=item["month"],
            day=item["day"],
            content=item["content"],
            created_at=now,
            updated_at=now,
        ))
        changed += 1
    if changed:
        db.commit()
    return changed


async def sync_holidays_for_year(db: Session, year: str | int) -> int:
    holidays = await fetch_public_holidays(year)
    return upsert_holidays(db, holidays)
