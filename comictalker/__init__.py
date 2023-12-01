from __future__ import annotations

import logging
import pathlib
import sys

from packaging.version import InvalidVersion, parse

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)

__all__ = [
    "ComicTalker",
    "TalkerError",
]


def get_talkers(version: str, cache: pathlib.Path) -> dict[str, ComicTalker]:
    """Returns all comic talker instances"""
    talkers: dict[str, ComicTalker] = {}

    for talker in entry_points(group="comictagger.talker"):
        try:
            talker_cls = talker.load()
            obj = talker_cls(version, cache)
            if obj.id != talker.name:
                logger.error("Talker ID must be the same as the entry point name")
                continue
            try:
                if parse(version) >= parse(obj.comictagger_min_ver):
                    talkers[talker.name] = obj
                else:
                    logger.error(
                        f"Minimum ComicTagger version required of {obj.comictagger_min_ver} for talker {talker.name} is not met, will NOT load talker"
                    )
            except InvalidVersion:
                logger.warning(
                    f"Invalid minimum required ComicTagger version number for talker: {talker.name} - version: {obj.comictagger_min_ver}, will load talker anyway"
                )
                # Attempt to use the talker anyway
                # TODO flag this problem for later display to the user
                talkers[talker.name] = obj

        except Exception:
            logger.exception("Failed to load talker: %s", talker.name)

    return talkers
