#!/usr/bin/python
"""ComicTagger CLI functions"""
#
# Copyright 2013 Anthony Beville
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
import logging
import os
import pathlib
import sys
from pprint import pprint

from comicapi import utils
from comicapi.comicarchive import ComicArchive, MetaDataStyle
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.filerenamer import FileRenamer, get_rename_dir
from comictaggerlib.graphics import graphics_path
from comictaggerlib.issueidentifier import IssueIdentifier
from comictaggerlib.resulttypes import MultipleMatch, OnlineMatchResults
from comictaggerlib.settings import ComicTaggerSettings
from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


def actual_issue_data_fetch(
    issue_id: int, settings: ComicTaggerSettings, opts: argparse.Namespace, talker_api: ComicTalker
) -> GenericMetadata:
    # now get the particular issue data
    try:
        ct_md = talker_api.fetch_comic_data(issue_id)
    except TalkerError as e:
        logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
        return GenericMetadata()

    if settings.apply_cbl_transform_on_ct_import:
        ct_md = CBLTransformer(ct_md, settings).apply()

    return ct_md


def actual_metadata_save(ca: ComicArchive, opts: argparse.Namespace, md: GenericMetadata) -> bool:
    if not opts.dryrun:
        for metadata_style in opts.type:
            # write out the new data
            if not ca.write_metadata(md, metadata_style):
                logger.error("The tag save seemed to fail for style: %s!", MetaDataStyle.name[metadata_style])
                return False

        print("Save complete.")
        logger.info("Save complete.")
    else:
        if opts.terse:
            logger.info("dry-run option was set, so nothing was written")
            print("dry-run option was set, so nothing was written")
        else:
            logger.info("dry-run option was set, so nothing was written, but here is the final set of tags:")
            print("dry-run option was set, so nothing was written, but here is the final set of tags:")
            print(f"{md}")
    return True


def display_match_set_for_choice(
    label: str,
    match_set: MultipleMatch,
    opts: argparse.Namespace,
    settings: ComicTaggerSettings,
    talker_api: ComicTalker,
) -> None:
    print(f"{match_set.ca.path} -- {label}:")

    # sort match list by year
    match_set.matches.sort(key=lambda k: k["year"] or 0)

    for (counter, m) in enumerate(match_set.matches):
        counter += 1
        print(
            "    {}. {} #{} [{}] ({}/{}) - {}".format(
                counter,
                m["series"],
                m["issue_number"],
                m["publisher"],
                m["month"],
                m["year"],
                m["issue_title"],
            )
        )
    if opts.interactive:
        while True:
            i = input("Choose a match #, or 's' to skip: ")
            if (i.isdigit() and int(i) in range(1, len(match_set.matches) + 1)) or i == "s":
                break
        if i != "s":
            # save the data!
            # we know at this point, that the file is all good to go
            ca = match_set.ca
            md = create_local_metadata(opts, ca, settings)
            ct_md = actual_issue_data_fetch(match_set.matches[int(i) - 1]["issue_id"], settings, opts, talker_api)
            if opts.overwrite:
                md = ct_md
            else:
                md.overlay(ct_md)

            if opts.auto_imprint:
                md.fix_publisher()

            actual_metadata_save(ca, opts, md)


def post_process_matches(
    match_results: OnlineMatchResults, opts: argparse.Namespace, settings: ComicTaggerSettings, talker_api: ComicTalker
) -> None:
    # now go through the match results
    if opts.show_save_summary:
        if len(match_results.good_matches) > 0:
            print("\nSuccessful matches:\n------------------")
            for f in match_results.good_matches:
                print(f)

        if len(match_results.no_matches) > 0:
            print("\nNo matches:\n------------------")
            for f in match_results.no_matches:
                print(f)

        if len(match_results.write_failures) > 0:
            print("\nFile Write Failures:\n------------------")
            for f in match_results.write_failures:
                print(f)

        if len(match_results.fetch_data_failures) > 0:
            print("\nNetwork Data Fetch Failures:\n------------------")
            for f in match_results.fetch_data_failures:
                print(f)

    if not opts.show_save_summary and not opts.interactive:
        # just quit if we're not interactive or showing the summary
        return

    if len(match_results.multiple_matches) > 0:
        print("\nArchives with multiple high-confidence matches:\n------------------")
        for match_set in match_results.multiple_matches:
            display_match_set_for_choice("Multiple high-confidence matches", match_set, opts, settings, talker_api)

    if len(match_results.low_confidence_matches) > 0:
        print("\nArchives with low-confidence matches:\n------------------")
        for match_set in match_results.low_confidence_matches:
            if len(match_set.matches) == 1:
                label = "Single low-confidence match"
            else:
                label = "Multiple low-confidence matches"

            display_match_set_for_choice(label, match_set, opts, settings, talker_api)


def cli_mode(opts: argparse.Namespace, settings: ComicTaggerSettings, talker_api: ComicTalker) -> None:
    if len(opts.file_list) < 1:
        logger.error("You must specify at least one filename.  Use the -h option for more info")
        return

    match_results = OnlineMatchResults()

    for f in opts.file_list:
        process_file_cli(f, opts, settings, talker_api, match_results)
        sys.stdout.flush()

    post_process_matches(match_results, opts, settings, talker_api)


def create_local_metadata(opts: argparse.Namespace, ca: ComicArchive, settings: ComicTaggerSettings) -> GenericMetadata:
    md = GenericMetadata()
    md.set_default_page_list(ca.get_number_of_pages())

    # now, overlay the parsed filename info
    if opts.parse_filename:
        f_md = ca.metadata_from_filename(
            settings.complicated_parser,
            settings.remove_c2c,
            settings.remove_fcbd,
            settings.remove_publisher,
            opts.split_words,
        )

        md.overlay(f_md)

    for metadata_style in opts.type:
        if ca.has_metadata(metadata_style):
            try:
                t_md = ca.read_metadata(metadata_style)
                md.overlay(t_md)
                break
            except Exception as e:
                logger.error("Failed to load metadata for %s: %s", ca.path, e)

    # finally, use explicit stuff
    md.overlay(opts.metadata)

    return md


def process_file_cli(
    filename: str,
    opts: argparse.Namespace,
    settings: ComicTaggerSettings,
    talker_api: ComicTalker,
    match_results: OnlineMatchResults,
) -> None:
    batch_mode = len(opts.file_list) > 1

    ca = ComicArchive(filename, settings.rar_exe_path, str(graphics_path / "nocover.png"))

    if not os.path.lexists(filename):
        logger.error("Cannot find %s", filename)
        return

    if not ca.seems_to_be_a_comic_archive():
        logger.error("Sorry, but %s is not a comic archive!", filename)
        return

    if not ca.is_writable() and (opts.delete or opts.copy or opts.save or opts.rename):
        logger.error("This archive is not writable")
        return

    has = [False, False, False]
    if ca.has_cix():
        has[MetaDataStyle.CIX] = True
    if ca.has_cbi():
        has[MetaDataStyle.CBI] = True
    if ca.has_comet():
        has[MetaDataStyle.COMET] = True

    if opts.print:

        if not opts.type:
            page_count = ca.get_number_of_pages()

            brief = ""

            if batch_mode:
                brief = f"{ca.path}: "

            if ca.is_sevenzip():
                brief += "7Z archive     "
            elif ca.is_zip():
                brief += "ZIP archive    "
            elif ca.is_rar():
                brief += "RAR archive    "
            elif ca.is_folder():
                brief += "Folder archive "

            brief += f"({page_count: >3} pages)"
            brief += "  tags:[ "

            if not (has[MetaDataStyle.CBI] or has[MetaDataStyle.CIX] or has[MetaDataStyle.COMET]):
                brief += "none "
            else:
                if has[MetaDataStyle.CBI]:
                    brief += "CBL "
                if has[MetaDataStyle.CIX]:
                    brief += "CR "
                if has[MetaDataStyle.COMET]:
                    brief += "CoMet "
            brief += "]"

            print(brief)

        if opts.terse:
            return

        print()

        if not opts.type or MetaDataStyle.CIX in opts.type:
            if has[MetaDataStyle.CIX]:
                print("--------- ComicRack tags ---------")
                try:
                    if opts.raw:
                        print(ca.read_raw_cix())
                    else:
                        print(ca.read_cix())
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        if not opts.type or MetaDataStyle.CBI in opts.type:
            if has[MetaDataStyle.CBI]:
                print("------- ComicBookLover tags -------")
                try:
                    if opts.raw:
                        pprint(json.loads(ca.read_raw_cbi()))
                    else:
                        print(ca.read_cbi())
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        if not opts.type or MetaDataStyle.COMET in opts.type:
            if has[MetaDataStyle.COMET]:
                print("----------- CoMet tags -----------")
                try:
                    if opts.raw:
                        print(ca.read_raw_comet())
                    else:
                        print(ca.read_comet())
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

    elif opts.delete:
        for metadata_style in opts.type:
            style_name = MetaDataStyle.name[metadata_style]
            if has[metadata_style]:
                if not opts.dryrun:
                    if not ca.remove_metadata(metadata_style):
                        print(f"{filename}: Tag removal seemed to fail!")
                    else:
                        print(f"{filename}: Removed {style_name} tags.")
                else:
                    print(f"{filename}: dry-run. {style_name} tags not removed")
            else:
                print(f"{filename}: This archive doesn't have {style_name} tags to remove.")

    elif opts.copy is not None:
        for metadata_style in opts.type:
            dst_style_name = MetaDataStyle.name[metadata_style]
            if opts.no_overwrite and has[metadata_style]:
                print(f"{filename}: Already has {dst_style_name} tags. Not overwriting.")
                return
            if opts.copy == metadata_style:
                print(f"{filename}: Destination and source are same: {dst_style_name}. Nothing to do.")
                return

            src_style_name = MetaDataStyle.name[opts.copy]
            if has[opts.copy]:
                if not opts.dryrun:
                    try:
                        md = ca.read_metadata(opts.copy)
                    except Exception as e:
                        md = GenericMetadata()
                        logger.error("Failed to load metadata for %s: %s", ca.path, e)

                    if settings.apply_cbl_transform_on_bulk_operation and metadata_style == MetaDataStyle.CBI:
                        md = CBLTransformer(md, settings).apply()

                    if not ca.write_metadata(md, metadata_style):
                        print(f"{filename}: Tag copy seemed to fail!")
                    else:
                        print(f"{filename}: Copied {src_style_name} tags to {dst_style_name}.")
                else:
                    print(f"{filename}: dry-run.  {src_style_name} tags not copied")
            else:
                print(f"{filename}: This archive doesn't have {src_style_name} tags to copy.")

    elif opts.save:

        if opts.no_overwrite:
            for metadata_style in opts.type:
                if has[metadata_style]:
                    print(f"{filename}: Already has {MetaDataStyle.name[metadata_style]} tags. Not overwriting.")
                    return

        if batch_mode:
            print(f"Processing {ca.path}...")

        md = create_local_metadata(opts, ca, settings)
        if md.issue is None or md.issue == "":
            if opts.assume_issue_one:
                md.issue = "1"

        # now, search online
        if opts.online:
            if opts.issue_id is not None:
                # we were given the actual issue ID to search with
                try:
                    ct_md = talker_api.fetch_comic_data(opts.issue_id)
                except TalkerError as e:
                    logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
                    match_results.fetch_data_failures.append(str(ca.path.absolute()))
                    return

                if ct_md is None:
                    logger.error("No match for ID %s was found.", opts.issue_id)
                    match_results.no_matches.append(str(ca.path.absolute()))
                    return

                if settings.apply_cbl_transform_on_ct_import:
                    ct_md = CBLTransformer(ct_md, settings).apply()
            else:
                if md is None or md.is_empty:
                    logger.error("No metadata given to search online with!")
                    match_results.no_matches.append(str(ca.path.absolute()))
                    return

                ii = IssueIdentifier(ca, settings, talker_api)

                def myoutput(text: str) -> None:
                    if opts.verbose:
                        IssueIdentifier.default_write_output(text)

                # use our overlaid MD struct to search
                ii.set_additional_metadata(md)
                ii.only_use_additional_meta_data = True
                ii.set_output_function(myoutput)
                ii.cover_page_index = md.get_cover_page_index_list()[0]
                matches = ii.search()

                result = ii.search_result

                found_match = False
                choices = False
                low_confidence = False

                if result == ii.result_no_matches:
                    pass
                elif result == ii.result_found_match_but_bad_cover_score:
                    low_confidence = True
                    found_match = True
                elif result == ii.result_found_match_but_not_first_page:
                    found_match = True
                elif result == ii.result_multiple_matches_with_bad_image_scores:
                    low_confidence = True
                    choices = True
                elif result == ii.result_one_good_match:
                    found_match = True
                elif result == ii.result_multiple_good_matches:
                    choices = True

                if choices:
                    if low_confidence:
                        logger.error("Online search: Multiple low confidence matches. Save aborted")
                        match_results.low_confidence_matches.append(MultipleMatch(ca, matches))
                        return

                    logger.error("Online search: Multiple good matches. Save aborted")
                    match_results.multiple_matches.append(MultipleMatch(ca, matches))
                    return
                if low_confidence and opts.abort_on_low_confidence:
                    logger.error("Online search: Low confidence match. Save aborted")
                    match_results.low_confidence_matches.append(MultipleMatch(ca, matches))
                    return
                if not found_match:
                    logger.error("Online search: No match found. Save aborted")
                    match_results.no_matches.append(str(ca.path.absolute()))
                    return

                # we got here, so we have a single match

                # now get the particular issue data
                ct_md = actual_issue_data_fetch(matches[0]["issue_id"], settings, opts, talker_api)
                if ct_md.is_empty:
                    match_results.fetch_data_failures.append(str(ca.path.absolute()))
                    return

            if opts.overwrite:
                md = ct_md
            else:
                md.overlay(ct_md)

            if opts.auto_imprint:
                md.fix_publisher()

        # ok, done building our metadata. time to save
        if not actual_metadata_save(ca, opts, md):
            match_results.write_failures.append(str(ca.path.absolute()))
        else:
            match_results.good_matches.append(str(ca.path.absolute()))

    elif opts.rename:
        original_path = ca.path
        msg_hdr = ""
        if batch_mode:
            msg_hdr = f"{ca.path}: "

        md = create_local_metadata(opts, ca, settings)

        if md.series is None:
            logger.error(msg_hdr + "Can't rename without series name")
            return

        new_ext = ""  # default
        if settings.rename_extension_based_on_archive:
            if ca.is_sevenzip():
                new_ext = ".cb7"
            elif ca.is_zip():
                new_ext = ".cbz"
            elif ca.is_rar():
                new_ext = ".cbr"

        renamer = FileRenamer(md, platform="universal" if settings.rename_strict else "auto")
        renamer.set_template(settings.rename_template)
        renamer.set_issue_zero_padding(settings.rename_issue_number_padding)
        renamer.set_smart_cleanup(settings.rename_use_smart_string_cleanup)
        renamer.move = settings.rename_move_dir

        try:
            new_name = renamer.determine_name(ext=new_ext)
        except ValueError:
            logger.exception(
                msg_hdr + "Invalid format string!\n"
                "Your rename template is invalid!\n\n"
                "%s\n\n"
                "Please consult the template help in the settings "
                "and the documentation on the format at "
                "https://docs.python.org/3/library/string.html#format-string-syntax",
                settings.rename_template,
            )
            return
        except Exception:
            logger.exception("Formatter failure: %s metadata: %s", settings.rename_template, renamer.metadata)

        folder = get_rename_dir(ca, settings.rename_dir if settings.rename_move_dir else None)

        full_path = folder / new_name

        if full_path == ca.path:
            print(msg_hdr + "Filename is already good!", file=sys.stderr)
            return

        suffix = ""
        if not opts.dryrun:
            # rename the file
            try:
                ca.rename(utils.unique_file(full_path))
            except OSError:
                logger.exception("Failed to rename comic archive: %s", ca.path)
        else:
            suffix = " (dry-run, no change)"

        print(f"renamed '{original_path.name}' -> '{new_name}' {suffix}")

    elif opts.export_to_zip:
        msg_hdr = ""
        if batch_mode:
            msg_hdr = f"{ca.path}: "

        if ca.is_zip():
            logger.error(msg_hdr + "Archive is already a zip file.")
            return

        filename_path = pathlib.Path(filename).absolute()
        new_file = filename_path.with_suffix(".cbz")

        if opts.abort_on_conflict and new_file.exists():
            print(msg_hdr + f"{new_file.name} already exists in the that folder.")
            return

        new_file = utils.unique_file(new_file)

        delete_success = False
        export_success = False
        if not opts.dryrun:
            if ca.export_as_zip(new_file):
                export_success = True
                if opts.delete_after_zip_export:
                    try:
                        filename_path.unlink(missing_ok=True)
                        delete_success = True
                    except OSError:
                        logger.exception(msg_hdr + "Error deleting original archive after export")
                        delete_success = False
            else:
                # last export failed, so remove the zip, if it exists
                new_file.unlink(missing_ok=True)
        else:
            msg = msg_hdr + f"Dry-run:  Would try to create {os.path.split(new_file)[1]}"
            if opts.delete_after_zip_export:
                msg += " and delete original."
            print(msg)
            return

        msg = msg_hdr
        if export_success:
            msg += f"Archive exported successfully to: {os.path.split(new_file)[1]}"
            if opts.delete_after_zip_export and delete_success:
                msg += " (Original deleted) "
        else:
            msg += "Archive failed to export!"

        print(msg)
