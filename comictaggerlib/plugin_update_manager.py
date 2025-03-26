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
    def load_yaml(data: str | TextIO) -> list[Plugin]:
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
    def load_yaml(data: str | TextIO) -> PluginReleases | None:
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
    def __init__(self, local_plugins: plugin_finder.Plugins, config: ct_ns):
        self.config = config
        self.local_plugins = local_plugins
        self.plugin_dir: Path = Path(self.config.Runtime_Options__config.user_plugin_dir)
        self.plugin_download_dir: Path = Path(self.config.Runtime_Options__config.user_plugin_dir.joinpath("downloads"))
        self._check_create_dir(self.plugin_download_dir)
        self.remote_plugin_list: list[Plugin] = []
        self._read_plugin_list()
        self.plugins_dict: dict[str, list[tuple[Version, Path]]] = self.create_plugins_dict(local_plugins)

    def cli_install_by_id(self, plugin_id: str) -> None:
        """CLI method to install remote plugin by manifest ID"""
        if self.install_by_id(plugin_id):
            print("Installed plugin:", plugin_id)  # noqa: T201
        else:
            print(f"Failed to install plugin ID {plugin_id}, see log for details.")  # noqa: T201

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
                break

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
            return False

        if success:
            test_plugin = self._check_new_plugin(new_plugin_file)  # type: ignore[arg-type]
            if test_plugin:
                self._move_old_plugins()
                self._clean_download_dir()
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
        dir_path = Path(dir_path)

        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return True
        except FileExistsError:
            logger.error("Failed to create directory, file exists with directory name: %s", dir_path)
            return False
        except Exception as e:
            logger.error("Failed to create directory. Error: %s", e)
            return False

    def _clean_download_dir(self) -> None:
        for _file in self.plugin_download_dir.iterdir():
            file = self.plugin_download_dir.joinpath(_file)
            if file.is_file():
                try:
                    file.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning("Failed to remove %s. Error: %s", file, e)

    def _move_plugin(self, old_loc: str | Path, new_loc: str | Path) -> bool:
        if not old_loc or not new_loc:
            logger.debug("No file path given to move plugin.")
            return False

        old_loc = Path(old_loc)
        new_loc = Path(new_loc)

        # *nix will replace files while Windows will not. Attempt to remove the file first for consistency of behaviour
        try:
            new_loc.unlink(missing_ok=True)
        except Exception as e:
            logger.error("Failed to remove %s. Error: %s", new_loc, e)
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
            self.create_plugins_dict(plugin_finder.find_plugins(self.plugin_dir))

            for item in self.plugins_dict.values():
                if len(item) > 1:
                    for i, (version, filename) in enumerate(item):
                        # First filename should be latest version to keep
                        if i > 0:
                            self._move_plugin(filename, old_dir.joinpath(filename.name))

    def _check_new_plugin(self, plugin_path: Path) -> bool:
        # Load newly downloaded plugins
        local_download_plugins = plugin_finder.find_plugins(self.plugin_download_dir)

        for plugin_type in local_download_plugins:
            for plugin in plugin_type:
                if plugin.plugin.path == plugin_path:
                    # Plugin loaded, move to plugin dir from download dir
                    return self._move_plugin(plugin_path, self.plugin_dir.joinpath(plugin_path.name))

        return False

    def create_plugins_dict(self, local_plugins: plugin_finder.Plugins) -> dict[str, list[tuple[Version, Path]]]:
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

        return {key: sorted(value, key=lambda x: x[0], reverse=True) for key, value in plugins_dict.items()}

    def _read_plugin_list(self) -> None:
        try:
            plugin_list_file = cast(Path, comictaggerlib.plugin_manifest.data_path.joinpath("plugin_list.yaml"))
            with open(plugin_list_file, encoding="utf-8") as f:
                self.remote_plugin_list = Plugin.load_yaml(f)
        except Exception as e:
            logger.error("Failed to load plugin_list.yaml: %s", e)

    def _download_plugin_manifest(self, url: str) -> PluginReleases | None:
        latest = self._manifest_request(url)

        if latest is not None:
            return PluginReleases.load_yaml(latest)

        return None

    def _download_plugin(self, url: str) -> tuple[bool, Path | None]:
        response = requests.get(url)

        if response.status_code == 200:
            name: str = ""

            # Get the file name from the request or URL
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
