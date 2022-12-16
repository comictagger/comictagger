from __future__ import annotations

from typing import NamedTuple


class Replacement(NamedTuple):
    find: str
    replce: str
    strict_only: bool


class Replacements(NamedTuple):
    literal_text: list[Replacement]
    format_value: list[Replacement]


DEFAULT_REPLACEMENTS = Replacements(
    literal_text=[
        Replacement(": ", " - ", True),
        Replacement(":", "-", True),
    ],
    format_value=[
        Replacement(": ", " - ", True),
        Replacement(":", "-", True),
        Replacement("/", "-", False),
        Replacement("//", "--", False),
        Replacement("\\", "-", True),
    ],
)
