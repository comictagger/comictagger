from __future__ import annotations

import itertools
import logging
import pathlib
from collections.abc import Sequence
from importlib.metadata import entry_points

from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)

__all__ = (
    "ComicTalker",
    "TalkerError",
)


def get_talkers(
    version: str, cache: pathlib.Path, local_plugins: Sequence[type[ComicTalker]] = tuple()
) -> tuple[dict[str, ComicTalker], str]:
    """Returns all comic talker instances"""
    talkers: dict[str, ComicTalker] = {}
    metron_location = ""
    # A dict is used, last plugin wins
    for talker in itertools.chain(entry_points(group="comictagger.talker")):
        try:
            talker_cls: type[ComicTalker] = talker.load()
            obj = talker_cls(version, cache)
            if talker.name == "metron" or "metron" in obj.website.casefold() or "metron" in obj.__module__.casefold():
                if talker.dist and not metron_location:
                    metron_location = f"pip package {talker.dist.name}"
                else:
                    metron_location = f"python module {talker.module}"
                continue
            if obj.id != talker.name:
                logger.error("Talker ID must be the same as the entry point name")
                continue
            talkers[talker.name] = obj

        except Exception:
            logger.exception("Failed to load talker: %s", talker.name)
            logger.debug("", exc_info=True)

    # A dict is used, last plugin wins
    for talker_cls in local_plugins:
        try:
            obj = talker_cls(version, cache)
            talkers[talker_cls.id] = obj
        except Exception:
            logger.exception("Failed to load talker: %s", talker_cls.id)
            logger.debug("", exc_info=True)

    return talkers, metron_location
