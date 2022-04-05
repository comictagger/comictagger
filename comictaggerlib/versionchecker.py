"""Version checker"""

# Copyright 2013 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import platform
import sys

import requests

from comictaggerlib import ctversion

logger = logging.getLogger(__name__)


class VersionChecker:
    def get_request_url(self, uuid, use_stats):

        base_url = "http://comictagger1.appspot.com/latest"
        params = {}
        if use_stats:
            params = {"uuid": uuid, "version": ctversion.version}
            if platform.system() == "Windows":
                params["platform"] = "win"
            elif platform.system() == "Linux":
                params["platform"] = "lin"
            elif platform.system() == "Darwin":
                params["platform"] = "mac"
            else:
                params["platform"] = "other"

            if not getattr(sys, "frozen", None):
                params["src"] = "T"

        return base_url, params

    def get_latest_version(self, uuid, use_stats=True):
        try:
            url, params = self.get_request_url(uuid, use_stats)
            new_version = requests.get(url, params=params).text
        except Exception:
            return None

        if new_version is None or new_version == "":
            return None
        return new_version.strip()
