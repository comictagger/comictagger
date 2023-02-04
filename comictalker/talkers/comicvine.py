"""
ComicVine information source
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

import argparse
import json
import logging
import pathlib
import time
from typing import Any, Callable, Generic, TypeVar
from urllib.parse import urljoin, urlsplit

import requests
import settngs
from typing_extensions import Required, TypedDict

import comictalker.talker_utils as talker_utils
from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictalker.comiccacher import ComicCacher
from comictalker.comictalker import ComicTalker, TalkerDataError, TalkerNetworkError
from comictalker.resulttypes import ComicIssue, ComicSeries, Credit

logger = logging.getLogger(__name__)


class CVTypeID:
    Volume = "4050"  # CV uses volume to mean series
    Issue = "4000"


class CVImage(TypedDict, total=False):
    icon_url: str
    medium_url: str
    screen_url: str
    screen_large_url: str
    small_url: str
    super_url: Required[str]
    thumb_url: str
    tiny_url: str
    original_url: str
    image_tags: str


class CVAltImage(TypedDict):
    original_url: str
    id: int
    caption: str
    image_tags: str


class CVPublisher(TypedDict, total=False):
    api_detail_url: str
    id: int
    name: Required[str]


class CVCredit(TypedDict):
    api_detail_url: str
    id: int
    name: str
    site_detail_url: str


class CVPersonCredit(TypedDict):
    api_detail_url: str
    id: int
    name: str
    site_detail_url: str
    role: str


class CVSeries(TypedDict):
    api_detail_url: str
    site_detail_url: str
    aliases: str
    count_of_issues: int
    description: str
    id: int
    image: CVImage
    name: str
    publisher: CVPublisher
    start_year: str
    resource_type: str
    characters: list[CVCredit]
    locations: list[CVCredit]
    people: list[CVPersonCredit]


class CVIssue(TypedDict, total=False):
    aliases: str
    api_detail_url: str
    associated_images: list[CVAltImage]
    character_credits: list[CVCredit]
    character_died_in: None
    concept_credits: list[CVCredit]
    cover_date: str
    date_added: str
    date_last_updated: str
    deck: None
    description: str
    first_appearance_characters: None
    first_appearance_concepts: None
    first_appearance_locations: None
    first_appearance_objects: None
    first_appearance_storyarcs: None
    first_appearance_teams: None
    has_staff_review: bool
    id: int
    image: CVImage
    issue_number: str
    location_credits: list[CVCredit]
    name: str
    object_credits: list[CVCredit]
    person_credits: list[CVPersonCredit]
    site_detail_url: str
    store_date: str
    story_arc_credits: list[CVCredit]
    team_credits: list[CVCredit]
    team_disbanded_in: None
    volume: CVSeries  # CV uses volume to mean series


T = TypeVar("T", CVIssue, CVSeries, list[CVSeries], list[CVIssue])


class CVResult(TypedDict, Generic[T]):
    error: str
    limit: int
    offset: int
    number_of_page_results: int
    number_of_total_results: int
    status_code: int
    results: T
    version: str


CV_STATUS_RATELIMIT = 107


class ComicVineTalker(ComicTalker):
    name: str = "Comic Vine"
    id: str = "comicvine"
    logo_url: str = "https://comicvine.gamespot.com/a/bundles/comicvinesite/images/logo.png"
    website: str = "https://comicvine.gamespot.com/"
    attribution: str = f"Metadata provided by <a href='{website}'>{name}</a>"

    def __init__(self, version: str, cache_folder: pathlib.Path):
        super().__init__(version, cache_folder)
        # Default settings
        self.api_url: str = "https://comicvine.gamespot.com/api"
        self.api_key: str = "27431e6787042105bd3e47e169a624521f89f3a4"
        self.remove_html_tables: bool = False
        self.use_series_start_as_volume: bool = False
        self.wait_on_ratelimit: bool = False

        tmp_url = urlsplit(self.api_url)

        # joinurl only works properly if there is a trailing slash
        if tmp_url.path and tmp_url.path[-1] != "/":
            tmp_url = tmp_url._replace(path=tmp_url.path + "/")

        self.api_url = tmp_url.geturl()

        # NOTE: This was hardcoded before which is why it isn't in settings
        self.wait_on_ratelimit_time: int = 20

    def register_settings(self, parser: settngs.Manager) -> None:
        parser.add_setting("--cv-use-series-start-as-volume", default=False, action=argparse.BooleanOptionalAction)
        parser.add_setting("--cv-wait-on-ratelimit", default=False, action=argparse.BooleanOptionalAction)
        parser.add_setting(
            "--cv-remove-html-tables",
            default=False,
            action=argparse.BooleanOptionalAction,
            help="Removes html tables instead of converting them to text.",
        )
        parser.add_setting(
            "--cv-api-key",
            help="Use the given Comic Vine API Key.",
        )
        parser.add_setting(
            "--cv-url",
            help="Use the given Comic Vine URL.",
        )

    def parse_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        if settings["cv_api_key"]:
            self.api_key = settings["cv_api_key"]
        if settings["cv_url"]:
            tmp_url = urlsplit(settings["cv_url"])
            # joinurl only works properly if there is a trailing slash
            if tmp_url.path and tmp_url.path[-1] != "/":
                tmp_url = tmp_url._replace(path=tmp_url.path + "/")

            self.api_url = tmp_url.geturl()

        self.use_series_start_as_volume = settings["cv_use_series_start_as_volume"]
        self.wait_on_ratelimit = settings["cv_wait_on_ratelimit"]
        self.remove_html_tables = settings["cv_remove_html_tables"]
        return settngs

    def check_api_key(self, key: str, url: str) -> bool:
        if not url:
            url = self.api_url
        try:
            tmp_url = urlsplit(url)
            if tmp_url.path and tmp_url.path[-1] != "/":
                tmp_url = tmp_url._replace(path=tmp_url.path + "/")
            url = tmp_url.geturl()
            test_url = urljoin(url, "issue/1/")

            cv_response: CVResult = requests.get(
                test_url,
                headers={"user-agent": "comictagger/" + self.version},
                params={"api_key": key, "format": "json", "field_list": "name"},
            ).json()

            # Bogus request, but if the key is wrong, you get error 100: "Invalid API Key"
            return cv_response["status_code"] != 100
        except Exception:
            return False

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
        series_match_thresh: int = 90,
    ) -> list[ComicSeries]:
        # Sanitize the series name for comicvine searching, comicvine search ignore symbols
        search_series_name = utils.sanitize_title(series_name, literal)
        logger.info(f"{self.name} searching: {search_series_name}")

        # Before we search online, look in our cache, since we might have done this same search recently
        # For literal searches always retrieve from online
        cvc = ComicCacher(self.cache_folder, self.version)
        if not refresh_cache and not literal:
            cached_search_results = cvc.get_search_results(self.id, series_name)

            if len(cached_search_results) > 0:
                return cached_search_results

        params = {  # CV uses volume to mean series
            "api_key": self.api_key,
            "format": "json",
            "resources": "volume",
            "query": search_series_name,
            "field_list": "volume,name,id,start_year,publisher,image,description,count_of_issues,aliases",
            "page": 1,
            "limit": 100,
        }

        cv_response: CVResult[list[CVSeries]] = self._get_cv_content(urljoin(self.api_url, "search"), params)

        search_results: list[CVSeries] = []

        # see http://api.comicvine.com/documentation/#handling_responses

        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        # 8 Dec 2018 - Comic Vine changed query results again. Terms are now
        # ORed together, and we get thousands of results.  Good news is the
        # results are sorted by relevance, so we can be smart about halting the search.
        # 1. Don't fetch more than some sane amount of pages.
        # 2. Halt when any result on the current page is less than or equal to a set ratio using thefuzz
        max_results = 500  # 5 pages

        total_result_count = min(total_result_count, max_results)

        if callback is None:
            logger.debug(
                f"Found {cv_response['number_of_page_results']} of {cv_response['number_of_total_results']} results"
            )
        search_results.extend(cv_response["results"])
        page = 1

        if callback is not None:
            callback(current_result_count, total_result_count)

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:

            if not literal:
                # Stop searching once any entry falls below the threshold
                stop_searching = any(
                    not utils.titles_match(search_series_name, series["name"], series_match_thresh)
                    for series in cv_response["results"]
                )

                if stop_searching:
                    break

            if callback is None:
                logger.debug(f"getting another page of results {current_result_count} of {total_result_count}...")
            page += 1

            params["page"] = page
            cv_response = self._get_cv_content(urljoin(self.api_url, "search"), params)

            search_results.extend(cv_response["results"])
            current_result_count += cv_response["number_of_page_results"]

            if callback is not None:
                callback(current_result_count, total_result_count)

        # Format result to ComicIssue
        formatted_search_results = self._format_search_results(search_results)

        # Cache these search results, even if it's literal we cache the results
        # The most it will cause is extra processing time
        cvc.add_search_results(self.id, series_name, formatted_search_results)

        return formatted_search_results

    def fetch_comic_data(
        self, issue_id: str | None = None, series_id: str | None = None, issue_number: str = ""
    ) -> GenericMetadata:
        comic_data = GenericMetadata()
        if issue_id:
            comic_data = self._fetch_issue_data_by_issue_id(issue_id)
        elif issue_number and series_id:
            comic_data = self._fetch_issue_data(int(series_id), issue_number)

        return comic_data

    def fetch_issues_by_series(self, series_id: str) -> list[ComicIssue]:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_series_issues_result = cvc.get_series_issues_info(series_id, self.id)

        series_data = self._fetch_series_data(int(series_id))

        if len(cached_series_issues_result) == series_data.count_of_issues:
            return cached_series_issues_result

        params = {  # CV uses volume to mean series
            "api_key": self.api_key,
            "filter": f"volume:{series_id}",
            "format": "json",
            "field_list": "id,volume,issue_number,name,image,cover_date,site_detail_url,description,aliases,associated_images",
            "offset": 0,
        }
        cv_response: CVResult[list[CVIssue]] = self._get_cv_content(urljoin(self.api_url, "issues/"), params)

        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        series_issues_result = cv_response["results"]
        page = 1
        offset = 0

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:
            page += 1
            offset += cv_response["number_of_page_results"]

            params["offset"] = offset
            cv_response = self._get_cv_content(urljoin(self.api_url, "issues/"), params)

            series_issues_result.extend(cv_response["results"])
            current_result_count += cv_response["number_of_page_results"]

        # Format to expected output
        formatted_series_issues_result = self._format_issue_results(series_issues_result)

        cvc.add_series_issues_info(self.id, formatted_series_issues_result)

        return formatted_series_issues_result

    def fetch_issues_by_series_issue_num_and_year(
        self, series_id_list: list[str], issue_number: str, year: str | int | None
    ) -> list[ComicIssue]:
        series_filter = ""
        for vid in series_id_list:
            series_filter += str(vid) + "|"
        flt = f"volume:{series_filter},issue_number:{issue_number}"  # CV uses volume to mean series

        int_year = utils.xlate(year, True)
        if int_year is not None:
            flt += f",cover_date:{int_year}-1-1|{int_year + 1}-1-1"

        params: dict[str, str | int] = {  # CV uses volume to mean series
            "api_key": self.api_key,
            "format": "json",
            "field_list": "id,volume,issue_number,name,image,cover_date,site_detail_url,description,aliases,associated_images",
            "filter": flt,
        }

        cv_response: CVResult[list[CVIssue]] = self._get_cv_content(urljoin(self.api_url, "issues/"), params)

        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        filtered_issues_result = cv_response["results"]
        page = 1
        offset = 0

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:
            page += 1
            offset += cv_response["number_of_page_results"]

            params["offset"] = offset
            cv_response = self._get_cv_content(urljoin(self.api_url, "issues/"), params)

            filtered_issues_result.extend(cv_response["results"])
            current_result_count += cv_response["number_of_page_results"]

        formatted_filtered_issues_result = self._format_issue_results(filtered_issues_result)

        return formatted_filtered_issues_result

    def _get_cv_content(self, url: str, params: dict[str, Any]) -> CVResult:
        """
        Get the content from the CV server.  If we're in "wait mode" and status code is a rate limit error
        sleep for a bit and retry.
        """
        total_time_waited = 0
        limit_wait_time = 1
        counter = 0
        wait_times = [1, 2, 3, 4]
        while True:
            cv_response: CVResult = self._get_url_content(url, params)
            if self.wait_on_ratelimit and cv_response["status_code"] == CV_STATUS_RATELIMIT:
                logger.info(f"Rate limit encountered.  Waiting for {limit_wait_time} minutes\n")
                time.sleep(limit_wait_time * 60)
                total_time_waited += limit_wait_time
                limit_wait_time = wait_times[counter]
                if counter < 3:
                    counter += 1
                # don't wait much more than 20 minutes
                if total_time_waited < self.wait_on_ratelimit_time:
                    continue
            if cv_response["status_code"] != 1:
                logger.debug(
                    f"{self.name} query failed with error #{cv_response['status_code']}:  [{cv_response['error']}]."
                )
                raise TalkerNetworkError(self.name, 0, f"{cv_response['status_code']}: {cv_response['error']}")

            # it's all good
            break
        return cv_response

    def _get_url_content(self, url: str, params: dict[str, Any]) -> Any:
        # connect to server:
        # if there is a 500 error, try a few more times before giving up
        # any other error, just bail
        for tries in range(3):
            try:
                resp = requests.get(url, params=params, headers={"user-agent": "comictagger/" + self.version})
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 500:
                    logger.debug(f"Try #{tries + 1}: ")
                    time.sleep(1)
                    logger.debug(str(resp.status_code))
                else:
                    break

            except requests.exceptions.Timeout:
                logger.debug(f"Connection to {self.name} timed out.")
                raise TalkerNetworkError(self.name, 4)
            except requests.exceptions.RequestException as e:
                logger.debug(f"Request exception: {e}")
                raise TalkerNetworkError(self.name, 0, str(e)) from e
            except json.JSONDecodeError as e:
                logger.debug(f"JSON decode error: {e}")
                raise TalkerDataError(self.name, 2, "ComicVine did not provide json")

        raise TalkerNetworkError(self.name, 5)

    def _format_search_results(self, search_results: list[CVSeries]) -> list[ComicSeries]:
        formatted_results = []
        for record in search_results:
            # Flatten publisher to name only
            if record.get("publisher") is None:
                pub_name = ""
            else:
                pub_name = record["publisher"].get("name", "")

            if record.get("image") is None:
                image_url = ""
            else:
                image_url = record["image"].get("super_url", "")

            start_year = utils.xlate(record.get("start_year", ""), True)

            aliases = record.get("aliases") or ""

            formatted_results.append(
                ComicSeries(
                    aliases=aliases.splitlines(),
                    count_of_issues=record.get("count_of_issues", 0),
                    description=record.get("description", ""),
                    id=str(record["id"]),
                    image_url=image_url,
                    name=record["name"],
                    publisher=pub_name,
                    start_year=start_year,
                )
            )

        return formatted_results

    def _format_issue_results(self, issue_results: list[CVIssue], complete: bool = False) -> list[ComicIssue]:
        formatted_results = []
        for record in issue_results:
            # Extract image super and thumb to name only
            if record.get("image") is None:
                image_url = ""
            else:
                image_url = record["image"].get("super_url", "")

            alt_images_list = []
            for alt in record["associated_images"]:
                alt_images_list.append(alt["original_url"])

            character_list = []
            if record.get("character_credits"):
                for char in record["character_credits"]:
                    character_list.append(char["name"])

            location_list = []
            if record.get("location_credits"):
                for loc in record["location_credits"]:
                    location_list.append(loc["name"])

            teams_list = []
            if record.get("team_credits"):
                for loc in record["team_credits"]:
                    teams_list.append(loc["name"])

            story_list = []
            if record.get("story_arc_credits"):
                for loc in record["story_arc_credits"]:
                    story_list.append(loc["name"])

            persons_list = []
            if record.get("person_credits"):
                for person in record["person_credits"]:
                    persons_list.append(Credit(name=person["name"], role=person["role"]))

            series = self._fetch_series_data(record["volume"]["id"])

            formatted_results.append(
                ComicIssue(
                    aliases=record["aliases"].split("\n") if record["aliases"] else [],
                    cover_date=record.get("cover_date", ""),
                    description=record.get("description", ""),
                    id=str(record["id"]),
                    image_url=image_url,
                    issue_number=record["issue_number"],
                    name=record["name"],
                    site_detail_url=record.get("site_detail_url", ""),
                    series=series,  # CV uses volume to mean series
                    alt_image_urls=alt_images_list,
                    characters=character_list,
                    locations=location_list,
                    teams=teams_list,
                    story_arcs=story_list,
                    credits=persons_list,
                    complete=complete,
                )
            )

        return formatted_results

    def _fetch_series_data(self, series_id: int) -> ComicSeries:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_series_result = cvc.get_series_info(str(series_id), self.id)

        if cached_series_result is not None:
            return cached_series_result

        series_url = urljoin(self.api_url, f"volume/{CVTypeID.Volume}-{series_id}")  # CV uses volume to mean series

        params = {
            "api_key": self.api_key,
            "format": "json",
        }
        cv_response: CVResult[CVSeries] = self._get_cv_content(series_url, params)

        series_results = cv_response["results"]
        formatted_series_results = self._format_search_results([series_results])

        if series_results:
            cvc.add_series_info(self.id, formatted_series_results[0])

        return formatted_series_results[0]

    def _fetch_issue_data(self, series_id: int, issue_number: str) -> GenericMetadata:
        issues_list_results = self.fetch_issues_by_series(str(series_id))

        # Loop through issue list to find the required issue info
        f_record = None
        for record in issues_list_results:
            if not IssueString(issue_number).as_string():
                issue_number = "1"
            if (
                IssueString(record.issue_number).as_string().casefold()
                == IssueString(issue_number).as_string().casefold()
            ):
                f_record = record
                break

        if f_record and f_record.complete:
            # Cache had full record
            return talker_utils.map_comic_issue_to_metadata(
                f_record, self.name, self.remove_html_tables, self.use_series_start_as_volume
            )

        if f_record is not None:
            return self._fetch_issue_data_by_issue_id(f_record.id)
        return GenericMetadata()

    def _fetch_issue_data_by_issue_id(self, issue_id: str) -> GenericMetadata:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_issues_result = cvc.get_issue_info(int(issue_id), self.id)

        if cached_issues_result and cached_issues_result.complete:
            return talker_utils.map_comic_issue_to_metadata(
                cached_issues_result,
                self.name,
                self.remove_html_tables,
                self.use_series_start_as_volume,
            )

        issue_url = urljoin(self.api_url, f"issue/{CVTypeID.Issue}-{issue_id}")
        params = {"api_key": self.api_key, "format": "json"}
        cv_response: CVResult[CVIssue] = self._get_cv_content(issue_url, params)

        issue_results = cv_response["results"]

        # Format to expected output
        cv_issues = self._format_issue_results([issue_results], True)

        # Due to issue not returning publisher, fetch the series.
        cv_issues[0].series = self._fetch_series_data(int(cv_issues[0].series.id))

        cvc.add_series_issues_info(self.id, cv_issues)

        # Now, map the ComicIssue data to generic metadata
        return talker_utils.map_comic_issue_to_metadata(
            cv_issues[0],
            self.name,
            self.remove_html_tables,
            self.use_series_start_as_volume,
        )
