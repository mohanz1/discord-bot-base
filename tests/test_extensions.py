from __future__ import annotations

import pytest

from botbase.errors import ExtensionLoadError
from botbase.extensions import discover_extensions, load_extensions, reload_all

FIXTURES = "tests.fixtures.extpkg"


def test_discover_finds_modules_recursively() -> None:
    found = discover_extensions(FIXTURES)
    assert f"{FIXTURES}.alpha" in found
    assert f"{FIXTURES}.beta" in found
    assert f"{FIXTURES}.sub.gamma" in found


def test_discover_skips_underscore_modules() -> None:
    found = discover_extensions(FIXTURES)
    assert all(not name.rpartition(".")[2].startswith("_") for name in found)
    assert f"{FIXTURES}._private" not in found


def test_discover_non_recursive() -> None:
    found = discover_extensions(FIXTURES, recursive=False)
    assert f"{FIXTURES}.sub.gamma" not in found
    assert f"{FIXTURES}.alpha" in found


def test_discover_plain_module_returns_itself() -> None:
    assert discover_extensions(f"{FIXTURES}.alpha") == [f"{FIXTURES}.alpha"]


async def test_load_reports_success_and_failure(bot: object) -> None:
    report = await load_extensions(bot, packages=[FIXTURES], disabled=["broken"])
    assert f"{FIXTURES}.alpha" in report.loaded
    assert f"{FIXTURES}.broken" in report.skipped
    assert report.ok


async def test_load_collects_failures_without_strict(bot: object) -> None:
    report = await load_extensions(bot, packages=[FIXTURES])
    assert f"{FIXTURES}.broken" in report.failed
    assert isinstance(report.failed[f"{FIXTURES}.broken"], RuntimeError)
    assert not report.ok


async def test_load_strict_raises(bot: object) -> None:
    with pytest.raises(ExtensionLoadError) as excinfo:
        await load_extensions(bot, packages=[FIXTURES], strict=True)
    assert "broken" in str(excinfo.value)


async def test_disabled_matches_dotted_and_leaf(bot: object) -> None:
    report = await load_extensions(
        bot,
        packages=[FIXTURES],
        disabled=[f"{FIXTURES}.alpha", "beta", "broken"],
    )
    assert f"{FIXTURES}.alpha" in report.skipped
    assert f"{FIXTURES}.beta" in report.skipped
    assert report.loaded == [f"{FIXTURES}.sub.gamma"]


async def test_reload_all(bot: object) -> None:
    await load_extensions(bot, packages=[FIXTURES], disabled=["broken"])
    report = await reload_all(bot)
    assert f"{FIXTURES}.alpha" in report.loaded
    assert report.ok
