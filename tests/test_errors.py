from __future__ import annotations

from botbase.errors import ExtensionLoadError, MissingDependencyError


def test_extension_load_error_lists_names() -> None:
    err = ExtensionLoadError({"a.b": RuntimeError("x"), "a.c": ValueError("y")})
    assert err.failures.keys() == {"a.b", "a.c"}
    assert "a.b" in str(err)
    assert "a.c" in str(err)
    assert "2 extension(s)" in str(err)


def test_missing_dependency_error_message() -> None:
    err = MissingDependencyError("The database layer", "db")
    assert "discord-bot-base[db]" in str(err)
    assert err.extra == "db"
