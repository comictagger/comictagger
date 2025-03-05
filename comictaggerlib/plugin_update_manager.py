"""Manages installing/updating plugins"""
import logging
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


import settngs
import os
from packaging.version import InvalidVersion, parse, Version
from typing import Any
import json
import time
from comicapi import utils
from urllib3.util import Url
from dataclasses import dataclass
from typing import List, Optional
import re
from pathlib import Path

import comictaggerlib
try:
    import niquests as requests
except ImportError:
    import requests

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

@dataclass
class User:
    login: str
    id: int
    node_id: str
    avatar_url: str
    gravatar_id: str
    url: str
    html_url: str
    followers_url: str
    following_url: str
    gists_url: str
    starred_url: str
    subscriptions_url: str
    organizations_url: str
    repos_url: str
    events_url: str
    received_events_url: str
    type: str
    user_view_type: str
    site_admin: bool

@dataclass
class Asset:
    url: str
    id: int
    node_id: str
    name: str
    label: str
    uploader: User
    content_type: str
    state: str
    size: int
    download_count: int
    created_at: str
    updated_at: str
    browser_download_url: str

@dataclass
class GitHubRelease:
    url: str
    assets_url: str
    upload_url: str
    html_url: str
    id: int
    author: User
    node_id: str
    tag_name: str
    target_commitish: str
    name: str
    draft: bool
    prerelease: bool
    created_at: str
    published_at: str
    assets: List[Asset]
    tarball_url: str
    zipball_url: str
    body: str

class PluginUpdateManager:
    def __init__(self, config: settngs.SettngsNS):
        self.config = config
        self.plugin_dir: Path = Path(self.config.Runtime_Options__config.user_plugin_dir)
        self.plugin_files: dict[str, list[tuple[Version, str]]] = {}
        self.remote_plugin_list = None
        self._read_plugin_list()
        self._find_plugin_files()
        #self.remove_old_plugins()
        #self.check_for_updates()
        #self.list_available_updates()
        print(logger.getEffectiveLevel())
        print(logger.isEnabledFor(20))
        logger.info("test")

    def _parse_version(self, file: str) -> Version | None:
        try:
            return parse(file)
        except InvalidVersion:
            logger.warning(f"PUM: Invalid version number for : {file}")
            return None

    def _find_plugin_files(self) -> None:
        plugins: list[tuple[str, Version]] = []  # filename, version number

        for file in os.listdir(self.plugin_dir):
            if str(file).endswith(".zip") or str(file).endswith(".whl"):
                version_str = re.search("[\d\.]+\d", file)
                version: Version | None = self._parse_version(version_str.group(0))
                if version is not None:
                    plugins.append((str(file), version))

        # Create a deuped dict with each version sorted by Version number
        plugins_dict = {}
        for filename, version in plugins:
            filename_name = filename.split("-")[0]
            if plugins_dict.get(filename_name) is None:
                plugins_dict[filename_name] = [(version, filename)]
            else:
                plugins_dict[filename_name].append((version, filename))

        self.plugin_files = {key: sorted(value, key=lambda x: x[0], reverse=True) for key, value in plugins_dict.items()}

    def _read_plugin_list(self) -> None:
        try:
            with open(comictaggerlib.data_path / "plugin_list.json") as f:
                self.remote_plugin_list = json.load(f)

        except Exception as e:
            logger.exception("PUM: Failed to load plugin_list.json: %s", e)

    def list_available_updates(self) -> None:
        available_updates = self.check_for_updates()
        if available_updates:
            print("Available Update(s):")
            [print(item[1]) for item in available_updates]
        else:
            print("No updates available")

    def update_all_plugins(self) -> None:
        updates = self.check_for_updates()
        if updates:
            for plugin in updates:
                self.download_plugin(plugin[0], plugin[1])
                logger.info(f"PUM: Updated remote plugin to {plugin[1]}")

        # Clean out old plugin files
        self.remove_old_plugins()

    def check_for_updates(self) -> list[tuple[str, str]]:
        available_updates: list[tuple[str, str]] = []
        for k, item in self.plugin_files.items():
            for r_plugin in self.remote_plugin_list:
                if k == r_plugin["filename_root"]:
                    result = self._check_for_update(r_plugin["update_url"], item[0])  # As it's sorted, 0 should be latest number
                    if result is not None:
                        available_updates.append((result[0], result[1]))

        return available_updates

    def install_by_id(self, plugin_id: str = "") -> None:
        """Install a plugin by its ID"""
        if not plugin_id:
            logger.warning("PUM: No plugin ID given. Please enter a valid plugin ID, e.g. 'metron'. Use --list-remote-plugins for list.")

        plugin_id = plugin_id.strip()
        plugin_details = None

        for item in self.remote_plugin_list:
            if item["id"] == plugin_id:
                plugin_details = item

        if plugin_details is None:
            logger.warning(f"PUM: No plugin with ID '{plugin_id}' found. Use --list-remote-plugins for list.")
        else:
            latest_version = self._api_latest(item["update_url"])

            if latest_version is None:
                logger.warning(f"PUM: Unable to find latest version for plugin from URL: {item['update_url']}")
            else:
                self.download_plugin(latest_version[1], latest_version[2])
                print(f"Installed: {latest_version[2]} to {self.plugin_dir}")

    def _check_for_update(self, url: str, item: (Version, str)) -> tuple[str, str] | None:
        latest = self._api_latest(url)
        if latest is not None:
            if latest[0] > item[0]:
                return latest[1], latest[2]

        return None

    def download_plugin(self, url: str, name: str) -> None:
        response = requests.get(url)

        if response.status_code == 200:
            filepath = self.plugin_dir.joinpath(name)
            try:
                with open(filepath, mode="wb") as file:
                    file.write(response.content)
            except Exception:
                logger.exception(f"PUM: Failed to save plugin download {filepath}")

    def remove_old_plugins(self) -> None:
        for key, item in self.plugin_files.items():
            if len(item) > 1:
                for i, (version, filename) in enumerate(item):
                    # First filename should be latest version to keep
                    if i > 0:
                        self.remove_plugin(self.plugin_dir.joinpath(filename))

    def remove_plugin(self, file: Path) -> None:
        filepath = self.plugin_dir.joinpath(file)
        # Don't want to be nuking dirs by mistake
        if filepath.is_file():
            try:
                os.remove(filepath)
                logger.info(f"PUM: Removed old plugin file: {filepath}")
            except Exception:
                logger.exception(f"PUM: Failed to remove old plugin file: {filepath}")

    def _api_latest(self, url: str) -> tuple[Version, str, str] | None:
        parse_url: Url = utils.parse_url(url + "releases/latest")
        latest: GitHubRelease = self._api_request(str(parse_url))

        # Do some basic testing to make sure we have the right plugin?

        # tag_name is expected to be a version number e.g. 0.1.3
        version_number: Version | None = self._parse_version(latest["tag_name"])
        if version_number is not None:
            return version_number, latest["assets"][0]["browser_download_url"], latest["assets"][0]["name"]

        return None

    def _api_request(self, url: str) -> Any:
        # if there is a 500 error, try a few more times before giving up
        limit_counter = 0

        for tries in range(1, 5):
            try:
                resp = requests.get(
                    url, headers={"user-agent": "comictagger", "accept": "application/vnd.github+json"}, timeout=10
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 500:
                    logger.debug(f"PUM: Try #{tries}: ")
                    time.sleep(1)
                    logger.debug(str(resp.status_code))

                elif resp.status_code in (requests.status_codes.codes.TOO_MANY_REQUESTS):
                    logger.info(f"PUM: {url} rate limit encountered. Waiting for 10 seconds\n")
                    time.sleep(10)
                    limit_counter += 1
                    if limit_counter > 3:
                        # Tried 3 times, inform user to check CV website.
                        logger.error(f"PUM: {url} rate limit error. Exceeded 3 retires.")
                else:
                    break

            except requests.exceptions.Timeout:
                logger.debug(f"PUM: Connection to {url} timed out.")
            except requests.exceptions.RequestException as e:
                logger.debug(f"PUM: Request exception: {e}")
            except json.JSONDecodeError as e:
                logger.debug(f"PUM: JSON decode error: {e}")
            except Exception as e:
                logger.debug(f"PUM: Request error: {e}")

        raise Exception("PUM: Unknown error occurred")
