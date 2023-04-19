"""A python app to (automatically) tag comic archives"""
#
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

import argparse
import json
import logging.handlers
import signal
import sys

import settngs

import comicapi
import comictalker
from comicapi.utils import save_locale, set_locale
from comictaggerlib import cli, ctsettings
from comictaggerlib.ctversion import version
from comictaggerlib.log import setup_logging

if sys.version_info < (3, 10):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata

logger = logging.getLogger("comictagger")


try:
    loc = save_locale()
    from comictaggerlib import gui

    set_locale(loc)

    qt_available = gui.qt_available
except Exception:
    logger.exception("Qt unavailable")
    qt_available = False


logger.setLevel(logging.DEBUG)


def update_publishers(config: settngs.Config[settngs.Namespace]) -> None:
    json_file = config[0].runtime_config.user_config_dir / "publishers.json"
    if json_file.exists():
        try:
            comicapi.utils.update_publishers(json.loads(json_file.read_text("utf-8")))
        except Exception as e:
            logger.exception("Failed to load publishers from %s: %s", json_file, e)


class App:
    """docstring for App"""

    def __init__(self) -> None:
        self.config: settngs.Config[settngs.Namespace]
        self.initial_arg_parser = ctsettings.initial_commandline_parser()
        self.config_load_success = False

    def run(self) -> None:
        conf = self.initialize()
        self.initialize_dirs(conf.config)
        self.load_plugins(conf)
        self.register_settings()
        self.config = self.parse_settings(conf.config)

        self.main()

    def load_plugins(self, opts: argparse.Namespace) -> None:
        comicapi.comicarchive.load_archive_plugins()
        ctsettings.talkers = comictalker.get_talkers(version, opts.config.user_cache_dir)

    def initialize(self) -> argparse.Namespace:
        conf, _ = self.initial_arg_parser.parse_known_args()
        assert conf is not None
        setup_logging(conf.verbose, conf.config.user_log_dir)
        return conf

    def register_settings(self) -> None:
        self.manager = settngs.Manager(
            """A utility for reading and writing metadata to comic archives.\n\n\nIf no options are given, %(prog)s will run in windowed mode.""",
            "For more help visit the wiki at: https://github.com/comictagger/comictagger/wiki",
        )
        ctsettings.register_commandline_settings(self.manager)
        ctsettings.register_file_settings(self.manager)
        ctsettings.register_plugin_settings(self.manager)

    def parse_settings(self, config_paths: ctsettings.ComicTaggerPaths) -> settngs.Config[settngs.Namespace]:
        cfg, self.config_load_success = self.manager.parse_config(config_paths.user_config_dir / "settings.json")
        config = self.manager.get_namespace(cfg)

        config = ctsettings.validate_commandline_settings(config, self.manager)
        config = ctsettings.validate_file_settings(config)
        config = ctsettings.validate_plugin_settings(config)
        return config

    def initialize_dirs(self, paths: ctsettings.ComicTaggerPaths) -> None:
        paths.user_data_dir.mkdir(parents=True, exist_ok=True)
        paths.user_config_dir.mkdir(parents=True, exist_ok=True)
        paths.user_cache_dir.mkdir(parents=True, exist_ok=True)
        paths.user_state_dir.mkdir(parents=True, exist_ok=True)
        paths.user_log_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("user_data_dir: %s", paths.user_data_dir)
        logger.debug("user_config_dir: %s", paths.user_config_dir)
        logger.debug("user_cache_dir: %s", paths.user_cache_dir)
        logger.debug("user_state_dir: %s", paths.user_state_dir)
        logger.debug("user_log_dir: %s", paths.user_log_dir)

    def main(self) -> None:
        assert self.config is not None
        # config already loaded
        error = None

        talkers = ctsettings.talkers
        del ctsettings.talkers

        if len(talkers) < 1:
            error = error = (
                f"Failed to load any talkers, please re-install and check the log located in '{self.config[0].runtime_config.user_log_dir}' for more details",
                True,
            )

        signal.signal(signal.SIGINT, signal.SIG_DFL)

        logger.debug("Installed Packages")
        for pkg in sorted(importlib_metadata.distributions(), key=lambda x: x.name):
            logger.debug("%s\t%s", pkg.metadata["Name"], pkg.metadata["Version"])

        comicapi.utils.load_publishers()
        update_publishers(self.config)

        if not qt_available and not self.config[0].runtime_no_gui:
            self.config[0].runtime_no_gui = True
            logger.warning("PyQt5 is not available. ComicTagger is limited to command-line mode.")

        # manage the CV API key
        # None comparison is used so that the empty string can unset the value
        if not error and (
            self.config[0].talker_comicvine_comicvine_key is not None
            or self.config[0].talker_comicvine_comicvine_url is not None
        ):
            settings_path = self.config[0].runtime_config.user_config_dir / "settings.json"
            if self.config_load_success:
                self.manager.save_file(self.config[0], settings_path)

        if self.config[0].commands_only_set_cv_key:
            if self.config_load_success:
                print("Key set")  # noqa: T201
                return

        if not self.config_load_success:
            error = (
                f"Failed to load settings, check the log located in '{self.config[0].runtime_config.user_log_dir}' for more details",
                True,
            )

        if self.config[0].runtime_no_gui:
            if error and error[1]:
                print(f"A fatal error occurred please check the log for more information: {error[0]}")  # noqa: T201
                raise SystemExit(1)
            try:
                cli.CLI(self.config[0], talkers).run()
            except Exception:
                logger.exception("CLI mode failed")
        else:
            gui.open_tagger_window(talkers, self.config, error)


def main() -> None:
    App().run()
