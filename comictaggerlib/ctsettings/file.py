from __future__ import annotations

import argparse
import uuid

import settngs

from comicapi import merge, utils
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS as ct_ns
from comictaggerlib.ctsettings.types import parse_metadata_from_string
from comictaggerlib.defaults import DEFAULT_REPLACEMENTS, Replacement, Replacements


def general(parser: settngs.Manager) -> None:
    # General Settings
    parser.add_setting("check_for_new_version", default=False, cmdline=False)
    parser.add_setting(
        "--prompt-on-save",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Prompts the user to confirm saving tags when using the GUI.\ndefault: %(default)s",
    )


def internal(parser: settngs.Manager) -> None:
    # automatic settings
    parser.add_setting("install_id", default=uuid.uuid4().hex, cmdline=False)
    parser.add_setting("write_tags", default=["cbi"], cmdline=False)
    parser.add_setting("read_tags", default=["cbi"], cmdline=False)
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
    parser.add_setting(
        "--series-match-identify-thresh",
        default=91,
        type=int,
        help="The minimum Series name similarity needed to auto-identify an issue default: %(default)s",
    )
    parser.add_setting(
        "--series-match-search-thresh",
        default=90,
        type=int,
        help="The minimum Series name similarity to return from a search result default: %(default)s",
    )
    parser.add_setting(
        "-b",
        "--border-crop-percent",
        default=10,
        type=int,
        help="ComicTagger will automatically add an additional cover that has any black borders cropped.\nIf the difference in height is less than %(default)s%% the cover will not be cropped.\ndefault: %(default)s\n\n",
    )

    parser.add_setting(
        "--sort-series-by-year",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Sorts series by year default: %(default)s",
    )
    parser.add_setting(
        "--exact-series-matches-first",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Puts series that are an exact match at the top of the list default: %(default)s",
    )


def dialog(parser: settngs.Manager) -> None:
    parser.add_setting("show_disclaimer", default=True, cmdline=False)
    parser.add_setting("dont_notify_about_this_version", default="", cmdline=False)
    parser.add_setting("ask_about_usage_stats", default=True, cmdline=False)


def filename(parser: settngs.Manager) -> None:
    parser.add_setting(
        "--filename-parser",
        default=utils.Parser.ORIGINAL,
        metavar=f"{{{','.join(utils.Parser)}}}",
        type=utils.Parser,
        choices=utils.Parser,
        help="Select the filename parser.\ndefault: %(default)s",
    )
    parser.add_setting(
        "--remove-c2c",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Removes c2c from filenames.\nRequires --complicated-parser\ndefault: %(default)s\n\n",
    )
    parser.add_setting(
        "--remove-fcbd",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Removes FCBD/free comic book day from filenames.\nRequires --complicated-parser\ndefault: %(default)s\n\n",
    )
    parser.add_setting(
        "--remove-publisher",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Attempts to remove publisher names from filenames, currently limited to Marvel and DC.\nRequires --complicated-parser\ndefault: %(default)s\n\n",
    )
    parser.add_setting(
        "--split-words",
        action="store_true",
        help="""Splits words before parsing the filename.\ne.g. 'judgedredd' to 'judge dredd'\ndefault: %(default)s\n\n""",
        file=False,
    )
    parser.add_setting(
        "--protofolius-issue-number-scheme",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Use an issue number scheme devised by protofolius for encoding format information as a letter in front of an issue number.\nImplies --allow-issue-start-with-letter.  Requires --complicated-parser\ndefault: %(default)s\n\n",
    )
    parser.add_setting(
        "--allow-issue-start-with-letter",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Allows an issue number to start with a single letter (e.g. '#X01').\nRequires --complicated-parser\ndefault: %(default)s\n\n",
    )


def talker(parser: settngs.Manager) -> None:
    parser.add_setting(
        "--source",
        default="comicvine",
        help="Use a specified source by source ID (use --list-plugins to list all sources).\ndefault: %(default)s",
    )
    parser.add_setting(
        "--remove-html-tables",
        default=False,
        action=argparse.BooleanOptionalAction,
        display_name="Remove HTML tables",
        help="Removes html tables instead of converting them to text.\ndefault: %(default)s",
    )


def md_options(parser: settngs.Manager) -> None:
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

    parser.add_setting("use_short_tag_names", default=False, action=argparse.BooleanOptionalAction, cmdline=False)
    parser.add_setting(
        "--cr",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Enable ComicRack tags. Turn off to only use CIX tags.\ndefault: %(default)s",
    )
    parser.add_setting(
        "--tag-merge",
        metavar=f"{{{','.join(merge.Mode)}}}",
        default=merge.Mode.OVERLAY,
        choices=merge.Mode,
        type=merge.Mode,
        help="How to merge fields when reading enabled tags (CR, CBL, etc.) See -t, --tags-read default: %(default)s",
    )
    parser.add_setting(
        "--metadata-merge",
        metavar=f"{{{','.join(merge.Mode)}}}",
        default=merge.Mode.OVERLAY,
        choices=merge.Mode,
        type=merge.Mode,
        help="How to merge fields when downloading new metadata (CV, Metron, GCD, etc.) default: %(default)s",
    )
    parser.add_setting(
        "--tag-merge-lists",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Merge lists when reading enabled tags (genres, characters, etc.) default: %(default)s",
    )
    parser.add_setting(
        "--metadata-merge-lists",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Merge lists when downloading new metadata (genres, characters, etc.) default: %(default)s",
    )


def rename(parser: settngs.Manager) -> None:
    parser.add_setting(
        "--template",
        default="{series} #{issue} ({year})",
        help="The teplate to use when renaming.\ndefault: %(default)s",
    )
    parser.add_setting(
        "--issue-number-padding",
        default=3,
        type=int,
        help="The minimum number of digits to use for the issue number when renaming.\ndefault: %(default)s",
    )
    parser.add_setting(
        "--use-smart-string-cleanup",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Attempts to intelligently cleanup whitespace when renaming.\ndefault: %(default)s",
    )
    parser.add_setting(
        "--auto-extension",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Automatically sets the extension based on the archive type e.g. cbr for rar, cbz for zip.\ndefault: %(default)s",
    )
    parser.add_setting("--dir", default="", help="The directory to move renamed files to.")
    parser.add_setting(
        "--move",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enables moving renamed files to a separate directory.\ndefault: %(default)s",
    )
    parser.add_setting(
        "--only-move",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Ignores the filename when moving renamed files to a separate directory.\ndefault: %(default)s",
    )
    parser.add_setting(
        "--strict-filenames",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Ensures that filenames are valid for all OSs.\ndefault: %(default)s",
    )
    parser.add_setting("replacements", default=DEFAULT_REPLACEMENTS, cmdline=False)


def autotag(parser: settngs.Manager) -> None:
    parser.add_setting(
        "-o",
        "--online",
        action="store_true",
        help="""Search online and attempt to identify file\nusing existing tags and images in archive.\nMay be used in conjunction with -f and -m.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--save-on-low-confidence",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Automatically save tags on low-confidence matches.\ndefault: %(default)s",
        cmdline=False,
    )
    parser.add_setting(
        "--use-year-when-identifying",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Use the year metadata attribute when auto-tagging a comic.\ndefault: %(default)s",
    )
    parser.add_setting(
        "-1",
        "--assume-issue-one",
        action=argparse.BooleanOptionalAction,
        help="Assume issue number is 1 if not found (relevant for -s).\ndefault: %(default)s\n\n",
        default=False,
    )
    parser.add_setting(
        "--ignore-leading-numbers-in-filename",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="When searching ignore leading numbers in the filename.\ndefault: %(default)s",
    )
    parser.add_setting("remove_archive_after_successful_match", default=False, cmdline=False)
    parser.add_setting(
        "-f",
        "--parse-filename",
        action="store_true",
        help="""Parse the filename to get some info,\nspecifically series name, issue number,\nvolume, and publication year.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--id",
        dest="issue_id",
        type=str,
        help="""Use the issue ID when searching online.\nOverrides all other metadata.\n\n""",
        file=False,
    )
    parser.add_setting(
        "-m",
        "--metadata",
        default=GenericMetadata(),
        type=parse_metadata_from_string,
        help="""Explicitly define some metadata to be used in YAML syntax.  Use @file.yaml to read from a file.  e.g.:\n"series: Plastic Man, publisher: Quality Comics, year: "\n"series: 'Kickers, Inc.', issue: '1', year: 1986"\nIf you want to erase a tag leave the value blank.\nSome names that can be used: series, issue, issue_count, year,\npublisher, title\n\n""",
        file=False,
    )
    parser.add_setting(
        "--clear-tags",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Clears all existing tags during import, default is to merge tags.\nMay be used in conjunction with -o, -f and -m.\ndefault: %(default)s\n\n",
    )
    parser.add_setting(
        "--publisher-filter",
        default=["Panini Comics", "Abril", "Planeta DeAgostini", "Editorial Televisa", "Dino Comics"],
        action="extend",
        nargs="+",
        help="When enabled, filters the listed publishers from all search results.\nEnding a publisher with a '-' removes a publisher from this list\ndefault: %(default)s\n\n",
    )
    parser.add_setting(
        "--use-publisher-filter",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enables the publisher filter.\ndefault: %(default)s",
    )
    parser.add_setting(
        "-a",
        "--auto-imprint",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enables the auto imprint functionality.\ne.g. if the publisher is set to 'vertigo' it\nwill be updated to 'DC Comics' and the imprint\nproperty will be set to 'Vertigo'.\ndefault: %(default)s\n\n",
    )


def parse_filter(config: settngs.Config[ct_ns]) -> settngs.Config[ct_ns]:
    new_filter = []
    remove = []
    for x in config[0].Auto_Tag__publisher_filter:
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
    config[0].Auto_Tag__publisher_filter = new_filter
    return config


def migrate_settings(config: settngs.Config[ct_ns]) -> settngs.Config[ct_ns]:
    original_types = ("cbi", "cr", "comet")
    write_Tags = config[0].internal__write_tags
    if not isinstance(write_Tags, list):
        if isinstance(write_Tags, int) and write_Tags in (0, 1, 2):
            config[0].internal__write_tags = [original_types[write_Tags]]
        elif isinstance(write_Tags, str):
            config[0].internal__write_tags = [write_Tags]
        else:
            config[0].internal__write_tags = ["cbi"]

    read_tags = config[0].internal__read_tags
    if not isinstance(read_tags, list):
        if isinstance(read_tags, int) and read_tags in (0, 1, 2):
            config[0].internal__read_tags = [original_types[read_tags]]
        elif isinstance(read_tags, str):
            config[0].internal__read_tags = [read_tags]
        else:
            config[0].internal__read_tags = ["cbi"]

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
    parser.add_group("Metadata Options", md_options, False)
    parser.add_group("File Rename", rename, False)
    parser.add_group("Auto-Tag", autotag, False)
    parser.add_group("General", general, False)
    parser.add_group("Dialog Flags", dialog, False)
