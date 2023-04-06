"""A class to encapsulate the ComicBookInfo data"""
# Copyright 2012-2014 ComicTagger Authors
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

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Literal, TypedDict

from comicapi import utils
from comicapi.genericmetadata import Date, GenericMetadata

logger = logging.getLogger(__name__)

CBILiteralType = Literal[
    "series",
    "title",
    "issue",
    "publisher",
    "publicationMonth",
    "publicationYear",
    "numberOfIssues",
    "comments",
    "genre",
    "volume",
    "numberOfVolumes",
    "language",
    "country",
    "rating",
    "credits",
    "tags",
]


class Credits(TypedDict):
    person: str
    role: str
    primary: bool


class ComicBookInfoJson(TypedDict, total=False):
    series: str
    title: str
    publisher: str
    publicationMonth: int
    publicationYear: int
    issue: int
    numberOfIssues: int
    volume: int
    numberOfVolumes: int
    rating: int
    genre: str
    language: str
    country: str
    credits: list[Credits]
    tags: list[str]
    comments: str


CBIContainer = TypedDict("CBIContainer", {"appID": str, "lastModified": str, "ComicBookInfo/1.0": ComicBookInfoJson})


class ComicBookInfo:
    def metadata_from_string(self, string: str) -> GenericMetadata:
        cbi_container = json.loads(string)

        metadata = GenericMetadata()

        cbi = defaultdict(lambda: None, cbi_container["ComicBookInfo/1.0"])

        metadata.series = utils.xlate(cbi["series"])
        metadata.title = utils.xlate(cbi["title"])
        metadata.issue = utils.xlate(cbi["issue"])
        metadata.publisher = utils.xlate(cbi["publisher"])

        metadata.cover_date = Date(utils.xlate_int(cbi["publicationYear"]), utils.xlate_int(cbi["publicationMonth"]))

        metadata.issue_count = utils.xlate_int(cbi["numberOfIssues"])
        metadata.description = utils.xlate(cbi["comments"])
        metadata.genres = utils.split(cbi["genre"], ",")
        metadata.volume = utils.xlate_int(cbi["volume"])
        metadata.volume_count = utils.xlate_int(cbi["numberOfVolumes"])
        metadata.language = utils.xlate(cbi["language"])
        metadata.country = utils.xlate(cbi["country"])
        metadata.critical_rating = utils.xlate_int(cbi["rating"])

        metadata.credits = [
            Credits(
                person=x["person"] if "person" in x else "",
                role=x["role"] if "role" in x else "",
                primary=x["primary"] if "primary" in x else False,
            )
            for x in cbi["credits"]
        ]
        metadata.tags.update(cbi["tags"] if cbi["tags"] is not None else set())

        # need the language string to be ISO
        if metadata.language:
            metadata.language = utils.get_language_iso(metadata.language)

        metadata.is_empty = False

        return metadata

    def string_from_metadata(self, metadata: GenericMetadata) -> str:
        cbi_container = self.create_json_dictionary(metadata)
        return json.dumps(cbi_container)

    def validate_string(self, string: bytes | str) -> bool:
        """Verify that the string actually contains CBI data in JSON format"""

        try:
            cbi_container = json.loads(string)
        except json.JSONDecodeError:
            return False

        return "ComicBookInfo/1.0" in cbi_container

    def create_json_dictionary(self, metadata: GenericMetadata) -> CBIContainer:
        """Create the dictionary that we will convert to JSON text"""

        cbi_container = CBIContainer(
            {
                "appID": "ComicTagger/1.0.0",
                "lastModified": str(datetime.now()),
                "ComicBookInfo/1.0": {},
            }
        )  # TODO: ctversion.version,

        # helper func
        def assign(cbi_entry: CBILiteralType, md_entry: Any) -> None:
            if md_entry is not None or isinstance(md_entry, str) and md_entry != "":
                cbi_container["ComicBookInfo/1.0"][cbi_entry] = md_entry

        assign("series", utils.xlate(metadata.series))
        assign("title", utils.xlate(metadata.title))
        assign("issue", utils.xlate(metadata.issue))
        assign("publisher", utils.xlate(metadata.publisher))
        assign("publicationMonth", utils.xlate_int(metadata.cover_date.month))
        assign("publicationYear", utils.xlate_int(metadata.cover_date.year))
        assign("numberOfIssues", utils.xlate_int(metadata.issue_count))
        assign("comments", utils.xlate(metadata.description))
        assign("genre", utils.xlate(",".join(metadata.genres)))
        assign("volume", utils.xlate_int(metadata.volume))
        assign("numberOfVolumes", utils.xlate_int(metadata.volume_count))
        assign("language", utils.xlate(utils.get_language_from_iso(metadata.language)))
        assign("country", utils.xlate(metadata.country))
        assign("rating", utils.xlate_int(metadata.critical_rating))
        assign("credits", metadata.credits)
        assign("tags", list(metadata.tags))

        return cbi_container

    def write_to_external_file(self, filename: str, metadata: GenericMetadata) -> None:
        cbi_container = self.create_json_dictionary(metadata)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(json.dumps(cbi_container, indent=4))
