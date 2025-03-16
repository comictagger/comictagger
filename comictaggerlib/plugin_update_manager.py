"""Manages installing/updating plugins"""

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

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

import yaml
from packaging.version import InvalidVersion, Version, parse

import comictaggerlib.plugin_manifest
from comictaggerlib.ctsettings import ct_ns, plugin_finder

try:
    import niquests as requests
except ImportError:
    import requests

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    plugin_id: str
    name: str
    type: str
    desc: str
    manifest: str

    @staticmethod
    def load(data: str | TextIO) -> list[Plugin]:
        try:
            return [Plugin(**entry) for entry in yaml.safe_load(data)]
        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML: %s", e)
            return []
        except Exception as e:
            logger.error("Error with YAML data: %s", e)
            return []


@dataclass
class Download:
    version: str
    url: str


@dataclass
class PluginReleases:
    latest: str
    downloads: list[Download]

    @staticmethod
    def load(data: str | TextIO) -> PluginReleases | None:
        try:
            yaml_data = yaml.safe_load(data)
            downloads: list[Download] = [Download(**entry) for entry in yaml_data.get("downloads", [])]
            return PluginReleases(latest=yaml_data["latest"], downloads=downloads)
        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML: %s", e)
            return None
        except Exception as e:
            logger.error("Error with YAML data: %s", e)
            return None


class PluginUpdateManager:
    def __init__(self, config: ct_ns):
        self.config = config
        self.plugin_dir: Path = Path(self.config.Runtime_Options__config.user_plugin_dir)
        self.plugin_download_dir: Path = Path(self.config.Runtime_Options__config.user_plugin_dir.joinpath("downloads"))
        self._check_create_dir(self.plugin_download_dir)
        self.plugin_files: dict[str, list[tuple[Version, Path]]] = {}
        self.remote_plugin_list: list[Plugin] = []
        self._read_plugin_list()
        self._find_local_plugins()

    def _check_create_dir(self, dir_path: str | Path) -> bool:
        if not os.path.exists(dir_path):
            try:
                os.mkdir(dir_path)
                return True
            except FileNotFoundError:
                logger.error("Failed to create plugin download directory, parent directory of %s not found!", dir_path)
            except Exception as e:
                logger.error("Failed to create plugin download directory. Error: %s", e)

        return False

    def _clean_download_dir(self) -> None:
        for file in os.listdir(self.plugin_download_dir):
            if Path(file).is_file():
                try:
                    os.unlink(file)
                except Exception as e:
                    logger.warning("Failed to remove %s. Error: %s", file, e)

    def _parse_version(self, file: str) -> Version | None:
        try:
            return parse(file)
        except InvalidVersion:
            logger.error(f"Invalid version number for : {file}")
            return None

    def _find_local_plugins(self) -> None:
        local_plugins = plugin_finder.find_plugins(self.plugin_dir)

        # Create a deduped dict with each sorted by Version number
        plugins_dict: dict[str, list[tuple[Version, Path]]] = {}

        for plugins in local_plugins:
            if plugins:
                for plugin in plugins:
                    version: Version | None = self._parse_version(plugin[0].version)
                    # Expect manifest ID and entry_name to match
                    # Archives have no ID but have entry_name so that is expected to be the manifest ID
                    if version is not None:
                        if plugins_dict.get(plugin.entry_name) is None:
                            plugins_dict[plugin.entry_name] = [(version, plugin[0].path)]
                        else:
                            plugins_dict[plugin.entry_name].append((version, plugin[0].path))

        self.plugin_files = {
            key: sorted(value, key=lambda x: x[0], reverse=True) for key, value in plugins_dict.items()
        }

    def _move_plugin(self, old_loc: str | Path, new_loc: str | Path = "") -> bool:
        if not old_loc:
            logger.debug("No file path given to move plugin.")
            return False

        old_loc = Path(old_loc)
        # Unless the new_loc is empty, it's expected the file name is included
        new_loc = Path(new_loc) if new_loc else Path(self.plugin_dir.joinpath(old_loc.name))

        try:
            # Windows will error if file exists
            os.unlink(new_loc)
        except FileNotFoundError:
            pass
        except OSError:
            logger.error("Failed to remove %s, expected file but got a directory", new_loc)
            return False

        try:
            old_loc.rename(new_loc)
            return True
        except Exception as e:
            logger.error("Failed to move %s to %s. Error: %s", old_loc, new_loc, e)

        return False

    def _check_plugin(self, plugin_path: Path) -> bool:
        # Load newly downloaded plugins
        local_download_plugins = plugin_finder.find_plugins(self.plugin_download_dir)

        for plugin_type in local_download_plugins:
            for plugin in plugin_type:
                if plugin.plugin.path == plugin_path:
                    return self._move_plugin(plugin_path)

        return False

    def _read_plugin_list(self) -> None:
        try:
            plugin_list_file = cast(Path, comictaggerlib.plugin_manifest.data_path.joinpath("plugin_list.yaml"))
            with open(plugin_list_file, encoding="utf-8") as f:
                self.remote_plugin_list = Plugin.load(f)
        except Exception as e:
            logger.error("Failed to load plugin_list.yaml: %s", e)

    def list_available_updates(self) -> None:
        """CLI method to list available updates of installed plugins"""
        available_updates: list[tuple[Plugin, str]] = self._check_for_all_updates()
        if available_updates:
            print("Available Update(s):")  # noqa: T201
            [print(item[0].name) for item in available_updates]  # noqa: T201
        else:
            print("No updates available")  # noqa: T201

    def update_all_plugins(self) -> None:
        available_updates: list[tuple[Plugin, str]] = self._check_for_all_updates()
        if available_updates:
            for update, download_url in available_updates:
                success, new_plugin_file = self._download_plugin(download_url)
                test_plugin = self._check_plugin(new_plugin_file)
                if success and test_plugin:
                    logger.info(f"Updated remote plugin {update.name}")
                else:
                    logger.warning("Failed to download plugin or failed loading, see above for details")

                if not test_plugin:
                    self._remove_plugin(new_plugin_file)

            self._clean_download_dir()
            self._move_old_plugins()

    def _check_for_all_updates(self) -> list[tuple[Plugin, str]]:
        available_updates: list[tuple[Plugin, str]] = []
        # TODO Check if the plugin has a 'manifest' entry (supersedes our remote list URL)
        for k, item in self.plugin_files.items():
            for r_plugin in self.remote_plugin_list:
                if k == r_plugin.plugin_id:
                    result = self._check_for_update(r_plugin.manifest, item[0][0])  # Sorted, item[0] should be latest
                    if result is not None:
                        available_updates.append((r_plugin, result))
                    break

        return available_updates

    def _check_for_update(self, url: str, installed_version: Version) -> str | None:
        latest = self._download_plugin_manifest(url)
        if latest is not None:
            for download in latest.downloads:
                if self._parse_version(download.version) > installed_version:
                    return download.url

        return None

    def install_by_id(self, plugin_id: str = "") -> None:
        """Install a plugin by its manifest ID"""
        if not plugin_id:
            logger.warning(
                "No plugin ID given. Please enter a valid plugin ID, e.g. 'metron'. Use --list-remote-plugins for list."
            )
            return

        plugin_id = plugin_id.strip()
        plugin_details: Plugin | None = None
        success: bool = False

        # TODO Check installed plugins what may not be in the list but provide a manifest URL
        for item in self.remote_plugin_list:
            if item.plugin_id == plugin_id:
                plugin_details = item

        if plugin_details is None:
            logger.warning(f"No plugin with ID '{plugin_id}' found. Use --list-remote-plugins for list.")
            return

        latest_version: PluginReleases | None = self._download_plugin_manifest(plugin_details.manifest)

        if latest_version is None:
            logger.warning(f"Unable to find latest version for plugin from URL: {plugin_details.manifest}")
            return

        if latest_version.latest:
            for download in latest_version.downloads:
                if latest_version.latest == download.version:
                    success, new_plugin_file = self._download_plugin(download.url)
                    break
        else:
            logger.error("No 'latest' found in download manifest: %s", plugin_details.manifest)
            logger.error(f"Failed to install plugin with ID '{plugin_id}', see log for details")
            return

        if success:
            test_plugin = self._check_plugin(new_plugin_file)
            if test_plugin:
                print(f"Installed: {plugin_details.name} {latest_version.latest} to {self.plugin_dir}")  # noqa: T201
                self._move_old_plugins()
            else:
                self._remove_plugin(new_plugin_file)

    def _download_plugin_manifest(self, url: str) -> PluginReleases | None:
        # TODO Remove test manifest URL
        url = "https://gist.githubusercontent.com/mizaki/52b60ac53cd3344ff1e1bfd44fc50ebd/raw/f446fd7c149053965fe9e4035fe66e296bf3a02d/manifest.yaml"
        latest = self._manifest_request(url)

        if latest is not None:
            return PluginReleases.load(latest)

        return None

    def _download_plugin(self, url: str, name: str = "") -> tuple[bool, Path]:
        response = requests.get(url)

        if response.status_code == 200:
            if not name:
                try:
                    name = response.headers["content-disposition"].split("=")[1]
                except Exception:
                    name = url.rsplit("/", 1)[1]
                finally:
                    if not (name.endswith(".whl") or name.endswith(".zip")):
                        logger.error("Ignoring download, unexpected or unknown file extension: %s", name)
                        return False, Path()

            filepath = self.plugin_download_dir.joinpath(name)

            try:
                with open(filepath, mode="wb") as file:
                    file.write(response.content)
                    return True, filepath
            except Exception as e:
                logger.exception("Failed to save plugin download file: %s. Error: %s", filepath, e)

        return False, Path()

    def _move_old_plugins(self) -> None:
        old_dir = self.plugin_dir.joinpath("old")
        self._check_create_dir(old_dir)
        # Update local plugins first
        self._find_local_plugins()

        for key, item in self.plugin_files.items():
            if len(item) > 1:
                for i, (version, filename) in enumerate(item):
                    # First filename should be latest version to keep
                    if i > 0:
                        self._move_plugin(filename, old_dir.joinpath(filename.name))

    def _remove_plugin(self, file: Path) -> None:
        filepath = self.plugin_dir.joinpath(file)
        # Don't want to be nuking dirs by mistake
        if filepath.is_file():
            try:
                os.remove(filepath)
                logger.info(f"Removed old plugin file: {filepath}")
            except Exception as e:
                logger.exception(f"Failed to remove old plugin file: {filepath}. Error: {e}")

    def _manifest_request(self, url: str) -> str | None:
        try:
            resp = requests.get(url, headers={"user-agent": "comictagger"}, timeout=10)
            if resp.status_code == 200:
                return resp.text
            logger.error("Failed to download manifest file: %s", url)
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request error for {url}: {e}")

        return None
