"""A template for an information source
"""
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
from typing import Any, Callable

from typing_extensions import Required, TypedDict

from comicapi.genericmetadata import GenericMetadata
from comictalker.resulttypes import ComicIssue, ComicVolume

logger = logging.getLogger(__name__)

# NOTE: Series and Volume are synonymous. Some sources (ComicVine) use "volume" and others (MangaUpdates) use "series".


class SourceDetails:
    def __init__(
        self,
        name: str = "",
        ident: str = "",
    ):
        self.name = name
        self.id = ident


class SourceStaticOptions:
    def __init__(
        self,
        logo_url: str = "",
        has_issues: bool = False,
        has_alt_covers: bool = False,
        requires_apikey: bool = False,
        has_nsfw: bool = False,
        has_censored_covers: bool = False,
    ) -> None:
        self.logo_url = logo_url
        self.has_issues = has_issues
        self.has_alt_covers = has_alt_covers
        self.requires_apikey = requires_apikey
        self.has_nsfw = has_nsfw
        self.has_censored_covers = has_censored_covers


class SourceSettingsOptions(TypedDict):
    # Source settings options and used to generate settings options in panel
    name: Required[str]  # Internal name for setting i.e "remove_html_tables"
    text: Required[str]  # Display text i.e "Remove HTML tables"
    help_text: str  # Tooltip text i.e "Enabling this will remove HTML tables from the description."
    hidden: Required[bool]  # To hide an option from the settings menu.
    type: Required[type[bool] | type[int] | type[str] | type[float]]
    value: Any


class TalkerError(Exception):
    """Base class exception for information sources.

    Attributes:
        code -- a numerical code
            1 - General
            2 - Network
            3 - Data
        desc -- description of the error
        source -- the name of the source producing the error
    """

    codes = {
        1: "General",
        2: "Network",
        3: "Data",
        4: "Other",
    }

    def __init__(self, source: str = "", code: int = 4, desc: str = "", sub_code: int = 0) -> None:
        super().__init__()
        if desc == "":
            desc = "Unknown"
        self.desc = desc
        self.code = code
        self.code_name = self.codes[code]
        self.sub_code = sub_code
        self.source = source

    def __str__(self):
        return f"{self.source} encountered a {self.code_name} error. {self.desc}"


class TalkerNetworkError(TalkerError):
    """Network class exception for information sources

    Attributes:
        sub_code -- numerical code for finer detail
            1 -- connected refused
            2 -- api key
            3 -- rate limit
            4 -- timeout
    """

    net_codes = {
        0: "General network error.",
        1: "The connection was refused.",
        2: "An API key error occurred.",
        3: "Rate limit exceeded. Please wait a bit or enter a personal key if using the default.",
        4: "The connection timed out.",
        5: "Number of retries exceeded.",
    }

    def __init__(self, source: str = "", sub_code: int = 0, desc: str = "") -> None:
        if desc == "":
            desc = self.net_codes[sub_code]

        super().__init__(source, 2, desc, sub_code)


class TalkerDataError(TalkerError):
    """Data class exception for information sources

    Attributes:
        sub_code -- numerical code for finer detail
            1 -- unexpected data
            2 -- malformed data
            3 -- missing data
    """

    data_codes = {
        0: "General data error.",
        1: "Unexpected data encountered.",
        2: "Malformed data encountered.",
        3: "Missing data encountered.",
    }

    def __init__(self, source: str = "", sub_code: int = 0, desc: str = "") -> None:
        if desc == "":
            desc = self.data_codes[sub_code]

        super().__init__(source, 3, desc, sub_code)


# Class talkers instance
class ComicTalker:
    """This is the class for mysource."""

    def __init__(self) -> None:
        # Identity name for the information source etc.
        self.source_details: SourceDetails = (
            SourceDetails()
        )  # Can use this to test if custom talker has been configured
        self.static_options: SourceStaticOptions = SourceStaticOptions()

    def check_api_key(self, key: str, url: str):
        raise NotImplementedError

    # Search for series/volumes
    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
    ) -> list[ComicVolume]:
        raise NotImplementedError

    # Get issues in a series/volume
    def fetch_issues_by_volume(self, series_id: int) -> list[ComicIssue]:
        raise NotImplementedError

    # Get issue or volume information
    def fetch_comic_data(self, issue_id: int = 0, series_id: int = 0, issue_number: str = "") -> GenericMetadata:
        """This function is expected to handle a few possibilities:
        1. Only series_id. Retrieve the SERIES/VOLUME information only.
        2. series_id and issue_number. Retrieve the ISSUE information.
        3. Only issue_id. Retrieve the ISSUE information."""
        raise NotImplementedError

    # TODO Should be able to remove with alt cover rework
    def fetch_alternate_cover_urls(self, issue_id: int) -> list[str]:
        raise NotImplementedError

    def fetch_issues_by_volume_issue_num_and_year(
        self, volume_id_list: list[int], issue_number: str, year: str | int | None
    ) -> list[ComicIssue]:
        raise NotImplementedError
