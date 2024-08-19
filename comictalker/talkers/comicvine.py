"""
ComicVine information source
"""

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

import argparse
import json
import logging
import pathlib
import time
from typing import Any, Callable, Generic, TypeVar
from urllib.parse import urljoin

import settngs
from pyrate_limiter import Limiter, RequestRate
from typing_extensions import Required, TypedDict

from comicapi import utils
from comicapi.genericmetadata import ComicSeries, GenericMetadata, MetadataOrigin
from comicapi.issuestring import IssueString
from comicapi.utils import LocationParseError, parse_url
from comictalker import talker_utils
from comictalker.comiccacher import ComicCacher, Issue, Series
from comictalker.comictalker import ComicTalker, TalkerDataError, TalkerNetworkError

try:
    import niquests as requests
except ImportError:
    import requests
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
    id: Required[int]
    caption: str
    image_tags: str


class CVPublisher(TypedDict, total=False):
    api_detail_url: str
    id: Required[int]
    name: Required[str]


class CVCredit(TypedDict):
    api_detail_url: str
    id: Required[int]
    name: str
    site_detail_url: str


class CVPersonCredit(TypedDict):
    api_detail_url: str
    id: Required[int]
    name: str
    site_detail_url: str
    role: str


class CVSeries(TypedDict):
    api_detail_url: str
    site_detail_url: str
    aliases: str
    count_of_issues: int
    description: str
    id: Required[int]
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
    id: Required[int]
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
    volume: Required[CVSeries]  # CV uses volume to mean series


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


# https://comicvine.gamespot.com/forums/api-developers-2334/api-rate-limiting-1746419/
# "Space out your requests so AT LEAST one second passes between each and you can make requests all day."
custom_limiter = Limiter(RequestRate(10, 10))
default_limiter = Limiter(RequestRate(1, 5))


class ComicVineTalker(ComicTalker):
    name: str = "Comic Vine"
    id: str = "comicvine"
    website: str = "https://comicvine.gamespot.com"
    logo_url: str = f"{website}/a/bundles/comicvinesite/images/logo.png"
    attribution: str = f"Metadata provided by <a href='{website}'>{name}</a>"
    about: str = (
        f"<a href='{website}'>{name}</a> has the largest collection of comic book data available through "
        f"its public facing API. "
        f"<p>NOTE: Using the default API key will serverly limit access times. A personal API "
        f"key will allow for a <b>5 times increase</b> in online search speed. See the "
        "<a href='https://github.com/comictagger/comictagger/wiki/UserGuide#comic-vine'>Wiki page</a> for "
        "more information.</p>"
    )

    def __init__(self, version: str, cache_folder: pathlib.Path):
        super().__init__(version, cache_folder)
        self.limiter = default_limiter
        # Default settings
        self.default_api_url = self.api_url = f"{self.website}/api/"
        self.default_api_key = self.api_key = "27431e6787042105bd3e47e169a624521f89f3a4"
        self.use_series_start_as_volume: bool = False

    def register_settings(self, parser: settngs.Manager) -> None:
        parser.add_setting(
            "--cv-use-series-start-as-volume",
            default=False,
            action=argparse.BooleanOptionalAction,
            display_name="Use series start as volume",
            help="Use the series start year as the volume number",
        )

        # The default needs to be unset or None.
        # This allows this setting to be unset with the empty string, allowing the default to change
        parser.add_setting(
            f"--{self.id}-key",
            display_name="API Key",
            help=f"Use the given Comic Vine API Key. (default: {self.default_api_key})",
        )
        parser.add_setting(
            f"--{self.id}-url",
            display_name="API URL",
            help=f"Use the given Comic Vine URL. (default: {self.default_api_url})",
        )

    def parse_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        settings = super().parse_settings(settings)

        self.use_series_start_as_volume = settings["cv_use_series_start_as_volume"]

        # Set a different limit if using the default API key
        if self.api_key == self.default_api_key:
            self.limiter = default_limiter
        else:
            self.limiter = custom_limiter

        return settings

    def check_status(self, settings: dict[str, Any]) -> tuple[str, bool]:
        url = talker_utils.fix_url(settings[f"{self.id}_url"])
        if not url:
            url = self.default_api_url
        try:
            test_url = urljoin(url, "issue/1/")

            cv_response: CVResult = requests.get(  # type: ignore[type-arg]
                test_url,
                headers={"user-agent": "comictagger/" + self.version},
                params={
                    "api_key": settings[f"{self.id}_key"] or self.default_api_key,
                    "format": "json",
                    "field_list": "name",
                },
            ).json()

            # Bogus request, but if the key is wrong, you get error 100: "Invalid API Key"
            if cv_response["status_code"] != 100:
                return "The API key is valid", True
            else:
                return "The API key is INVALID!", False
        except Exception:
            return "Failed to connect to the URL!", False

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
        series_match_thresh: int = 90,
    ) -> list[ComicSeries]:
        # Sanitize the series name for comicvine searching, comicvine search ignore symbols
        search_series_name = utils.sanitize_title(series_name, basic=literal)

        # A literal search was asked for, do not sanitize
        if literal:
            search_series_name = series_name

        logger.info(f"{self.name} searching: {search_series_name}")

        # Before we search online, look in our cache, since we might have done this same search recently
        # For literal searches always retrieve from online
        cvc = ComicCacher(self.cache_folder, self.version)
        if not refresh_cache and not literal:
            cached_search_results = cvc.get_search_results(self.id, series_name)

            if len(cached_search_results) > 0:
                return self._format_search_results([json.loads(x[0].data) for x in cached_search_results])

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

        # Format result to GenericMetadata
        formatted_search_results = self._format_search_results(search_results)

        # Cache these search results, even if it's literal we cache the results
        # The most it will cause is extra processing time
        cvc.add_search_results(
            self.id,
            series_name,
            [Series(id=str(x["id"]), data=json.dumps(x).encode("utf-8")) for x in search_results],
            False,
        )

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

    def fetch_series(self, series_id: str) -> ComicSeries:
        return self._fetch_series_data(int(series_id))[0]

    def fetch_issues_in_series(self, series_id: str) -> list[GenericMetadata]:
        return [x[0] for x in self._fetch_issues_in_series(series_id)]

    def fetch_issues_by_series_issue_num_and_year(
        self, series_id_list: list[str], issue_number: str, year: str | int | None
    ) -> list[GenericMetadata]:
        series_filter = ""
        for vid in series_id_list:
            series_filter += str(vid) + "|"
        flt = f"volume:{series_filter},issue_number:{issue_number}"  # CV uses volume to mean series

        int_year = utils.xlate_int(year)
        if int_year is not None:
            flt += f",cover_date:{int_year}-1-1|{int_year + 1}-12-31"

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

        formatted_filtered_issues_result = [
            self._map_comic_issue_to_metadata(x, self._fetch_series_data(x["volume"]["id"])[0])
            for x in filtered_issues_result
        ]

        return formatted_filtered_issues_result

    def fetch_comics(self, *, issue_ids: list[str]) -> list[GenericMetadata]:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_results: list[GenericMetadata] = []
        needed_issues: list[int] = []
        for issue_id in issue_ids:
            cached_issue = cvc.get_issue_info(issue_id, self.id)

            if cached_issue and cached_issue[1]:
                cached_results.append(
                    self._map_comic_issue_to_metadata(
                        json.loads(cached_issue[0].data),
                        self._fetch_series([int(cached_issue[0].series_id)])[0][0],
                    ),
                )
            else:
                needed_issues.append(int(issue_id))  # CV uses integers for it's IDs

        if not needed_issues:
            return cached_results
        issue_filter = ""
        for iid in needed_issues:
            issue_filter += str(iid) + "|"
        flt = "id:" + issue_filter.rstrip("|")

        issue_url = urljoin(self.api_url, "issues/")
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "format": "json",
            "filter": flt,
        }
        cv_response: CVResult[list[CVIssue]] = self._get_cv_content(issue_url, params)

        issue_results = cv_response["results"]
        page = 1
        offset = 0
        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:
            page += 1
            offset += cv_response["number_of_page_results"]

            params["offset"] = offset
            cv_response = self._get_cv_content(issue_url, params)

            issue_results.extend(cv_response["results"])
            current_result_count += cv_response["number_of_page_results"]

        series_info = {s[0].id: s[0] for s in self._fetch_series([int(i["volume"]["id"]) for i in issue_results])}

        for issue in issue_results:
            cvc.add_issues_info(
                self.id,
                [
                    Issue(
                        id=str(issue["id"]),
                        series_id=str(issue["volume"]["id"]),
                        data=json.dumps(issue).encode("utf-8"),
                    ),
                ],
                True,
            )
            cached_results.append(
                self._map_comic_issue_to_metadata(issue, series_info[str(issue["volume"]["id"])]),
            )

        return cached_results

    def _fetch_series(self, series_ids: list[int]) -> list[tuple[ComicSeries, bool]]:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_results: list[tuple[ComicSeries, bool]] = []
        needed_series: list[int] = []
        for series_id in series_ids:
            cached_series = cvc.get_series_info(str(series_id), self.id)
            if cached_series is not None:
                cached_results.append((self._format_series(json.loads(cached_series[0].data)), cached_series[1]))
            else:
                needed_series.append(series_id)

        if needed_series == []:
            return cached_results

        series_filter = ""
        for vid in needed_series:
            series_filter += str(vid) + "|"
        flt = "id:" + series_filter.rstrip("|")  # CV uses volume to mean series

        series_url = urljoin(self.api_url, "volumes/")  # CV uses volume to mean series
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "format": "json",
            "filter": flt,
        }
        cv_response: CVResult[list[CVSeries]] = self._get_cv_content(series_url, params)

        series_results = cv_response["results"]
        page = 1
        offset = 0
        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:
            page += 1
            offset += cv_response["number_of_page_results"]

            params["offset"] = offset
            cv_response = self._get_cv_content(series_url, params)

            series_results.extend(cv_response["results"])
            current_result_count += cv_response["number_of_page_results"]

        if series_results:
            for series in series_results:
                cvc.add_series_info(
                    self.id,
                    Series(id=str(series["id"]), data=json.dumps(series).encode("utf-8")),
                    True,
                )
                cached_results.append((self._format_series(series), True))

        return cached_results

    def _get_cv_content(self, url: str, params: dict[str, Any]) -> CVResult[T]:
        """
        Get the content from the CV server.
        """
        with self.limiter.ratelimit("cv", delay=True):
            cv_response: CVResult[T] = self._get_url_content(url, params)

            if cv_response["status_code"] != 1:
                logger.debug(
                    f"{self.name} query failed with error #{cv_response['status_code']}:  [{cv_response['error']}]."
                )
                raise TalkerNetworkError(self.name, 0, f"{cv_response['status_code']}: {cv_response['error']}")

            return cv_response

    def _get_url_content(self, url: str, params: dict[str, Any]) -> Any:
        # if there is a 500 error, try a few more times before giving up
        limit_counter = 0

        for tries in range(1, 5):
            try:
                resp = requests.get(url, params=params, headers={"user-agent": "comictagger/" + self.version})
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 500:
                    logger.debug(f"Try #{tries}: ")
                    time.sleep(1)
                    logger.debug(str(resp.status_code))

                if resp.status_code == requests.status_codes.codes.TOO_MANY_REQUESTS:
                    logger.info(f"{self.name} rate limit encountered. Waiting for 10 seconds\n")
                    time.sleep(10)
                    limit_counter += 1
                    if limit_counter > 3:
                        # Tried 3 times, inform user to check CV website.
                        logger.error(f"{self.name} rate limit error. Exceeded 3 retires.")
                        raise TalkerNetworkError(
                            self.name,
                            3,
                            "Rate Limit Error: Check your current API usage limit at https://comicvine.gamespot.com/api/",
                        )
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
            formatted_results.append(self._format_series(record))

        return formatted_results

    def _format_series(self, record: CVSeries) -> ComicSeries:
        # Flatten publisher to name only
        if record.get("publisher") is None:
            pub_name = ""
        else:
            pub_name = record["publisher"].get("name", "")

        if record.get("image") is None:
            image_url = ""
        else:
            image_url = record["image"].get("super_url", "")

        start_year = utils.xlate_int(record.get("start_year", ""))

        aliases = record.get("aliases") or ""

        return ComicSeries(
            aliases=set(utils.split(aliases, "\n")),
            count_of_issues=record.get("count_of_issues"),
            count_of_volumes=None,
            description=record.get("description", ""),
            id=str(record["id"]),
            image_url=image_url,
            name=record["name"],
            publisher=pub_name,
            start_year=start_year,
            format=None,
        )

    def _fetch_issues_in_series(self, series_id: str) -> list[tuple[GenericMetadata, bool]]:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_series_issues_result = cvc.get_series_issues_info(series_id, self.id)

        series = self._fetch_series_data(int(series_id))[0]

        if len(cached_series_issues_result) == series.count_of_issues:
            return [
                (self._map_comic_issue_to_metadata(json.loads(x[0].data), series), x[1])
                for x in cached_series_issues_result
            ]

        params = {  # CV uses volume to mean series
            "api_key": self.api_key,
            "filter": f"volume:{series_id}",
            "format": "json",
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
        formatted_series_issues_result = [
            self._map_comic_issue_to_metadata(x, self._fetch_series_data(x["volume"]["id"])[0])
            for x in series_issues_result
        ]

        cvc.add_issues_info(
            self.id,
            [
                Issue(id=str(x["id"]), series_id=series_id, data=json.dumps(x).encode("utf-8"))
                for x in series_issues_result
            ],
            False,
        )
        return [(x, False) for x in formatted_series_issues_result]

    def _fetch_series_data(self, series_id: int) -> tuple[ComicSeries, bool]:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_series = cvc.get_series_info(str(series_id), self.id)

        if cached_series is not None:
            return (self._format_series(json.loads(cached_series[0].data)), cached_series[1])

        series_url = urljoin(self.api_url, f"volume/{CVTypeID.Volume}-{series_id}")  # CV uses volume to mean series

        params = {
            "api_key": self.api_key,
            "format": "json",
        }
        cv_response: CVResult[CVSeries] = self._get_cv_content(series_url, params)

        series_results = cv_response["results"]

        if series_results:
            cvc.add_series_info(
                self.id, Series(id=str(series_results["id"]), data=json.dumps(series_results).encode("utf-8")), True
            )

        return self._format_series(series_results), True

    def _fetch_issue_data(self, series_id: int, issue_number: str) -> GenericMetadata:
        issues_list_results = self._fetch_issues_in_series(str(series_id))

        # Loop through issue list to find the required issue info
        f_record = (GenericMetadata(), False)
        for record in issues_list_results:
            if not IssueString(issue_number).as_string():
                issue_number = "1"
            if IssueString(record[0].issue).as_string().casefold() == IssueString(issue_number).as_string().casefold():
                f_record = record
                break

        if not f_record[0].is_empty and f_record[1]:
            # Cache had full record
            return f_record[0]

        if f_record[0].issue_id is not None:
            return self._fetch_issue_data_by_issue_id(f_record[0].issue_id)
        return GenericMetadata()

    def _fetch_issue_data_by_issue_id(self, issue_id: str) -> GenericMetadata:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher(self.cache_folder, self.version)
        cached_issue = cvc.get_issue_info(issue_id, self.id)

        if cached_issue and cached_issue[1]:
            return self._map_comic_issue_to_metadata(
                json.loads(cached_issue[0].data), self._fetch_series_data(int(cached_issue[0].series_id))[0]
            )

        issue_url = urljoin(self.api_url, f"issue/{CVTypeID.Issue}-{issue_id}")
        params = {"api_key": self.api_key, "format": "json"}
        cv_response: CVResult[CVIssue] = self._get_cv_content(issue_url, params)

        issue_results = cv_response["results"]

        cvc.add_issues_info(
            self.id,
            [
                Issue(
                    id=str(issue_results["id"]),
                    series_id=str(issue_results["volume"]["id"]),
                    data=json.dumps(issue_results).encode("utf-8"),
                )
            ],
            True,
        )

        # Now, map the GenericMetadata data to generic metadata
        return self._map_comic_issue_to_metadata(
            issue_results, self._fetch_series_data(int(issue_results["volume"]["id"]))[0]
        )

    def _map_comic_issue_to_metadata(self, issue: CVIssue, series: ComicSeries) -> GenericMetadata:
        md = GenericMetadata(
            data_origin=MetadataOrigin(self.id, self.name),
            issue_id=utils.xlate(issue.get("id")),
            series_id=series.id,
            title_aliases=set(utils.split(issue.get("aliases"), "\n")),
            publisher=utils.xlate(series.publisher),
            description=issue.get("description"),
            issue=utils.xlate(IssueString(issue.get("issue_number")).as_string()),
            issue_count=utils.xlate_int(series.count_of_issues),
            format=utils.xlate(series.format),
            volume_count=utils.xlate_int(series.count_of_volumes),
            title=utils.xlate(issue.get("name")),
            series=utils.xlate(series.name),
            series_aliases=series.aliases,
        )
        url = utils.xlate(issue.get("site_detail_url"))
        if url:
            try:
                md.web_links = [parse_url(url)]
            except LocationParseError:
                ...
        if issue.get("image") is None:
            md._cover_image = ""
        else:
            md._cover_image = issue.get("image", {}).get("super_url", "")

        for alt in issue.get("associated_images", []):
            md._alternate_images.append(alt["original_url"])

        for character in issue.get("character_credits", set()):
            md.characters.add(character["name"])

        for location in issue.get("location_credits", set()):
            md.locations.add(location["name"])

        for team in issue.get("team_credits", set()):
            md.teams.add(team["name"])

        for arc in issue.get("story_arc_credits", []):
            md.story_arcs.append(arc["name"])

        for person in issue.get("person_credits", []):
            roles = utils.split(person.get("role", ""), ",")
            for role in roles:
                md.add_credit(person["name"], role.title(), False)

        md.volume = utils.xlate_int(issue.get("volume"))
        if self.use_series_start_as_volume:
            md.volume = series.start_year

        if issue.get("cover_date"):
            md.day, md.month, md.year = utils.parse_date_str(issue.get("cover_date"))
        elif series.start_year:
            md.year = utils.xlate_int(series.start_year)

        return md
