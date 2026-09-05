from __future__ import annotations

import datetime as dt

import pytest

from botbase.utils import humanize_timedelta, plural


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "0 cats"), (1, "1 cat"), (2, "2 cats"), (-1, "-1 cat")],
)
def test_plural(count: int, expected: str) -> None:
    assert plural(count, "cat") == expected


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (dt.timedelta(0), "0s"),
        (dt.timedelta(seconds=5), "5s"),
        (dt.timedelta(minutes=3, seconds=9), "3m 9s"),
        (dt.timedelta(days=2, hours=1, minutes=30), "2d 1h"),
        (dt.timedelta(seconds=-30), "-30s"),
    ],
)
def test_humanize_timedelta(delta: dt.timedelta, expected: str) -> None:
    assert humanize_timedelta(delta) == expected
