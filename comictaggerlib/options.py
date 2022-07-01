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
import sys

from comicapi import utils
from comicapi.comicarchive import MetaDataStyle
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion

logger = logging.getLogger(__name__)


def define_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="""A utility for reading and writing metadata to comic archives.

    If no options are given, %(prog)s will run in windowed mode.""",
        epilog="For more help visit the wiki at: https://github.com/comictagger/comictagger/wiki",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Display version.",
    )
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="""Print out tag info from file. Specify type\n(via -t) to get only info of that tag type.\n\n""",
    )
    commands.add_argument(
        "-d",
        "--delete",
        action="store_true",
        help="Deletes the tag block of specified type (via -t).\n",
    )
    commands.add_argument(
        "-c",
        "--copy",
        type=metadata_type,
        metavar="{CR,CBL,COMET}",
        help="Copy the specified source tag block to\ndestination style specified via -t\n(potentially lossy operation).\n\n",
    )
    commands.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="Save out tags as specified type (via -t).\nMust specify also at least -o, -f, or -m.\n\n",
    )
    commands.add_argument(
        "-r",
        "--rename",
        action="store_true",
        help="Rename the file based on specified tag style.",
    )
    commands.add_argument(
        "-e",
        "--export-to-zip",
        action="store_true",
        help="Export RAR archive to Zip format.",
    )
    commands.add_argument(
        "--only-set-cv-key",
        action="store_true",
        help="Only set the Comic Vine API key and quit.\n\n",
    )
    parser.add_argument(
        "-1",
        "--assume-issue-one",
        action="store_true",
        help="""Assume issue number is 1 if not found (relevant for -s).\n\n""",
    )
    parser.add_argument(
        "--abort-on-conflict",
        action="store_true",
        help="""Don't export to zip if intended new filename\nexists (otherwise, creates a new unique filename).\n\n""",
    )
    parser.add_argument(
        "-a",
        "--auto-imprint",
        action="store_true",
        help="""Enables the auto imprint functionality.\ne.g. if the publisher is set to 'vertigo' it\nwill be updated to 'DC Comics' and the imprint\nproperty will be set to 'Vertigo'.\n\n""",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        help="""Config directory defaults to ~/.ComicTagger\non Linux/Mac and %%APPDATA%% on Windows\n""",
    )
    parser.add_argument(
        "--cv-api-key",
        help="Use the given Comic Vine API Key (persisted in settings).",
    )
    parser.add_argument(
        "--cv-url",
        help="Use the given Comic Vine URL (persisted in settings).",
    )
    parser.add_argument(
        "--delete-rar",
        action="store_true",
        dest="delete_after_zip_export",
        help="""Delete original RAR archive after successful\nexport to Zip.""",
    )
    parser.add_argument(
        "-f",
        "--parse-filename",
        "--parsefilename",
        action="store_true",
        help="""Parse the filename to get some info,\nspecifically series name, issue number,\nvolume, and publication year.\n\n""",
    )
    parser.add_argument(
        "--id",
        dest="issue_id",
        type=int,
        help="""Use the issue ID when searching online.\nOverrides all other metadata.\n\n""",
    )
    parser.add_argument(
        "-t",
        "--type",
        metavar="{CR,CBL,COMET}",
        default=[],
        type=metadata_type,
        help="""Specify TYPE as either CR, CBL or COMET\n(as either ComicRack, ComicBookLover,\nor CoMet style tags, respectively).\nUse commas for multiple types.\nFor searching the metadata will use the first listed:\neg '-t cbl,cr' with no CBL tags, CR will be used if they exist\n\n""",
    )
    parser.add_argument(
        "-o",
        "--online",
        action="store_true",
        help="""Search online and attempt to identify file\nusing existing metadata and images in archive.\nMay be used in conjunction with -f and -m.\n\n""",
    )
    parser.add_argument(
        "-m",
        "--metadata",
        default=GenericMetadata(),
        type=parse_metadata_from_string,
        help="""Explicitly define, as a list, some tags to be used.  e.g.:\n"series=Plastic Man, publisher=Quality Comics"\n"series=Kickers^, Inc., issue=1, year=1986"\nName-Value pairs are comma separated. Use a\n"^" to escape an "=" or a ",", as shown in\nthe example above.  Some names that can be\nused: series, issue, issue_count, year,\npublisher, title\n\n""",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="""Interactively query the user when there are\nmultiple matches for an online search.\n\n""",
    )
    parser.add_argument(
        "--no-overwrite",
        "--nooverwrite",
        action="store_true",
        help="""Don't modify tag block if it already exists (relevant for -s or -c).""",
    )
    parser.add_argument(
        "--noabort",
        dest="abort_on_low_confidence",
        action="store_false",
        help="""Don't abort save operation when online match\nis of low confidence.\n\n""",
    )
    parser.add_argument(
        "--nosummary",
        dest="show_save_summary",
        action="store_false",
        help="Suppress the default summary after a save operation.\n\n",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="""Overwrite all existing metadata.\nMay be used in conjunction with -o, -f and -m.\n\n""",
    )
    parser.add_argument(
        "--raw", action="store_true", help="""With -p, will print out the raw tag block(s)\nfrom the file.\n"""
    )
    parser.add_argument(
        "-R",
        "--recursive",
        action="store_true",
        help="Recursively include files in sub-folders.",
    )
    parser.add_argument(
        "-S",
        "--script",
        help="""Run an "add-on" python script that uses the\nComicTagger library for custom processing.\nScript arguments can follow the script name.\n\n""",
    )
    parser.add_argument(
        "--split-words",
        action="store_true",
        help="""Splits words before parsing the filename.\ne.g. 'judgedredd' to 'judge dredd'\n\n""",
    )
    parser.add_argument(
        "--terse",
        action="store_true",
        help="Don't say much (for print mode).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Be noisy when doing what it does.",
    )
    parser.add_argument(
        "-w",
        "--wait-on-cv-rate-limit",
        action="store_true",
        help="""When encountering a Comic Vine rate limit\nerror, wait and retry query.\n\n""",
    )
    parser.add_argument(
        "-n", "--dryrun", action="store_true", help="Don't actually modify file (only relevant for -d, -s, or -r).\n\n"
    )
    parser.add_argument(
        "--darkmode",
        action="store_true",
        help="Windows only. Force a dark pallet",
    )
    parser.add_argument(
        "-g",
        "--glob",
        action="store_true",
        help="Windows only. Enable globbing",
    )
    parser.add_argument("files", nargs="*")
    return parser


def metadata_type(types: str) -> list[int]:
    result = []
    types = types.casefold()
    for typ in types.split(","):
        typ = typ.strip()
        if typ not in MetaDataStyle.short_name:
            choices = ", ".join(MetaDataStyle.short_name)
            raise argparse.ArgumentTypeError(f"invalid choice: {typ} (choose from {choices.upper()})")
        result.append(MetaDataStyle.short_name.index(typ))
    return result


def parse_metadata_from_string(mdstr: str) -> GenericMetadata:
    """The metadata string is a comma separated list of name-value pairs
    The names match the attributes of the internal metadata struct (for now)
    The caret is the special "escape character", since it's not common in
    natural language text

    example = "series=Kickers^, Inc. ,issue=1, year=1986"
    """

    escaped_comma = "^,"
    escaped_equals = "^="
    replacement_token = "<_~_>"

    md = GenericMetadata()

    # First, replace escaped commas with with a unique token (to be changed back later)
    mdstr = mdstr.replace(escaped_comma, replacement_token)
    tmp_list = mdstr.split(",")
    md_list = []
    for item in tmp_list:
        item = item.replace(replacement_token, ",")
        md_list.append(item)

    # Now build a nice dict from the list
    md_dict = {}
    for item in md_list:
        # Make sure to fix any escaped equal signs
        i = item.replace(escaped_equals, replacement_token)
        key, value = i.split("=")
        value = value.replace(replacement_token, "=").strip()
        key = key.strip()
        if key.casefold() == "credit":
            cred_attribs = value.split(":")
            role = cred_attribs[0]
            person = cred_attribs[1] if len(cred_attribs) > 1 else ""
            primary = len(cred_attribs) > 2
            md.add_credit(person.strip(), role.strip(), primary)
        else:
            md_dict[key] = value

    # Map the dict to the metadata object
    for key, value in md_dict.items():
        if not hasattr(md, key):
            raise argparse.ArgumentTypeError(f"'{key}' is not a valid tag name")
        else:
            md.is_empty = False
            setattr(md, key, value)
    return md


def launch_script(scriptfile: str, args: list[str]) -> None:
    # we were given a script.  special case for the args:
    # 1. ignore everything before the -S,
    # 2. pass all the ones that follow (including script name) to the script
    if not os.path.exists(scriptfile):
        logger.error("Can't find %s", scriptfile)
    else:
        # I *think* this makes sense:
        # assume the base name of the file is the module name
        # add the folder of the given file to the python path import module
        dirname = os.path.dirname(scriptfile)
        module_name = os.path.splitext(os.path.basename(scriptfile))[0]
        sys.path = [dirname] + sys.path
        try:
            script = __import__(module_name)

            # Determine if the entry point exists before trying to run it
            if "main" in dir(script):
                script.main(args)
            else:
                logger.error("Can't find entry point 'main()' in module '%s'", module_name)
        except Exception:
            logger.exception("Script: %s raised an unhandled exception: ", module_name)

    sys.exit(0)


def parse_cmd_line() -> argparse.Namespace:

    if platform.system() == "Darwin" and getattr(sys, "frozen", False):
        # remove the PSN (process serial number) argument from OS/X
        input_args = [a for a in sys.argv[1:] if "-psn_0_" not in a]
    else:
        input_args = sys.argv[1:]

    script_args = []

    # first check if we're launching a script and split off script args
    for n, _ in enumerate(input_args):
        if input_args[n] == "--":
            break

        if input_args[n] in ["-S", "--script"] and n + 1 < len(input_args):
            # insert a "--" which will cause getopt to ignore the remaining args
            # so they will be passed to the script
            script_args = input_args[n + 2 :]
            input_args = input_args[: n + 2]
            break

    parser = define_args()
    opts = parser.parse_args(input_args)

    if opts.config_path:
        opts.config_path = os.path.abspath(opts.config_path)
    if opts.version:
        parser.exit(
            status=1,
            message=f"ComicTagger {ctversion.version}:  Copyright (c) 2012-2022 ComicTagger Team\n"
            "Distributed under Apache License 2.0 (http://www.apache.org/licenses/LICENSE-2.0)\n",
        )

    opts.no_gui = any(
        [
            opts.print,
            opts.delete,
            opts.save,
            opts.copy,
            opts.rename,
            opts.export_to_zip,
            opts.only_set_cv_key,
        ]
    )

    if opts.script is not None:
        launch_script(opts.script, script_args)

    if platform.system() == "Windows" and opts.glob:
        # no globbing on windows shell, so do it for them
        import glob

        globs = opts.files
        opts.files = []
        for item in globs:
            opts.files.extend(glob.glob(item))

    if opts.only_set_cv_key and opts.cv_api_key is None and opts.cv_url is None:
        parser.exit(message="Key not given!\n", status=1)

    if not opts.only_set_cv_key and opts.no_gui and not opts.files:
        parser.exit(message="Command requires at least one filename!\n", status=1)

    if opts.delete and not opts.type:
        parser.exit(message="Please specify the type to delete with -t\n", status=1)

    if opts.save and not opts.type:
        parser.exit(message="Please specify the type to save with -t\n", status=1)

    if opts.copy:
        if not opts.type:
            parser.exit(message="Please specify the type to copy to with -t\n", status=1)
        if len(opts.copy) > 1:
            parser.exit(message="Please specify only one type to copy to with -c\n", status=1)
        opts.copy = opts.copy[0]

    if opts.recursive:
        opts.file_list = utils.get_recursive_filelist(opts.file_list)

    return opts
