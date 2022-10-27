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
from comictalker.talkerbase import ComicTalker, TalkerError  # renamed TalkerBase to ComicTalker

logger = logging.getLogger(__name__)


# To signal image loaded etc. TODO Won't be needed hopefully with new async loading
def list_fetch_complete(url_list: list[str]) -> None:
    ...


def url_fetch_complete(image_url: str, thumb_url: str | None) -> None:
    ...


alt_url_list_fetch_complete = list_fetch_complete
url_fetch_complete = url_fetch_complete


def get_comic_talker(source_name: str) -> type[ComicTalker]:
    # Retrieve the available sources modules
    sources = get_talkers()
    if source_name not in sources:
        raise TalkerError(source=source_name, code=4, desc="The talker does not exist")

    talker = sources[source_name]
    return talker


def get_talkers():
    return {"comicvine": comictalker.talkers.comicvine.ComicVineTalker}
