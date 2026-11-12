from __future__ import annotations

from pydantic import Field

from botbase.config import Settings


class CustomSettings(Settings):
    extension_packages: list[str] = Field(default_factory=lambda: ["tests.fixtures.extpkg"])
    disabled_extensions: set[str] = Field(default_factory=lambda: {"broken"})


class NotSettings:
    pass
