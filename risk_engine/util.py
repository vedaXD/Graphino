"""Small, dependency-free helpers. Real data is messy: coerce defensively."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable


def pick(props: dict | None, names: Iterable[str]) -> Any:
    """First non-empty value among candidate property names."""
    if not props:
        return None
    for n in names:
        v = props.get(n)
        if v is not None and v != "":
            return v
    return None


def to_float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def to_int(v: Any) -> int | None:
    f = to_float(v)
    return None if f is None else int(f)


def to_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def to_epoch(v: Any) -> float | None:
    """Unix seconds from seconds, milliseconds, numeric strings or ISO dates."""
    if v is None or isinstance(v, bool):
        return None
    f = to_float(v)
    if f is not None:
        return f / 1000.0 if f > 1e11 else f
    try:
        s = str(v).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def days_between(ts: float | None, now: float) -> float | None:
    return None if ts is None else (now - ts) / 86400.0


def short_hash(*parts: Any, n: int = 8) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:n]


def clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def clamp_float(v: Any, lo: float, hi: float, default: float) -> float:
    f = to_float(v)
    return default if f is None else max(lo, min(hi, f))


def usd(x: float) -> str:
    return f"${x:,.0f}"
