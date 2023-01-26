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

import argparse
import logging
import pathlib
from typing import Any

import comictalker.talkers.comicvine
from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


def set_talker_settings(talker: ComicTalker, settings: argparse.Namespace) -> None:
    try:
        talker.set_settings(settings)
    except Exception as e:
        logger.exception(
            f"Failed to set talker settings for {talker.source_details.name}, will use defaults. Error: {str(e)}",
        )
        raise TalkerError(source=talker.source_details.name, code=4, desc="Could not apply talker settings")


def get_talkers(version: str, cache: pathlib.Path) -> dict[str, Any]:
    """Returns all comic talker instances"""
    # TODO separate PR will bring talkers in via entry points. TalkerError etc. source will then be a var
    talkers = {}
    for talker in [comictalker.talkers.comicvine.ComicVineTalker]:
        try:
            obj = talker(version, cache)
            talkers[obj.source_details.id] = obj
        except Exception:
            logger.exception("Failed to load talker: %s", "comicvine")
            raise TalkerError(source="comicvine", code=4, desc="Failed to initialise talker")
    return talkers
