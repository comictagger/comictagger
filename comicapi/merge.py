from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Collection
from enum import auto
from typing import Any

from comicapi.utils import StrEnum, norm_fold


@dataclasses.dataclass
class Credit:
    person: str = ""
    role: str = ""
    primary: bool = False

    def __str__(self) -> str:
        return f"{self.role}: {self.person}"


class Mode(StrEnum):
    OVERLAY = auto()
    ADD_MISSING = auto()


def merge_lists(old: Collection[Any], new: Collection[Any]) -> list[Any] | set[Any]:
    """Dedupes normalised (NFKD), casefolded values using 'new' values on collisions"""
    if len(new) == 0:
        return old if isinstance(old, set) else list(old)
    if len(old) == 0:
        return new if isinstance(new, set) else list(new)

    # Create dict to preserve case
    new_dict = {norm_fold(str(n)): n for n in new}
    old_dict = {norm_fold(str(c)): c for c in old}

    old_dict.update(new_dict)

    if isinstance(old, set):
        return set(old_dict.values())

    return list(old_dict.values())


def overlay(old: Any, new: Any) -> Any:
    """overlay - When the `new` object is not empty, replace `old` with `new`."""
    if new is None or (isinstance(new, Collection) and len(new) == 0):
        return old

    return new


attribute = defaultdict(
    lambda: overlay,
    {
        Mode.OVERLAY: overlay,
        Mode.ADD_MISSING: lambda old, new: overlay(new, old),
    },
)


lists = defaultdict(
    lambda: overlay,
    {
        Mode.OVERLAY: merge_lists,
        Mode.ADD_MISSING: lambda old, new: merge_lists(new, old),
    },
)
