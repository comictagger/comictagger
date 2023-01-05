"""Handles collecting data from source talkers."""

# Copyright 2012-2014 Anthony Beville
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import logging
import sys
from functools import cache

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


def get_comic_talker(talker_name: str) -> type[ComicTalker]:
    """Returns the requested talker module"""
    talkers = get_talkers()
    if talker_name not in talkers:
        raise TalkerError(source=talker_name, code=4, desc="The talker does not exist")

    return talkers[talker_name]


@cache
def get_talkers():
    """Returns all comic talker plugins (internal and external)"""
    talkers = {}

    for ep in entry_points(group="comictagger_talkers"):
        try:
            talkers[ep.name] = ep.load()
            logger.info(
                "Found talker ID: %s, name: %s, version: %s",
                ep.name,
                talkers[ep.name].display_name,
                talkers[ep.name].talker_version,
            )
        except Exception:
            logger.exception("Failed to load talker: %s", ep.name)

    return talkers
