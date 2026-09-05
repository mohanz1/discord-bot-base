from __future__ import annotations

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
    calls: list[object] = []
    monkeypatch.setattr("botbase.app.run", lambda settings=None: calls.append(settings))
    assert cli.main(["run"]) == 0
    assert calls == [None]


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
