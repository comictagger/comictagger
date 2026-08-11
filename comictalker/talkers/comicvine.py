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
import datetime
import json
import logging
import pathlib
import time
from collections.abc import Callable
from functools import cache
from typing import Any, Generic, TypeVar, cast
from urllib.parse import parse_qsl, urlencode, urljoin

import settngs
from typing_extensions import Required, TypedDict

from comicapi import utils
from comicapi.genericmetadata import ComicSeries, GenericMetadata, ImageHash, MetadataOrigin
from comicapi.issuestring import IssueString
from comicapi.utils import LocationParseError, StrEnum, parse_url
from comictalker import talker_utils
from comictalker.comiccacher import ComicCacher, Issue, Series
from comictalker.comictalker import ComicTalker, RLCallBack, TalkerDataError, TalkerError, TalkerNetworkError
from comictalker.vendor.pyrate_limiter import Limiter, RequestRate

try:
    import niquests as requests
except ImportError:
    import requests
logger = logging.getLogger(__name__)

TWITTER_TOO_MANY_REQUESTS = 420


class CVTypeID(StrEnum):
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


class PartialCVIssue(TypedDict):
    api_detail_url: str  # "https://comicvine.gamespot.com/api/issue/4000-335661/",
    id: int  # 335661,
    name: str  # "The Kingdom, Part 1",
    issue_number: str  # "107"


class CVSeries(TypedDict, total=False):
    api_detail_url: str
    site_detail_url: str
    aliases: str
    count_of_issues: int
    description: str
    id: Required[int]
    image: CVImage
    name: Required[str]
    publisher: CVPublisher
    start_year: str
    resource_type: str
    characters: list[CVCredit]
    locations: list[CVCredit]
    people: list[CVPersonCredit]
    date_last_updated: str  # "2012-11-11 00:54:18"
    last_issue: PartialCVIssue


class CVIssue(TypedDict, total=False):
    aliases: str
    api_detail_url: str
    associated_images: list[CVAltImage]
    character_credits: list[CVCredit]
    character_died_in: None
    concept_credits: list[CVCredit]
    cover_date: str
    date_added: str
    date_last_updated: Required[str]
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
custom_limiter = Limiter(RequestRate(10, 10), RequestRate(200, 1 * 60 * 60))
default_limiter = Limiter(RequestRate(1, 10), RequestRate(100, 1 * 60 * 60))


class ComicVineTalker(ComicTalker):
    name: str = "Comic Vine"
    id: str = "comicvine"
    website: str = "https://comicvine.gamespot.com"
    logo_url: str = f"{website}/a/bundles/comicvinesite/images/logo.png"
    attribution: str = f"Metadata provided by <a href='{website}'>{name}</a>"
    about: str = (
        f"<a href='{website}'>{name}</a> has the largest collection of comic book data available through "
        f"its public facing API. "
        f"<p>NOTE: Using the default API key will severely limit access times. A personal API "
        f"key will allow for a <b>10 times increase</b> in online search speed. See the "
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
        self.total_requests_made: dict[str, int] = utils.DefaultDict(default=lambda _: 0)
        self.custom_url_parameters: dict[str, str] = {}

    def _log_total_requests(self) -> None:
        logger.debug("Total requests made to cv: %s", dict(self.total_requests_made))

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
        parser.add_setting(
            f"--{self.id}-custom-parameters",
            display_name="Custom URL Parameters",
            help="Custom url parameters to add to the url, must already be url encoded. (eg. refresh_cache=true)",
        )

    def parse_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        settings = super().parse_settings(settings)

        self.use_series_start_as_volume = settings["cv_use_series_start_as_volume"]

        self.custom_url_parameters = dict(parse_qsl(settings[f"{self.id}_custom_parameters"]))

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
            test_url = urljoin(url, "team/1/")

            self.total_requests_made[test_url] += 1
            cv_response: CVResult = requests.get(  # type: ignore[type-arg]
                test_url,
                headers={"user-agent": "comictagger/" + self.version},
                params={
                    "api_key": settings[f"{self.id}_key"] or self.default_api_key,
                    "format": "json",
                },
                timeout=10,
            ).json()

            # Bogus request, but if the key is wrong, you get error 100: "Invalid API Key"
            if cv_response["status_code"] != 100:
                self._log_total_requests()
                return "The API key is valid", True
            else:
                self._log_total_requests()
                return "The API key is INVALID!", False
        except Exception:
            self._log_total_requests()
            return "Failed to connect to the URL!", False

    @cache
    def cacher(self) -> ComicCacher:
        return ComicCacher(self.cache_folder, self.version)

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
        series_match_thresh: int = 90,
        *,
        on_rate_limit: RLCallBack | None = None,
    ) -> list[ComicSeries]:
        # Sanitize the series name for comicvine searching, comicvine search ignore symbols
        search_series_name = utils.sanitize_title(series_name, basic=literal)

        # A literal search was asked for, do not sanitize
        if literal:
            search_series_name = series_name

        logger.info("%s searching: %s", self.name, search_series_name)

        # Before we search online, look in our cache, since we might have done this same search recently
        # For literal searches always retrieve from online
        cvc = self.cacher()
        if not refresh_cache and not literal:
            cached_search_results = cvc.get_search_results(self.id, series_name)

            if cached_search_results:
                logger.debug("Search for %s cached: True", repr(series_name))
                return self._format_search_results([json.loads(x[0].data) for x in cached_search_results])
        logger.debug("Search for %s cached: False", repr(series_name))

        params = {  # CV uses volume to mean series
            "api_key": self.api_key,
            "format": "json",
            "resources": "volume",
            "query": search_series_name,
            "field_list": "volume,name,id,start_year,publisher,image,description,count_of_issues,aliases,site_detail_url",
            "page": 1,
            "limit": 100,
        }

        cv_response: CVResult[list[CVSeries]] = self._get_cv_content(
            urljoin(self.api_url, "search/"),
            params,
            on_rate_limit=on_rate_limit,
        )

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
                "Found %s of %s results", cv_response["number_of_page_results"], cv_response["number_of_total_results"]
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
                logger.debug("getting another page of results %s of %s...", current_result_count, total_result_count)
            page += 1

            params["page"] = page
            cv_response = self._get_cv_content(
                urljoin(self.api_url, "search/"),
                params,
                on_rate_limit=on_rate_limit,
            )

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
            [
                Series(id=str(x["id"]), data=json.dumps(x).encode("utf-8"), expiration=cvc.a_week())
                for x in search_results
            ],
            False,
        )

        return formatted_search_results

    def fetch_comic_data(
        self,
        issue_id: str | None = None,
        series_id: str | None = None,
        issue_number: str = "",
        *,
        on_rate_limit: RLCallBack | None = None,
    ) -> GenericMetadata:
        comic_data = GenericMetadata()
        if issue_id:
            comic_data = self._fetch_issue_data_by_issue_id(
                issue_id,
                on_rate_limit=on_rate_limit,
            )
        elif issue_number and series_id:
            comic_data = self._fetch_issue_data(
                int(series_id),
                issue_number,
                on_rate_limit=on_rate_limit,
            )

        return comic_data

    def fetch_series(
        self,
        series_id: str,
        *,
        on_rate_limit: RLCallBack | None = None,
    ) -> ComicSeries:
        return self._fetch_series_data(
            int(series_id),
            on_rate_limit=on_rate_limit,
        )[0]

    def fetch_issues_in_series(
        self,
        series_id: str,
        *,
        on_rate_limit: RLCallBack | None = None,
    ) -> list[GenericMetadata]:
        return [
            x[0]
            for x in self._fetch_issues_in_series(
                series_id,
                on_rate_limit=on_rate_limit,
            )
        ]

    def fetch_issues_by_series_issue_num_and_year(
        self,
        series_id_list: list[str],
        issue_number: str,
        year: str | int | None,
        *,
        on_rate_limit: RLCallBack | None = None,
    ) -> list[GenericMetadata]:
        logger.debug("Fetching comics by series ids: %s and number: %s", series_id_list, issue_number)
        # before we search online, look in our cache, since we might already have this info
        cvc = self.cacher()
        cached_results: list[GenericMetadata] = []
        needed_volumes: set[int] = set()
        for series_id in series_id_list:
            series = cvc.get_series_info(series_id, self.id, expire_stale=False)
            issues = []
            # Explicitly mark count_of_issues at an impossible value
            cvseries = CVSeries(id=int(series_id), count_of_issues=-1)  # type: ignore[typeddict-item]

            # Check if we have the series cached
            if series:
                cvseries = cast(CVSeries, json.loads(series[0].data))
                issues = cvc.get_series_issues_info(series_id, self.id, expire_stale=True)
            issue_found = False
            for issue, _ in issues:
                cvissue = cast(CVIssue, json.loads(issue.data))
                if cvissue.get("issue_number") == issue_number:
                    comicseries = self._fetch_series([int(cvissue["volume"]["id"])], on_rate_limit=on_rate_limit)[0][0]
                    cached_results.append(
                        self._map_comic_issue_to_metadata(
                            cvissue,
                            comicseries,
                        ),
                    )
                    issue_found = True
                    break
            if not issues:
                needed_volumes.add(int(series_id))  # we got no results from cache, we definitely need to check online

            # If we didn't find the issue and we don't have all the issues we don't know if the issue exists, we have to check
            if (not issue_found) and cvseries.get("count_of_issues") != len(issues):
                needed_volumes.add(int(series_id))

        logger.debug("Found %d issues cached need %d issues", len(cached_results), len(needed_volumes))
        if not needed_volumes:
            return cached_results

        series_filter = ""
        for vid in needed_volumes:
            series_filter += str(vid) + "|"
        flt = f"volume:{series_filter[:-1]},issue_number:{issue_number}"  # CV uses volume to mean series

        int_year = utils.xlate_int(year)
        if int_year is not None:
            flt += f",cover_date:{int_year}-1-1|{int_year + 1}-12-31"

        params: dict[str, str | int] = {  # CV uses volume to mean series
            "api_key": self.api_key,
            "format": "json",
            "filter": flt,
        }

        cv_response: CVResult[list[CVIssue]] = self._get_cv_content(
            urljoin(self.api_url, "issues/"),
            params,
            on_rate_limit=on_rate_limit,
        )

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
            cv_response = self._get_cv_content(
                urljoin(self.api_url, "issues/"),
                params,
                on_rate_limit=on_rate_limit,
            )

            filtered_issues_result.extend(cv_response["results"])
            current_result_count += cv_response["number_of_page_results"]

        cvc.add_all_issues_info(
            self.id,
            [
                Issue(
                    str(x["id"]),
                    str(x["volume"]["id"]),
                    json.dumps(x).encode("utf-8"),
                    expiration=self._get_issue_expiration(x),
                )
                for x in filtered_issues_result
            ],
            False,
        )

        formatted_filtered_issues_result = [
            self._map_comic_issue_to_metadata(
                x,
                self._fetch_series_data(
                    x["volume"]["id"],
                    on_rate_limit=on_rate_limit,
                )[0],
            )
            for x in filtered_issues_result
        ]
        formatted_filtered_issues_result.extend(cached_results)

        return formatted_filtered_issues_result

    def _get_issue_expiration(self, issue: CVIssue) -> datetime.datetime:
        today = datetime.datetime.today()
        store_date = None
        try:
            store_date = datetime.datetime.fromisoformat(issue["store_date"])
        except (ValueError, TypeError):
            ...
        if store_date:
            if store_date > today - datetime.timedelta(days=2):
                return today + datetime.timedelta(days=1)
            if store_date > today - datetime.timedelta(days=30):
                return today + datetime.timedelta(days=7)

        if "date_last_updated" in issue:
            if datetime.datetime.fromisoformat(issue["date_last_updated"]) > today - datetime.timedelta(days=2):
                return today + datetime.timedelta(days=1)
            if datetime.datetime.fromisoformat(issue["date_last_updated"]) > today - datetime.timedelta(days=30):
                return self.cacher().a_week()
        return self.cacher().a_year()

    def _get_series_expiration(self, series: CVSeries) -> datetime.datetime:
        # TODO: this is relatively brittle as we don't have a way to determine how long a series should be cached for if we don't have any issues to compare to.
        # Also if we only have an early issue this guess as to how long to cache will be inaccurate see https://comicvine.gamespot.com/detective-comics/4050-91098/
        # CV provides no way to determine, in a single API call, if a series has gotten a new issue recently. The response include title and id for the latest issue but,
        # Another API call would have to be made to check to see when it was issued
        today = datetime.datetime.today()
        cached_results = self.cacher().get_series_issues_info(str(series["id"]), self.id, expire_stale=False)

        # This can also be misleading because "date_last_updated" will not necessarily be a new issue
        # It may be someone back-filling issue information on existing issues or adding old issues
        cached_issues = sorted(
            [json.loads(x.data.data) for x in cached_results],
            key=lambda i: i.get("date_last_updated", "") or "",
            reverse=True,
        )
        if cached_issues:
            return self._get_issue_expiration(cached_issues[0])
        if series.get("start_year") == str(today.year):
            return self.cacher().a_week()
        return self.cacher().a_year()

    def _get_id_list(self, needed_issues: list[str]) -> tuple[str, set[str]]:
        used_issues = set(needed_issues[: min(len(needed_issues), 100)])
        flt = "id:" + "|".join(used_issues)
        return flt, used_issues

    def fetch_comics(
        self,
        *,
        issue_ids: list[str],
        on_rate_limit: RLCallBack | None = None,
    ) -> list[GenericMetadata]:
        # before we search online, look in our cache, since we might already have this info
        cvc = self.cacher()
        final_results: list[GenericMetadata] = []
        needed_issues: set[str] = set(issue_ids)
        cached_issues = [x for x in (cvc.get_issue_info(issue_id, self.id) for issue_id in issue_ids) if x is not None]
        needed_issues -= {i.data.id for i in cached_issues}

        # We are retrieving by ID. There is no inherent order here
        cvissue_results: list[CVIssue] = []

        for cached_issue in cached_issues:
            issue: CVIssue = json.loads(cached_issue.data.data)
            cvissue_results.append(issue)

        logger.debug("Found %d issues cached need %d issues", len(final_results), len(needed_issues))
        if not needed_issues:
            return final_results

        issue_url = urljoin(self.api_url, "issues/")
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "format": "json",
        }

        issue_results: list[CVIssue] = []

        # see if we need to keep asking for more pages...
        while needed_issues:
            flt, used_issues = self._get_id_list(list(needed_issues))
            params["filter"] = flt

            cv_response: CVResult[list[CVIssue]] = self._get_cv_content(issue_url, params, on_rate_limit=on_rate_limit)

            issue_results.extend(cv_response["results"])

            retrieved_issues = {str(x["id"]) for x in cv_response["results"]}
            used_issues.difference_update(retrieved_issues)
            if used_issues:
                logger.debug("%s issue ids %r do not exist anymore", self.name, used_issues)

            needed_issues = needed_issues.difference(retrieved_issues, used_issues)

            issues_to_cache: list[Issue] = []
            issue = {}  # type: ignore[typeddict-item]
            for issue in issue_results:
                issues_to_cache.append(
                    Issue(
                        id=str(issue["id"]),
                        series_id=str(issue["volume"]["id"]),
                        data=json.dumps(issue).encode("utf-8"),
                        expiration=self._get_issue_expiration(issue),
                    )
                )
            cvc.add_all_issues_info(
                self.id,
                issues_to_cache,
                False,  # The /issues/ endpoint never provides credits
            )
            if issue:
                cvc.add_series_info(
                    self.id,
                    Series(
                        id=str(issue["volume"]["id"]),
                        data=json.dumps(issue["volume"]).encode("utf-8"),
                        expiration=datetime.datetime.today(),  # TODO: fix this
                    ),
                    False,
                )

        for issue in cvissue_results + issue_results:
            series = issue["volume"]
            cached_series = cvc.get_series_info(str(series["id"]), self.id, expire_stale=False)
            if cached_series is not None and cached_series.complete:
                series = json.loads(cached_series.data.data)
            final_results.append(
                self._map_comic_issue_to_metadata(issue, self._format_series(series)),
            )
        return final_results

    def _fetch_series(
        self,
        series_ids: list[int],
        on_rate_limit: RLCallBack | None,
    ) -> list[tuple[ComicSeries, bool]]:
        # before we search online, look in our cache, since we might already have this info
        cvc = self.cacher()
        cached_results: list[tuple[ComicSeries, bool]] = []
        needed_series: set[str] = set()
        for series_id in series_ids:
            cached_series = cvc.get_series_info(str(series_id), self.id)
            if cached_series is not None and cached_series.complete:
                cached_results.append((self._format_series(json.loads(cached_series[0].data)), cached_series[1]))
            else:
                needed_series.add(str(series_id))

        if not needed_series:
            return cached_results
        logger.debug("Found %d series cached need %d series", len(cached_results), len(needed_series))

        series_url = urljoin(self.api_url, "volumes/")  # CV uses volume to mean series
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "format": "json",
        }
        series_results: list[CVSeries] = []

        while needed_series:
            flt, used_series = self._get_id_list(list(needed_series))
            params["filter"] = flt

            cv_response: CVResult[list[CVSeries]] = self._get_cv_content(
                series_url, params, on_rate_limit=on_rate_limit
            )

            series_results.extend(cv_response["results"])

            retrieved_series = {str(x["id"]) for x in series_results}
            used_series.difference_update(retrieved_series)
            if used_series:
                logger.debug("%s series ids %r do not exist anymore", self.name, used_series)

            needed_series = needed_series.difference(retrieved_series, used_series)
            for series in series_results:
                cvc.add_series_info(
                    self.id,
                    Series(
                        id=str(series["id"]),
                        data=json.dumps(series).encode("utf-8"),
                        expiration=self._get_series_expiration(series),
                    ),
                    True,
                )

        if series_results:
            for series in series_results:
                cached_results.append((self._format_series(series), True))

        return cached_results

    def _get_cv_content(
        self,
        url: str,
        params: dict[str, Any],
        *,
        on_rate_limit: RLCallBack | None,
    ) -> CVResult[T]:
        """
        Get the content from the CV server.
        """

        cv_response: CVResult[T] = self._get_url_content(url, params, on_rate_limit=on_rate_limit)
        if cv_response["status_code"] != 1:
            logger.debug(
                "%s query failed with error #%s:  [%s].",
                self.name,
                cv_response["status_code"],
                cv_response["error"],
            )
            raise TalkerNetworkError(self.name, 0, f"{cv_response['status_code']}: {cv_response['error']}")

        return cv_response

    def _get_url_content(self, url: str, params: dict[str, Any], on_rate_limit: RLCallBack | None = None) -> Any:
        # if there is a 500 error, try a few more times before giving up
        limit_counter = 0
        final_params = self.custom_url_parameters.copy()
        final_params.update(params)

        for tries in range(1, 5):
            try:
                ratelimit_key = self._get_ratelimit_key(url)
                with self.limiter.ratelimit(ratelimit_key, delay=True, on_rate_limit=on_rate_limit):
                    logged_params = final_params.copy()
                    logged_params.pop("api_key")
                    logger.debug("Requesting: %s?%s", url, urlencode(logged_params))
                    self.total_requests_made[ratelimit_key] += 1
                    resp = requests.get(
                        url, params=final_params, headers={"user-agent": "comictagger/" + self.version}, timeout=60
                    )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (
                    requests.codes.SERVER_ERROR,
                    requests.codes.BAD_GATEWAY,
                    requests.codes.UNAVAILABLE,
                ):
                    logger.debug("Try #%d: %d", tries, resp.status_code)

                elif resp.status_code in (requests.codes.TOO_MANY_REQUESTS, TWITTER_TOO_MANY_REQUESTS):
                    logger.info("%s rate limit encountered. Waiting for 10 seconds", self.name)
                    self._log_total_requests()
                    time.sleep(10)
                    limit_counter += 1
                    if limit_counter > 3:
                        # Tried 3 times, inform user to check CV website.
                        logger.error("%s rate limit error. Exceeded 3 retires.", self.name)
                        raise TalkerNetworkError(
                            self.name,
                            3,
                            "Rate Limit Error: Check your current API usage limit at https://comicvine.gamespot.com/api/",
                        )
                else:
                    logger.error("Unknown status code: %d, %s", resp.status_code, resp.content)
                    break

            except requests.exceptions.Timeout:
                logger.debug("Connection to %s timed out.", self.name)
                if tries > 3:
                    raise TalkerNetworkError(self.name, 4)
            except requests.exceptions.RequestException as e:
                logger.debug("Request exception", exc_info=True)
                raise TalkerNetworkError(self.name, 0, str(e)) from e
            except json.JSONDecodeError:
                logger.debug("JSON decode error", exc_info=True)
                raise TalkerDataError(self.name, 2, "ComicVine did not provide json")
            except TalkerError as e:
                raise e
            except Exception as e:
                raise TalkerNetworkError(self.name, 5, str(e))

        raise TalkerNetworkError(self.name, 5, "Unknown error occurred")

    def _get_ratelimit_key(self, url: str) -> str:
        if self.api_key == self.default_api_key:
            return "cv"

        ratelimit_key = url.removeprefix(self.api_url)
        for x in CVTypeID:
            ratelimit_key = ratelimit_key.partition(f"/{x}-")[0]
        return ratelimit_key

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

        series = ComicSeries(
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
        url = utils.xlate(record.get("site_detail_url"))
        if url:
            try:
                series.web_links = [parse_url(url)]
            except LocationParseError:
                ...
        return series

    def _fetch_issues_in_series(
        self,
        series_id: str,
        on_rate_limit: RLCallBack | None,
    ) -> list[tuple[GenericMetadata, bool]]:
        logger.debug("Fetching all issues in series: %s", series_id)
        # before we search online, look in our cache, since we might already have this info
        cvc = self.cacher()
        cached_results = cvc.get_series_issues_info(series_id, self.id)

        series = self._fetch_series_data(
            int(series_id),
            on_rate_limit=on_rate_limit,
        )[0]

        logger.debug(
            "Found %d issues cached need %d issues",
            len(cached_results),
            cast(int, series.count_of_issues) - len(cached_results),
        )
        if len(cached_results) == series.count_of_issues:
            return [(self._map_comic_issue_to_metadata(json.loads(x[0].data), series), x[1]) for x in cached_results]

        # There is no direct way to know what issue we need so we get all of them...
        # We could try to be more intelligent as most likely it will be an issue at the end

        params = {  # CV uses volume to mean series
            "api_key": self.api_key,
            "filter": f"volume:{series_id}",
            "format": "json",
            "offset": 0,
        }
        cv_response: CVResult[list[CVIssue]] = self._get_cv_content(
            urljoin(self.api_url, "issues/"),
            params,
            on_rate_limit=on_rate_limit,
        )

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
            cv_response = self._get_cv_content(
                urljoin(self.api_url, "issues/"),
                params,
                on_rate_limit=on_rate_limit,
            )

            series_issues_result.extend(cv_response["results"])
            current_result_count += cv_response["number_of_page_results"]
        # Format to expected output
        formatted_series_issues_result = [
            self._map_comic_issue_to_metadata(
                x,
                self._fetch_series_data(
                    x["volume"]["id"],
                    on_rate_limit=on_rate_limit,
                )[0],
            )
            for x in series_issues_result
        ]

        cvc.add_all_issues_info(
            self.id,
            [
                Issue(
                    id=str(x["id"]),
                    series_id=series_id,
                    data=json.dumps(x).encode("utf-8"),
                    expiration=self._get_issue_expiration(x),
                )
                for x in series_issues_result
            ],
            False,
        )
        return [(x, False) for x in formatted_series_issues_result]

    def _fetch_series_data(
        self,
        series_id: int,
        on_rate_limit: RLCallBack | None,
    ) -> tuple[ComicSeries, bool]:
        logger.debug("Fetching series info: %s", series_id)
        # before we search online, look in our cache, since we might already have this info
        cvc = self.cacher()
        cached_series = cvc.get_series_info(str(series_id), self.id)

        logger.debug("Series cached: %s", bool(cached_series))
        if cached_series is not None and cached_series.complete:
            return (self._format_series(json.loads(cached_series[0].data)), cached_series[1])

        series_url = urljoin(self.api_url, f"volume/{CVTypeID.Volume}-{series_id}/")  # CV uses volume to mean series

        params = {
            "api_key": self.api_key,
            "format": "json",
        }
        cv_response: CVResult[CVSeries] = self._get_cv_content(
            series_url,
            params,
            on_rate_limit=on_rate_limit,
        )

        series_results = cv_response["results"]

        if series_results:
            cvc.add_series_info(
                self.id,
                Series(
                    id=str(series_results["id"]),
                    data=json.dumps(series_results).encode("utf-8"),
                    expiration=self._get_series_expiration(series_results),
                ),
                True,
            )

        return self._format_series(series_results), True

    def _fetch_issue_data(
        self,
        series_id: int,
        issue_number: str,
        on_rate_limit: RLCallBack | None,
    ) -> GenericMetadata:
        logger.debug("Fetching issue by series ID: %s and issue number: %s", series_id, issue_number)
        issues_list_results = self._fetch_issues_in_series(
            str(series_id),
            on_rate_limit=on_rate_limit,
        )

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
            return self._fetch_issue_data_by_issue_id(
                f_record[0].issue_id,
                on_rate_limit=on_rate_limit,
            )
        return GenericMetadata()

    def _fetch_issue_data_by_issue_id(
        self,
        issue_id: str,
        on_rate_limit: RLCallBack | None,
    ) -> GenericMetadata:
        logger.debug("Fetching issue by issue ID: %s", issue_id)
        # before we search online, look in our cache, since we might already have this info
        cvc = self.cacher()
        cached_issue = cvc.get_issue_info(issue_id, self.id)

        logger.debug("Issue cached: %s", bool(cached_issue and cached_issue[1]))
        if cached_issue and cached_issue.complete:
            return self._map_comic_issue_to_metadata(
                json.loads(cached_issue[0].data),
                self._fetch_series_data(
                    int(cached_issue[0].series_id),
                    on_rate_limit=on_rate_limit,
                )[0],
            )

        issue_url = urljoin(self.api_url, f"issue/{CVTypeID.Issue}-{issue_id}/")
        params = {"api_key": self.api_key, "format": "json"}
        cv_response: CVResult[CVIssue] = self._get_cv_content(
            issue_url,
            params,
            on_rate_limit=on_rate_limit,
        )

        issue_results = cv_response["results"]

        cvc.add_all_issues_info(
            self.id,
            [
                Issue(
                    id=str(issue_results["id"]),
                    series_id=str(issue_results["volume"]["id"]),
                    data=json.dumps(issue_results).encode("utf-8"),
                    expiration=self._get_issue_expiration(issue_results),
                )
            ],
            True,
        )

        # Now, map the GenericMetadata data to generic metadata
        return self._map_comic_issue_to_metadata(
            issue_results,
            self._fetch_series_data(
                int(issue_results["volume"]["id"]),
                on_rate_limit=on_rate_limit,
            )[0],
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
        if issue.get("image") is not None:
            md._cover_image = ImageHash(URL=issue.get("image", {}).get("super_url", ""), Hash=0, Kind="")

        for alt in issue.get("associated_images", []):
            md._alternate_images.append(ImageHash(URL=alt["original_url"], Hash=0, Kind=""))

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
