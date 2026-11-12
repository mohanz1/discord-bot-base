from __future__ import annotations

import pytest
from discord.ext import commands

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
    cause = excinfo.value.__cause__
    assert isinstance(cause, BaseExceptionGroup)
    assert [type(e) for e in cause.exceptions] == [RuntimeError]


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


async def test_reload_all_unwraps_extension_failed(bot: object, monkeypatch: pytest.MonkeyPatch) -> None:
    await load_extensions(bot, packages=[FIXTURES], disabled=["broken"])
    root = RuntimeError("boom")

    async def failing_reload(name: str) -> None:
        raise commands.ExtensionFailed(name, root)

    monkeypatch.setattr(bot, "reload_extension", failing_reload)
    report = await reload_all(bot)
    assert report.failed
    assert all(exc is root for exc in report.failed.values())


BADSUB = "tests.fixtures.badsubpkg"


def test_discover_propagates_import_errors_by_default() -> None:
    with pytest.raises(RuntimeError, match="optional dependency"):
        discover_extensions(BADSUB)


def test_discover_on_error_reports_and_skips_branch() -> None:
    errors: dict[str, Exception] = {}
    found = discover_extensions(BADSUB, on_error=errors.__setitem__)
    assert found == [f"{BADSUB}.ok"]
    assert list(errors) == [f"{BADSUB}.broken_sub"]
    assert isinstance(errors[f"{BADSUB}.broken_sub"], RuntimeError)


def test_discover_on_error_for_missing_top_level_package() -> None:
    errors: dict[str, Exception] = {}
    assert discover_extensions("tests.fixtures.does_not_exist", on_error=errors.__setitem__) == []
    assert isinstance(errors["tests.fixtures.does_not_exist"], ModuleNotFoundError)


def test_discover_skip_prevents_import() -> None:
    seen: list[str] = []

    def skip(name: str) -> bool:
        seen.append(name)
        return True

    assert discover_extensions(BADSUB, skip=skip) == [f"{BADSUB}.ok"]
    assert seen == [f"{BADSUB}.broken_sub"]


async def test_load_survives_broken_sub_package(bot: object) -> None:
    report = await load_extensions(bot, packages=[BADSUB])
    assert report.loaded == [f"{BADSUB}.ok"]
    assert isinstance(report.failed[f"{BADSUB}.broken_sub"], RuntimeError)


async def test_load_disabled_sub_package_is_not_imported(bot: object) -> None:
    report = await load_extensions(bot, packages=[BADSUB], disabled=["broken_sub"])
    assert report.ok
    assert report.skipped == [f"{BADSUB}.broken_sub"]
    assert report.loaded == [f"{BADSUB}.ok"]


async def test_load_strict_raises_for_broken_sub_package(bot: object) -> None:
    with pytest.raises(ExtensionLoadError, match="broken_sub"):
        await load_extensions(bot, packages=[BADSUB], strict=True)
