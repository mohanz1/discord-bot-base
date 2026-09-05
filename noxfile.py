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
nox.options.sessions = ["lint", "types", "slots", "spelling", "tests", "docs"]

EXTRAS = ("--extra", "db", "--extra", "rich")


def _uv_run(session: nox.Session, *args: str) -> None:
    # Python version comes from the ambient uv (UV_PYTHON / .python-version);
    # CI drives the 3.13/3.14 matrix, not nox.
    session.run("uv", "run", "--frozen", *EXTRAS, *args, external=True)


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


@nox.session
def docs(session: nox.Session) -> None:
    """Build the documentation site (strict — warnings fail)."""
    _uv_run(session, "mkdocs", "build", "--strict", *session.posargs)


@nox.session
def tests(session: nox.Session) -> None:
    """pytest with coverage (runs on the project's Python; CI covers 3.13 + 3.14)."""
    _uv_run(session, "pytest", *session.posargs)


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
            # The rendered project has no lockfile yet; let `uv sync` create one
            # even when the parent job sets UV_FROZEN=1.
            env = {"UV_FROZEN": "0", "VIRTUAL_ENV": ""}
            session.chdir(str(dst))
            session.run("uv", "sync", external=True, env=env)
            session.run("uv", "run", "ruff", "check", ".", external=True, env=env)
            session.run("uv", "run", "ruff", "format", "--check", ".", external=True, env=env)
            session.run("uv", "run", "ty", "check", external=True, env=env)
            session.run("uv", "run", "pytest", "-q", external=True, env=env)
        finally:
            session.chdir(str(root))
            shutil.rmtree(dst, ignore_errors=True)
