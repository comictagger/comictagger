"""Version checker"""
#
# Copyright 2013 Anthony Beville
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

import requests

from comictaggerlib import ctversion

logger = logging.getLogger(__name__)


class VersionChecker:
    def get_request_url(self, uuid: str) -> tuple[str, dict[str, str]]:

        base_url = "https://api.github.com/repos/comictagger/comictagger/releases/latest"
        params: dict[str, str] = {}

        return base_url, params

    def get_latest_version(self, uuid: str) -> tuple[str, str]:
        try:
            url, params = self.get_request_url(uuid)
            release = requests.get(
                url,
                params=params,
                headers={"user-agent": "comictagger/" + ctversion.version},
            ).json()
        except Exception:
            return ("", "")

        new_version = release["tag_name"]
        if new_version is None or new_version == "":
            return ("", "")
        return (new_version.strip(), release["name"])
