"""ComicVine information source
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

import json
import logging
import pathlib
import re
import time
from typing import Any, Callable, cast
from urllib.parse import urljoin

import requests
from typing_extensions import TypedDict

import comictalker.talker_utils as t_utils
from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib import ctversion
from comictalker.resulttypes import ComicIssue, ComicSeries
from comictalker.talkerbase import ComicTalker, SourceDetails, SourceStaticOptions, TalkerDataError, TalkerNetworkError

logger = logging.getLogger(__name__)


# For the sake of ease, VOLUME refers to search results and ISSUE refers to series result.
class MUGenre(TypedDict, total=False):
    genre: str
    color: str


class MUImageURL(TypedDict):
    original: str
    thumb: str


class MUImage(TypedDict):
    url: MUImageURL
    height: int
    width: int


class MULastUpdated(TypedDict):
    timestamp: int
    as_rfc3339: str
    as_string: str


class MURecord(TypedDict, total=False):
    series_id: int
    title: str
    url: str
    description: str
    image: MUImage
    type: str
    year: str
    bayesian_rating: float
    rating_votes: int
    genres: list[MUGenre]
    last_updated: MULastUpdated


class MUStatus(TypedDict):
    volume: int
    chapter: int


class MUUserList(TypedDict):
    list_type: str
    list_icon: str
    status: MUStatus


class MUMetadata(TypedDict):
    user_list: MUUserList


class MUResult(TypedDict):
    record: MURecord
    hit_title: str
    metadata: MUMetadata
    user_genre_highlights: list[MUGenre]


class MUVolumeReply(TypedDict):
    reason: str
    status: str
    context: dict
    total_hits: int
    page: int
    per_page: int
    results: (list[MUResult] | MUResult)


class MUAssTitle(TypedDict):
    title: str


class MUCategories(TypedDict):
    series_id: int
    category: str
    votes: int
    votes_plus: int
    votes_minus: int
    added_by: int


class MUAnime(TypedDict):
    start: str
    end: str


class MURelatedSeries(TypedDict):
    relation_id: int
    relation_type: str
    related_series_id: int
    related_series_name: str
    triggered_by_relation_id: int


class MUAuthor(TypedDict):
    name: str
    author_id: int
    type: str


class MUPublisher(TypedDict):
    publisher_name: str
    publisher_id: int
    type: str
    notes: str


class MUPublication(TypedDict):
    publication_name: str
    publisher_name: str
    publisher_id: int


class MURecommendations(TypedDict):
    series_name: str
    series_id: int
    weight: int


class MUPosition(TypedDict):
    week: int
    month: int
    three_months: int
    six_months: int
    year: int


class MULists(TypedDict):
    reading: int
    wish: int
    complete: int
    unfinished: int
    custom: int


class MURank(TypedDict):
    position: MUPosition
    old_position: MUPosition


class MUIssue(TypedDict):
    series_id: int
    title: str
    url: str
    associated: list[MUAssTitle]
    description: str
    image: MUImage
    type: str
    year: str
    bayesian_rating: float
    rating_votes: int
    genres: list[MUGenre]
    categories: list[MUCategories]
    latest_chapter: int
    forum_id: int
    status: str
    licensed: bool
    completed: bool
    anime: MUAnime
    related_series: list[MURelatedSeries]
    authors: list[MUAuthor]
    publishers: list[MUPublisher]
    publications: list[MUPublication]
    recommendations: list[MURecommendations]
    category_recommendations: list[MURecommendations]
    rank: MURank
    last_updated: MULastUpdated


class MangaUpdatesTalker(ComicTalker):
    default_api_url = "https://api.mangaupdates.com/v1"

    def __init__(
        self,
        version: str,
        cache_folder: pathlib.Path,
        api_url: str = "",
        api_key: str = "",
        series_match_thresh: int = 90,
        remove_html_tables: bool = False,
        use_series_start_as_volume: bool = False,
        wait_on_ratelimit: bool = False,
    ):
        super().__init__(version, cache_folder, api_url, api_key)
        self.source_details = SourceDetails(
            name="Manga Updates",
            ident="mangaupdates",
            logo="comictalker/talkers/logos/mangaupdates.jpg",
        )
        self.static_options = SourceStaticOptions(
            website="https://www.mangaupdates.com",
            has_issues=False,
            has_alt_covers=False,
            requires_apikey=False,
            has_nsfw=True,
            has_censored_covers=True,
        )
        # TODO Temp holder for settings
        self.settings_options = {
            "use_search_title": False,
            "dup_title": False,
            "use_original_publisher": False,
            "filter_nsfw": False,
            "filter_dojin": False,
            "use_ongoing": False,
            "use_series_start_as_volume": False,
            "api_url": "https://api.mangaupdates.com/v1",
        }

        # Identity name for the information source
        self.source_name: str = self.source_details.id
        self.source_name_friendly: str = self.source_details.name

        self.series_match_thresh: int = series_match_thresh

        # TODO Overwrite default settings with saved

        # Flags for comparing cache options to know if the cache needs to be refreshed.
        self.flags = []
        self.flags.append(self.settings_options["use_search_title"])
        self.flags.append(self.settings_options["filter_nsfw"])
        self.flags.append(self.settings_options["filter_dojin"])
        self.flags.append(self.settings_options["use_original_publisher"])
        self.flags.append(self.settings_options["dup_title"])

    def check_api_key(self, key: str, url: str) -> bool:
        return False

    def get_cv_content(self, url: str, params: dict[str, Any]) -> MUVolumeReply:
        """
        Get the content from the MU server.
        """
        while True:
            mu_response: MUVolumeReply = self.get_url_content(url, params)
            if mu_response.get("status") == "exception":
                logger.debug(f"{self.source_name_friendly} query failed with error {mu_response['reason']}.")
                raise TalkerNetworkError(self.source_name_friendly, 0, f"{mu_response['reason']}")

            # it's all good
            break
        return mu_response

    def get_url_content(self, url: str, params: dict[str, Any]) -> Any:
        # connect to server:
        # if there is a 500 error, try a few more times before giving up
        # any other error, just bail
        for tries in range(3):
            try:
                if not params:
                    resp = requests.get(url, headers={"user-agent": "comictagger/" + ctversion.version})
                else:
                    resp = requests.post(url, json=params, headers={"user-agent": "comictagger/" + ctversion.version})
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 500:
                    logger.debug(f"Try #{tries + 1}: ")
                    time.sleep(1)
                    logger.debug(str(resp.status_code))
                if resp.status_code == 400:
                    logger.debug(f"Validation or service error: {resp.json()}")
                    raise TalkerNetworkError(
                        self.source_name_friendly, 2, f"Validation or service error: {resp.json()}"
                    )
                if resp.status_code == 404:
                    logger.debug(f"Series not found: {resp.json()}")
                    raise TalkerNetworkError(self.source_name_friendly, 2, f"Series not found: {resp.json()}")

                else:
                    break

            except requests.exceptions.Timeout:
                logger.debug(f"Connection to {self.source_name_friendly} timed out.")
                raise TalkerNetworkError(self.source_name_friendly, 4)
            except requests.exceptions.RequestException as e:
                logger.debug(f"Request exception: {e}")
                raise TalkerNetworkError(self.source_name_friendly, 0, str(e)) from e
            except json.JSONDecodeError as e:
                logger.debug(f"JSON decode error: {e}")
                raise TalkerDataError(self.source_name_friendly, 2, f"{self.source_name_friendly} did not provide json")

        raise TalkerNetworkError(self.source_name_friendly, 5)

    def format_search_results(self, search_results: list[MUResult]) -> list[ComicSeries]:

        formatted_results = []
        for record in search_results:
            formatted_results.append(self.format_volume(record["record"], record["hit_title"]))

        return formatted_results

    def format_volume(self, MUIssue, title=""):
        if MUIssue["image"]["url"]["original"] is None:
            image_url = ""
        else:
            image_url = MUIssue["image"]["url"]["original"]

        if MUIssue["year"] is None:
            start_year = 0
        else:
            start_year = utils.xlate(MUIssue["year"], True)

        if not title:
            title = MUIssue["title"]

        count = None
        if "status" in MUIssue:
            count_match = re.match(r"^(\d+)\s+volumes?", MUIssue["status"], re.IGNORECASE | re.MULTILINE)
            if count_match is not None:
                count = int(count_match.groups()[0])
        return ComicSeries(
            aliases=[],  # Not returned from search, use to store hit_title # record["hit_title"]
            count_of_issues=count,
            description=MUIssue.get("description", ""),
            id=MUIssue["series_id"],
            image_url=image_url,
            name=title,
            publisher="",  # Publisher not returned from search
            start_year=start_year,
        )

    def fetch_issues_by_series(self, series_id: str) -> list[ComicIssue]:
        """Expected to return a list of issues with a given series ID"""
        series = self.fetch_series_data(int(series_id))
        issues = []
        for i in range(series.count_of_issues or 0):
            issues.append(self.format_issue(series, i + 1))
        return issues

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
    ) -> list[ComicSeries]:

        # Sanitize the series name for searching
        search_series_name = utils.sanitize_title(series_name, literal)

        params: dict[str, Any] = {
            "search": search_series_name,
            "exclude_genre": [],
            "page": 1,
            "perpage": 100,
        }

        mu_response = self.get_cv_content(urljoin(self.api_url, "series/search"), params)

        search_results: list[MUResult] = []

        total_result_count = mu_response["total_hits"]

        # 1. Don't fetch more than some sane amount of pages.
        # 2. Halt when any result on the current page is less than or equal to a set ratio using thefuzz
        max_results = 500  # 5 pages

        current_result_count = mu_response["per_page"] * mu_response["page"]
        total_result_count = min(total_result_count, max_results)

        if callback is None or True:
            logger.debug(
                "Found %d of %d results", mu_response["per_page"] * mu_response["page"], mu_response["total_hits"]
            )
        search_results.extend(cast(list[MUResult], mu_response["results"]))
        page = 1

        if callback is not None:
            callback(current_result_count, total_result_count)

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:

            if not literal:
                # Stop searching once any entry falls below the threshold
                stop_searching = any(
                    not utils.titles_match(search_series_name, volume["hit_title"], self.series_match_thresh)
                    for volume in cast(list[MUResult], mu_response["results"])
                )

                if stop_searching:
                    break

            if callback is None or True:
                logger.debug(f"getting another page of results {current_result_count} of {total_result_count}...")
            page += 1

            params["page"] = page
            mu_response = self.get_cv_content(urljoin(self.api_url, "series/search"), params)

            search_results.extend(cast(list[MUResult], mu_response["results"]))
            current_result_count += mu_response["per_page"]

            if callback is not None:
                callback(current_result_count, total_result_count)

        # Format result to ComicSearchResult
        formatted_search_results = self.format_search_results(search_results)

        return formatted_search_results

    # Get issue or volume information
    def fetch_comic_data(
        self, issue_id: str | None = None, series_id: str | None = None, issue_number: str = ""
    ) -> GenericMetadata:
        if issue_id:
            series_id, _, issue_number = issue_id.partition("-")
        issue_num = IssueString(issue_number).num
        if issue_num is None:
            return GenericMetadata()
        if issue_num and series_id:
            series = self.fetch_series_data(int(series_id))
            return t_utils.map_comic_issue_to_metadata(self.format_issue(series, int(issue_num)), self.source_name)
        else:
            return GenericMetadata()

    def fetch_series_data(self, series_id: int):

        issue_url = urljoin(self.api_url, f"series/{series_id}")
        mu_response = self.get_cv_content(issue_url, {})

        issue_results = cast(MUIssue, mu_response)
        return self.format_volume(issue_results)

    def format_issues(self, series_list: list[ComicSeries], issue_number: int):
        formatted_results = []
        for series in series_list:
            formatted_results.append(self.format_issue(series, issue_number))
        return formatted_results

    def format_issue(self, series: ComicSeries, issue_number: int):
        if issue_number == 1:
            image_url = series.image_url
        else:
            image_url = ""

        return ComicIssue(
            aliases=[],
            description="",
            id=f"{series.id}-{issue_number}",  # not unique
            issue_number=str(issue_number),
            image_url=image_url,
            site_detail_url="",
            alt_image_urls=[],
            cover_date="",
            name="",
            series=series,
            credits=[],
            complete=True,
            locations=[],
            characters=[],
            story_arcs=[],
            teams=[],
        )

    def fetch_issues_by_series_issue_num_and_year(
        self, series_id_list: list[str], issue_number: str, year: str | int | None
    ) -> list[ComicIssue]:
        issue_num = IssueString(issue_number).num
        if issue_num is None:
            return []
        series_list = []
        for series_id in series_id_list:
            series = self.fetch_series_data(int(series_id))
            if int(issue_num) < series.count_of_issues:
                series_list.append(series)

        return self.format_issues(series_list, int(issue_num))
