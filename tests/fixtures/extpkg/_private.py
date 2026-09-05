from __future__ import annotations


async def setup(bot: object) -> None:
    msg = "underscore-prefixed modules must never be discovered"
    raise AssertionError(msg)
