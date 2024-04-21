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
import shlex
import subprocess

import settngs

from comicapi import utils
from comicapi.comicarchive import metadata_styles
from comicapi.genericmetadata import GenericMetadata, OverlayMode
from comictaggerlib import ctversion
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS as ct_ns
from comictaggerlib.ctsettings.types import (
    ComicTaggerPaths,
    metadata_type,
    metadata_type_single,
    parse_metadata_from_string,
)
from comictaggerlib.resulttypes import Action

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
        help="""Explicitly define some tags to be used in YAML syntax.  Use @file.yaml to read from a file.  e.g.:\n"series: Plastic Man, publisher: Quality Comics, year: "\n"series: 'Kickers, Inc.', issue: '1', year: 1986"\nIf you want to erase a tag leave the value blank.\nSome names that can be used: series, issue, issue_count, year,\npublisher, title\n\n""",
        file=False,
    )
    parser.add_setting(
        "-i",
        "--interactive",
        action="store_true",
        help="""Interactively query the user when there are\nmultiple matches for an online search. Disabled json output\n\n""",
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
        "--json", "-j", action="store_true", help="Output json on stdout. Ignored in interactive mode.", file=False
    )
    parser.add_setting(
        "--type-modify",
        metavar=f"{{{','.join(metadata_styles).upper()}}}",
        default=[],
        type=metadata_type,
        help="""Specify the type of tags to write.\nUse commas for multiple types.\nRead types will be used if unspecified\nSee --list-plugins for the available types.\n\n""",
        file=False,
    )
    parser.add_setting(
        "-t",
        "--type-read",
        metavar=f"{{{','.join(metadata_styles).upper()}}}",
        default=[],
        type=metadata_type,
        help="""Specify the type of tags to read.\nUse commas for multiple types.\nSee --list-plugins for the available types.\nThe tag use will be 'overlayed' in order:\ne.g. '-t cbl,cr' with no CBL tags, CR will be used if they exist and CR will overwrite any shared CBL tags.\n\n""",
        file=False,
    )
    parser.add_setting(
        "--read-style-overlay",
        type=OverlayMode,
        help="How to overlay new metadata on the current for enabled read styles (CR, CBL, etc.)",
        file=False,
    )
    parser.add_setting(
        "--source-overlay",
        type=OverlayMode,
        help="How to overlay new metadata from a data source (CV, Metron, GCD, etc.) on to the current",
        file=False,
    )
    parser.add_setting(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="""Apply metadata to already tagged archives, otherwise skips archives with existing metadata (relevant for -s or -c).""",
        file=False,
    )
    parser.add_setting("--no-gui", action="store_true", help="Do not open the GUI, force the commandline", file=False)
    parser.add_setting("files", nargs="*", file=False)


def register_commands(parser: settngs.Manager) -> None:
    parser.add_setting("--version", action="store_true", help="Display version.", file=False)

    parser.add_setting(
        "-p",
        "--print",
        dest="command",
        action="store_const",
        const=Action.print,
        help="""Print out tag info from file. Specify type\n(via --type-read) to get only info of that tag type.\n\n""",
        file=False,
    )
    parser.add_setting(
        "-d",
        "--delete",
        dest="command",
        action="store_const",
        const=Action.delete,
        help="Deletes the tag block of specified type (via --type-modify).\n",
        file=False,
    )
    parser.add_setting(
        "-c",
        "--copy",
        type=metadata_type_single,
        metavar=f"{{{','.join(metadata_styles).upper()}}}",
        help="Copy the specified source tag block to\ndestination style specified via --type-modify\n(potentially lossy operation).\n\n",
        file=False,
    )
    parser.add_setting(
        "-s",
        "--save",
        dest="command",
        action="store_const",
        const=Action.save,
        help="Save out tags as specified type (via --type-modify).\nMust specify also at least -o, -f, or -m.\n\n",
        file=False,
    )
    parser.add_setting(
        "-r",
        "--rename",
        dest="command",
        action="store_const",
        const=Action.rename,
        help="Rename the file based on specified tag style.",
        file=False,
    )
    parser.add_setting(
        "-e",
        "--export-to-zip",
        dest="command",
        action="store_const",
        const=Action.export,
        help="Export RAR archive to Zip format.",
        file=False,
    )
    parser.add_setting(
        "--only-save-config",
        dest="command",
        action="store_const",
        const=Action.save_config,
        help="Only save the configuration (eg, Comic Vine API key) and quit.",
        file=False,
    )
    parser.add_setting(
        "--list-plugins",
        dest="command",
        action="store_const",
        const=Action.list_plugins,
        help="List the available plugins.\n\n",
        file=False,
    )


def register_commandline_settings(parser: settngs.Manager) -> None:
    parser.add_group("Commands", register_commands, True)
    parser.add_persistent_group("Runtime Options", register_runtime)


def validate_commandline_settings(config: settngs.Config[ct_ns], parser: settngs.Manager) -> settngs.Config[ct_ns]:
    if config[0].Commands__version:
        parser.exit(
            status=1,
            message=f"ComicTagger {ctversion.version}:  Copyright (c) 2012-2022 ComicTagger Team\n"
            + "Distributed under Apache License 2.0 (http://www.apache.org/licenses/LICENSE-2.0)\n",
        )

    config[0].Runtime_Options__no_gui = any(
        (config[0].Commands__command, config[0].Runtime_Options__no_gui, config[0].Commands__copy)
    )

    if platform.system() == "Windows" and config[0].Runtime_Options__glob:
        # no globbing on windows shell, so do it for them
        import glob

        globs = config[0].Runtime_Options__files
        config[0].Runtime_Options__files = []
        for item in globs:
            config[0].Runtime_Options__files.extend(glob.glob(item))

    if config[0].Runtime_Options__json and config[0].Runtime_Options__interactive:
        config[0].Runtime_Options__json = False

    if config[0].Runtime_Options__type_read and not config[0].Runtime_Options__type_modify:
        config[0].Runtime_Options__type_modify = config[0].Runtime_Options__type_read

    if (
        config[0].Commands__command not in (Action.save_config, Action.list_plugins)
        and config[0].Runtime_Options__no_gui
        and not config[0].Runtime_Options__files
    ):
        parser.exit(message="Command requires at least one filename!\n", status=1)

    if config[0].Commands__command == Action.delete and not config[0].Runtime_Options__type_modify:
        parser.exit(message="Please specify the type to delete with --type-modify\n", status=1)

    if config[0].Commands__command == Action.save and not config[0].Runtime_Options__type_modify:
        parser.exit(message="Please specify the type to save with --type-modify\n", status=1)

    if config[0].Commands__copy:
        config[0].Commands__command = Action.copy
        if not config[0].Runtime_Options__type_modify:
            parser.exit(message="Please specify the type to copy to with --type-modify\n", status=1)

    if config[0].Runtime_Options__recursive:
        config[0].Runtime_Options__files = utils.get_recursive_filelist(config[0].Runtime_Options__files)

    # take a crack at finding rar exe if it's not in the path
    if not utils.which("rar"):
        if platform.system() == "Windows":
            letters = ["C"]
            letters.extend({f"{d}" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")} - {"C"})
            for letter in letters:
                # look in some likely places for Windows machines
                utils.add_to_path(rf"{letters}:\Program Files\WinRAR")
                utils.add_to_path(rf"{letters}:\Program Files (x86)\WinRAR")
        else:
            if platform.system() == "Darwin":
                result = subprocess.run(("/usr/libexec/path_helper", "-s"), capture_output=True)
                for path in reversed(
                    shlex.split(result.stdout.decode("utf-8", errors="ignore"))[0]
                    .partition("=")[2]
                    .rstrip(";")
                    .split(os.pathsep)
                ):
                    utils.add_to_path(path)
            utils.add_to_path("/opt/homebrew/bin")

    return config
