"""Task runner. Sessions delegate to ``uv run`` so there is a single, locked
environment (mirrors CI).

    uv run nox                 # lint + types + slots + spelling + tests
    uv run nox -s format       # apply ruff autofixes + formatting
    uv run nox -s tests        # both Python versions
    uv run nox -s template     # render the copier template and check the output
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import nox

nox.options.default_venv_backend = "none"
nox.options.sessions = ["lint", "types", "slots", "spelling", "tests"]

PYTHON_VERSIONS = ["3.13", "3.14"]
EXTRAS = ("--extra", "db", "--extra", "rich")


def _uv_run(session: nox.Session, *args: str, python: str | None = None) -> None:
    cmd = ["uv", "run", "--frozen"]
    if python:
        cmd += ["--python", python]
    session.run(*cmd, *EXTRAS, *args, external=True)


@nox.session
def format(session: nox.Session) -> None:  # noqa: A001 - conventional session name
    """Apply ruff autofixes and formatting."""
    _uv_run(session, "ruff", "check", ".", "--fix")
    _uv_run(session, "ruff", "format", ".")


@nox.session
def lint(session: nox.Session) -> None:
    """ruff lint + format check."""
    _uv_run(session, "ruff", "check", ".")
    _uv_run(session, "ruff", "format", "--check", ".")


@nox.session
def types(session: nox.Session) -> None:
    """ty type check."""
    _uv_run(session, "ty", "check")


@nox.session
def slots(session: nox.Session) -> None:
    """slotscheck: verify __slots__ correctness."""
    _uv_run(session, "slotscheck", "-m", "botbase")


@nox.session
def spelling(session: nox.Session) -> None:
    """codespell."""
    _uv_run(session, "codespell")


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """pytest with coverage, on each supported Python."""
    _uv_run(session, "pytest", *session.posargs, python=session.python)


@nox.session
def template(session: nox.Session) -> None:
    """Render template/ (with and without a database) and run its own checks."""
    from copier import run_copy

    root = Path(__file__).parent
    template_dir = root / "template"
    base = {
        "project_name": "Demo Bot",
        "project_slug": "demo-bot",
        "package_import_name": "demo_bot",
        "author_name": "Test",
        "author_email": "test@example.com",
        "github_owner": "example",
        "python_floor": "3.13",
    }
    for with_db in (False, True):
        dst = Path(tempfile.mkdtemp(prefix=f"tmpl-db{int(with_db)}-"))
        try:
            run_copy(
                str(template_dir),
                str(dst),
                data={**base, "use_database": with_db},
                defaults=True,
                unsafe=True,
            )
            session.log(f"rendered template (use_database={with_db}) -> {dst}")
            # Smoke tests run before discord-bot-base is on PyPI: point at this checkout.
            pyproject = dst / "pyproject.toml"
            pyproject.write_text(
                pyproject.read_text() + f'\n[tool.uv.sources]\ndiscord-bot-base = {{ path = "{root}" }}\n'
            )
            session.chdir(str(dst))
            session.run("uv", "sync", external=True)
            session.run("uv", "run", "ruff", "check", ".", external=True)
            session.run("uv", "run", "ruff", "format", "--check", ".", external=True)
            session.run("uv", "run", "ty", "check", external=True)
            session.run("uv", "run", "pytest", "-q", external=True)
        finally:
            session.chdir(str(root))
            shutil.rmtree(dst, ignore_errors=True)
