"""CLI options class for ComicTagger app"""
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
import logging
import os
import platform
from typing import Any

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion
from comictaggerlib.settings.manager import Manager
from comictaggerlib.settings.types import ComicTaggerPaths, metadata_type, parse_metadata_from_string

logger = logging.getLogger(__name__)


def initial_cmd_line_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    # Ensure this stays up to date with register_options
    parser.add_argument(
        "--config",
        help="Config directory defaults to ~/.ComicTagger\non Linux/Mac and %%APPDATA%% on Windows\n",
        type=ComicTaggerPaths,
        default=ComicTaggerPaths(),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Be noisy when doing what it does.",
    )
    return parser


def register_options(parser: Manager) -> None:
    parser.add_setting(
        "--config",
        help="Config directory defaults to ~/.Config/ComicTagger\non Linux, ~/Library/Application Support/ComicTagger on Mac and %%APPDATA%%\\ComicTagger on Windows\n",
        type=ComicTaggerPaths,
        default=ComicTaggerPaths(),
        file=False,
    )
    parser.add_setting(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Be noisy when doing what it does.",
        file=False,
    )
    parser.add_setting(
        "--abort-on-conflict",
        action="store_true",
        help="""Don't export to zip if intended new filename\nexists (otherwise, creates a new unique filename).\n\n""",
        file=False,
    )
    parser.add_setting(
        "--delete-original",
        action="store_true",
        dest="delete_after_zip_export",
        help="""Delete original archive after successful\nexport to Zip. (only relevant for -e)""",
        file=False,
    )
    parser.add_setting(
        "-f",
        "--parse-filename",
        "--parsefilename",
        action="store_true",
        help="""Parse the filename to get some info,\nspecifically series name, issue number,\nvolume, and publication year.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--id",
        dest="issue_id",
        type=int,
        help="""Use the issue ID when searching online.\nOverrides all other metadata.\n\n""",
        file=False,
    )
    parser.add_setting(
        "-o",
        "--online",
        action="store_true",
        help="""Search online and attempt to identify file\nusing existing metadata and images in archive.\nMay be used in conjunction with -f and -m.\n\n""",
        file=False,
    )
    parser.add_setting(
        "-m",
        "--metadata",
        default=GenericMetadata(),
        type=parse_metadata_from_string,
        help="""Explicitly define, as a list, some tags to be used.  e.g.:\n"series=Plastic Man, publisher=Quality Comics"\n"series=Kickers^, Inc., issue=1, year=1986"\nName-Value pairs are comma separated. Use a\n"^" to escape an "=" or a ",", as shown in\nthe example above.  Some names that can be\nused: series, issue, issue_count, year,\npublisher, title\n\n""",
        file=False,
    )
    parser.add_setting(
        "-i",
        "--interactive",
        action="store_true",
        help="""Interactively query the user when there are\nmultiple matches for an online search.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--noabort",
        dest="abort_on_low_confidence",
        action="store_false",
        help="""Don't abort save operation when online match\nis of low confidence.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--nosummary",
        dest="show_save_summary",
        action="store_false",
        help="Suppress the default summary after a save operation.\n\n",
        file=False,
    )
    parser.add_setting(
        "--raw",
        action="store_true",
        help="""With -p, will print out the raw tag block(s)\nfrom the file.\n""",
        file=False,
    )
    parser.add_setting(
        "-R",
        "--recursive",
        action="store_true",
        help="Recursively include files in sub-folders.",
        file=False,
    )
    parser.add_setting(
        "-S",
        "--script",
        help="""Run an "add-on" python script that uses the\nComicTagger library for custom processing.\nScript arguments can follow the script name.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--split-words",
        action="store_true",
        help="""Splits words before parsing the filename.\ne.g. 'judgedredd' to 'judge dredd'\n\n""",
        file=False,
    )
    parser.add_setting(
        "-n",
        "--dryrun",
        action="store_true",
        help="Don't actually modify file (only relevant for -d, -s, or -r).\n\n",
        file=False,
    )
    parser.add_setting(
        "--darkmode",
        action="store_true",
        help="Windows only. Force a dark pallet",
        file=False,
    )
    parser.add_setting(
        "-g",
        "--glob",
        action="store_true",
        help="Windows only. Enable globbing",
        file=False,
    )
    parser.add_setting(
        "--terse",
        action="store_true",
        help="Don't say much (for print mode).",
        file=False,
    )

    parser.add_setting(
        "-t",
        "--type",
        metavar="{CR,CBL,COMET}",
        default=[],
        type=metadata_type,
        help="""Specify TYPE as either CR, CBL or COMET\n(as either ComicRack, ComicBookLover,\nor CoMet style tags, respectively).\nUse commas for multiple types.\nFor searching the metadata will use the first listed:\neg '-t cbl,cr' with no CBL tags, CR will be used if they exist\n\n""",
        file=False,
    )
    parser.add_setting(
        # "--no-overwrite",
        # "--nooverwrite",
        "--temporary",
        dest="no_overwrite",
        action="store_true",
        help="""Don't modify tag block if it already exists (relevant for -s or -c).""",
        file=False,
    )
    parser.add_setting("files", nargs="*", file=False)


def register_commands(parser: Manager) -> None:
    parser.add_setting(
        "--version",
        action="store_true",
        help="Display version.",
        file=False,
    )

    parser.add_setting(
        "-p",
        "--print",
        action="store_true",
        help="""Print out tag info from file. Specify type\n(via -t) to get only info of that tag type.\n\n""",
        file=False,
    )
    parser.add_setting(
        "-d",
        "--delete",
        action="store_true",
        help="Deletes the tag block of specified type (via -t).\n",
        file=False,
    )
    parser.add_setting(
        "-c",
        "--copy",
        type=metadata_type,
        metavar="{CR,CBL,COMET}",
        help="Copy the specified source tag block to\ndestination style specified via -t\n(potentially lossy operation).\n\n",
        file=False,
    )
    parser.add_setting(
        "-s",
        "--save",
        action="store_true",
        help="Save out tags as specified type (via -t).\nMust specify also at least -o, -f, or -m.\n\n",
        file=False,
    )
    parser.add_setting(
        "-r",
        "--rename",
        action="store_true",
        help="Rename the file based on specified tag style.",
        file=False,
    )
    parser.add_setting(
        "-e",
        "--export-to-zip",
        action="store_true",
        help="Export RAR archive to Zip format.",
        file=False,
    )
    parser.add_setting(
        "--only-set-cv-key",
        action="store_true",
        help="Only set the Comic Vine API key and quit.\n\n",
        file=False,
    )


def register_commandline(parser: Manager) -> None:
    parser.add_group("commands", register_commands, True)
    parser.add_group("runtime", register_options)


def validate_commandline_options(options: dict[str, dict[str, Any]], parser: Manager) -> dict[str, dict[str, Any]]:

    if options["commands"]["version"]:
        parser.exit(
            status=1,
            message=f"ComicTagger {ctversion.version}:  Copyright (c) 2012-2022 ComicTagger Team\n"
            "Distributed under Apache License 2.0 (http://www.apache.org/licenses/LICENSE-2.0)\n",
        )

    options["runtime"]["no_gui"] = any(
        [
            options["commands"]["print"],
            options["commands"]["delete"],
            options["commands"]["save"],
            options["commands"]["copy"],
            options["commands"]["rename"],
            options["commands"]["export_to_zip"],
            options["commands"]["only_set_cv_key"],
        ]
    )

    if platform.system() == "Windows" and options["runtime"]["glob"]:
        # no globbing on windows shell, so do it for them
        import glob

        globs = options["runtime"]["files"]
        options["runtime"]["files"] = []
        for item in globs:
            options["runtime"]["files"].extend(glob.glob(item))

    if (
        options["commands"]["only_set_cv_key"]
        and options["comicvine"]["cv_api_key"] is None
        and options["comicvine"]["cv_url"] is None
    ):
        parser.exit(message="Key not given!\n", status=1)

    if not options["commands"]["only_set_cv_key"] and options["runtime"]["no_gui"] and not options["runtime"]["files"]:
        parser.exit(message="Command requires at least one filename!\n", status=1)

    if options["commands"]["delete"] and not options["runtime"]["type"]:
        parser.exit(message="Please specify the type to delete with -t\n", status=1)

    if options["commands"]["save"] and not options["runtime"]["type"]:
        parser.exit(message="Please specify the type to save with -t\n", status=1)

    if options["commands"]["copy"]:
        if not options["runtime"]["type"]:
            parser.exit(message="Please specify the type to copy to with -t\n", status=1)
        if len(options["commands"]["copy"]) > 1:
            parser.exit(message="Please specify only one type to copy to with -c\n", status=1)
        options["commands"]["copy"] = options["commands"]["copy"][0]

    if options["runtime"]["recursive"]:
        options["runtime"]["file_list"] = utils.get_recursive_filelist(options["runtime"]["files"])
    else:
        options["runtime"]["file_list"] = options["runtime"]["files"]

    # take a crack at finding rar exe, if not set already
    if options["general"]["rar_exe_path"].strip() in ("", "rar"):
        if platform.system() == "Windows":
            # look in some likely places for Windows machines
            if os.path.exists(r"C:\Program Files\WinRAR\Rar.exe"):
                options["general"]["rar_exe_path"] = r"C:\Program Files\WinRAR\Rar.exe"
            elif os.path.exists(r"C:\Program Files (x86)\WinRAR\Rar.exe"):
                options["general"]["rar_exe_path"] = r"C:\Program Files (x86)\WinRAR\Rar.exe"
        else:
            if os.path.exists("/opt/homebrew/bin"):
                utils.add_to_path("/opt/homebrew/bin")
            # see if it's in the path of unix user
            rarpath = utils.which("rar")
            if rarpath is not None:
                options["general"]["rar_exe_path"] = "rar"

    return options
