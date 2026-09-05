from __future__ import annotations

import pytest
from discord import app_commands

from botbase.app import Bot
from botbase.ext.admin import Admin, _cleanup_code, _resolve
from tests.conftest import FakeInteraction

FIXTURES = "tests.fixtures.extpkg"


def _last(interaction: FakeInteraction) -> str:
    return str(interaction.followup.messages[-1]["content"])


@pytest.fixture
def owner_bot(bot: Bot, interaction: FakeInteraction) -> Bot:
    bot.owner_id = interaction.user.id
    return bot


# -- cleanup / resolve --------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("```py\nreturn 1\n```", "return 1"),
        ("`return 2`", "return 2"),
        ("  return 3  ", "return 3"),
    ],
)
def test_cleanup_code(raw: str, expected: str) -> None:
    assert _cleanup_code(raw) == expected


async def test_resolve_matches_loaded_leaf_and_dotted(owner_bot: Bot) -> None:
    await owner_bot.load_extension(f"{FIXTURES}.alpha")
    assert _resolve(owner_bot, f"{FIXTURES}.alpha") == f"{FIXTURES}.alpha"
    assert _resolve(owner_bot, "alpha") == f"{FIXTURES}.alpha"
    assert _resolve(owner_bot, "does.not.exist") == "does.not.exist"


# -- owner gate -------------------------------------------------------------------


async def test_interaction_check_allows_owner(owner_bot: Bot, interaction: FakeInteraction) -> None:
    assert await Admin(owner_bot).interaction_check(interaction) is True


async def test_interaction_check_blocks_others(bot: Bot, interaction: FakeInteraction) -> None:
    bot.owner_id = 424242
    with pytest.raises(app_commands.CheckFailure):
        await Admin(bot).interaction_check(interaction)


# -- reload / load / unload -----------------------------------------------------


async def test_reload_one(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await owner_bot.load_extension(f"{FIXTURES}.alpha")
    await Admin.reload.callback(Admin(owner_bot), interaction, "alpha")
    assert f"reloaded `{FIXTURES}.alpha`" in _last(interaction)


async def test_reload_unknown_reports_error(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin.reload.callback(Admin(owner_bot), interaction, "nope")
    assert "could not reload" in _last(interaction)


async def test_reload_no_arg_opens_picker(owner_bot: Bot, interaction: FakeInteraction) -> None:
    from botbase.ext.admin import _ReloadView

    await owner_bot.load_extension(f"{FIXTURES}.alpha")
    await Admin.reload.callback(Admin(owner_bot), interaction, None)
    assert isinstance(interaction.response.messages[0]["view"], _ReloadView)


async def test_reload_select_reloads_chosen(owner_bot: Bot) -> None:
    from botbase.ext.admin import _ReloadView

    await owner_bot.load_extension(f"{FIXTURES}.alpha")
    await owner_bot.load_extension(f"{FIXTURES}.beta")
    view = _ReloadView(owner_bot)
    select = view.children[0]
    select._values = [f"{FIXTURES}.alpha"]  # type: ignore[attr-defined]
    inner = FakeInteraction(client=owner_bot)
    await select.callback(inner)  # type: ignore[attr-defined]
    payload = inner.response.messages[0]
    assert payload["edit_message"] is True
    assert "reloaded 1" in str(payload["content"])


async def test_reload_select_all(owner_bot: Bot) -> None:
    from botbase.ext.admin import _RELOAD_ALL, _ReloadView

    await owner_bot.load_extension(f"{FIXTURES}.alpha")
    view = _ReloadView(owner_bot)
    select = view.children[0]
    select._values = [_RELOAD_ALL]  # type: ignore[attr-defined]
    inner = FakeInteraction(client=owner_bot)
    await select.callback(inner)  # type: ignore[attr-defined]
    assert "reloaded" in str(inner.response.messages[0]["content"])


async def test_reload_select_blocks_non_owner(bot: Bot) -> None:
    from botbase.ext.admin import _ReloadView

    bot.owner_id = 999
    await bot.load_extension(f"{FIXTURES}.alpha")
    view = _ReloadView(bot)
    select = view.children[0]
    select._values = [f"{FIXTURES}.alpha"]  # type: ignore[attr-defined]
    inner = FakeInteraction(client=bot)
    await select.callback(inner)  # type: ignore[attr-defined]
    assert inner.response.messages[0]["content"] == "Owner only."


async def test_load_then_unload(owner_bot: Bot, interaction: FakeInteraction) -> None:
    cog = Admin(owner_bot)
    await Admin.load.callback(cog, interaction, f"{FIXTURES}.alpha")
    assert "loaded" in _last(interaction)
    assert f"{FIXTURES}.alpha" in owner_bot.extensions

    await Admin.unload.callback(cog, interaction, "alpha")
    assert "unloaded" in _last(interaction)
    assert f"{FIXTURES}.alpha" not in owner_bot.extensions


async def test_load_failure_reports_error(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin.load.callback(Admin(owner_bot), interaction, f"{FIXTURES}.broken")
    assert "could not load" in _last(interaction)


# -- sync --------------------------------------------------------------------------


async def test_sync_guild_requires_a_guild(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin.sync.callback(Admin(owner_bot), interaction, "guild")
    assert "run this in a server" in _last(interaction)


async def test_sync_global(owner_bot: Bot, interaction: FakeInteraction, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sync(*_a: object, **_k: object) -> list[object]:
        return []

    monkeypatch.setattr(owner_bot.tree, "sync", fake_sync)
    await Admin.sync.callback(Admin(owner_bot), interaction, "global")
    assert "global command" in _last(interaction)


# -- exec ------------------------------------------------------------------------


async def test_exec_returns_value(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin.exec_.callback(Admin(owner_bot), interaction, "return 6 * 7")
    assert "42" in _last(interaction)


async def test_exec_captures_stdout_and_keeps_last(owner_bot: Bot, interaction: FakeInteraction) -> None:
    cog = Admin(owner_bot)
    await Admin.exec_.callback(cog, interaction, "print('yo')\nreturn 5")
    assert "yo" in _last(interaction)
    assert cog._last_eval == 5


async def test_exec_reports_runtime_error(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin.exec_.callback(Admin(owner_bot), interaction, "1 / 0")
    assert "ZeroDivisionError" in _last(interaction)


async def test_exec_reports_syntax_error(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin.exec_.callback(Admin(owner_bot), interaction, "return (")
    assert "SyntaxError" in _last(interaction)


async def test_exec_no_code_opens_modal(owner_bot: Bot, interaction: FakeInteraction) -> None:
    from botbase.ext.admin import _ExecModal

    await Admin.exec_.callback(Admin(owner_bot), interaction, None)
    assert isinstance(interaction.response.modals[0], _ExecModal)


async def test_exec_blocks_non_owner(bot: Bot, interaction: FakeInteraction) -> None:
    bot.owner_id = 999
    await Admin(bot)._run_eval(interaction, "return 1")
    assert interaction.response.messages[0]["content"] == "Owner only."


async def test_send_result_uses_a_file_when_long(interaction: FakeInteraction) -> None:
    await Admin._send_result(interaction, "x" * 3000)
    assert interaction.followup.messages[-1].get("file") is not None


async def test_exec_modal_submit_runs(owner_bot: Bot, interaction: FakeInteraction) -> None:
    from botbase.ext.admin import _ExecModal

    modal = _ExecModal(Admin(owner_bot)._run_eval)
    modal.source._value = "return 2 + 2"
    await modal.on_submit(interaction)
    assert "4" in _last(interaction)
