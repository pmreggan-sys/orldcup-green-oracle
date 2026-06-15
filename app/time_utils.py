from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone


BEIJING_TZ = timezone(timedelta(hours=8))


def to_beijing(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(BEIJING_TZ)


def format_beijing(dt: datetime | None, fmt: str = "%m-%d %H:%M") -> str | None:
    localized = to_beijing(dt)
    if localized is None:
        return None
    return localized.strftime(fmt)
