from __future__ import annotations

import math

from botbase.app import Bot
from botbase.ext.meta import Meta, _AboutView, _build_about_embed, _grade, _meter, refresh_about
from tests.conftest import FakeInteraction, FakeMessage

_PUBLIC_FIELDS = {"version", "python", "event loop", "uptime", "gateway", "commands"}


def test_meter_and_grade_handle_non_finite() -> None:
    assert set(_meter(math.nan)) == {"\N{LIGHT SHADE}"}
    assert _meter(10_000.0).endswith("\N{FULL BLOCK}")
    assert _grade(math.nan)[1].value == 0x99AAB5  # neutral colour when not connected
    assert _grade(20.0)[1].value != _grade(300.0)[1].value  # green != red


async def test_about_view_timeout_disables_button() -> None:
    view = _AboutView()
    view.message = FakeMessage()  # type: ignore[assignment]
    await view.on_timeout()
    assert all(child.disabled for child in view.children)
    assert view.message.edits


async def test_meta_loads(bot: Bot) -> None:
    await bot.load_extension("botbase.ext.meta")
    assert bot.get_cog("Meta") is not None


async def test_ping_reports_latencies(bot: Bot, interaction: FakeInteraction) -> None:
    await Meta.ping.callback(Meta(bot), interaction)
    assert interaction.response.messages[0]["content"] == "pinging\N{HORIZONTAL ELLIPSIS}"
    embed = interaction.edited[0]["embed"]
    assert "```ansi" in embed.description
    for token in ("gateway", "rest", "loop"):
        assert token in embed.description
    assert embed.colour is not None


def test_about_embed_hides_infra_from_non_owner(bot: Bot) -> None:
    embed = _build_about_embed(bot, owner=False)
    fields = {f.name: f.value for f in embed.fields}
    assert set(fields) == _PUBLIC_FIELDS
    assert "discord.py" in fields["version"]
    assert embed.footer.text is None


def test_about_embed_owner_view_adds_infra(bot: Bot) -> None:
    names = {f.name for f in _build_about_embed(bot, owner=True).fields}
    assert names >= _PUBLIC_FIELDS
    assert {"host", "memory", "process", "guilds", "gc gen counts"} <= names


async def test_about_command_sends_embed_and_view(bot: Bot, interaction: FakeInteraction) -> None:
    bot.owner_id = interaction.user.id
    await Meta.about.callback(Meta(bot), interaction)
    message = interaction.response.messages[0]
    assert message["embed"].fields
    assert isinstance(message["view"], _AboutView)


async def test_refresh_about_rerenders_with_owner_gate(bot: Bot) -> None:
    bot.owner_id = 1  # matches FakeInteraction default user id
    inner = FakeInteraction(client=bot)
    await refresh_about(inner, _AboutView())
    payload = inner.response.messages[0]
    assert payload["edit_message"] is True
    assert {f.name for f in payload["embed"].fields} >= {"host", "guilds"}


async def test_refresh_about_non_owner_gets_public_only(bot: Bot) -> None:
    bot.owner_id = 424242
    inner = FakeInteraction(client=bot)
    await refresh_about(inner, _AboutView())
    names = {f.name for f in inner.response.messages[0]["embed"].fields}
    assert names == _PUBLIC_FIELDS


async def test_uptime_replies(bot: Bot, interaction: FakeInteraction) -> None:
    await Meta.uptime.callback(Meta(bot), interaction)
    assert "Up for" in interaction.response.messages[0]["content"]
