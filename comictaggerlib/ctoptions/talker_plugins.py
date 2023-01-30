from __future__ import annotations

import logging
from collections.abc import Mapping

import settngs

from comictalker.talkerbase import ComicTalker

logger = logging.getLogger(__name__)


def register_talker_settings(parser: settngs.Manager, plugins: Mapping[str, ComicTalker]) -> None:
    for talker_name, talker in plugins.items():
        try:
            parser.add_group(talker_name, talker.register_settings, False)
        except Exception:
            logger.exception("Failed to register settings for %s", talker_name)
