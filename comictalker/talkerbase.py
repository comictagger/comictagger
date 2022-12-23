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
from typing import Callable
from urllib.parse import urlsplit

import settngs

from comicapi.genericmetadata import GenericMetadata
from comictalker.resulttypes import ComicIssue, ComicSeries

logger = logging.getLogger(__name__)


class SourceDetails:
    def __init__(
        self,
        name: str = "",
        ident: str = "",
        logo: str = "",
    ):
        self.name = name
        self.id = ident
        self.logo = logo


class SourceStaticOptions:
    def __init__(
        self,
        website: str = "",
        has_issues: bool = False,
        has_alt_covers: bool = False,
        requires_apikey: bool = False,
        has_nsfw: bool = False,
        has_censored_covers: bool = False,
    ) -> None:
        self.website = website
        self.has_issues = has_issues
        self.has_alt_covers = has_alt_covers
        self.requires_apikey = requires_apikey
        self.has_nsfw = has_nsfw
        self.has_censored_covers = has_censored_covers


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

    def __init__(self, source: str, desc: str, code: int = 4, sub_code: int = 0) -> None:
        super().__init__()
        if desc == "":
            desc = "Unknown"
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


# Class talkers instance
class ComicTalker:
    """The base class for all comic source talkers"""

    default_api_url: str = ""
    default_api_key: str = ""

    def comic_settings(parser: settngs.Manager) -> None:
        ...

    def __init__(self, version: str, cache_folder: pathlib.Path, api_url: str = "", api_key: str = "") -> None:
        # Identity name for the information source etc.
        self.source_details = SourceDetails()
        self.static_options = SourceStaticOptions()
        self.api_key = api_key
        self.cache_folder = cache_folder
        self.version = version

        self.api_key = api_key or self.default_api_key
        self.api_url = api_url or self.default_api_url

        tmp_url = urlsplit(self.api_url)

        # joinurl only works properly if there is a trailing slash
        if tmp_url.path and tmp_url.path[-1] != "/":
            tmp_url = tmp_url._replace(path=tmp_url.path + "/")

        self.api_url = tmp_url.geturl()

    def check_api_key(self, key: str, url: str) -> bool:
        """
        This function should return true if the given api key and url are valid.
        If the Talker does not use an api key it should validate that the url works.
        """
        raise NotImplementedError

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
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

    def fetch_issues_by_series(self, series_id: str) -> list[ComicIssue]:
        """Expected to return a list of issues with a given series ID"""
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
