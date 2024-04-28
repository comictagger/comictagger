from __future__ import annotations

import argparse
import uuid

import settngs

from comicapi import utils
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS as ct_ns
from comictaggerlib.defaults import DEFAULT_REPLACEMENTS, Replacement, Replacements


def general(parser: settngs.Manager) -> None:
    # General Settings
    parser.add_setting("check_for_new_version", default=False, cmdline=False)
    parser.add_setting(
        "--disable-cr",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Disable the ComicRack metadata type",
    )
    parser.add_setting("use_short_metadata_names", default=False, action=argparse.BooleanOptionalAction, cmdline=False)
    parser.add_setting(
        "--prompt-on-save",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Prompts the user to confirm saving tags when using the GUI.",
    )


def internal(parser: settngs.Manager) -> None:
    # automatic settings
    parser.add_setting("install_id", default=uuid.uuid4().hex, cmdline=False)
    parser.add_setting("save_data_style", default=["cbi"], cmdline=False)
    parser.add_setting("load_data_style", default=["cbi"], cmdline=False)
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
        action="extend",
        nargs="+",
        help="When enabled, filters the listed publishers from all search results. Ending a publisher with a '-' removes a publisher from this list",
    )
    parser.add_setting("--series-match-search-thresh", default=90, type=int)
    parser.add_setting(
        "--clear-metadata",
        default=False,
        help="Clears all existing metadata during import, default is to merge metadata.\nMay be used in conjunction with -o, -f and -m.\n\n",
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


def dialog(parser: settngs.Manager) -> None:
    # Show/ask dialog flags
    parser.add_setting("show_disclaimer", default=True, cmdline=False)
    parser.add_setting("dont_notify_about_this_version", default="", cmdline=False)
    parser.add_setting("ask_about_usage_stats", default=True, cmdline=False)


def filename(parser: settngs.Manager) -> None:
    # filename parsing settings
    parser.add_setting(
        "--filename-parser",
        default=utils.Parser.ORIGINAL,
        metavar=f"{{{','.join(utils.Parser)}}}",
        type=utils.Parser,
        choices=[p.value for p in utils.Parser],
        help="Select the filename parser, defaults to original",
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
    parser.add_setting(
        "--split-words",
        action="store_true",
        help="""Splits words before parsing the filename.\ne.g. 'judgedredd' to 'judge dredd'\n\n""",
        file=False,
    )
    parser.add_setting(
        "--protofolius-issue-number-scheme",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Use an issue number scheme devised by protofolius for encoding format informatino as a letter in front of an issue number. Implies --allow-issue-start-with-letter.  Requires --complicated-parser",
    )
    parser.add_setting(
        "--allow-issue-start-with-letter",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Allows an issue number to start with a single letter (e.g. '#X01'). Requires --complicated-parser",
    )


def talker(parser: settngs.Manager) -> None:
    # General settings for talkers
    parser.add_setting(
        "--source",
        default="comicvine",
        help="Use a specified source by source ID (use --list-plugins to list all sources)",
    )
    parser.add_setting(
        "--remove-html-tables",
        default=False,
        action=argparse.BooleanOptionalAction,
        display_name="Remove HTML tables",
        help="Removes html tables instead of converting them to text",
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
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Automatically sets the extension based on the archive type e.g. cbr for rar, cbz for zip",
    )
    parser.add_setting("--dir", default="", help="The directory to move renamed files to")
    parser.add_setting(
        "--move",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enables moving renamed files to a separate directory",
    )
    parser.add_setting(
        "--only-move",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Ignores the filename when moving renamed files to a separate directory",
    )
    parser.add_setting(
        "--strict",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Ensures that filenames are valid for all OSs",
    )
    parser.add_setting("replacements", default=DEFAULT_REPLACEMENTS, cmdline=False)


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


def parse_filter(config: settngs.Config[ct_ns]) -> settngs.Config[ct_ns]:
    new_filter = []
    remove = []
    for x in config[0].Issue_Identifier__publisher_filter:
        x = x.strip()
        if x:  # ignore empty arguments
            if x[-1] == "-":  # this publisher needs to be removed. We remove after all publishers have been enumerated
                remove.append(x.strip("-"))
            else:
                if x not in new_filter:
                    new_filter.append(x)
    for x in remove:  # remove publishers
        if x in new_filter:
            new_filter.remove(x)
    config[0].Issue_Identifier__publisher_filter = new_filter
    return config


def migrate_settings(config: settngs.Config[ct_ns]) -> settngs.Config[ct_ns]:
    original_types = ("cbi", "cr", "comet")
    save_style = config[0].internal__save_data_style
    if not isinstance(save_style, list):
        if isinstance(save_style, int) and save_style in (0, 1, 2):
            config[0].internal__save_data_style = [original_types[save_style]]
        elif isinstance(save_style, str):
            config[0].internal__save_data_style = [save_style]
        else:
            config[0].internal__save_data_style = ["cbi"]

    load_style = config[0].internal__load_data_style
    if not isinstance(load_style, list):
        if isinstance(load_style, int) and load_style in (0, 1, 2):
            config[0].internal__load_data_style = [original_types[load_style]]
        elif isinstance(load_style, str):
            config[0].internal__load_data_style = [load_style]
        else:
            config[0].internal__load_data_style = ["cbi"]

    return config


def validate_file_settings(config: settngs.Config[ct_ns]) -> settngs.Config[ct_ns]:
    config = parse_filter(config)

    config = migrate_settings(config)

    if config[0].Filename_Parsing__protofolius_issue_number_scheme:
        config[0].Filename_Parsing__allow_issue_start_with_letter = True

    config[0].File_Rename__replacements = Replacements(
        [Replacement(x[0], x[1], x[2]) for x in config[0].File_Rename__replacements[0]],
        [Replacement(x[0], x[1], x[2]) for x in config[0].File_Rename__replacements[1]],
    )
    return config


def register_file_settings(parser: settngs.Manager) -> None:
    parser.add_group("internal", internal, False)
    parser.add_group("Issue Identifier", identifier, False)
    parser.add_group("Filename Parsing", filename, False)
    parser.add_group("Sources", talker, False)
    parser.add_group("Comic Book Lover", cbl, False)
    parser.add_group("File Rename", rename, False)
    parser.add_group("Auto-Tag", autotag, False)
    parser.add_group("General", general, False)
    parser.add_group("Dialog Flags", dialog, False)
