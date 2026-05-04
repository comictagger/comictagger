from __future__ import annotations

from collections.abc import Callable, Collection
from enum import auto
from typing import Any

from .utils import DefaultDict, StrEnum, norm_fold


class Mode(StrEnum):
    OVERLAY = auto()
    ADD_MISSING = auto()


def merge_lists(old: Collection[Any], new: Collection[Any]) -> list[Any] | set[Any]:
    """Dedupes normalised (NFKD), casefolded values using 'new' values on collisions"""
    if not new:
        return old if isinstance(old, set) else list(old)
    if not old:
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


attribute: DefaultDict[Mode, Callable[[Any, Any], Any]] = DefaultDict(
    {
        Mode.OVERLAY: overlay,
        Mode.ADD_MISSING: lambda old, new: overlay(new, old),
    },
    default=lambda x: overlay,
)


lists: DefaultDict[Mode, Callable[[Collection[Any], Collection[Any]], list[Any] | set[Any]]] = DefaultDict(
    {
        Mode.OVERLAY: merge_lists,
        Mode.ADD_MISSING: lambda old, new: merge_lists(new, old),
    },
    default=lambda x: overlay,
)
