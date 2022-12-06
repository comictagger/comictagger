"""A python app to (automatically) tag comic archives"""
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

import argparse
import json
import logging.handlers
import platform
import pprint
import signal
import sys
from typing import Any

import comictalker.comictalkerapi as ct_api
from comicapi import utils
from comictaggerlib import cli, settings
from comictaggerlib.ctversion import version
from comictaggerlib.log import setup_logging
from comictalker.talkerbase import TalkerError

if sys.version_info < (3, 10):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata

try:
    from comictaggerlib import gui

    qt_available = gui.qt_available
except Exception:
    qt_available = False

logger = logging.getLogger("comictagger")


logger.setLevel(logging.DEBUG)


def update_publishers(options: dict[str, dict[str, Any]]) -> None:
    json_file = options["runtime"]["config"].user_config_dir / "publishers.json"
    if json_file.exists():
        try:
            utils.update_publishers(json.loads(json_file.read_text("utf-8")))
        except Exception:
            logger.exception("Failed to load publishers from %s", json_file)
            # show_exception_box(str(e))


class App:
    """docstring for App"""

    def __init__(self) -> None:
        self.options: dict[str, dict[str, Any]] = {}
        self.initial_arg_parser = settings.initial_cmd_line_parser()

    def run(self) -> None:
        opts = self.initialize()
        self.register_options()
        self.parse_options(opts.config)
        self.initialize_dirs()

        self.ctmain()

    def initialize(self) -> argparse.Namespace:
        opts, _ = self.initial_arg_parser.parse_known_args()
        assert opts is not None
        setup_logging(opts.verbose, opts.config.user_log_dir / "log")
        return opts

    def register_options(self) -> None:
        self.manager = settings.Manager()
        settings.register_commandline(self.manager)
        settings.register_settings(self.manager)

    def parse_options(self, config_paths: settings.ComicTaggerPaths) -> None:
        options = self.manager.parse_options(config_paths)
        self.options = settings.validate_commandline_options(options, self.manager)
        self.options = settings.validate_settings(options, self.manager)

    def initialize_dirs(self) -> None:
        self.options["runtime"]["config"].user_data_dir.mkdir(parents=True, exist_ok=True)
        self.options["runtime"]["config"].user_config_dir.mkdir(parents=True, exist_ok=True)
        self.options["runtime"]["config"].user_cache_dir.mkdir(parents=True, exist_ok=True)
        self.options["runtime"]["config"].user_state_dir.mkdir(parents=True, exist_ok=True)
        self.options["runtime"]["config"].user_log_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("user_data_dir: %s", self.options["runtime"]["config"].user_data_dir)
        logger.debug("user_config_dir: %s", self.options["runtime"]["config"].user_config_dir)
        logger.debug("user_cache_dir: %s", self.options["runtime"]["config"].user_cache_dir)
        logger.debug("user_state_dir: %s", self.options["runtime"]["config"].user_state_dir)
        logger.debug("user_log_dir: %s", self.options["runtime"]["config"].user_log_dir)

    def ctmain(self) -> None:
        assert self.options is not None
        # options already loaded

        # manage the CV API key
        # None comparison is used so that the empty string can unset the value
        if self.options["comicvine"]["cv_api_key"] is not None or self.options["comicvine"]["cv_url"] is not None:
            self.options["comicvine"]["cv_api_key"] = (
                self.options["comicvine"]["cv_api_key"]
                if self.options["comicvine"]["cv_api_key"] is not None
                else self.options["comicvine"]["cv_api_key"]
            )
            self.options["comicvine"]["cv_url"] = (
                self.options["comicvine"]["cv_url"]
                if self.options["comicvine"]["cv_url"] is not None
                else self.options["comicvine"]["cv_url"]
            )
            self.manager.save_file(self.options, self.options["runtime"]["config"].user_config_dir / "settings.json")
        logger.debug(pprint.pformat(self.options))
        if self.options["commands"]["only_set_cv_key"]:
            print("Key set")  # noqa: T201
            return

        signal.signal(signal.SIGINT, signal.SIG_DFL)

        logger.info(
            "ComicTagger Version: %s running on: %s PyInstaller: %s",
            version,
            platform.system(),
            "Yes" if getattr(sys, "frozen", None) else "No",
        )

        logger.debug("Installed Packages")
        for pkg in sorted(importlib_metadata.distributions(), key=lambda x: x.name):
            logger.debug("%s\t%s", pkg.metadata["Name"], pkg.metadata["Version"])

        utils.load_publishers()
        update_publishers(self.options)

        if not qt_available and not self.options["runtime"]["no_gui"]:
            self.options["runtime"]["no_gui"] = True
            logger.warning("PyQt5 is not available. ComicTagger is limited to command-line mode.")

        gui_exception = None
        try:
            talker_api = ct_api.get_comic_talker("comicvine")(  # type: ignore[call-arg]
                version=version,
                cache_folder=self.options["runtime"]["config"].user_cache_dir,
                series_match_thresh=self.options["comicvine"]["series_match_search_thresh"],
                remove_html_tables=self.options["comicvine"]["remove_html_tables"],
                use_series_start_as_volume=self.options["comicvine"]["use_series_start_as_volume"],
                wait_on_ratelimit=self.options["comicvine"]["wait_and_retry_on_rate_limit"],
                api_url=self.options["comicvine"]["cv_url"],
                api_key=self.options["comicvine"]["cv_api_key"],
            )
        except TalkerError as e:
            logger.exception("Unable to load talker")
            gui_exception = e
            if self.options["runtime"]["no_gui"]:
                raise SystemExit(1)

        if self.options["runtime"]["no_gui"]:
            try:
                cli.cli_mode(self.options, talker_api)
            except Exception:
                logger.exception("CLI mode failed")
        else:

            gui.open_tagger_window(talker_api, self.options, gui_exception)
