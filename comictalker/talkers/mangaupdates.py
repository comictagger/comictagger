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
from comictaggerlib import ctversion
from comictalker.comiccacher import ComicCacher
from comictalker.resulttypes import ComicIssue, ComicSeries, Credit
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
            if record["record"]["image"]["url"]["original"] is None:
                image_url = ""
            else:
                image_url = record["record"]["image"]["url"]["original"]

            if record["record"]["year"] is None:
                start_year = 0
            else:
                start_year = utils.xlate(record["record"]["year"], True)

            if self.settings_options["use_search_title"]:
                title = record["hit_title"]
            else:
                title = record["record"]["title"]

            formatted_results.append(
                ComicSeries(
                    aliases=[record["hit_title"]],  # Not returned from search, use to store hit_title
                    count_of_issues=0,  # Not returned from search
                    description=record["record"].get("description", ""),
                    id=str(record["record"]["series_id"]),
                    image_url=image_url,
                    name=title,
                    publisher="",  # Publisher not returned from search
                    start_year=start_year,
                )
            )

        return formatted_results

    def format_issue(self, issue: MUIssue, volume: ComicSeries, complete: bool = True) -> ComicIssue:
        # Will always be complete

        image_url = issue["image"]["url"].get("original", "")

        aliases_list = []
        for alias in issue["associated"]:
            aliases_list.append(alias["title"])

        publisher_list = []
        for pub in issue["publishers"]:
            if self.settings_options["use_original_publisher"] and pub["type"] == "Original":
                publisher_list.append(pub["publisher_name"])
            elif not self.settings_options["use_original_publisher"] and pub["type"] == "English":
                publisher_list.append(pub["publisher_name"])
        publisher = ", ".join(publisher_list)

        persons_list = []
        for person in issue["authors"]:
            persons_list.append(Credit(name=person["name"], role=person["type"]))

        # Use search title can desync between series search and fetching the issue so do this:
        title = issue["title"]
        if self.settings_options["use_search_title"] and len(volume.aliases) == 1:
            title = volume.aliases[0]

        issue_title = ""
        if self.settings_options["dup_title"]:
            issue_title = volume.name

        start_year = utils.xlate(issue["year"], True)

        manga = ""
        if issue["type"] == "Manga":
            manga = "Yes"

        genre_list = []
        for genre in issue["genres"]:
            genre_list.append(genre["genre"])

        tag_list = []
        for cat in issue["categories"]:
            tag_list.append(cat["category"])

        count_of_issue = 0  # TODO parse from status but also publisher notes depending on lang?
        # TODO Option to use ongoing number?
        if self.settings_options["use_ongoing"]:
            ...
        reg = re.compile(r"((\d+).*volume.).*(complete)(.*)", re.IGNORECASE)
        reg_match = reg.search(issue["status"])
        if reg_match is not None:
            count_of_issue = utils.xlate(reg_match.group(2), True)

        volume.name = title
        volume.count_of_issues = count_of_issue
        volume.start_year = start_year
        volume.publisher = publisher
        volume.image_url = image_url
        volume.description = issue.get("description", "")

        formatted_results = ComicIssue(
            aliases=aliases_list,
            description=issue.get("description", ""),
            id=str(issue["series_id"]),
            image_url=image_url,
            rating=issue["bayesian_rating"] / 2,
            manga=manga,
            genres=genre_list,
            tags=tag_list,
            name=issue_title,
            site_detail_url=issue.get("url", ""),
            series=volume,
            credits=persons_list,
            complete=complete,
        )

        return formatted_results

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
    ) -> list[ComicSeries]:

        # Sanitize the series name for searching
        search_series_name = utils.sanitize_title(series_name, literal)
        logger.info(f"{self.source_name_friendly} searching: {search_series_name}")

        # Before we search online, look in our cache, since we might have done this same search recently
        # For literal searches always retrieve from online
        cvc = ComicCacher(self.cache_folder, self.version)
        if not refresh_cache and not literal:
            cached_search_results = cvc.get_search_results(self.source_name, series_name)

            # Check if filter options have been changed, ignore cache if so.
            if len(cached_search_results) > 0:
                if (
                    self.flags[0] == self.settings_options["use_search_title"]
                    and self.flags[1] == self.settings_options["filter_nsfw"]
                    and self.flags[2] == self.settings_options["filter_dojin"]
                ):
                    return cached_search_results

        params: dict[str, Any] = {
            "search": search_series_name,
            "exclude_genre": [],
            "page": 1,
            "perpage": 100,
        }

        if self.settings_options["filter_nsfw"]:
            params["exclude_genre"].append("Adult")
            params["exclude_genre"].append("Hentai")
        if self.settings_options["filter_dojin"]:
            params["exclude_genre"].append("Doujinshi")

        mu_response = self.get_cv_content(urljoin(self.api_url, "series/search"), params)

        search_results: list[MUResult] = []

        total_result_count = mu_response["total_hits"]

        # 1. Don't fetch more than some sane amount of pages.
        # 2. Halt when any result on the current page is less than or equal to a set ratio using thefuzz
        max_results = 500  # 5 pages

        current_result_count = mu_response["per_page"] * mu_response["page"]
        total_result_count = min(total_result_count, max_results)

        if callback is None:
            logger.debug(
                f"Found {mu_response['per_page'] * mu_response['page']} of {mu_response['total_hits']} results"
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
                    not utils.titles_match(search_series_name, volume["record"]["title"], self.series_match_thresh)
                    for volume in cast(list[MUResult], mu_response["results"])
                )

                if stop_searching:
                    break

            if callback is None:
                logger.debug(f"getting another page of results {current_result_count} of {total_result_count}...")
            page += 1

            params["page"] = page
            mu_response = self.get_cv_content(urljoin(self.api_url, "series/search"), params)

            search_results.extend(cast(list[MUResult], mu_response["results"]))
            # current_result_count += mu_response["number_of_page_results"]

            if callback is not None:
                callback(current_result_count, total_result_count)

        # Format result to ComicSearchResult
        formatted_search_results = self.format_search_results(search_results)

        # Cache these search results, even if it's literal we cache the results
        # The most it will cause is extra processing time
        cvc.add_search_results(self.source_name, series_name, formatted_search_results)

        # Refresh the option flags
        self.flags[0] = self.settings_options["use_search_title"]
        self.flags[1] = self.settings_options["filter_nsfw"]
        self.flags[2] = self.settings_options["filter_dojin"]

        return formatted_search_results

    # Get issue or volume information
    def fetch_comic_data(
        self, issue_id: str | None = None, series_id: str | None = None, issue_number: str = ""
    ) -> GenericMetadata:
        # issue_id in this case is series_id because MU lacks issue data
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_issues_result = cvc.get_issue_info(str(series_id), self.source_name)

        # It's possible a new search with new options has wiped the series publisher so refresh if it's empty
        if (
            cached_issues_result
            and cached_issues_result.series.publisher
            and self.flags[0] == self.settings_options["use_search_title"]
            and self.flags[3] == self.settings_options["use_original_publisher"]
            and self.flags[4] == self.settings_options["dup_title"]
        ):

            return t_utils.map_comic_issue_to_metadata(
                cached_issues_result,
                self.source_name_friendly,
                False,
                bool(self.settings_options["use_series_start_as_volume"]),
            )

        issue_url = urljoin(self.api_url, f"series/{series_id}")
        # params = {"api_key": self.api_key, "format": "json"}
        # mu_response = self.get_cv_content(issue_url, params)
        mu_response = self.get_cv_content(issue_url, {})

        issue_results = cast(MUIssue, mu_response)
        # TODO Store file parsed issue number? Don't want to cache it
        # if issue_number:
        # issue_results["issue_number"] = issue_number

        # Fetch the cached volume info which should have the hit_title in aliases
        volume = cvc.get_series_info(str(series_id), self.source_name)

        if volume is None:
            volume = ComicSeries(
                aliases=[],
                count_of_issues=0,
                description="",
                id=str(series_id),
                image_url="",
                name="",
                publisher="",
                start_year=0,
            )

        # Format to expected output
        formatted_issues_result = self.format_issue(issue_results, volume, True)

        cvc.add_series_issues_info(self.source_name, [formatted_issues_result])

        # Series will now have publisher so update cache record
        cvc.add_series_info(self.source_name, formatted_issues_result.series)

        # Refresh options flags
        self.flags[0] = self.settings_options["use_search_title"]
        self.flags[3] = self.settings_options["use_original_publisher"]
        self.flags[4] = self.settings_options["dup_title"]

        # Now, map the ComicIssue data to generic metadata
        return t_utils.map_comic_issue_to_metadata(
            formatted_issues_result,
            self.source_name_friendly,
            False,
            bool(self.settings_options["use_series_start_as_volume"]),
        )
