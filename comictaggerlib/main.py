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
import signal
import sys

import settngs

import comictalker.comictalkerapi as ct_api
from comicapi import utils
from comictaggerlib import cli, ctoptions
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


def update_publishers(options: settngs.Namespace) -> None:
    json_file = options.runtime_config.user_config_dir / "publishers.json"
    if json_file.exists():
        try:
            utils.update_publishers(json.loads(json_file.read_text("utf-8")))
        except Exception:
            logger.exception("Failed to load publishers from %s", json_file)
            # show_exception_box(str(e))


class App:
    """docstring for App"""

    def __init__(self) -> None:
        self.options = settngs.Config({}, {})
        self.initial_arg_parser = ctoptions.initial_cmd_line_parser()
        self.config_load_success = False
        self.talker_plugins = ct_api.get_talkers()

    def run(self) -> None:
        opts = self.initialize()
        self.register_options()
        self.parse_options(opts.config)
        self.initialize_dirs()

        self.main()

    def initialize(self) -> argparse.Namespace:
        opts, _ = self.initial_arg_parser.parse_known_args()
        assert opts is not None
        setup_logging(opts.verbose, opts.config.user_log_dir)
        return opts

    def register_options(self) -> None:
        self.manager = settngs.Manager(
            """A utility for reading and writing metadata to comic archives.\n\n\nIf no options are given, %(prog)s will run in windowed mode.""",
            "For more help visit the wiki at: https://github.com/comictagger/comictagger/wiki",
        )
        ctoptions.register_commandline(self.manager)
        ctoptions.register_settings(self.manager)

    def parse_options(self, config_paths: ctoptions.ComicTaggerPaths) -> None:
        self.options, self.config_load_success = self.manager.parse_config(
            config_paths.user_config_dir / "settings.json"
        )
        self.options = self.manager.get_namespace(self.options)

        self.options = ctoptions.validate_commandline_options(self.options, self.manager)
        self.options = ctoptions.validate_settings(self.options, self.manager)
        self.options = self.options

    def initialize_dirs(self) -> None:
        self.options[0].runtime_config.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.options[0].runtime_config.user_config_dir.mkdir(parents=True, exist_ok=True)
        self.options[0].runtime_config.user_cache_dir.mkdir(parents=True, exist_ok=True)
        self.options[0].runtime_config.user_state_dir.mkdir(parents=True, exist_ok=True)
        self.options[0].runtime_config.user_log_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("user_data_dir: %s", self.options[0].runtime_config.user_data_dir)
        logger.debug("user_config_dir: %s", self.options[0].runtime_config.user_config_dir)
        logger.debug("user_cache_dir: %s", self.options[0].runtime_config.user_cache_dir)
        logger.debug("user_state_dir: %s", self.options[0].runtime_config.user_state_dir)
        logger.debug("user_log_dir: %s", self.options[0].runtime_config.user_log_dir)

    def main(self) -> None:
        assert self.options is not None
        # options already loaded
        error = None

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
        update_publishers(self.options[0])

        if not qt_available and not self.options[0].runtime_no_gui:
            self.options[0].runtime_no_gui = True
            logger.warning("PyQt5 is not available. ComicTagger is limited to command-line mode.")

        # manage the CV API key
        # None comparison is used so that the empty string can unset the value
        if self.options[0].comicvine_cv_api_key is not None or self.options[0].comicvine_cv_url is not None:
            settings_path = self.options[0].runtime_config.user_config_dir / "settings.json"
            if self.config_load_success:
                self.manager.save_file(self.options[0], settings_path)

        if self.options[0].commands_only_set_cv_key:
            if self.config_load_success:
                print("Key set")  # noqa: T201
                return

        try:
            talker_api = self.talker_plugins["comicvine"](  # type: ignore[operator, call-arg]
                version=version,
                cache_folder=self.options[0].runtime_config.user_cache_dir,
                series_match_thresh=self.options[0].comicvine_series_match_search_thresh,
                remove_html_tables=self.options[0].comicvine_remove_html_tables,
                use_series_start_as_volume=self.options[0].comicvine_use_series_start_as_volume,
                wait_on_ratelimit=self.options[0].autotag_wait_and_retry_on_rate_limit,
                api_url=self.options[0].comicvine_cv_url,
                api_key=self.options[0].comicvine_cv_api_key,
            )
        except TalkerError as e:
            logger.exception("Unable to load talker")
            error = (str(e), True)

        if not self.config_load_success:
            error = (
                f"Failed to load settings, check the log located in '{self.options[0].runtime_config.user_log_dir}' for more details",
                True,
            )
        if self.options[0].runtime_no_gui:
            if error and error[1]:
                print(f"A fatal error occurred please check the log for more information: {error[0]}")  # noqa: T201
                raise SystemExit(1)
            try:
                cli.CLI(self.options[0], talker_api).run()
            except Exception:
                logger.exception("CLI mode failed")
        else:
            gui.open_tagger_window(talker_api, self.options, error)
