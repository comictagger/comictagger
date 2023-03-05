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

import logging
import pathlib
from typing import Any, Callable

import settngs

from comicapi.genericmetadata import GenericMetadata
from comictalker.resulttypes import ComicIssue, ComicSeries
from comictalker.talker_utils import fix_url

logger = logging.getLogger(__name__)


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

    codes = {1: "General", 2: "Network", 3: "Data", 4: "Other"}

    def __init__(self, source: str, desc: str = "Unknown", code: int = 4, sub_code: int = 0) -> None:
        super().__init__()
        self.desc = desc
        self.code = code
        self.code_name = self.codes[code]
        self.sub_code = sub_code
        self.source = source

    def __str__(self) -> str:
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

        super().__init__(source, desc, 2, sub_code)


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

        super().__init__(source, desc, 3, sub_code)


class ComicTalker:
    """The base class for all comic source talkers"""

    name: str = "Example"
    id: str = "example"
    website: str = "https://example.com"
    logo_url: str = f"{website}/logo.png"
    attribution: str = f"Metadata provided by <a href='{website}'>{name}</a>"

    def __init__(self, version: str, cache_folder: pathlib.Path) -> None:
        self.cache_folder = cache_folder
        self.version = version
        self.api_key = self.default_api_key = ""
        self.api_url = self.default_api_url = ""

    def register_settings(self, parser: settngs.Manager) -> None:
        """
        Allows registering settings using the settngs package with an argparse like interface.
        The order that settings are declared is the order they will be displayed.
        """
        return None

    def parse_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """
        settings is a dictionary of settings defined in register_settings.
        It is only guaranteed that the settings defined in register_settings will be present.
        """
        if settings.get(f"{self.id}_key"):
            self.api_key = settings[f"{self.id}_key"]
        if settings.get(f"{self.id}_url"):
            self.api_url = fix_url(settings[f"{self.id}_url"])

        settings[f"{self.id}_url"] = self.api_url

        if self.api_key == "":
            self.api_key = self.default_api_key
        if self.api_url == "":
            self.api_url = self.default_api_url
        return settings

    def check_api_key(self, url: str, key: str) -> tuple[str, bool]:
        """
        This function should return (msg, True) if the given API key and URL are valid,
        where msg is a message to display to the user.

        This function should return (msg, False) if the given API key or URL are not valid,
        where msg is a message to display to the user.

        If the Talker does not use an API key it should validate that the URL works.
        If the Talker does not use an API key or URL it should check that the source is available.
        """
        raise NotImplementedError

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
        series_match_thresh: int = 90,
    ) -> list[ComicSeries]:
        """
        This function should return a list of series that match the given series name
        according to the source the Talker uses.

        Sanitizing the series name is the responsibility of the talker.

        If `literal` == True then it is requested that no filtering or
        transformation/sanitizing of the title or results be performed by the talker.

        A sensible amount of results should be returned.

        For example the `ComicVineTalker` stops requesting new pages after the results
        become too different from the `series_name`  by use of the `titles_match` function
        provided by the `comicapi.utils` module, and only allows a maximum of 5 pages
        """
        raise NotImplementedError

    def fetch_comic_data(
        self, issue_id: str | None = None, series_id: str | None = None, issue_number: str = ""
    ) -> GenericMetadata:
        """
        This function should return an instance of GenericMetadata for a single issue.
        It is guaranteed that either `issue_id` or (`series_id` and `issue_number` is set).
        Below is an example of how this function might be implemented:

        if issue_number and series_id:
            return self.fetch_issue_data(series_id, issue_number)
        elif issue_id:
            return self.fetch_issue_data_by_issue_id(issue_id)
        else:
            return GenericMetadata()
        """
        raise NotImplementedError

    def fetch_issues_by_series(self, series_id: str) -> list[ComicIssue]:
        """Expected to return a list of issues with a given series ID"""
        raise NotImplementedError

    def fetch_issues_by_series_issue_num_and_year(
        self, series_id_list: list[str], issue_number: str, year: int | None
    ) -> list[ComicIssue]:
        """
        This function should return a single issue for each series id in
        the `series_id_list` and it should match the issue_number.

        Preferably it should also only return issues published in the given `year`.

        If there is no year given (`year` == None) or the Talker does not have issue publication info
        return the results unfiltered.
        """
        raise NotImplementedError
