from __future__ import annotations

from tests.fixtures.dbext_models import FixtureNote  # noqa: F401 - registers the table


async def setup(bot: object) -> None:
    """Nothing to add; importing the model is the point."""
