from __future__ import annotations

import pytest
from discord import app_commands

from botbase.app import Bot
from botbase.ext.admin import (
    Admin,
    DevPanel,
    _cleanup_code,
    _do_load,
    _do_sync,
    _do_unload,
    _ExecModal,
    _ExtModal,
    _resolve,
)
from tests.conftest import FakeInteraction

FIXTURES = "tests.fixtures.extpkg"


def _last(interaction: FakeInteraction) -> str:
    return str(interaction.followup.messages[-1]["content"])


@pytest.fixture
def owner_bot(bot: Bot, interaction: FakeInteraction) -> Bot:
    bot.owner_id = interaction.user.id
    return bot


def _panel(bot: Bot) -> DevPanel:
    return DevPanel(bot, Admin(bot)._run_eval)


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


# -- /dev opens the panel -------------------------------------------------------


async def test_dev_opens_panel(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin.dev.callback(Admin(owner_bot), interaction)
    assert isinstance(interaction.response.messages[0]["view"], DevPanel)


def test_dev_command_hidden_from_non_admins() -> None:
    # default_permissions() with no perms -> Discord hides the command from
    # everyone without admin in the guild.
    perms = Admin.dev.default_permissions
    assert perms is not None
    assert perms.value == 0


def test_dev_command_is_not_offered_in_dms() -> None:
    # Discord ignores default_permissions in DMs, so /dev must be guild-only or every
    # user who DMs the bot sees it in their command picker.
    assert Admin.dev.guild_only is True
    contexts = Admin.dev.allowed_contexts
    assert contexts is not None
    assert contexts.guild
    assert not contexts.dm_channel
    assert not contexts.private_channel


async def test_panel_gate_blocks_non_owner(bot: Bot) -> None:
    bot.owner_id = 999
    panel = _panel(bot)
    inner = FakeInteraction(client=bot)
    assert await panel.interaction_check(inner) is False
    assert inner.response.messages[0]["content"] == "This command is owner-only."


# -- reload picker ------------------------------------------------------------------


async def test_panel_reload_button_opens_picker(owner_bot: Bot, interaction: FakeInteraction) -> None:
    from botbase.ext.admin import _ReloadView

    await owner_bot.load_extension(f"{FIXTURES}.alpha")
    await _panel(owner_bot).reload.callback(interaction)
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


# -- load / unload ----------------------------------------------------------------


async def test_load_then_unload(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await _do_load(owner_bot, interaction, f"{FIXTURES}.alpha")
    assert "loaded" in _last(interaction)
    assert f"{FIXTURES}.alpha" in owner_bot.extensions

    await _do_unload(owner_bot, interaction, "alpha")
    assert "unloaded" in _last(interaction)
    assert f"{FIXTURES}.alpha" not in owner_bot.extensions


async def test_load_failure_reports_error(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await _do_load(owner_bot, interaction, f"{FIXTURES}.broken")
    assert "could not load" in _last(interaction)


@pytest.mark.parametrize(("button", "title"), [("load", "load"), ("unload", "unload")])
async def test_panel_ext_buttons_open_modal(
    owner_bot: Bot, interaction: FakeInteraction, button: str, title: str
) -> None:
    await getattr(_panel(owner_bot), button).callback(interaction)
    modal = interaction.response.modals[0]
    assert isinstance(modal, _ExtModal)
    assert modal.title == title


async def test_ext_modal_submit_runs(owner_bot: Bot, interaction: FakeInteraction) -> None:
    from functools import partial

    modal = _ExtModal("load", partial(_do_load, owner_bot))
    modal.name._value = f"{FIXTURES}.alpha"  # type: ignore[attr-defined]
    await modal.on_submit(interaction)
    assert "loaded" in _last(interaction)
    assert f"{FIXTURES}.alpha" in owner_bot.extensions


async def test_panel_on_timeout_disables_buttons(owner_bot: Bot) -> None:
    from tests.conftest import FakeMessage

    panel = _panel(owner_bot)
    panel.message = FakeMessage()  # type: ignore[assignment]
    await panel.on_timeout()
    assert all(child.disabled for child in panel.children)
    assert panel.message.edits  # type: ignore[union-attr]


# -- sync --------------------------------------------------------------------------


async def test_sync_guild_requires_a_guild(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await _do_sync(owner_bot, interaction, "guild")
    assert "run this in a server" in _last(interaction)


async def test_panel_sync_buttons(owner_bot: Bot, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sync(*_a: object, **_k: object) -> list[object]:
        return []

    monkeypatch.setattr(owner_bot.tree, "sync", fake_sync)
    panel = _panel(owner_bot)

    guild_inter = FakeInteraction(client=owner_bot)
    await panel.sync_guild.callback(guild_inter)
    assert "run this in a server" in str(guild_inter.followup.messages[-1]["content"])

    global_inter = FakeInteraction(client=owner_bot)
    await panel.sync_global.callback(global_inter)
    assert "global command" in str(global_inter.followup.messages[-1]["content"])


async def test_sync_global(owner_bot: Bot, interaction: FakeInteraction, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sync(*_a: object, **_k: object) -> list[object]:
        return []

    monkeypatch.setattr(owner_bot.tree, "sync", fake_sync)
    await _do_sync(owner_bot, interaction, "global")
    assert "global command" in _last(interaction)


# -- exec ------------------------------------------------------------------------


async def test_exec_returns_value(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin(owner_bot)._run_eval(interaction, "return 6 * 7")
    assert "42" in _last(interaction)


async def test_exec_captures_stdout_and_keeps_last(owner_bot: Bot, interaction: FakeInteraction) -> None:
    cog = Admin(owner_bot)
    await cog._run_eval(interaction, "print('yo')\nreturn 5")
    assert "yo" in _last(interaction)
    assert cog._last_eval == 5


async def test_exec_reports_runtime_error(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin(owner_bot)._run_eval(interaction, "1 / 0")
    assert "ZeroDivisionError" in _last(interaction)


async def test_exec_reports_syntax_error(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await Admin(owner_bot)._run_eval(interaction, "return (")
    assert "SyntaxError" in _last(interaction)


async def test_panel_exec_button_opens_modal(owner_bot: Bot, interaction: FakeInteraction) -> None:
    await _panel(owner_bot).exec_.callback(interaction)
    assert isinstance(interaction.response.modals[0], _ExecModal)


async def test_exec_blocks_non_owner(bot: Bot, interaction: FakeInteraction) -> None:
    bot.owner_id = 999
    await Admin(bot)._run_eval(interaction, "return 1")
    assert interaction.response.messages[0]["content"] == "Owner only."


async def test_send_result_uses_a_file_when_long(interaction: FakeInteraction) -> None:
    await Admin._send_result(interaction, "x" * 3000)
    assert interaction.followup.messages[-1].get("file") is not None


async def test_exec_modal_submit_runs(owner_bot: Bot, interaction: FakeInteraction) -> None:
    modal = _ExecModal(Admin(owner_bot)._run_eval)
    modal.source._value = "return 2 + 2"
    await modal.on_submit(interaction)
    assert "4" in _last(interaction)


# -- audit log ----------------------------------------------------------------------


async def test_dev_actions_are_audited(
    owner_bot: Bot, interaction: FakeInteraction, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="botbase.ext.admin")
    await _do_load(owner_bot, interaction, f"{FIXTURES}.alpha")
    await _do_unload(owner_bot, interaction, "alpha")
    await _do_load(owner_bot, interaction, f"{FIXTURES}.broken")
    lines = [(r.levelname, r.getMessage()) for r in caplog.records if r.name == "botbase.ext.admin"]
    who = f"({interaction.user.id})"
    assert any(lvl == "INFO" and m.startswith(f"/dev load {FIXTURES}.alpha by ") and who in m for lvl, m in lines)
    assert any(lvl == "INFO" and m.startswith(f"/dev unload {FIXTURES}.alpha by ") for lvl, m in lines)
    assert any(
        lvl == "WARNING" and m.startswith(f"/dev load {FIXTURES}.broken by ") and "failed" in m for lvl, m in lines
    )


async def test_exec_is_audited_without_source_or_output(
    owner_bot: Bot, interaction: FakeInteraction, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="botbase.ext.admin")
    await Admin(owner_bot)._run_eval(interaction, "secret = 'hunter2'\nreturn secret")
    await Admin(owner_bot)._run_eval(interaction, "1 / 0")
    text = "\n".join(r.getMessage() for r in caplog.records if r.name == "botbase.ext.admin")
    assert "/dev exec by" in text
    assert "2 line(s)" in text
    assert "raised ZeroDivisionError" in text
    assert "hunter2" not in text
    assert any(r.levelname == "WARNING" for r in caplog.records if r.name == "botbase.ext.admin")
