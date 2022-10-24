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

import inspect
import logging
from importlib import import_module
from typing import Callable

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

    def get_active_talker(self):
        # This should always work because it will have errored at get_talkers if there are none
        if not self.sources[self.source] is None:
            return self.sources[self.source]

    @staticmethod
    def get_talkers():
        def check_talker(module: str):
            testmodule = import_module("comictalker.talkers." + module)
            for name, obj in inspect.getmembers(testmodule):
                if inspect.isclass(obj):
                    if name != "ComicTalker" and name.endswith("Talker"):
                        # TODO Check if enabled?
                        talker = obj()
                        required_fields_details = ["name", "id"]
                        required_fields_static = ["has_issues", "has_alt_covers", "has_censored_covers"]
                        required_fields_settings = ["enabled", "url_root"]
                        errors_found = False

                        if talker.source_details is None:
                            logger.warning(module + " is missing required source_details.")
                            return False
                        if not talker.source_details.static_options:
                            logger.warning(module + " is missing required static_options.")
                            return False
                        if not talker.source_details.settings_options:
                            logger.warning(module + " is missing required settings_options.")
                            return False

                        for field in required_fields_details:
                            if not hasattr(talker.source_details, field):
                                logger.warning(module + " is missing required source_details: " + field)
                                errors_found = True
                        # No need to check these as they have defaults, should defaults be None to catch?
                        for field in required_fields_static:
                            if not hasattr(talker.source_details.static_options, field):
                                logger.warning(module + " is missing required static_options: " + field)
                                errors_found = True
                        for field in required_fields_settings:
                            if field not in talker.source_details.settings_options:
                                logger.warning(module + " is missing required settings_options: " + field)
                                errors_found = True

                        if errors_found:
                            return False

                        for key, val in talker.source_details.static_options.__dict__.items():
                            # Check for required options has the correct type
                            if key == "has_issues":
                                if type(val) is not bool:
                                    logger.warning(module + " has incorrect key type: " + key + ":" + str(val))
                                    errors_found = True
                            if key == "has_alt_covers":
                                if type(val) is not bool:
                                    logger.warning(module + " has incorrect key type: " + key + ":" + str(val))
                                    errors_found = True
                            if key == "has_censored_covers":
                                if type(val) is not bool:
                                    logger.warning(module + " has incorrect key type: " + key + ":" + str(val))
                                    errors_found = True

                        for key, val in talker.source_details.settings_options.items():
                            if key == "enabled":
                                if type(val["value"]) is not bool:
                                    logger.warning(module + " has incorrect key type: " + key + ":" + str(val))
                                    errors_found = True
                            if key == "url_root":
                                # Check starts with http[s]:// too?
                                if not val["value"]:
                                    logger.warning(module + " has missing value: " + key + ":" + str(val))
                                    errors_found = True

                        if errors_found:
                            logger.warning(module + " is missing required settings. Check logs.")
                            return False
            return True

        # Hardcode import for now. Placed here to prevent circular import
        import comictalker.talkers.comicvine

        if check_talker("comicvine"):
            return {"comicvine": comictalker.talkers.comicvine.ComicVineTalker()}

    # For issueidentifier
    def set_log_func(self, log_func: Callable[[str], None]) -> None:
        self.talker.log_func = log_func

    def check_api_key(self, key: str, url: str, source_id: str):
        for source in self.sources.values():
            if source.source_details.id == source_id:
                return source.check_api_key(key, url)
        # Return false as back up or error?
        return False
