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
from typing import NamedTuple

if sys.version_info < (3, 10):
    from importlib_metadata import EntryPoint, distributions
else:
    from importlib.metadata import EntryPoint, distributions

from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class Plugin(NamedTuple):
    package: str
    version: str
    entry_point: EntryPoint


def get_comic_talker(talker_name: str) -> type[ComicTalker]:
    """Returns the requested talker module"""
    talkers = get_talkers()
    if talker_name not in talkers:
        raise TalkerError(source=talker_name, code=4, desc="The talker does not exist")

    return talkers[talker_name].entry_point.load()


def get_talkers() -> dict[str, Plugin]:
    """Returns all comic talker plugins (internal and external)"""
    talkers: dict[str, Plugin] = {}
    for dist in distributions():
        eps = dist.entry_points

        # perf: skip parsing `.metadata` (slow) if no entry points match
        if not any(ep.group in ("comictagger_talkers") for ep in eps):
            continue

        # assigned to prevent continual reparsing
        meta = dist.metadata

        for ep in eps:
            # Only want comic talkers
            if ep.group == "comictagger_talkers":
                talkers[ep.name] = Plugin(ep.name, meta["version"], ep)

    return talkers
