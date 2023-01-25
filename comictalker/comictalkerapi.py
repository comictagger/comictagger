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
import pathlib
from typing import Any, TypedDict

import comictalker.talkers.comicvine
from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class TalkerPlugin(TypedDict, total=False):
    cls: type[ComicTalker]
    obj: ComicTalker


def set_talker_settings(talker, settings) -> None:
    try:
        talker.set_settings(settings)
    except Exception as e:
        logger.exception(
            f"Failed to set talker settings for {talker.talker_id}, will use defaults. Error: {str(e)}",
        )
        raise TalkerError(source=talker.talker_id, code=4, desc="Could not apply talker settings, will use defaults")


def get_talker_objects(
    version: str, cache_folder: pathlib.Path, settings: dict[str, Any], plugins: dict[str, TalkerPlugin]
) -> dict[str, TalkerPlugin]:
    for talker_name, talker in plugins.items():
        try:
            obj = talker["cls"](version, cache_folder)
            plugins[talker_name]["obj"] = obj
        except Exception:
            logger.exception("Failed to create talker object")
            raise TalkerError(source=talker_name, code=4, desc="Failed to initialise talker object")

        # Run outside of try block so as to keep except separate
        set_talker_settings(plugins[talker_name]["obj"], settings)
    return plugins


def get_talkers() -> dict[str, TalkerPlugin]:
    """Returns all comic talker modules NOT objects"""
    return {"comicvine": TalkerPlugin(cls=comictalker.talkers.comicvine.ComicVineTalker)}
