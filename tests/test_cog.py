from __future__ import annotations

import pytest

from botbase.app import Bot
from botbase.cog import BaseCog


class Sample(BaseCog):
    pass


def test_basecog_exposes_bot_and_settings(bot: Bot) -> None:
    cog = Sample(bot)
    assert cog.bot is bot
    assert cog.settings is bot.settings
    assert cog.log.name == "botbase.ext.test_cog"


def test_basecog_db_delegates_and_raises(bot: Bot) -> None:
    cog = Sample(bot)
    with pytest.raises(RuntimeError, match="Database not configured"):
        _ = cog.db
