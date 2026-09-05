from __future__ import annotations

import pytest

from botbase.app import Bot
from botbase.config import Settings
from botbase.ext.help import Help
from tests.conftest import FakeInteraction


@pytest.fixture
async def loaded_bot() -> Bot:
    bot = Bot(Settings(_env_file=None, token=None, sync_commands_on_startup=False))
    bot.owner_id = 999_999_999  # a real, non-matching id so is_owner() never hits the API
    await bot.setup_hook()  # loads botbase.ext.* into the tree
    yield bot
    await bot.close()


def _overview_text(interaction: FakeInteraction) -> str:
    embed = interaction.response.messages[0]["embed"]
    return "\n".join(f.value for f in embed.fields)


async def test_overview_lists_public_commands(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    await Help.help_cmd.callback(Help(loaded_bot), interaction, None)
    text = _overview_text(interaction)
    assert "/ping" in text
    assert "/help" in text


async def test_overview_hides_dev_from_normal_user(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    await Help.help_cmd.callback(Help(loaded_bot), interaction, None)
    assert "/dev" not in _overview_text(interaction)


async def test_overview_shows_dev_to_owner(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    loaded_bot.owner_id = interaction.user.id
    await Help.help_cmd.callback(Help(loaded_bot), interaction, None)
    assert "/dev exec" in _overview_text(interaction)


async def test_detail_for_a_plain_command(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    await Help.help_cmd.callback(Help(loaded_bot), interaction, "ping")
    embed = interaction.response.messages[0]["embed"]
    assert embed.title == "/ping"
    assert embed.description


async def test_detail_unknown_command(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    await Help.help_cmd.callback(Help(loaded_bot), interaction, "does-not-exist")
    assert "No command" in interaction.response.messages[0]["content"]


async def test_detail_of_hidden_command_does_not_leak(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    await Help.help_cmd.callback(Help(loaded_bot), interaction, "dev exec")
    assert "No command" in interaction.response.messages[0]["content"]


async def test_detail_group_and_params_for_owner(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    loaded_bot.owner_id = interaction.user.id

    await Help.help_cmd.callback(Help(loaded_bot), interaction, "dev")
    group_fields = {f.name for f in interaction.response.messages[0]["embed"].fields}
    assert "/dev exec" in group_fields

    other = FakeInteraction(user_id=interaction.user.id)
    await Help.help_cmd.callback(Help(loaded_bot), other, "dev exec")
    exec_fields = {f.name for f in other.response.messages[0]["embed"].fields}
    assert {"parameters", "access"} <= exec_fields


async def test_autocomplete_filters_and_hides(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    choices = await Help(loaded_bot)._complete(interaction, "p")
    values = {c.value for c in choices}
    assert "ping" in values
    assert not any(v.startswith("dev") for v in values)


async def test_autocomplete_includes_dev_for_owner(loaded_bot: Bot, interaction: FakeInteraction) -> None:
    loaded_bot.owner_id = interaction.user.id
    choices = await Help(loaded_bot)._complete(interaction, "exec")
    assert any(c.value == "dev exec" for c in choices)
