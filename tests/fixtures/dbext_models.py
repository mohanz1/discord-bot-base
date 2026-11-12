"""A model that only ``tests.fixtures.dbext.notes`` imports.

Kept outside the extension module: discord.py re-executes an extension module on
every load, which would redefine the table on the shared metadata.
"""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class FixtureNote(SQLModel, table=True):
    __tablename__ = "fixture_note_auto_create"

    key: str = Field(primary_key=True)
    value: str
