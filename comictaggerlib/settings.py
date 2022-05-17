"""Settings class for ComicTagger app"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import configparser
import logging
import os
import pathlib
import platform
import sys
import uuid
from typing import Iterator, TextIO, Union, no_type_check

from comicapi import utils

logger = logging.getLogger(__name__)


class ComicTaggerSettings:
    folder: Union[pathlib.Path, str] = ""

    @staticmethod
    def get_settings_folder() -> pathlib.Path:
        if not ComicTaggerSettings.folder:
            if platform.system() == "Windows":
                ComicTaggerSettings.folder = pathlib.Path(os.environ["APPDATA"]) / "ComicTagger"
            else:
                ComicTaggerSettings.folder = pathlib.Path(os.path.expanduser("~")) / ".ComicTagger"
        return pathlib.Path(ComicTaggerSettings.folder)

    @staticmethod
    def base_dir() -> pathlib.Path:
        if getattr(sys, "frozen", None):
            return pathlib.Path(sys._MEIPASS)

        return pathlib.Path(__file__).parent

    @staticmethod
    def get_graphic(filename: Union[str, pathlib.Path]) -> str:
        return str(ComicTaggerSettings.base_dir() / "graphics" / filename)

    @staticmethod
    def get_ui_file(filename: Union[str, pathlib.Path]) -> pathlib.Path:
        return ComicTaggerSettings.base_dir() / "ui" / filename

    def __init__(self, folder: Union[str, pathlib.Path, None]) -> None:
        # General Settings
        self.rar_exe_path = ""
        self.allow_cbi_in_rar = True
        self.check_for_new_version = False
        self.send_usage_stats = False

        # automatic settings
        self.install_id = uuid.uuid4().hex
        self.last_selected_save_data_style = 0
        self.last_selected_load_data_style = 0
        self.last_opened_folder = ""
        self.last_main_window_width = 0
        self.last_main_window_height = 0
        self.last_main_window_x = 0
        self.last_main_window_y = 0
        self.last_form_side_width = -1
        self.last_list_side_width = -1
        self.last_filelist_sorted_column = -1
        self.last_filelist_sorted_order = 0

        # identifier settings
        self.id_length_delta_thresh = 5
        self.id_publisher_filter = "Panini Comics, Abril, Planeta DeAgostini, Editorial Televisa, Dino Comics"

        # Show/ask dialog flags
        self.ask_about_cbi_in_rar = True
        self.show_disclaimer = True
        self.dont_notify_about_this_version = ""
        self.ask_about_usage_stats = True

        # filename parsing settings
        self.complicated_parser = False
        self.remove_c2c = False
        self.remove_fcbd = False
        self.remove_publisher = False

        # Comic Vine settings
        self.use_series_start_as_volume = False
        self.clear_form_before_populating_from_cv = False
        self.remove_html_tables = False
        self.cv_api_key = ""

        self.sort_series_by_year = True
        self.exact_series_matches_first = True
        self.always_use_publisher_filter = False

        # CBL Tranform settings

        self.assume_lone_credit_is_primary = False
        self.copy_characters_to_tags = False
        self.copy_teams_to_tags = False
        self.copy_locations_to_tags = False
        self.copy_storyarcs_to_tags = False
        self.copy_notes_to_comments = False
        self.copy_weblink_to_comments = False
        self.apply_cbl_transform_on_cv_import = False
        self.apply_cbl_transform_on_bulk_operation = False

        # Rename settings
        self.rename_template = "%series% #%issue% (%year%)"
        self.rename_issue_number_padding = 3
        self.rename_use_smart_string_cleanup = True
        self.rename_extension_based_on_archive = True
        self.rename_dir = ""
        self.rename_move_dir = False
        self.rename_strict = False

        # Auto-tag stickies
        self.save_on_low_confidence = False
        self.dont_use_year_when_identifying = False
        self.assume_1_if_no_issue_num = False
        self.ignore_leading_numbers_in_filename = False
        self.remove_archive_after_successful_match = False
        self.wait_and_retry_on_rate_limit = False

        self.config = configparser.RawConfigParser()
        if folder:
            ComicTaggerSettings.folder = pathlib.Path(folder)
        else:
            ComicTaggerSettings.folder = ComicTaggerSettings.get_settings_folder()

        if not os.path.exists(ComicTaggerSettings.folder):
            os.makedirs(ComicTaggerSettings.folder)

        self.settings_file = os.path.join(ComicTaggerSettings.folder, "settings")

        # if config file doesn't exist, write one out
        if not os.path.exists(self.settings_file):
            self.save()
        else:
            self.load()

        # take a crack at finding rar exe, if not set already
        if self.rar_exe_path == "":
            if platform.system() == "Windows":
                # look in some likely places for Windows machines
                if os.path.exists(r"C:\Program Files\WinRAR\Rar.exe"):
                    self.rar_exe_path = r"C:\Program Files\WinRAR\Rar.exe"
                elif os.path.exists(r"C:\Program Files (x86)\WinRAR\Rar.exe"):
                    self.rar_exe_path = r"C:\Program Files (x86)\WinRAR\Rar.exe"
            else:
                # see if it's in the path of unix user
                rarpath = utils.which("rar")
                if rarpath is not None:
                    self.rar_exe_path = rarpath
            if self.rar_exe_path != "":
                self.save()
        if self.rar_exe_path != "":
            # make sure rar program is now in the path for the rar class
            utils.add_to_path(os.path.dirname(self.rar_exe_path))

    def load(self) -> None:
        def readline_generator(f: TextIO) -> Iterator[str]:
            line = f.readline()
            while line:
                yield line
                line = f.readline()

        with open(self.settings_file, "r", encoding="utf-8") as f:
            self.config.read_file(readline_generator(f))

        self.rar_exe_path = self.config.get("settings", "rar_exe_path")
        if self.config.has_option("settings", "check_for_new_version"):
            self.check_for_new_version = self.config.getboolean("settings", "check_for_new_version")
        if self.config.has_option("settings", "send_usage_stats"):
            self.send_usage_stats = self.config.getboolean("settings", "send_usage_stats")

        if self.config.has_option("auto", "install_id"):
            self.install_id = self.config.get("auto", "install_id")
        if self.config.has_option("auto", "last_selected_load_data_style"):
            self.last_selected_load_data_style = self.config.getint("auto", "last_selected_load_data_style")
        if self.config.has_option("auto", "last_selected_save_data_style"):
            self.last_selected_save_data_style = self.config.getint("auto", "last_selected_save_data_style")
        if self.config.has_option("auto", "last_opened_folder"):
            self.last_opened_folder = self.config.get("auto", "last_opened_folder")
        if self.config.has_option("auto", "last_main_window_width"):
            self.last_main_window_width = self.config.getint("auto", "last_main_window_width")
        if self.config.has_option("auto", "last_main_window_height"):
            self.last_main_window_height = self.config.getint("auto", "last_main_window_height")
        if self.config.has_option("auto", "last_main_window_x"):
            self.last_main_window_x = self.config.getint("auto", "last_main_window_x")
        if self.config.has_option("auto", "last_main_window_y"):
            self.last_main_window_y = self.config.getint("auto", "last_main_window_y")
        if self.config.has_option("auto", "last_form_side_width"):
            self.last_form_side_width = self.config.getint("auto", "last_form_side_width")
        if self.config.has_option("auto", "last_list_side_width"):
            self.last_list_side_width = self.config.getint("auto", "last_list_side_width")
        if self.config.has_option("auto", "last_filelist_sorted_column"):
            self.last_filelist_sorted_column = self.config.getint("auto", "last_filelist_sorted_column")
        if self.config.has_option("auto", "last_filelist_sorted_order"):
            self.last_filelist_sorted_order = self.config.getint("auto", "last_filelist_sorted_order")

        if self.config.has_option("identifier", "id_length_delta_thresh"):
            self.id_length_delta_thresh = self.config.getint("identifier", "id_length_delta_thresh")
        if self.config.has_option("identifier", "id_publisher_filter"):
            self.id_publisher_filter = self.config.get("identifier", "id_publisher_filter")

        if self.config.has_option("filenameparser", "complicated_parser"):
            self.complicated_parser = self.config.getboolean("filenameparser", "complicated_parser")
        if self.config.has_option("filenameparser", "remove_c2c"):
            self.remove_c2c = self.config.getboolean("filenameparser", "remove_c2c")
        if self.config.has_option("filenameparser", "remove_fcbd"):
            self.remove_fcbd = self.config.getboolean("filenameparser", "remove_fcbd")
        if self.config.has_option("filenameparser", "remove_publisher"):
            self.remove_publisher = self.config.getboolean("filenameparser", "remove_publisher")

        if self.config.has_option("dialogflags", "ask_about_cbi_in_rar"):
            self.ask_about_cbi_in_rar = self.config.getboolean("dialogflags", "ask_about_cbi_in_rar")
        if self.config.has_option("dialogflags", "show_disclaimer"):
            self.show_disclaimer = self.config.getboolean("dialogflags", "show_disclaimer")
        if self.config.has_option("dialogflags", "dont_notify_about_this_version"):
            self.dont_notify_about_this_version = self.config.get("dialogflags", "dont_notify_about_this_version")
        if self.config.has_option("dialogflags", "ask_about_usage_stats"):
            self.ask_about_usage_stats = self.config.getboolean("dialogflags", "ask_about_usage_stats")

        if self.config.has_option("comicvine", "use_series_start_as_volume"):
            self.use_series_start_as_volume = self.config.getboolean("comicvine", "use_series_start_as_volume")
        if self.config.has_option("comicvine", "clear_form_before_populating_from_cv"):
            self.clear_form_before_populating_from_cv = self.config.getboolean(
                "comicvine", "clear_form_before_populating_from_cv"
            )
        if self.config.has_option("comicvine", "remove_html_tables"):
            self.remove_html_tables = self.config.getboolean("comicvine", "remove_html_tables")

        if self.config.has_option("comicvine", "sort_series_by_year"):
            self.sort_series_by_year = self.config.getboolean("comicvine", "sort_series_by_year")
        if self.config.has_option("comicvine", "exact_series_matches_first"):
            self.exact_series_matches_first = self.config.getboolean("comicvine", "exact_series_matches_first")
        if self.config.has_option("comicvine", "always_use_publisher_filter"):
            self.always_use_publisher_filter = self.config.getboolean("comicvine", "always_use_publisher_filter")

        if self.config.has_option("comicvine", "cv_api_key"):
            self.cv_api_key = self.config.get("comicvine", "cv_api_key")

        if self.config.has_option("cbl_transform", "assume_lone_credit_is_primary"):
            self.assume_lone_credit_is_primary = self.config.getboolean(
                "cbl_transform", "assume_lone_credit_is_primary"
            )
        if self.config.has_option("cbl_transform", "copy_characters_to_tags"):
            self.copy_characters_to_tags = self.config.getboolean("cbl_transform", "copy_characters_to_tags")
        if self.config.has_option("cbl_transform", "copy_teams_to_tags"):
            self.copy_teams_to_tags = self.config.getboolean("cbl_transform", "copy_teams_to_tags")
        if self.config.has_option("cbl_transform", "copy_locations_to_tags"):
            self.copy_locations_to_tags = self.config.getboolean("cbl_transform", "copy_locations_to_tags")
        if self.config.has_option("cbl_transform", "copy_notes_to_comments"):
            self.copy_notes_to_comments = self.config.getboolean("cbl_transform", "copy_notes_to_comments")
        if self.config.has_option("cbl_transform", "copy_storyarcs_to_tags"):
            self.copy_storyarcs_to_tags = self.config.getboolean("cbl_transform", "copy_storyarcs_to_tags")
        if self.config.has_option("cbl_transform", "copy_weblink_to_comments"):
            self.copy_weblink_to_comments = self.config.getboolean("cbl_transform", "copy_weblink_to_comments")
        if self.config.has_option("cbl_transform", "apply_cbl_transform_on_cv_import"):
            self.apply_cbl_transform_on_cv_import = self.config.getboolean(
                "cbl_transform", "apply_cbl_transform_on_cv_import"
            )
        if self.config.has_option("cbl_transform", "apply_cbl_transform_on_bulk_operation"):
            self.apply_cbl_transform_on_bulk_operation = self.config.getboolean(
                "cbl_transform", "apply_cbl_transform_on_bulk_operation"
            )

        if self.config.has_option("rename", "rename_template"):
            self.rename_template = self.config.get("rename", "rename_template")
        if self.config.has_option("rename", "rename_issue_number_padding"):
            self.rename_issue_number_padding = self.config.getint("rename", "rename_issue_number_padding")
        if self.config.has_option("rename", "rename_use_smart_string_cleanup"):
            self.rename_use_smart_string_cleanup = self.config.getboolean("rename", "rename_use_smart_string_cleanup")
        if self.config.has_option("rename", "rename_extension_based_on_archive"):
            self.rename_extension_based_on_archive = self.config.getboolean(
                "rename", "rename_extension_based_on_archive"
            )
        if self.config.has_option("rename", "rename_dir"):
            self.rename_dir = self.config.get("rename", "rename_dir")
        if self.config.has_option("rename", "rename_move_dir"):
            self.rename_move_dir = self.config.getboolean("rename", "rename_move_dir")
        if self.config.has_option("rename", "rename_strict"):
            self.rename_strict = self.config.getboolean("rename", "rename_strict")

        if self.config.has_option("autotag", "save_on_low_confidence"):
            self.save_on_low_confidence = self.config.getboolean("autotag", "save_on_low_confidence")
        if self.config.has_option("autotag", "dont_use_year_when_identifying"):
            self.dont_use_year_when_identifying = self.config.getboolean("autotag", "dont_use_year_when_identifying")
        if self.config.has_option("autotag", "assume_1_if_no_issue_num"):
            self.assume_1_if_no_issue_num = self.config.getboolean("autotag", "assume_1_if_no_issue_num")
        if self.config.has_option("autotag", "ignore_leading_numbers_in_filename"):
            self.ignore_leading_numbers_in_filename = self.config.getboolean(
                "autotag", "ignore_leading_numbers_in_filename"
            )
        if self.config.has_option("autotag", "remove_archive_after_successful_match"):
            self.remove_archive_after_successful_match = self.config.getboolean(
                "autotag", "remove_archive_after_successful_match"
            )
        if self.config.has_option("autotag", "wait_and_retry_on_rate_limit"):
            self.wait_and_retry_on_rate_limit = self.config.getboolean("autotag", "wait_and_retry_on_rate_limit")

    @no_type_check
    def save(self) -> None:

        if not self.config.has_section("settings"):
            self.config.add_section("settings")

        self.config.set("settings", "check_for_new_version", self.check_for_new_version)
        self.config.set("settings", "rar_exe_path", self.rar_exe_path)
        self.config.set("settings", "send_usage_stats", self.send_usage_stats)

        if not self.config.has_section("auto"):
            self.config.add_section("auto")

        self.config.set("auto", "install_id", self.install_id)
        self.config.set("auto", "last_selected_load_data_style", self.last_selected_load_data_style)
        self.config.set("auto", "last_selected_save_data_style", self.last_selected_save_data_style)
        self.config.set("auto", "last_opened_folder", self.last_opened_folder)
        self.config.set("auto", "last_main_window_width", self.last_main_window_width)
        self.config.set("auto", "last_main_window_height", self.last_main_window_height)
        self.config.set("auto", "last_main_window_x", self.last_main_window_x)
        self.config.set("auto", "last_main_window_y", self.last_main_window_y)
        self.config.set("auto", "last_form_side_width", self.last_form_side_width)
        self.config.set("auto", "last_list_side_width", self.last_list_side_width)
        self.config.set("auto", "last_filelist_sorted_column", self.last_filelist_sorted_column)
        self.config.set("auto", "last_filelist_sorted_order", self.last_filelist_sorted_order)

        if not self.config.has_section("identifier"):
            self.config.add_section("identifier")

        self.config.set("identifier", "id_length_delta_thresh", self.id_length_delta_thresh)
        self.config.set("identifier", "id_publisher_filter", self.id_publisher_filter)

        if not self.config.has_section("dialogflags"):
            self.config.add_section("dialogflags")

        self.config.set("dialogflags", "ask_about_cbi_in_rar", self.ask_about_cbi_in_rar)
        self.config.set("dialogflags", "show_disclaimer", self.show_disclaimer)
        self.config.set("dialogflags", "dont_notify_about_this_version", self.dont_notify_about_this_version)
        self.config.set("dialogflags", "ask_about_usage_stats", self.ask_about_usage_stats)

        if not self.config.has_section("filenameparser"):
            self.config.add_section("filenameparser")

        self.config.set("filenameparser", "complicated_parser", self.complicated_parser)
        self.config.set("filenameparser", "remove_c2c", self.remove_c2c)
        self.config.set("filenameparser", "remove_fcbd", self.remove_fcbd)
        self.config.set("filenameparser", "remove_publisher", self.remove_publisher)

        if not self.config.has_section("comicvine"):
            self.config.add_section("comicvine")

        self.config.set("comicvine", "use_series_start_as_volume", self.use_series_start_as_volume)
        self.config.set("comicvine", "clear_form_before_populating_from_cv", self.clear_form_before_populating_from_cv)
        self.config.set("comicvine", "remove_html_tables", self.remove_html_tables)

        self.config.set("comicvine", "sort_series_by_year", self.sort_series_by_year)
        self.config.set("comicvine", "exact_series_matches_first", self.exact_series_matches_first)
        self.config.set("comicvine", "always_use_publisher_filter", self.always_use_publisher_filter)

        self.config.set("comicvine", "cv_api_key", self.cv_api_key)

        if not self.config.has_section("cbl_transform"):
            self.config.add_section("cbl_transform")

        self.config.set("cbl_transform", "assume_lone_credit_is_primary", self.assume_lone_credit_is_primary)
        self.config.set("cbl_transform", "copy_characters_to_tags", self.copy_characters_to_tags)
        self.config.set("cbl_transform", "copy_teams_to_tags", self.copy_teams_to_tags)
        self.config.set("cbl_transform", "copy_locations_to_tags", self.copy_locations_to_tags)
        self.config.set("cbl_transform", "copy_storyarcs_to_tags", self.copy_storyarcs_to_tags)
        self.config.set("cbl_transform", "copy_notes_to_comments", self.copy_notes_to_comments)
        self.config.set("cbl_transform", "copy_weblink_to_comments", self.copy_weblink_to_comments)
        self.config.set("cbl_transform", "apply_cbl_transform_on_cv_import", self.apply_cbl_transform_on_cv_import)
        self.config.set(
            "cbl_transform",
            "apply_cbl_transform_on_bulk_operation",
            self.apply_cbl_transform_on_bulk_operation,
        )

        if not self.config.has_section("rename"):
            self.config.add_section("rename")

        self.config.set("rename", "rename_template", self.rename_template)
        self.config.set("rename", "rename_issue_number_padding", self.rename_issue_number_padding)
        self.config.set("rename", "rename_use_smart_string_cleanup", self.rename_use_smart_string_cleanup)
        self.config.set("rename", "rename_extension_based_on_archive", self.rename_extension_based_on_archive)
        self.config.set("rename", "rename_dir", self.rename_dir)
        self.config.set("rename", "rename_move_dir", self.rename_move_dir)
        self.config.set("rename", "rename_strict", self.rename_strict)

        if not self.config.has_section("autotag"):
            self.config.add_section("autotag")
        self.config.set("autotag", "save_on_low_confidence", self.save_on_low_confidence)
        self.config.set("autotag", "dont_use_year_when_identifying", self.dont_use_year_when_identifying)
        self.config.set("autotag", "assume_1_if_no_issue_num", self.assume_1_if_no_issue_num)
        self.config.set("autotag", "ignore_leading_numbers_in_filename", self.ignore_leading_numbers_in_filename)
        self.config.set("autotag", "remove_archive_after_successful_match", self.remove_archive_after_successful_match)
        self.config.set("autotag", "wait_and_retry_on_rate_limit", self.wait_and_retry_on_rate_limit)

        with open(self.settings_file, "w", encoding="utf-8") as configfile:
            self.config.write(configfile)
