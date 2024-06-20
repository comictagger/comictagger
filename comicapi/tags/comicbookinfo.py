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
from datetime import datetime
from typing import Any, Literal, TypedDict

from comicapi import utils
from comicapi.archivers import Archiver
from comicapi.genericmetadata import Credit, GenericMetadata
from comicapi.tags import Tag

logger = logging.getLogger(__name__)

_CBILiteralType = Literal[
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


class credit(TypedDict):
    person: str
    role: str
    primary: bool


class _ComicBookInfoJson(TypedDict, total=False):
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
    credits: list[credit]
    tags: list[str]
    comments: str


_CBIContainer = TypedDict("_CBIContainer", {"appID": str, "lastModified": str, "ComicBookInfo/1.0": _ComicBookInfoJson})


class ComicBookInfo(Tag):
    enabled = True

    id = "cbi"

    def __init__(self, version: str) -> None:
        super().__init__(version)

        self.supported_attributes = {
            "series",
            "issue",
            "issue_count",
            "title",
            "volume",
            "volume_count",
            "genres",
            "description",
            "publisher",
            "month",
            "year",
            "language",
            "country",
            "critical_rating",
            "tags",
            "credits",
            "credits.person",
            "credits.primary",
            "credits.role",
        }

    def supports_credit_role(self, role: str) -> bool:
        return True

    def supports_tags(self, archive: Archiver) -> bool:
        return archive.supports_comment()

    def has_tags(self, archive: Archiver) -> bool:
        return self.supports_tags(archive) and self._validate_string(archive.get_comment())

    def remove_tags(self, archive: Archiver) -> bool:
        return archive.set_comment("")

    def read_tags(self, archive: Archiver) -> GenericMetadata:
        if self.has_tags(archive):
            comment = archive.get_comment()
            if self._validate_string(comment):
                return self._metadata_from_string(comment)
        return GenericMetadata()

    def read_raw_tags(self, archive: Archiver) -> str:
        if self.has_tags(archive):
            return json.dumps(json.loads(archive.get_comment()), indent=2)
        return ""

    def write_tags(self, metadata: GenericMetadata, archive: Archiver) -> bool:
        if self.supports_tags(archive):
            return archive.set_comment(self._string_from_metadata(metadata))
        else:
            logger.warning(f"Archive ({archive.name()}) does not support {self.name()} metadata")
        return False

    def name(self) -> str:
        return "ComicBookInfo"

    def _metadata_from_string(self, string: str) -> GenericMetadata:
        cbi_container: _CBIContainer = json.loads(string)

        metadata = GenericMetadata()

        cbi = cbi_container["ComicBookInfo/1.0"]

        metadata.series = utils.xlate(cbi.get("series"))
        metadata.title = utils.xlate(cbi.get("title"))
        metadata.issue = utils.xlate(cbi.get("issue"))
        metadata.publisher = utils.xlate(cbi.get("publisher"))
        metadata.month = utils.xlate_int(cbi.get("publicationMonth"))
        metadata.year = utils.xlate_int(cbi.get("publicationYear"))
        metadata.issue_count = utils.xlate_int(cbi.get("numberOfIssues"))
        metadata.description = utils.xlate(cbi.get("comments"))
        metadata.genres = set(utils.split(cbi.get("genre"), ","))
        metadata.volume = utils.xlate_int(cbi.get("volume"))
        metadata.volume_count = utils.xlate_int(cbi.get("numberOfVolumes"))
        metadata.language = utils.xlate(cbi.get("language"))
        metadata.country = utils.xlate(cbi.get("country"))
        metadata.critical_rating = utils.xlate_int(cbi.get("rating"))

        metadata.credits = [
            Credit(
                person=x["person"] if "person" in x else "",
                role=x["role"] if "role" in x else "",
                primary=x["primary"] if "primary" in x else False,
            )
            for x in cbi.get("credits", [])
        ]
        metadata.tags.update(cbi.get("tags", set()))

        # need the language string to be ISO
        if metadata.language:
            metadata.language = utils.get_language_iso(metadata.language)

        metadata.is_empty = False

        return metadata

    def _string_from_metadata(self, metadata: GenericMetadata) -> str:
        cbi_container = self._create_json_dictionary(metadata)
        return json.dumps(cbi_container)

    def _validate_string(self, string: bytes | str) -> bool:
        """Verify that the string actually contains CBI data in JSON format"""

        try:
            cbi_container = json.loads(string)
        except json.JSONDecodeError:
            return False

        return "ComicBookInfo/1.0" in cbi_container

    def _create_json_dictionary(self, metadata: GenericMetadata) -> _CBIContainer:
        """Create the dictionary that we will convert to JSON text"""

        cbi_container = _CBIContainer(
            {
                "appID": "ComicTagger/1.0.0",
                "lastModified": str(datetime.now()),
                "ComicBookInfo/1.0": {},
            }
        )  # TODO: ctversion.version,

        # helper func
        def assign(cbi_entry: _CBILiteralType, md_entry: Any) -> None:
            if md_entry is not None or isinstance(md_entry, str) and md_entry != "":
                cbi_container["ComicBookInfo/1.0"][cbi_entry] = md_entry

        assign("series", utils.xlate(metadata.series))
        assign("title", utils.xlate(metadata.title))
        assign("issue", utils.xlate(metadata.issue))
        assign("publisher", utils.xlate(metadata.publisher))
        assign("publicationMonth", utils.xlate_int(metadata.month))
        assign("publicationYear", utils.xlate_int(metadata.year))
        assign("numberOfIssues", utils.xlate_int(metadata.issue_count))
        assign("comments", utils.xlate(metadata.description))
        assign("genre", utils.xlate(",".join(metadata.genres)))
        assign("volume", utils.xlate_int(metadata.volume))
        assign("numberOfVolumes", utils.xlate_int(metadata.volume_count))
        assign("language", utils.xlate(utils.get_language_from_iso(metadata.language)))
        assign("country", utils.xlate(metadata.country))
        assign("rating", utils.xlate_int(metadata.critical_rating))
        assign("credits", [credit(person=c.person, role=c.role, primary=c.primary) for c in metadata.credits])
        assign("tags", list(metadata.tags))

        return cbi_container
