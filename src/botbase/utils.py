"""Small, dependency-free helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import datetime as dt


def plural(count: int, singular: str, suffix: str = "s") -> str:
    """``plural(1, "cat") -> "1 cat"``; ``plural(3, "cat") -> "3 cats"``."""
    word = singular if abs(count) == 1 else f"{singular}{suffix}"
    return f"{count} {word}"


def humanize_timedelta(delta: dt.timedelta) -> str:
    """Render a timedelta as ``"2d 3h 4m 5s"`` (largest two non-zero units)."""
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    days, rem = divmod(total, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, seconds = divmod(rem, 60)
    parts = [(days, "d"), (hours, "h"), (minutes, "m"), (seconds, "s")]
    shown = [f"{value}{unit}" for value, unit in parts if value] or ["0s"]
    return sign + " ".join(shown[:2])
