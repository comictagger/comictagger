from __future__ import annotations

import logging
import pathlib

import comictalker.talkers.comicvine
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

    for talker in [comictalker.talkers.comicvine.ComicVineTalker]:
        try:
            obj = talker(version, cache)
            talkers[obj.id] = obj
        except Exception:
            logger.exception("Failed to load talker: %s", "comicvine")
            raise TalkerError(source="comicvine", code=4, desc="Failed to initialise talker")
    return talkers
