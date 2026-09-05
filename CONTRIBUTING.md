# Contributing

Thanks for helping out.

## Setup

```bash
uv sync --all-extras          # dev group is included by default
uv run pre-commit install
```

## Before you push

```bash
uv run nox            # lint + types + slots + spelling + tests (exactly what CI runs)
uv run nox -s format  # apply ruff autofixes + formatting
```

Everything must be green. CI enforces `ruff` (lint + format), `ty`, `slotscheck`,
`codespell`, and `pytest` on Python 3.13 and 3.14 with a **90% branch-coverage**
gate, plus a copier-template smoke test.

## Conventions

- New behaviour needs tests. Test *our* logic, not discord.py.
- Keep the public surface small — re-export from `botbase/__init__.py` only what
  downstream bots actually need.
- Runtime dependencies land in `[project.dependencies]`; anything optional goes
  behind an extra (`db`, `speedups`, `rich`). Dev tooling goes in the `dev`
  dependency group.
- Update `CHANGELOG.md` under `[Unreleased]`.
- Conventional-ish commit subjects (`feat:`, `fix:`, `docs:`, `chore:`) are
  appreciated but not enforced.

## Releasing (maintainers)

Bump `version` in `pyproject.toml`, move `[Unreleased]` to a dated section in
`CHANGELOG.md`, tag `vX.Y.Z`, push the tag. `release.yml` builds and publishes to
PyPI via Trusted Publishing.
