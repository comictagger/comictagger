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
                test_plugin = False
                success, new_plugin_file = self._download_plugin(download_url)
                if success:
                    test_plugin = self._check_new_plugin(new_plugin_file)  # type: ignore[arg-type]
                if success and test_plugin:
                    logger.info(f"Updated remote plugin {update.name}")
                else:
                    logger.error("Failed to download plugin or failed loading, see above for details")

            self._clean_download_dir()
            self._move_old_plugins()

    def cli_install_by_id(self, plugin_id: str) -> None:
        """CLI method to install remote plugin by manifest ID"""
        if self.install_by_id(plugin_id):
            print("Installed: %s", plugin_id)  # noqa: T201
        else:
            print("Failed to install plugin ID %s, see log for details.", plugin_id)  # noqa: T201

    def install_by_id(self, plugin_id: str = "") -> bool:
        """Install a plugin by its manifest ID"""
        if not plugin_id:
            logger.warning(
                "No plugin ID given. Please enter a valid plugin ID, e.g. 'metron'. Use --list-remote-plugins for available plugins."
            )
            return False

        plugin_id = plugin_id.strip()
        plugin_details: Plugin | None = None
        success: bool = False

        for item in self.remote_plugin_list:
            if item.plugin_id == plugin_id:
                plugin_details = item

        if plugin_details is None:
            logger.warning(f"No plugin with ID '{plugin_id}' found. Use --list-remote-plugins for available plugins.")
            return False

        latest_version: PluginReleases | None = self._download_plugin_manifest(plugin_details.manifest)

        if latest_version is None:
            logger.error(f"Unable to find latest version for plugin from URL: {plugin_details.manifest}")
            return False

        if latest_version.latest:
            for download in latest_version.downloads:
                if latest_version.latest == download.version:
                    success, new_plugin_file = self._download_plugin(download.url)
                    break
        else:
            logger.error("No 'latest' found in download manifest: %s", plugin_details.manifest)
            logger.error(f"Failed to install plugin with ID '{plugin_id}', see log for details")
            return False

        if success:
            test_plugin = self._check_new_plugin(new_plugin_file)  # type: ignore[arg-type]
            if test_plugin:
                self._move_old_plugins()
                logger.info(f"Installed: {plugin_details.name} {latest_version.latest} to {self.plugin_dir}")
                return True

            self._clean_download_dir()

        return False

    def _parse_version(self, version: str) -> Version | None:
        try:
            return parse(version)
        except InvalidVersion:
            logger.error(f"Invalid version number for : {version}")
            return None

    def _check_create_dir(self, dir_path: str | Path) -> bool:
        if not os.path.exists(dir_path):
            try:
                os.mkdir(dir_path)
                return True
            except FileNotFoundError:
                logger.error("Failed to create directory, parent directory of %s not found!", dir_path)
            except Exception as e:
                logger.error("Failed to create directory. Error: %s", e)

        return False

    def _clean_download_dir(self) -> None:
        for file in os.listdir(self.plugin_download_dir):
            if Path(file).is_file():
                try:
                    os.remove(file)
                except Exception as e:
                    logger.warning("Failed to remove %s. Error: %s", file, e)

    def _move_plugin(self, old_loc: str | Path, new_loc: str | Path) -> bool:
        if not old_loc or not new_loc:
            logger.debug("No file path given to move plugin.")
            return False

        old_loc = Path(old_loc)
        new_loc = Path(new_loc)

        try:
            # Windows will error if file exists
            os.remove(new_loc)
        except FileNotFoundError:
            pass
        except OSError:
            logger.error("Failed to remove %s, expected file but got a directory", new_loc)
            return False

        try:
            old_loc.rename(new_loc)  # rename will move file
            return True
        except Exception as e:
            logger.error("Failed to move %s to %s. Error: %s", old_loc, new_loc, e)

        return False

    def _move_old_plugins(self) -> None:
        old_dir = self.plugin_dir.joinpath("old")
        if self._check_create_dir(old_dir):
            # Update local plugins first
            self._find_local_plugins()

            for item in self.plugin_files.values():
                if len(item) > 1:
                    for i, (version, filename) in enumerate(item):
                        # First filename should be latest version to keep
                        if i > 0:
                            self._move_plugin(filename, old_dir.joinpath(filename.name))

    def _remove_plugin(self, file: Path) -> None:
        filepath = file  # self.plugin_dir.joinpath(file)
        # Don't want to be nuking dirs by mistake
        if filepath.is_file():
            try:
                os.remove(filepath)
                logger.info(f"Removed plugin file: {filepath}")
            except Exception as e:
                logger.error(f"Failed to remove plugin file: {filepath}. Error: {e}")

    def _check_new_plugin(self, plugin_path: Path) -> bool:
        # Load newly downloaded plugins
        local_download_plugins = plugin_finder.find_plugins(self.plugin_download_dir)

        for plugin_type in local_download_plugins:
            for plugin in plugin_type:
                if plugin.plugin.path == plugin_path:
                    # Plugin loaded, move to plugin dir from download dir
                    return self._move_plugin(plugin_path, self.plugin_dir.joinpath(plugin_path.name))

        return False

    def _find_local_plugins(self) -> None:
        local_plugins = plugin_finder.find_plugins(self.plugin_dir)

        # Create a deduped dict with each sorted by Version number
        plugins_dict: dict[str, list[tuple[Version, Path]]] = {}

        for k, plugins in local_plugins._asdict().items():
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

                    # Check and update manifest URL or add manually installed plugin to remote plugin list
                    if hasattr(plugin.obj, "manifest"):
                        add_to_list = True

                        for r_plugin in self.remote_plugin_list:
                            # As archivers don't have an ID, use entry_name
                            if k == "archivers":
                                plugin.obj.id = plugin.entry_name

                            if r_plugin.plugin_id == plugin.obj.id:
                                add_to_list = False
                                if plugin.obj.manifest and r_plugin.manifest != plugin.obj.manifest:
                                    # Supersede remote list manifest with plugin class value
                                    r_plugin.manifest = plugin.obj.manifest
                                    break

                        # Not in current remote plugin list, add it
                        if add_to_list:
                            self.remote_plugin_list.append(
                                Plugin(
                                    plugin_id=plugin.entry_name,
                                    name=plugin.entry_name,
                                    type=k.capitalize(),
                                    desc="Manually installed plugin",
                                    manifest=plugin.obj.manifest,
                                )
                            )

        self.plugin_files = {
            key: sorted(value, key=lambda x: x[0], reverse=True) for key, value in plugins_dict.items()
        }

    def _read_plugin_list(self) -> None:
        try:
            plugin_list_file = cast(Path, comictaggerlib.plugin_manifest.data_path.joinpath("plugin_list.yaml"))
            with open(plugin_list_file, encoding="utf-8") as f:
                self.remote_plugin_list = Plugin.load(f)
        except Exception as e:
            logger.error("Failed to load plugin_list.yaml: %s", e)

    def _check_for_all_updates(self) -> list[tuple[Plugin, str]]:
        available_updates: list[tuple[Plugin, str]] = []
        for k, item in self.plugin_files.items():
            for r_plugin in self.remote_plugin_list:
                if k == r_plugin.plugin_id:
                    url = self._check_for_update(r_plugin.manifest, item[0][0])  # Sorted, item[0] should be latest
                    if url is not None:
                        available_updates.append((r_plugin, url))
                    break

        return available_updates

    def _check_for_update(self, url: str, installed_version: Version) -> str | None:
        latest = self._download_plugin_manifest(url)
        if latest is not None:
            for download in latest.downloads:
                if self._parse_version(download.version) > installed_version:
                    return download.url

        return None

    def _download_plugin_manifest(self, url: str) -> PluginReleases | None:
        latest = self._manifest_request(url)

        if latest is not None:
            return PluginReleases.load(latest)

        return None

    def _download_plugin(self, url: str, name: str = "") -> tuple[bool, Path | None]:
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
                        return False, None

            filepath = self.plugin_download_dir.joinpath(name)

            try:
                with open(filepath, mode="wb") as file:
                    file.write(response.content)
                    return True, filepath
            except Exception as e:
                logger.error("Failed to save plugin download file: %s. Error: %s", filepath, e)

        return False, None

    def _manifest_request(self, url: str) -> str | None:
        try:
            resp = requests.get(url, headers={"user-agent": "comictagger"}, timeout=10)
            if resp.status_code == 200:
                return resp.text
            logger.error("Failed to download manifest file: %s", url)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {e}")

        return None
