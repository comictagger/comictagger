"""Handles collecting data from source talkers.
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
from typing import Callable

from comicapi.genericmetadata import GenericMetadata
from comictalker.resulttypes import ComicIssue, ComicVolume
from comictalker.talkerbase import SourceStaticOptions, TalkerError

logger = logging.getLogger(__name__)


# To signal image loaded etc.
def list_fetch_complete(url_list: list[str]) -> None:
    ...


def url_fetch_complete(image_url: str, thumb_url: str | None) -> None:
    ...


class ComicTalker:
    alt_url_list_fetch_complete = list_fetch_complete
    url_fetch_complete = url_fetch_complete

    def __init__(self, source_name) -> None:
        # ID of the source to use e.g. comicvine
        self.source = source_name
        # Retrieve the available sources modules
        self.sources = self.get_talkers()
        # Set the active talker
        self.talker = self.get_active_talker()
        self.static_options = self.get_static_options()

    def get_active_talker(self):
        # This should always work because it will have errored at get_talkers if there are none
        if not self.sources[self.source] is None:
            return self.sources[self.source]

    @staticmethod
    def get_talkers():
        # Hardcode import for now. Placed here to prevent circular import
        import comictalker.talkers.comicvine

        return {"comicvine": comictalker.talkers.comicvine.ComicVineTalker()}

    # For issueidentifier
    def set_log_func(self, log_func: Callable[[str], None]) -> None:
        self.talker.log_func = log_func

    def get_static_options(self) -> SourceStaticOptions:
        return self.talker.source_details.static_options

    def check_api_key(self, key: str, url: str, source_id: str):
        for source in self.sources.values():
            if source.source_details.id == source_id:
                return source.check_api_key(key, url)
        # Return false as back up or error?
        return False

    # Master function to search for series/volumes
    def search_for_series(
        self,
        series_name: str,
        callback: Callable[[int, int], None] | None = None,
        refresh_cache: bool = False,
        literal: bool = False,
    ) -> list[ComicVolume]:
        try:
            series_result = self.talker.search_for_series(series_name, callback, refresh_cache, literal)
            return series_result
        except NotImplementedError:
            logger.warning(f"{self.talker.source_details.name} has not implemented: 'search_for_series'")
            raise TalkerError(
                self.talker.source_details.name,
                4,
                "The source has not implemented: 'search_for_series'",
            )

    # Get issue or volume information. issue_id is used by CLI
    def fetch_comic_data(self, series_id: int = 0, issue_number: str = "", issue_id: int = 0) -> GenericMetadata:
        """This function is expected to handle a few possibilities:
        1. Only series_id. Retrieve the SERIES/VOLUME information only.
        2. series_id and issue_number. Retrieve the ISSUE information.
        3. Only issue_id. Used solely by the CLI to retrieve the ISSUE information."""
        try:
            comic_data = self.talker.fetch_comic_data(series_id, issue_number, issue_id)
            return comic_data
        except NotImplementedError:
            logger.warning(f"{self.talker.source_details.name} has not implemented: 'fetch_comic_data'")
            raise TalkerError(
                self.talker.source_details.name,
                4,
                "The source has not implemented: 'fetch_comic_data'",
            )

    # Master function to get issues in a series/volume
    def fetch_issues_by_volume(self, series_id: int) -> list[ComicIssue]:
        try:
            issues_result = self.talker.fetch_issues_by_volume(series_id)
            return issues_result
        except NotImplementedError:
            logger.warning(f"{self.talker.source_details.name} has not implemented: 'fetch_issues_by_volume'")
            raise TalkerError(
                self.talker.source_details.name,
                4,
                "The source has not implemented: 'fetch_issues_by_volume'",
            )

    # For issueidentifer
    def fetch_alternate_cover_urls(self, issue_id: int) -> list[str]:
        try:
            alt_covers = self.talker.fetch_alternate_cover_urls(issue_id)
            return alt_covers
        except NotImplementedError:
            logger.warning(f"{self.talker.source_details.name} has not implemented: 'fetch_alternate_cover_urls'")
            raise TalkerError(
                self.talker.source_details.name,
                4,
                "The source has not implemented: 'fetch_alternate_cover_urls'",
            )

    # For issueidentifier
    def fetch_issues_by_volume_issue_num_and_year(
        self, volume_id_list: list[int], issue_number: str, year: str | int | None
    ) -> list[ComicIssue]:
        try:
            issue_results = self.talker.fetch_issues_by_volume_issue_num_and_year(volume_id_list, issue_number, year)
            return issue_results
        except NotImplementedError:
            logger.warning(
                f"{self.talker.source_details.name} has not implemented: 'fetch_issues_by_volume_issue_num_and_year'"
            )
            raise TalkerError(
                self.talker.source_details.name,
                4,
                "The source has not implemented: 'fetch_issues_by_volume_issue_num_and_year'",
            )

    def fetch_issue_cover_urls(self, issue_id: int) -> tuple[str | None, str | None]:
        try:
            cover_urls = self.talker.fetch_issue_cover_urls(issue_id)
            return cover_urls
        except NotImplementedError:
            logger.warning(f"{self.talker.source_details.name} has not implemented: 'fetch_issue_cover_urls'")
            raise TalkerError(
                self.talker.source_details.name,
                4,
                "The source has not implemented: 'fetch_issue_cover_urls'",
            )

    # Master function to get issue cover. Used by coverimagewidget
    def async_fetch_issue_cover_urls(self, issue_id: int) -> None:
        try:
            # TODO: Figure out async
            image_url, thumb_url = self.fetch_issue_cover_urls(issue_id)
            ComicTalker.url_fetch_complete(image_url or "", thumb_url)
            logger.info("Should be downloading image: %s  thumb: %s", image_url, thumb_url)
            return

            # Should be all that's needed? CV functions will trigger everything.
            self.talker.async_fetch_issue_cover_urls(issue_id)
        except NotImplementedError:
            logger.warning(f"{self.talker.source_details.name} has not implemented: 'async_fetch_issue_cover_urls'")

    def async_fetch_alternate_cover_urls(self, issue_id: int) -> None:
        try:
            # TODO: Figure out async
            url_list = self.fetch_alternate_cover_urls(issue_id)
            ComicTalker.alt_url_list_fetch_complete(url_list)
            logger.info("Should be downloading alt image list: %s", url_list)
            return

            self.talker.async_fetch_alternate_cover_urls(issue_id)
        except NotImplementedError:
            logger.warning(f"{self.talker.source_details.name} has not implemented: 'async_fetch_alternate_cover_urls'")
