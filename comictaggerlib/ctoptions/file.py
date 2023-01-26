from __future__ import annotations

import argparse
import uuid
from typing import Any

import settngs

from comictaggerlib.ctoptions.types import AppendAction
from comictaggerlib.defaults import DEFAULT_REPLACEMENTS, Replacement, Replacements


def general(parser: settngs.Manager) -> None:
    # General Settings
    parser.add_setting("--rar-exe-path", default="rar", help="The path to the rar program")
    parser.add_setting(
        "--allow-cbi-in-rar",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Allows ComicBookLover tags in RAR/CBR files",
    )
    parser.add_setting("check_for_new_version", default=False, cmdline=False)
    parser.add_setting("send_usage_stats", default=False, cmdline=False)


def internal(parser: settngs.Manager) -> None:
    # automatic settings
    parser.add_setting("install_id", default=uuid.uuid4().hex, cmdline=False)
    parser.add_setting("save_data_style", default=0, cmdline=False)
    parser.add_setting("load_data_style", default=0, cmdline=False)
    parser.add_setting("last_opened_folder", default="", cmdline=False)
    parser.add_setting("window_width", default=0, cmdline=False)
    parser.add_setting("window_height", default=0, cmdline=False)
    parser.add_setting("window_x", default=0, cmdline=False)
    parser.add_setting("window_y", default=0, cmdline=False)
    parser.add_setting("form_width", default=-1, cmdline=False)
    parser.add_setting("list_width", default=-1, cmdline=False)
    parser.add_setting("sort_column", default=-1, cmdline=False)
    parser.add_setting("sort_direction", default=0, cmdline=False)


def identifier(parser: settngs.Manager) -> None:
    # identifier settings
    parser.add_setting("--series-match-identify-thresh", default=91, type=int, help="")
    parser.add_setting(
        "-b",
        "--border-crop-percent",
        default=10,
        type=int,
        help="ComicTagger will automatically add an additional cover that has any black borders cropped. If the difference in height is less than %(default)s%% the cover will not be cropped.",
    )
    parser.add_setting(
        "--publisher-filter",
        default=["Panini Comics", "Abril", "Planeta DeAgostini", "Editorial Televisa", "Dino Comics"],
        action=AppendAction,
        help="When enabled filters the listed publishers from all search results",
    )


def dialog(parser: settngs.Manager) -> None:
    # Show/ask dialog flags
    parser.add_setting("ask_about_cbi_in_rar", default=True, cmdline=False)
    parser.add_setting("show_disclaimer", default=True, cmdline=False)
    parser.add_setting("dont_notify_about_this_version", default="", cmdline=False)
    parser.add_setting("ask_about_usage_stats", default=True, cmdline=False)


def filename(parser: settngs.Manager) -> None:
    # filename parsing settings
    parser.add_setting(
        "--complicated-parser",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enables the new parser which tries to extract more information from filenames",
    )
    parser.add_setting(
        "--remove-c2c",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Removes c2c from filenames. Requires --complicated-parser",
    )
    parser.add_setting(
        "--remove-fcbd",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Removes FCBD/free comic book day from filenames. Requires --complicated-parser",
    )
    parser.add_setting(
        "--remove-publisher",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Attempts to remove publisher names from filenames, currently limited to Marvel and DC. Requires --complicated-parser",
    )


def talkers(parser: settngs.Manager) -> None:
    # General settings for all information talkers
    parser.add_setting("--source", default="comicvine", help="Use a specified source by source ID")
    parser.add_setting(
        "--series-match-search-thresh",
        default=90,
        type=int,
    )
    parser.add_setting(
        "--clear-metadata",
        default=True,
        help="Clears all existing metadata during import, default is to merges metadata.\nMay be used in conjunction with -o, -f and -m.\n\n",
        dest="clear_metadata_on_import",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_setting(
        "-a",
        "--auto-imprint",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enables the auto imprint functionality.\ne.g. if the publisher is set to 'vertigo' it\nwill be updated to 'DC Comics' and the imprint\nproperty will be set to 'Vertigo'.\n\n",
    )

    parser.add_setting(
        "--sort-series-by-year", default=True, action=argparse.BooleanOptionalAction, help="Sorts series by year"
    )
    parser.add_setting(
        "--exact-series-matches-first",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Puts series that are an exact match at the top of the list",
    )
    parser.add_setting(
        "--always-use-publisher-filter",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enables the publisher filter",
    )
    parser.add_setting(
        "--clear-form-before-populating",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Clears all existing metadata when applying metadata from comic source",
    )


def cbl(parser: settngs.Manager) -> None:
    # CBL Transform settings
    parser.add_setting("--assume-lone-credit-is-primary", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-characters-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-teams-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-locations-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-storyarcs-to-tags", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-notes-to-comments", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--copy-weblink-to-comments", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--apply-transform-on-import", default=False, action=argparse.BooleanOptionalAction)
    parser.add_setting("--apply-transform-on-bulk-operation", default=False, action=argparse.BooleanOptionalAction)


def rename(parser: settngs.Manager) -> None:
    # Rename settings
    parser.add_setting("--template", default="{series} #{issue} ({year})", help="The teplate to use when renaming")
    parser.add_setting(
        "--issue-number-padding",
        default=3,
        type=int,
        help="The minimum number of digits to use for the issue number when renaming",
    )
    parser.add_setting(
        "--use-smart-string-cleanup",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Attempts to intelligently cleanup whitespace when renaming",
    )
    parser.add_setting(
        "--auto-extension",
        dest="set_extension_based_on_archive",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Automatically sets the extension based on the archive type e.g. cbr for rar, cbz for zip",
    )
    parser.add_setting("--dir", default="", help="The directory to move renamed files to")
    parser.add_setting(
        "--move",
        dest="move_to_dir",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enables moving renamed files to a separate directory",
    )
    parser.add_setting(
        "--strict",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Ensures that filenames are valid for all OSs",
    )
    parser.add_setting(
        "replacements",
        default=DEFAULT_REPLACEMENTS,
        cmdline=False,
    )


def autotag(parser: settngs.Manager) -> None:
    # Auto-tag stickies
    parser.add_setting(
        "--save-on-low-confidence",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Automatically save metadata on low-confidence matches",
    )
    parser.add_setting(
        "--dont-use-year-when-identifying",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Ignore the year metadata attribute when identifying a comic",
    )
    parser.add_setting(
        "-1",
        "--assume-issue-one",
        dest="assume_1_if_no_issue_num",
        action=argparse.BooleanOptionalAction,
        help="Assume issue number is 1 if not found (relevant for -s).\n\n",
        default=False,
    )
    parser.add_setting(
        "--ignore-leading-numbers-in-filename",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="When searching ignore leading numbers in the filename",
    )
    parser.add_setting("remove_archive_after_successful_match", default=False, cmdline=False)
    parser.add_setting(
        "-w",
        "--wait-on-rate-limit",
        dest="wait_and_retry_on_rate_limit",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When encountering a Comic Vine rate limit\nerror, wait and retry query.\n\n",
    )


def validate_settings(options: settngs.Config[settngs.Values], parser: settngs.Manager) -> dict[str, dict[str, Any]]:
    options[0].identifier_publisher_filter = [x.strip() for x in options[0].identifier_publisher_filter if x.strip()]
    options[0].rename_replacements = Replacements(
        [Replacement(x[0], x[1], x[2]) for x in options[0].rename_replacements[0]],
        [Replacement(x[0], x[1], x[2]) for x in options[0].rename_replacements[1]],
    )
    return options


def register_settings(parser: settngs.Manager) -> None:
    parser.add_group("general", general, False)
    parser.add_group("internal", internal, False)
    parser.add_group("identifier", identifier, False)
    parser.add_group("dialog", dialog, False)
    parser.add_group("filename", filename, False)
    parser.add_group("talkers", talkers, False)
    parser.add_group("cbl", cbl, False)
    parser.add_group("rename", rename, False)
    parser.add_group("autotag", autotag, False)
