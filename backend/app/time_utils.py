from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """SQLite drops tzinfo, so use naive UTC everywhere to keep `due <= now` comparisons sane."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
