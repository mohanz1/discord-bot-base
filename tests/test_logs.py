from __future__ import annotations

import json
import logging

from botbase.logs import JsonFormatter, configure_logging


def test_configure_logging_text_sets_level_and_single_handler() -> None:
    configure_logging("DEBUG", "text")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert logging.getLogger("discord.http").level == logging.WARNING


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO", "text")
    configure_logging("INFO", "text")
    assert len(logging.getLogger().handlers) == 1


def test_json_formatter_emits_valid_json() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["message"] == "hello world"
    assert payload["logger"] == "x"


def test_configure_logging_json_roundtrips_a_record(capsys: object) -> None:
    configure_logging("INFO", "json")
    logging.getLogger("botbase.test").info("structured %s", "line")
    err = capsys.readouterr().err
    payload = json.loads(err.strip().splitlines()[-1])
    assert payload["message"] == "structured line"
    configure_logging("INFO", "text")


def test_configure_logging_rich_falls_back_when_unavailable(monkeypatch: object) -> None:
    import builtins

    real_import = builtins.__import__

    def deny_rich(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("rich"):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny_rich)
    configure_logging("INFO", "rich")
    assert len(logging.getLogger().handlers) == 1
    configure_logging("INFO", "text")


def test_json_formatter_includes_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), __import__("sys").exc_info())
    payload = json.loads(JsonFormatter().format(record))
    assert "boom" in payload["exc_info"]
