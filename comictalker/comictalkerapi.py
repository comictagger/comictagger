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

import comictalker.talkers.comicvine
import comictalker.talkers.mangaupdates
from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


def get_comic_talker(source_name: str) -> type[ComicTalker]:
    """Retrieve the available sources modules"""
    sources = get_talkers()
    if source_name not in sources:
        raise TalkerError(source=source_name, code=4, desc="The talker does not exist")

    talker = sources[source_name]
    return talker


def get_talkers() -> dict[str, type[ComicTalker]]:
    """Returns all comic talker modules NOT objects"""
    return {
        "comicvine": comictalker.talkers.comicvine.ComicVineTalker,
        "mangaupdates": comictalker.talkers.mangaupdates.MangaUpdatesTalker,
    }
