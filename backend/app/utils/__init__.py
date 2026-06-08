from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))


def to_kst(dt) -> str | None:
    """UTC naive datetime → KST 문자열 (YYYY-MM-DD HH:mm)"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')


def to_kst_date(d) -> str | None:
    """date 또는 datetime → YYYY-MM-DD (날짜만)"""
    if d is None:
        return None
    return str(d)[:10]
