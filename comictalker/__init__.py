from __future__ import annotations

import logging
import pathlib
import sys

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

from comictalker.comictalker import ComicTalker, TalkerError
from comictalker.resulttypes import ComicIssue, ComicSeries

logger = logging.getLogger(__name__)

__all__ = [
    "ComicTalker",
    "TalkerError",
    "ComicIssue",
    "ComicSeries",
]


def get_talkers(version: str, cache: pathlib.Path) -> dict[str, ComicTalker]:
    """Returns all comic talker instances"""
    talkers: dict[str, ComicTalker] = {}

    for talker in entry_points(group="comictagger.talkers"):
        try:
            talker_cls = talker.load()
            obj = talker_cls(version, cache)
            talkers[obj.id] = obj
        except Exception:
            logger.exception("Failed to load talker: %s", talker.name)
            raise TalkerError(source=talker.name, code=4, desc="Failed to initialise talker")

    return talkers
