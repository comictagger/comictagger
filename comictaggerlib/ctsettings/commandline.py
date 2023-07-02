"""CLI settings for ComicTagger"""
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
import logging
import os
import platform

import settngs

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion
from comictaggerlib.ctsettings.settngs_namespace import settngs_namespace as ct_ns
from comictaggerlib.ctsettings.types import (
    ComicTaggerPaths,
    metadata_type,
    metadata_type_single,
    parse_metadata_from_string,
)

logger = logging.getLogger(__name__)


def initial_commandline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    # Ensure this stays up to date with register_runtime
    parser.add_argument(
        "--config",
        help="Config directory defaults to ~/.ComicTagger\non Linux/Mac and %%APPDATA%% on Windows\n",
        type=ComicTaggerPaths,
        default=ComicTaggerPaths(),
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Be noisy when doing what it does.")
    return parser


def register_runtime(parser: settngs.Manager) -> None:
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
        type=str,
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
        "--abort",
        dest="abort_on_low_confidence",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="""Abort save operation when online match\nis of low confidence.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--summary",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Show the summary after a save operation.\n\n",
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
    parser.add_setting("--darkmode", action="store_true", help="Windows only. Force a dark pallet", file=False)
    parser.add_setting("-g", "--glob", action="store_true", help="Windows only. Enable globbing", file=False)
    parser.add_setting("--quiet", "-q", action="store_true", help="Don't say much (for print mode).", file=False)

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
        "--overwrite",
        dest="overwrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="""Apply metadata to already tagged archives (relevant for -s or -c).""",
        file=False,
    )
    parser.add_setting("--no-gui", action="store_true", help="Do not open the GUI, force the commandline", file=False)
    parser.add_setting("files", nargs="*", file=False)


def register_commands(parser: settngs.Manager) -> None:
    parser.add_setting("--version", action="store_true", help="Display version.", file=False)

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
        type=metadata_type_single,
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


def register_commandline_settings(parser: settngs.Manager) -> None:
    parser.add_group("commands", register_commands, True)
    parser.add_persistent_group("runtime", register_runtime)


def validate_commandline_settings(config: settngs.Config[ct_ns], parser: settngs.Manager) -> settngs.Config[ct_ns]:
    if config[0].commands_version:
        parser.exit(
            status=1,
            message=f"ComicTagger {ctversion.version}:  Copyright (c) 2012-2022 ComicTagger Team\n"
            "Distributed under Apache License 2.0 (http://www.apache.org/licenses/LICENSE-2.0)\n",
        )

    config[0].runtime_no_gui = any(
        [
            config[0].commands_print,
            config[0].commands_delete,
            config[0].commands_save,
            config[0].commands_copy,
            config[0].commands_rename,
            config[0].commands_export_to_zip,
            config[0].commands_only_set_cv_key,
            config[0].runtime_no_gui,
        ]
    )

    if platform.system() == "Windows" and config[0].runtime_glob:
        # no globbing on windows shell, so do it for them
        import glob

        globs = config[0].runtime_files
        config[0].runtime_files = []
        for item in globs:
            config[0].runtime_files.extend(glob.glob(item))

    if not config[0].commands_only_set_cv_key and config[0].runtime_no_gui and not config[0].runtime_files:
        parser.exit(message="Command requires at least one filename!\n", status=1)

    if config[0].commands_delete and not config[0].runtime_type:
        parser.exit(message="Please specify the type to delete with -t\n", status=1)

    if config[0].commands_save and not config[0].runtime_type:
        parser.exit(message="Please specify the type to save with -t\n", status=1)

    if config[0].commands_copy:
        if not config[0].runtime_type:
            parser.exit(message="Please specify the type to copy to with -t\n", status=1)

    if config[0].runtime_recursive:
        config[0].runtime_files = utils.get_recursive_filelist(config[0].runtime_files)

    # take a crack at finding rar exe if it's not in the path
    if not utils.which("rar"):
        if platform.system() == "Windows":
            # look in some likely places for Windows machines
            if os.path.exists(r"C:\Program Files\WinRAR\Rar.exe"):
                utils.add_to_path(r"C:\Program Files\WinRAR")
            elif os.path.exists(r"C:\Program Files (x86)\WinRAR\Rar.exe"):
                utils.add_to_path(r"C:\Program Files (x86)\WinRAR")
        else:
            if os.path.exists("/opt/homebrew/bin"):
                utils.add_to_path("/opt/homebrew/bin")

    return config
