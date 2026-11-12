from __future__ import annotations

from pathlib import Path

import pytest

from botbase import cli


def test_version_is_default(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "discord-bot-base" in out
    assert "discord.py" in out


def test_version_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["version"]) == 0
    assert "Python" in capsys.readouterr().out


def test_run_subcommand_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    from botbase.config import get_settings

    calls: list[object] = []
    monkeypatch.setattr("botbase.app.run", lambda settings=None: calls.append(settings))
    assert cli.main(["run"]) == 0
    assert calls == [get_settings()]


def test_run_uses_settings_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.fixtures.custom_settings import CustomSettings

    calls: list[object] = []
    monkeypatch.setattr("botbase.app.run", lambda settings=None: calls.append(settings))
    assert cli.main(["run", "--settings", "tests.fixtures.custom_settings:CustomSettings"]) == 0
    assert isinstance(calls[0], CustomSettings)


def test_run_env_file_with_base_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env = tmp_path / "prod.env"
    env.write_text("BOT_LOG_LEVEL=DEBUG\n")
    calls: list[object] = []
    monkeypatch.setattr("botbase.app.run", lambda settings=None: calls.append(settings))
    assert cli.main(["run", "--env-file", str(env)]) == 0
    assert calls[0].log_level == "DEBUG"  # type: ignore[attr-defined]


def test_settings_from_pyproject(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.botbase]\nsettings = "tests.fixtures.custom_settings:CustomSettings"\n'
    )
    assert cli.main(["ext", "list"]) == 0
    out = capsys.readouterr().out
    assert "tests.fixtures.extpkg.alpha" in out
    assert "tests.fixtures.extpkg.broken  (disabled)" in out
    assert "botbase.ext" not in out


def test_pyproject_without_botbase_table_uses_base(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert cli.main(["ext", "list"]) == 0
    assert "botbase.ext.meta" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("spec", "fragment"),
    [
        ("no_colon_here", "expected 'module:ClassName'"),
        ("tests.fixtures.does_not_exist:X", "Cannot load"),
        ("tests.fixtures.custom_settings:Missing", "Cannot load"),
        ("tests.fixtures.custom_settings:NotSettings", "not a botbase.Settings subclass"),
    ],
)
@pytest.mark.parametrize("command", [["run"], ["ext", "list"], ["sync"]])
def test_bad_settings_spec_is_graceful(
    spec: str,
    fragment: str,
    command: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main([*command, "--settings", spec]) == 1
    assert fragment in capsys.readouterr().out


def test_ext_list_reports_broken_package(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_EXTENSION_PACKAGES", '["tests.fixtures.badsubpkg"]')
    assert cli.main(["ext", "list"]) == 1
    out = capsys.readouterr().out
    assert "tests.fixtures.badsubpkg.ok" in out
    assert "tests.fixtures.badsubpkg.broken_sub  (failed to import: optional dependency missing)" in out


def test_ext_list_skips_disabled_sub_package(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOT_EXTENSION_PACKAGES", '["tests.fixtures.badsubpkg"]')
    monkeypatch.setenv("BOT_DISABLED_EXTENSIONS", '["broken_sub"]')
    assert cli.main(["ext", "list"]) == 0
    assert "failed" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        ["db", "revision", "-m", "add notes"],
        ["db", "revision", "--message", "add notes"],
        ["db", "revision", "add notes"],
    ],
)
def test_db_revision_message_forms(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("alembic")
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        "botbase.database.migrations.revision",
        lambda message, *, autogenerate: calls.append((message, autogenerate)),
    )
    assert cli.main([*argv, "--no-autogenerate"]) == 0
    assert calls == [("add notes", False)]


def test_db_revision_requires_message(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["db", "revision"])
    assert excinfo.value.code == 2
    assert "message is required" in capsys.readouterr().err


def test_ext_list(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_EXTENSION_PACKAGES", '["botbase.ext"]')
    monkeypatch.setenv("BOT_DISABLED_EXTENSIONS", '["meta"]')
    from botbase.config import get_settings

    get_settings.cache_clear()
    rc = cli.main(["ext", "list"])
    get_settings.cache_clear()
    out = capsys.readouterr().out
    assert rc == 0
    assert "botbase.ext.errors" in out
    assert "botbase.ext.meta  (disabled)" in out


def test_sync_parser_accepts_guilds_and_clear() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["sync", "--guild", "1", "--guild", "2", "--clear"])
    assert args.guild == [1, 2]
    assert args.clear is True
    assert args.func is cli._cmd_sync


def test_sync_without_token_is_graceful(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    from botbase.config import get_settings

    get_settings.cache_clear()
    rc = cli.main(["sync"])
    get_settings.cache_clear()
    assert rc == 1
    assert "token" in capsys.readouterr().out.lower()


@pytest.mark.db
def test_db_current_without_alembic_ini_is_graceful(
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["db", "current"])
    assert rc == 1
    assert "alembic.ini" in capsys.readouterr().out
