from __future__ import annotations

import dataclasses
import sys
from collections import defaultdict
from collections.abc import Collection
from enum import Enum, auto
from typing import Any

from comicapi.utils import norm_fold

if sys.version_info < (3, 11):

    class StrEnum(str, Enum):
        """
        Enum where members are also (and must be) strings
        """

        def __new__(cls, *values: Any) -> Any:
            "values must already be of type `str`"
            if len(values) > 3:
                raise TypeError(f"too many arguments for str(): {values!r}")
            if len(values) == 1:
                # it must be a string
                if not isinstance(values[0], str):
                    raise TypeError(f"{values[0]!r} is not a string")
            if len(values) >= 2:
                # check that encoding argument is a string
                if not isinstance(values[1], str):
                    raise TypeError(f"encoding must be a string, not {values[1]!r}")
            if len(values) == 3:
                # check that errors argument is a string
                if not isinstance(values[2], str):
                    raise TypeError("errors must be a string, not %r" % (values[2]))
            value = str(*values)
            member = str.__new__(cls, value)
            member._value_ = value
            return member

        @staticmethod
        def _generate_next_value_(name: str, start: int, count: int, last_values: Any) -> str:
            """
            Return the lower-cased version of the member name.
            """
            return name.lower()

else:
    from enum import StrEnum


@dataclasses.dataclass
class Credit:
    person: str = ""
    role: str = ""
    primary: bool = False


class Mode(StrEnum):
    OVERLAY = auto()
    ADD_MISSING = auto()
    COMBINE = auto()


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


def combine(old: Any, new: Any) -> Any:
    """combine - Same as `overlay` except lists are merged"""
    if new is None:
        return old

    if (
        not (isinstance(new, str) or isinstance(old, str))
        and isinstance(new, Collection)
        and isinstance(old, Collection)
    ):
        return merge_lists(old, new)
    if isinstance(new, str) and len(new) == 0:
        return old
    return new


def overlay(old: Any, new: Any) -> Any:
    """overlay - When the `new` object is not empty, replace `old` with `new`."""
    if new is None:
        return old
    if (
        not (isinstance(new, str) or isinstance(old, str))
        and isinstance(new, Collection)
        and isinstance(old, Collection)
    ):
        if isinstance(new, list) and len(new) > 0 and isinstance(new[0], Credit):
            return merge_lists(old, new)
        if len(new) == 0:
            return old

    return new


def add_missing(old: Any, new: Any) -> Any:
    """add_missing - When the `old` object is empty, replace `old` with `new`"""
    return overlay(new, old)


function = defaultdict(
    lambda: overlay,
    {
        Mode.OVERLAY: overlay,
        Mode.ADD_MISSING: add_missing,
        Mode.COMBINE: combine,
    },
)
