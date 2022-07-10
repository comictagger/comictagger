"""A python class to manage communication with Comic Vine's REST API"""
#
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
import re
import time
from datetime import datetime
from typing import Any, Callable, cast

import requests
from bs4 import BeautifulSoup

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib import ctversion
from comictaggerlib.comiccacher import ComicCacher
from comictaggerlib.resulttypes import CVIssueDetailResults, CVIssuesResults, CVResult, CVVolumeResults, SelectDetails
from comictaggerlib.settings import ComicTaggerSettings

logger = logging.getLogger(__name__)

try:
    from PyQt5 import QtCore, QtNetwork

    qt_available = True
except ImportError:
    qt_available = False

logger = logging.getLogger(__name__)


class CVTypeID:
    Volume = "4050"
    Issue = "4000"


class ComicVineTalkerException(Exception):
    Unknown = -1
    Network = -2
    InvalidKey = 100
    RateLimit = 107

    def __init__(self, code: int = -1, desc: str = "") -> None:
        super().__init__()
        self.desc = desc
        self.code = code

    def __str__(self) -> str:
        if self.code in (ComicVineTalkerException.Unknown, ComicVineTalkerException.Network):
            return self.desc

        return f"CV error #{self.code}:  [{self.desc}]. \n"


def list_fetch_complete(url_list: list[str]) -> None:
    ...


def url_fetch_complete(image_url: str, thumb_url: str | None) -> None:
    ...


class ComicVineTalker:
    logo_url = "http://static.comicvine.com/bundles/comicvinesite/images/logo.png"
    api_key = ""
    api_base_url = ""

    alt_url_list_fetch_complete = list_fetch_complete
    url_fetch_complete = url_fetch_complete

    @staticmethod
    def get_rate_limit_message() -> str:
        if ComicVineTalker.api_key == "":
            return "Comic Vine rate limit exceeded.  You should configure your own Comic Vine API key."

        return "Comic Vine rate limit exceeded.  Please wait a bit."

    def __init__(self) -> None:
        # Identity name for the information source
        self.source_name = "comicvine"

        self.wait_for_rate_limit = False

        # key that is registered to comictagger
        default_api_key = "27431e6787042105bd3e47e169a624521f89f3a4"
        default_url = "https://comicvine.gamespot.com/api"

        self.issue_id: int | None = None

        self.api_key = ComicVineTalker.api_key or default_api_key
        self.api_base_url = ComicVineTalker.api_base_url or default_url

        self.log_func: Callable[[str], None] | None = None

        if qt_available:
            self.nam = QtNetwork.QNetworkAccessManager()

    def set_log_func(self, log_func: Callable[[str], None]) -> None:
        self.log_func = log_func

    def write_log(self, text: str) -> None:
        if self.log_func is None:
            logger.info(text)
        else:
            self.log_func(text)

    def parse_date_str(self, date_str: str) -> tuple[int | None, int | None, int | None]:
        day = None
        month = None
        year = None
        if date_str:
            parts = date_str.split("-")
            year = utils.xlate(parts[0], True)
            if len(parts) > 1:
                month = utils.xlate(parts[1], True)
                if len(parts) > 2:
                    day = utils.xlate(parts[2], True)
        return day, month, year

    def test_key(self, key: str, url: str) -> bool:
        if not url:
            url = self.api_base_url
        try:
            test_url = url + "/issue/1/?api_key=" + key + "&format=json&field_list=name"

            cv_response: CVResult = requests.get(
                test_url, headers={"user-agent": "comictagger/" + ctversion.version}
            ).json()

            # Bogus request, but if the key is wrong, you get error 100: "Invalid API Key"
            return cv_response["status_code"] != 100
        except Exception:
            return False

    def get_cv_content(self, url: str, params: dict[str, Any]) -> CVResult:
        """
        Get the content from the CV server.  If we're in "wait mode" and status code is a rate limit error
        sleep for a bit and retry.
        """
        total_time_waited = 0
        limit_wait_time = 1
        counter = 0
        wait_times = [1, 2, 3, 4]
        while True:
            cv_response: CVResult = self.get_url_content(url, params)
            if self.wait_for_rate_limit and cv_response["status_code"] == ComicVineTalkerException.RateLimit:
                self.write_log(f"Rate limit encountered.  Waiting for {limit_wait_time} minutes\n")
                time.sleep(limit_wait_time * 60)
                total_time_waited += limit_wait_time
                limit_wait_time = wait_times[counter]
                if counter < 3:
                    counter += 1
                # don't wait much more than 20 minutes
                if total_time_waited < 20:
                    continue
            if cv_response["status_code"] != 1:
                self.write_log(
                    f"Comic Vine query failed with error #{cv_response['status_code']}:  [{cv_response['error']}]. \n"
                )
                raise ComicVineTalkerException(cv_response["status_code"], cv_response["error"])

            # it's all good
            break
        return cv_response

    def get_url_content(self, url: str, params: dict[str, Any]) -> Any:
        # connect to server:
        #  if there is a 500 error, try a few more times before giving up
        #  any other error, just bail
        for tries in range(3):
            try:
                resp = requests.get(url, params=params, headers={"user-agent": "comictagger/" + ctversion.version})
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 500:
                    self.write_log(f"Try #{tries + 1}: ")
                    time.sleep(1)
                    self.write_log(str(resp.status_code) + "\n")
                else:
                    break

            except requests.exceptions.RequestException as e:
                self.write_log(str(e) + "\n")
                raise ComicVineTalkerException(ComicVineTalkerException.Network, "Network Error!") from e

        raise ComicVineTalkerException(ComicVineTalkerException.Unknown, "Error on Comic Vine server")

    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
    ) -> list[CVVolumeResults]:

        # Sanitize the series name for comicvine searching, comicvine search ignore symbols
        search_series_name = utils.sanitize_title(series_name, literal)
        logger.info("Searching: %s", search_series_name)

        # Before we search online, look in our cache, since we might have done this same search recently
        # For literal searches always retrieve from online
        cvc = ComicCacher()
        if not refresh_cache and not literal:
            cached_search_results = cvc.get_search_results(self.source_name, series_name)

            if len(cached_search_results) > 0:
                return cached_search_results

        params = {
            "api_key": self.api_key,
            "format": "json",
            "resources": "volume",
            "query": search_series_name,
            "field_list": "volume,name,id,start_year,publisher,image,description,count_of_issues",
            "page": 1,
            "limit": 100,
        }

        cv_response = self.get_cv_content(self.api_base_url + "/search", params)

        search_results: list[CVVolumeResults] = []

        # see http://api.comicvine.com/documentation/#handling_responses

        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        # 8 Dec 2018 - Comic Vine changed query results again. Terms are now
        # ORed together, and we get thousands of results.  Good news is the
        # results are sorted by relevance, so we can be smart about halting the search.
        # 1. Don't fetch more than some sane amount of pages.
        max_results = 500
        # 2. Halt when not all of our search terms are present in a result
        # 3. Halt when the results contain more (plus threshold) words than our search
        result_word_count_max = len(search_series_name.split()) + 3

        total_result_count = min(total_result_count, max_results)

        if callback is None:
            self.write_log(
                f"Found {cv_response['number_of_page_results']} of {cv_response['number_of_total_results']} results\n"
            )
        search_results.extend(cast(list[CVVolumeResults], cv_response["results"]))
        page = 1

        if callback is not None:
            callback(current_result_count, total_result_count)

        # see if we need to keep asking for more pages...
        stop_searching = False
        while current_result_count < total_result_count:

            if not literal:
                # Sanitize the series name for comicvine searching, comicvine search ignore symbols
                last_result = utils.sanitize_title(search_results[-1]["name"])

                # See if the last result's name has all the of the search terms.
                # If not, break out of this, loop, we're done.
                for term in search_series_name.split():
                    if term not in last_result:
                        stop_searching = True
                        break

                # Also, stop searching when the word count of last results is too much longer than our search terms list
                if len(last_result) > result_word_count_max:
                    stop_searching = True

                if stop_searching:
                    break

            if callback is None:
                self.write_log(f"getting another page of results {current_result_count} of {total_result_count}...\n")
            page += 1

            params["page"] = page
            cv_response = self.get_cv_content(self.api_base_url + "/search", params)

            search_results.extend(cast(list[CVVolumeResults], cv_response["results"]))
            current_result_count += cv_response["number_of_page_results"]

            if callback is not None:
                callback(current_result_count, total_result_count)

        # Literal searches simply return the matches no extra processing is doneo
        if not literal:
            # Remove any search results that don't contain all the search terms (iterate backwards for easy removal)
            for record in reversed(search_results):
                # Sanitize the series name for comicvine searching, comicvine search ignore symbols
                record_name = utils.sanitize_title(record["name"])
                for term in search_series_name.split():
                    if term not in record_name:
                        search_results.remove(record)
                        break

        # Cache these search results, even if it's literal we cache the results
        # The most it will cause is extra processing time
        cvc.add_search_results(self.source_name, series_name, search_results)

        return search_results

    def fetch_volume_data(self, series_id: int) -> CVVolumeResults:

        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher()
        cached_volume_result = cvc.get_volume_info(series_id, self.source_name)

        if cached_volume_result is not None:
            return cached_volume_result

        volume_url = self.api_base_url + "/volume/" + CVTypeID.Volume + "-" + str(series_id)

        params = {
            "api_key": self.api_key,
            "format": "json",
            "field_list": "name,id,start_year,publisher,count_of_issues",
        }
        cv_response = self.get_cv_content(volume_url, params)

        volume_results = cast(CVVolumeResults, cv_response["results"])

        if volume_results:
            cvc.add_volume_info(self.source_name, volume_results)

        return volume_results

    def fetch_issues_by_volume(self, series_id: int) -> list[CVIssuesResults]:
        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher()
        cached_volume_issues_result = cvc.get_volume_issues_info(series_id, self.source_name)

        if cached_volume_issues_result:
            return cached_volume_issues_result

        params = {
            "api_key": self.api_key,
            "filter": "volume:" + str(series_id),
            "format": "json",
            "field_list": "id,volume,issue_number,name,image,cover_date,site_detail_url,description",
            "offset": 0,
        }
        cv_response = self.get_cv_content(self.api_base_url + "/issues/", params)

        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        volume_issues_result = cast(list[CVIssuesResults], cv_response["results"])
        page = 1
        offset = 0

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:
            page += 1
            offset += cv_response["number_of_page_results"]

            params["offset"] = offset
            cv_response = self.get_cv_content(self.api_base_url + "/issues/", params)

            volume_issues_result.extend(cast(list[CVIssuesResults], cv_response["results"]))
            current_result_count += cv_response["number_of_page_results"]

        self.repair_urls(volume_issues_result)

        cvc.add_volume_issues_info(self.source_name, series_id, volume_issues_result)

        return volume_issues_result

    def fetch_issues_by_volume_issue_num_and_year(
        self, volume_id_list: list[int], issue_number: str, year: str | int | None
    ) -> list[CVIssuesResults]:
        volume_filter = ""
        for vid in volume_id_list:
            volume_filter += str(vid) + "|"
        flt = f"volume:{volume_filter},issue_number:{issue_number}"

        int_year = utils.xlate(year, True)
        if int_year is not None:
            flt += f",cover_date:{int_year}-1-1|{int_year+1}-1-1"

        params: dict[str, str | int] = {
            "api_key": self.api_key,
            "format": "json",
            "field_list": "id,volume,issue_number,name,image,cover_date,site_detail_url,description",
            "filter": flt,
        }

        cv_response = self.get_cv_content(self.api_base_url + "/issues", params)

        current_result_count = cv_response["number_of_page_results"]
        total_result_count = cv_response["number_of_total_results"]

        filtered_issues_result = cast(list[CVIssuesResults], cv_response["results"])
        page = 1
        offset = 0

        # see if we need to keep asking for more pages...
        while current_result_count < total_result_count:
            page += 1
            offset += cv_response["number_of_page_results"]

            params["offset"] = offset
            cv_response = self.get_cv_content(self.api_base_url + "/issues/", params)

            filtered_issues_result.extend(cast(list[CVIssuesResults], cv_response["results"]))
            current_result_count += cv_response["number_of_page_results"]

        self.repair_urls(filtered_issues_result)

        return filtered_issues_result

    def fetch_issue_data(self, series_id: int, issue_number: str, settings: ComicTaggerSettings) -> GenericMetadata:
        volume_results = self.fetch_volume_data(series_id)
        issues_list_results = self.fetch_issues_by_volume(series_id)

        f_record = None
        for record in issues_list_results:
            if IssueString(issue_number).as_string() is None:
                issue_number = "1"
            if (
                IssueString(record["issue_number"]).as_string().casefold()
                == IssueString(issue_number).as_string().casefold()
            ):
                f_record = record
                break

        if f_record is not None:
            issue_url = self.api_base_url + "/issue/" + CVTypeID.Issue + "-" + str(f_record["id"])
            params = {"api_key": self.api_key, "format": "json"}
            cv_response = self.get_cv_content(issue_url, params)
            issue_results = cast(CVIssueDetailResults, cv_response["results"])

        else:
            return GenericMetadata()

        # Now, map the Comic Vine data to generic metadata
        return self.map_cv_data_to_metadata(volume_results, issue_results, settings)

    def fetch_issue_data_by_issue_id(self, issue_id: int, settings: ComicTaggerSettings) -> GenericMetadata:

        issue_url = self.api_base_url + "/issue/" + CVTypeID.Issue + "-" + str(issue_id)
        params = {"api_key": self.api_key, "format": "json"}
        cv_response = self.get_cv_content(issue_url, params)

        issue_results = cast(CVIssueDetailResults, cv_response["results"])

        volume_results = self.fetch_volume_data(issue_results["volume"]["id"])

        # Now, map the Comic Vine data to generic metadata
        md = self.map_cv_data_to_metadata(volume_results, issue_results, settings)
        md.is_empty = False
        return md

    def map_cv_data_to_metadata(
        self, volume_results: CVVolumeResults, issue_results: CVIssueDetailResults, settings: ComicTaggerSettings
    ) -> GenericMetadata:

        # Now, map the Comic Vine data to generic metadata
        metadata = GenericMetadata()
        metadata.is_empty = False

        metadata.series = utils.xlate(issue_results["volume"]["name"])
        metadata.issue = IssueString(issue_results["issue_number"]).as_string()
        metadata.title = utils.xlate(issue_results["name"])

        if volume_results["publisher"] is not None:
            metadata.publisher = utils.xlate(volume_results["publisher"]["name"])
        metadata.day, metadata.month, metadata.year = self.parse_date_str(issue_results["cover_date"])

        metadata.comments = self.cleanup_html(issue_results["description"], settings.remove_html_tables)
        if settings.use_series_start_as_volume:
            metadata.volume = int(volume_results["start_year"])

        metadata.notes = (
            f"Tagged with ComicTagger {ctversion.version} using info from Comic Vine on"
            f" {datetime.now():%Y-%m-%d %H:%M:%S}.  [Issue ID {issue_results['id']}]"
        )
        metadata.web_link = issue_results["site_detail_url"]

        person_credits = issue_results["person_credits"]
        for person in person_credits:
            if "role" in person:
                roles = person["role"].split(",")
                for role in roles:
                    # can we determine 'primary' from CV??
                    metadata.add_credit(person["name"], role.title().strip(), False)

        character_credits = issue_results["character_credits"]
        character_list = []
        for character in character_credits:
            character_list.append(character["name"])
        metadata.characters = ", ".join(character_list)

        team_credits = issue_results["team_credits"]
        team_list = []
        for team in team_credits:
            team_list.append(team["name"])
        metadata.teams = ", ".join(team_list)

        location_credits = issue_results["location_credits"]
        location_list = []
        for location in location_credits:
            location_list.append(location["name"])
        metadata.locations = ", ".join(location_list)

        story_arc_credits = issue_results["story_arc_credits"]
        arc_list = []
        for arc in story_arc_credits:
            arc_list.append(arc["name"])
        if len(arc_list) > 0:
            metadata.story_arc = ", ".join(arc_list)

        return metadata

    def cleanup_html(self, string: str, remove_html_tables: bool) -> str:
        if string is None:
            return ""
        # find any tables
        soup = BeautifulSoup(string, "html.parser")
        tables = soup.findAll("table")

        # remove all newlines first
        string = string.replace("\n", "")

        # put in our own
        string = string.replace("<br>", "\n")
        string = string.replace("</li>", "\n")
        string = string.replace("</p>", "\n\n")
        string = string.replace("<h1>", "*")
        string = string.replace("</h1>", "*\n")
        string = string.replace("<h2>", "*")
        string = string.replace("</h2>", "*\n")
        string = string.replace("<h3>", "*")
        string = string.replace("</h3>", "*\n")
        string = string.replace("<h4>", "*")
        string = string.replace("</h4>", "*\n")
        string = string.replace("<h5>", "*")
        string = string.replace("</h5>", "*\n")
        string = string.replace("<h6>", "*")
        string = string.replace("</h6>", "*\n")

        # remove the tables
        p = re.compile(r"<table[^<]*?>.*?</table>")
        if remove_html_tables:
            string = p.sub("", string)
            string = string.replace("*List of covers and their creators:*", "")
        else:
            string = p.sub("{}", string)

        # now strip all other tags
        p = re.compile(r"<[^<]*?>")
        newstring = p.sub("", string)

        newstring = newstring.replace("&nbsp;", " ")
        newstring = newstring.replace("&amp;", "&")

        newstring = newstring.strip()

        if not remove_html_tables:
            # now rebuild the tables into text from BSoup
            try:
                table_strings = []
                for table in tables:
                    rows = []
                    hdrs = []
                    col_widths = []
                    for hdr in table.findAll("th"):
                        item = hdr.string.strip()
                        hdrs.append(item)
                        col_widths.append(len(item))
                    rows.append(hdrs)

                    for row in table.findAll("tr"):
                        cols = []
                        col = row.findAll("td")
                        i = 0
                        for c in col:
                            item = c.string.strip()
                            cols.append(item)
                            if len(item) > col_widths[i]:
                                col_widths[i] = len(item)
                            i += 1
                        if len(cols) != 0:
                            rows.append(cols)
                    # now we have the data, make it into text
                    fmtstr = ""
                    for w in col_widths:
                        fmtstr += f" {{:{w + 1}}}|"
                    width = sum(col_widths) + len(col_widths) * 2
                    table_text = ""
                    counter = 0
                    for row in rows:
                        table_text += fmtstr.format(*row) + "\n"
                        if counter == 0 and len(hdrs) != 0:
                            table_text += "-" * width + "\n"
                        counter += 1

                    table_strings.append(table_text)

                newstring = newstring.format(*table_strings)
            except Exception:
                # we caught an error rebuilding the table.
                # just bail and remove the formatting
                logger.exception("table parse error")
                newstring.replace("{}", "")

        return newstring

    def fetch_issue_date(self, issue_id: int) -> tuple[int | None, int | None]:
        details = self.fetch_issue_select_details(issue_id)
        _, month, year = self.parse_date_str(details["cover_date"] or "")
        return month, year

    def fetch_issue_cover_urls(self, issue_id: int) -> tuple[str | None, str | None]:
        details = self.fetch_issue_select_details(issue_id)
        return details["image_url"], details["thumb_image_url"]

    def fetch_issue_page_url(self, issue_id: int) -> str | None:
        details = self.fetch_issue_select_details(issue_id)
        return details["site_detail_url"]

    def fetch_issue_select_details(self, issue_id: int) -> SelectDetails:
        cached_details = self.fetch_cached_issue_select_details(issue_id)
        if cached_details["image_url"] is not None:
            return cached_details

        issue_url = self.api_base_url + "/issue/" + CVTypeID.Issue + "-" + str(issue_id)

        params = {"api_key": self.api_key, "format": "json", "field_list": "image,cover_date,site_detail_url"}

        cv_response = self.get_cv_content(issue_url, params)
        results = cast(CVIssueDetailResults, cv_response["results"])

        details: SelectDetails = {
            "image_url": results["image"]["super_url"],
            "thumb_image_url": results["image"]["thumb_url"],
            "cover_date": results["cover_date"],
            "site_detail_url": results["site_detail_url"],
        }

        if (
            details["image_url"] is not None
            and details["thumb_image_url"] is not None
            and details["cover_date"] is not None
            and details["site_detail_url"] is not None
        ):
            self.cache_issue_select_details(
                issue_id,
                details["image_url"],
                details["thumb_image_url"],
                details["cover_date"],
                details["site_detail_url"],
            )
        return details

    def fetch_cached_issue_select_details(self, issue_id: int) -> SelectDetails:

        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher()
        return cvc.get_issue_select_details(issue_id, self.source_name)

    def cache_issue_select_details(
        self, issue_id: int, image_url: str, thumb_url: str, cover_date: str, page_url: str
    ) -> None:
        cvc = ComicCacher()
        cvc.add_issue_select_details(issue_id, image_url, thumb_url, cover_date, page_url)

    def fetch_alternate_cover_urls(self, issue_id: int, issue_page_url: str) -> list[str]:
        url_list = self.fetch_cached_alternate_cover_urls(issue_id)
        if url_list is not None:
            return url_list

        # scrape the CV issue page URL to get the alternate cover URLs
        content = requests.get(issue_page_url, headers={"user-agent": "comictagger/" + ctversion.version}).text
        alt_cover_url_list = self.parse_out_alt_cover_urls(content)

        # cache this alt cover URL list
        self.cache_alternate_cover_urls(issue_id, alt_cover_url_list)

        return alt_cover_url_list

    def parse_out_alt_cover_urls(self, page_html: str) -> list[str]:
        soup = BeautifulSoup(page_html, "html.parser")

        alt_cover_url_list = []

        # Using knowledge of the layout of the Comic Vine issue page here:
        # look for the divs that are in the classes 'imgboxart' and 'issue-cover'
        div_list = soup.find_all("div")
        covers_found = 0
        for d in div_list:
            if "class" in d.attrs:
                c = d["class"]
                if "imgboxart" in c and "issue-cover" in c:
                    if d.img["src"].startswith("http"):
                        covers_found += 1
                        if covers_found != 1:
                            alt_cover_url_list.append(d.img["src"])
                    elif d.img["data-src"].startswith("http"):
                        covers_found += 1
                        if covers_found != 1:
                            alt_cover_url_list.append(d.img["data-src"])

        return alt_cover_url_list

    def fetch_cached_alternate_cover_urls(self, issue_id: int) -> list[str]:

        # before we search online, look in our cache, since we might already have this info
        cvc = ComicCacher()
        url_list = cvc.get_alt_covers(self.source_name, issue_id)

        return url_list

    def cache_alternate_cover_urls(self, issue_id: int, url_list: list[str]) -> None:
        cvc = ComicCacher()
        cvc.add_alt_covers(self.source_name, issue_id, url_list)

    def async_fetch_issue_cover_urls(self, issue_id: int) -> None:

        self.issue_id = issue_id
        details = self.fetch_cached_issue_select_details(issue_id)
        if details["image_url"] is not None:
            ComicVineTalker.url_fetch_complete(details["image_url"], details["thumb_image_url"])
            return

        issue_url = (
            self.api_base_url
            + "/issue/"
            + CVTypeID.Issue
            + "-"
            + str(issue_id)
            + "/?api_key="
            + self.api_key
            + "&format=json&field_list=image,cover_date,site_detail_url"
        )

        self.nam.finished.connect(self.async_fetch_issue_cover_url_complete)
        self.nam.get(QtNetwork.QNetworkRequest(QtCore.QUrl(issue_url)))

    def async_fetch_issue_cover_url_complete(self, reply: QtNetwork.QNetworkReply) -> None:
        # read in the response
        data = reply.readAll()

        try:
            cv_response = cast(CVResult, json.loads(bytes(data)))
        except Exception:
            logger.exception("Comic Vine query failed to get JSON data\n%s", str(data))
            return

        if cv_response["status_code"] != 1:
            logger.error("Comic Vine query failed with error:  [%s]. ", cv_response["error"])
            return

        result = cast(CVIssuesResults, cv_response["results"])

        image_url = result["image"]["super_url"]
        thumb_url = result["image"]["thumb_url"]
        cover_date = result["cover_date"]
        page_url = result["site_detail_url"]

        self.cache_issue_select_details(cast(int, self.issue_id), image_url, thumb_url, cover_date, page_url)

        ComicVineTalker.url_fetch_complete(image_url, thumb_url)

    def async_fetch_alternate_cover_urls(self, issue_id: int, issue_page_url: str) -> None:
        # This async version requires the issue page url to be provided!
        self.issue_id = issue_id
        url_list = self.fetch_cached_alternate_cover_urls(issue_id)
        if url_list:
            ComicVineTalker.alt_url_list_fetch_complete(url_list)
            return

        self.nam.finished.connect(self.async_fetch_alternate_cover_urls_complete)
        self.nam.get(QtNetwork.QNetworkRequest(QtCore.QUrl(str(issue_page_url))))

    def async_fetch_alternate_cover_urls_complete(self, reply: QtNetwork.QNetworkReply) -> None:
        # read in the response
        html = str(reply.readAll())
        alt_cover_url_list = self.parse_out_alt_cover_urls(html)

        # cache this alt cover URL list
        self.cache_alternate_cover_urls(cast(int, self.issue_id), alt_cover_url_list)

        ComicVineTalker.alt_url_list_fetch_complete(alt_cover_url_list)

    def repair_urls(
        self, issue_list: list[CVIssuesResults] | list[CVVolumeResults] | list[CVIssueDetailResults]
    ) -> None:
        # make sure there are URLs for the image fields
        for issue in issue_list:
            if issue["image"] is None:
                issue["image"] = {
                    "super_url": ComicVineTalker.logo_url,
                    "thumb_url": ComicVineTalker.logo_url,
                }
