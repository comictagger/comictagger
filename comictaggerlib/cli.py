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

import json
import logging
import os
import sys
from datetime import datetime
from pprint import pprint

from comicapi import utils
from comicapi.comicarchive import ComicArchive, MetaDataStyle
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion, settings
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.filerenamer import FileRenamer, get_rename_dir
from comictaggerlib.graphics import graphics_path
from comictaggerlib.issueidentifier import IssueIdentifier
from comictaggerlib.resulttypes import MultipleMatch, OnlineMatchResults
from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class CLI:
    def __init__(self, options: settings.OptionValues, talker_api: ComicTalker):
        self.options = options
        self.talker_api = talker_api
        self.batch_mode = False

    def actual_issue_data_fetch(self, issue_id: int) -> GenericMetadata:
        # now get the particular issue data
        try:
            ct_md = self.talker_api.fetch_comic_data(issue_id)
        except TalkerError as e:
            logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
            return GenericMetadata()

        if self.options["cbl"]["apply_cbl_transform_on_cv_import"]:
            ct_md = CBLTransformer(ct_md, self.options).apply()

        return ct_md

    def actual_metadata_save(self, ca: ComicArchive, md: GenericMetadata) -> bool:
        if not self.options["runtime"]["dryrun"]:
            for metadata_style in self.options["runtime"]["type"]:
                # write out the new data
                if not ca.write_metadata(md, metadata_style):
                    logger.error("The tag save seemed to fail for style: %s!", MetaDataStyle.name[metadata_style])
                    return False

            print("Save complete.")
            logger.info("Save complete.")
        else:
            if self.options["runtime"]["terse"]:
                logger.info("dry-run option was set, so nothing was written")
                print("dry-run option was set, so nothing was written")
            else:
                logger.info("dry-run option was set, so nothing was written, but here is the final set of tags:")
                print("dry-run option was set, so nothing was written, but here is the final set of tags:")
                print(f"{md}")
        return True

    def display_match_set_for_choice(self, label: str, match_set: MultipleMatch) -> None:
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
        if self.options["runtime"]["interactive"]:
            while True:
                i = input("Choose a match #, or 's' to skip: ")
                if (i.isdigit() and int(i) in range(1, len(match_set.matches) + 1)) or i == "s":
                    break
            if i != "s":
                # save the data!
                # we know at this point, that the file is all good to go
                ca = match_set.ca
                md = self.create_local_metadata(ca)
                ct_md = self.actual_issue_data_fetch(match_set.matches[int(i) - 1]["issue_id"])
                if self.options["comicvine"]["clear_metadata_on_import"]:
                    md = ct_md
                else:
                    notes = (
                        f"Tagged with ComicTagger {ctversion.version} using info from Comic Vine on"
                        f" {datetime.now():%Y-%m-%d %H:%M:%S}.  [Issue ID {ct_md.issue_id}]"
                    )
                    md.overlay(ct_md.replace(notes=utils.combine_notes(md.notes, notes, "Tagged with ComicTagger")))

                if self.options["comicvine"]["auto_imprint"]:
                    md.fix_publisher()

                self.actual_metadata_save(ca, md)

    def post_process_matches(self, match_results: OnlineMatchResults) -> None:
        # now go through the match results
        if self.options["runtime"]["show_save_summary"]:
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

        if not self.options["runtime"]["show_save_summary"] and not self.options["runtime"]["interactive"]:
            # just quit if we're not interactive or showing the summary
            return

        if len(match_results.multiple_matches) > 0:
            print("\nArchives with multiple high-confidence matches:\n------------------")
            for match_set in match_results.multiple_matches:
                self.display_match_set_for_choice("Multiple high-confidence matches", match_set)

        if len(match_results.low_confidence_matches) > 0:
            print("\nArchives with low-confidence matches:\n------------------")
            for match_set in match_results.low_confidence_matches:
                if len(match_set.matches) == 1:
                    label = "Single low-confidence match"
                else:
                    label = "Multiple low-confidence matches"

                self.display_match_set_for_choice(label, match_set)

    def run(self) -> None:
        if len(self.options["runtime"]["file_list"]) < 1:
            logger.error("You must specify at least one filename.  Use the -h option for more info")
            return

        match_results = OnlineMatchResults()
        self.batch_mode = len(self.options["runtime"]["file_list"]) > 1

        for f in self.options["runtime"]["file_list"]:
            self.process_file_cli(f, match_results)
            sys.stdout.flush()

        self.post_process_matches(match_results)

    def create_local_metadata(self, ca: ComicArchive) -> GenericMetadata:
        md = GenericMetadata()
        md.set_default_page_list(ca.get_number_of_pages())

        # now, overlay the parsed filename info
        if self.options["runtime"]["parse_filename"]:
            f_md = ca.metadata_from_filename(
                self.options["filename"]["complicated_parser"],
                self.options["filename"]["remove_c2c"],
                self.options["filename"]["remove_fcbd"],
                self.options["filename"]["remove_publisher"],
                self.options["runtime"]["split_words"],
            )

            md.overlay(f_md)

        for metadata_style in self.options["runtime"]["type"]:
            if ca.has_metadata(metadata_style):
                try:
                    t_md = ca.read_metadata(metadata_style)
                    md.overlay(t_md)
                    break
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        # finally, use explicit stuff
        md.overlay(self.options["runtime"]["metadata"])

        return md

    def print(self, ca: ComicArchive) -> None:
        if not self.options["runtime"]["type"]:
            page_count = ca.get_number_of_pages()

            brief = ""

            if self.batch_mode:
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

            if not (
                ca.has_metadata(MetaDataStyle.CBI)
                or ca.has_metadata(MetaDataStyle.CIX)
                or ca.has_metadata(MetaDataStyle.COMET)
            ):
                brief += "none "
            else:
                if ca.has_metadata(MetaDataStyle.CBI):
                    brief += "CBL "
                if ca.has_metadata(MetaDataStyle.CIX):
                    brief += "CR "
                if ca.has_metadata(MetaDataStyle.COMET):
                    brief += "CoMet "
            brief += "]"

            print(brief)

        if self.options["runtime"]["terse"]:
            return

        print()

        if not self.options["runtime"]["type"] or MetaDataStyle.CIX in self.options["runtime"]["type"]:
            if ca.has_metadata(MetaDataStyle.CIX):
                print("--------- ComicRack tags ---------")
                try:
                    if self.options["runtime"]["raw"]:
                        print(ca.read_raw_cix())
                    else:
                        print(ca.read_cix())
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        if not self.options["runtime"]["type"] or MetaDataStyle.CBI in self.options["runtime"]["type"]:
            if ca.has_metadata(MetaDataStyle.CBI):
                print("------- ComicBookLover tags -------")
                try:
                    if self.options["runtime"]["raw"]:
                        pprint(json.loads(ca.read_raw_cbi()))
                    else:
                        print(ca.read_cbi())
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        if not self.options["runtime"]["type"] or MetaDataStyle.COMET in self.options["runtime"]["type"]:
            if ca.has_metadata(MetaDataStyle.COMET):
                print("----------- CoMet tags -----------")
                try:
                    if self.options["runtime"]["raw"]:
                        print(ca.read_raw_comet())
                    else:
                        print(ca.read_comet())
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

    def delete(self, ca: ComicArchive) -> None:
        for metadata_style in self.options["runtime"]["type"]:
            style_name = MetaDataStyle.name[metadata_style]
            if ca.has_metadata(metadata_style):
                if not self.options["runtime"]["dryrun"]:
                    if not ca.remove_metadata(metadata_style):
                        print(f"{ca.path}: Tag removal seemed to fail!")
                    else:
                        print(f"{ca.path}: Removed {style_name} tags.")
                else:
                    print(f"{ca.path}: dry-run. {style_name} tags not removed")
            else:
                print(f"{ca.path}: This archive doesn't have {style_name} tags to remove.")

    def copy(self, ca: ComicArchive) -> None:
        for metadata_style in self.options["runtime"]["type"]:
            dst_style_name = MetaDataStyle.name[metadata_style]
            if self.options["runtime"]["no_overwrite"] and ca.has_metadata(metadata_style):
                print(f"{ca.path}: Already has {dst_style_name} tags. Not overwriting.")
                return
            if self.options["commands"]["copy"] == metadata_style:
                print(f"{ca.path}: Destination and source are same: {dst_style_name}. Nothing to do.")
                return

            src_style_name = MetaDataStyle.name[self.options["commands"]["copy"]]
            if ca.has_metadata(self.options["commands"]["copy"]):
                if not self.options["runtime"]["dryrun"]:
                    try:
                        md = ca.read_metadata(self.options["commands"]["copy"])
                    except Exception as e:
                        md = GenericMetadata()
                        logger.error("Failed to load metadata for %s: %s", ca.path, e)

                    if self.options["apply_cbl_transform_on_bulk_operation"] and metadata_style == MetaDataStyle.CBI:
                        md = CBLTransformer(md, self.options).apply()

                    if not ca.write_metadata(md, metadata_style):
                        print(f"{ca.path}: Tag copy seemed to fail!")
                    else:
                        print(f"{ca.path}: Copied {src_style_name} tags to {dst_style_name}.")
                else:
                    print(f"{ca.path}: dry-run.  {src_style_name} tags not copied")
            else:
                print(f"{ca.path}: This archive doesn't have {src_style_name} tags to copy.")

    def save(self, ca: ComicArchive, match_results: OnlineMatchResults) -> None:
        if self.options["runtime"]["no_overwrite"]:
            for metadata_style in self.options["runtime"]["type"]:
                if ca.has_metadata(metadata_style):
                    print(f"{ca.path}: Already has {MetaDataStyle.name[metadata_style]} tags. Not overwriting.")
                    return

        if self.batch_mode:
            print(f"Processing {ca.path}...")

        md = self.create_local_metadata(ca)
        if md.issue is None or md.issue == "":
            if self.options["runtime"]["assume_issue_one"]:
                md.issue = "1"

        # now, search online
        if self.options["runtime"]["online"]:
            if self.options["runtime"]["issue_id"] is not None:
                # we were given the actual issue ID to search with
                try:
                    ct_md = self.talker_api.fetch_comic_data(self.options["runtime"]["issue_id"])
                except TalkerError as e:
                    logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
                    match_results.fetch_data_failures.append(str(ca.path.absolute()))
                    return

                if ct_md is None:
                    logger.error("No match for ID %s was found.", self.options["runtime"]["issue_id"])
                    match_results.no_matches.append(str(ca.path.absolute()))
                    return

                if self.options["cbl"]["apply_cbl_transform_on_cv_import"]:
                    ct_md = CBLTransformer(ct_md, self.options).apply()
            else:
                if md is None or md.is_empty:
                    logger.error("No metadata given to search online with!")
                    match_results.no_matches.append(str(ca.path.absolute()))
                    return

                ii = IssueIdentifier(ca, self.options, self.talker_api)

                def myoutput(text: str) -> None:
                    if self.options["runtime"]["verbose"]:
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
                if low_confidence and self.options["runtime"]["abort_on_low_confidence"]:
                    logger.error("Online search: Low confidence match. Save aborted")
                    match_results.low_confidence_matches.append(MultipleMatch(ca, matches))
                    return
                if not found_match:
                    logger.error("Online search: No match found. Save aborted")
                    match_results.no_matches.append(str(ca.path.absolute()))
                    return

                # we got here, so we have a single match

                # now get the particular issue data
                ct_md = self.actual_issue_data_fetch(matches[0]["issue_id"])
                if ct_md.is_empty:
                    match_results.fetch_data_failures.append(str(ca.path.absolute()))
                    return

            if self.options["comicvine"]["clear_metadata_on_import"]:
                md = ct_md
            else:
                notes = (
                    f"Tagged with ComicTagger {ctversion.version} using info from Comic Vine on"
                    f" {datetime.now():%Y-%m-%d %H:%M:%S}.  [Issue ID {ct_md.issue_id}]"
                )
                md.overlay(ct_md.replace(notes=utils.combine_notes(md.notes, notes, "Tagged with ComicTagger")))

            if self.options["comicvine"]["auto_imprint"]:
                md.fix_publisher()

        # ok, done building our metadata. time to save
        if not self.actual_metadata_save(ca, md):
            match_results.write_failures.append(str(ca.path.absolute()))
        else:
            match_results.good_matches.append(str(ca.path.absolute()))

    def rename(self, ca: ComicArchive) -> None:
        original_path = ca.path
        msg_hdr = ""
        if self.batch_mode:
            msg_hdr = f"{ca.path}: "

        md = self.create_local_metadata(ca)

        if md.series is None:
            logger.error(msg_hdr + "Can't rename without series name")
            return

        new_ext = ""  # default
        if self.options["filename"]["rename_set_extension_based_on_archive"]:
            if ca.is_sevenzip():
                new_ext = ".cb7"
            elif ca.is_zip():
                new_ext = ".cbz"
            elif ca.is_rar():
                new_ext = ".cbr"

        renamer = FileRenamer(
            md,
            platform="universal" if self.options["filename"]["rename_strict"] else "auto",
            replacements=self.options["rename"]["replacements"],
        )
        renamer.set_template(self.options["filename"]["rename_template"])
        renamer.set_issue_zero_padding(self.options["filename"]["rename_issue_number_padding"])
        renamer.set_smart_cleanup(self.options["filename"]["rename_use_smart_string_cleanup"])
        renamer.move = self.options["filename"]["rename_move_to_dir"]

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
                self.options["filename"]["rename_template"],
            )
            return
        except Exception:
            logger.exception(
                "Formatter failure: %s metadata: %s", self.options["filename"]["rename_template"], renamer.metadata
            )

        folder = get_rename_dir(
            ca, self.options["filename"]["rename_dir"] if self.options["filename"]["rename_move_to_dir"] else None
        )

        full_path = folder / new_name

        if full_path == ca.path:
            print(msg_hdr + "Filename is already good!", file=sys.stderr)
            return

        suffix = ""
        if not self.options["runtime"]["dryrun"]:
            # rename the file
            try:
                ca.rename(utils.unique_file(full_path))
            except OSError:
                logger.exception("Failed to rename comic archive: %s", ca.path)
        else:
            suffix = " (dry-run, no change)"

        print(f"renamed '{original_path.name}' -> '{new_name}' {suffix}")

    def export(self, ca: ComicArchive) -> None:
        msg_hdr = ""
        if self.batch_mode:
            msg_hdr = f"{ca.path}: "

        if ca.is_zip():
            logger.error(msg_hdr + "Archive is already a zip file.")
            return

        filename_path = ca.path
        new_file = filename_path.with_suffix(".cbz")

        if self.options["runtime"]["abort_on_conflict"] and new_file.exists():
            print(msg_hdr + f"{new_file.name} already exists in the that folder.")
            return

        new_file = utils.unique_file(new_file)

        delete_success = False
        export_success = False
        if not self.options["runtime"]["dryrun"]:
            if ca.export_as_zip(new_file):
                export_success = True
                if self.options["runtime"]["delete_after_zip_export"]:
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
            if self.options["runtime"]["delete_after_zip_export"]:
                msg += " and delete original."
            print(msg)
            return

        msg = msg_hdr
        if export_success:
            msg += f"Archive exported successfully to: {os.path.split(new_file)[1]}"
            if self.options["runtime"]["delete_after_zip_export"] and delete_success:
                msg += " (Original deleted) "
        else:
            msg += "Archive failed to export!"

        print(msg)

    def process_file_cli(self, filename: str, match_results: OnlineMatchResults) -> None:
        if not os.path.lexists(filename):
            logger.error("Cannot find %s", filename)
            return

        ca = ComicArchive(filename, self.options["general"]["rar_exe_path"], str(graphics_path / "nocover.png"))

        if not ca.seems_to_be_a_comic_archive():
            logger.error("Sorry, but %s is not a comic archive!", filename)
            return

        if not ca.is_writable() and (
            self.options["commands"]["delete"]
            or self.options["commands"]["copy"]
            or self.options["commands"]["save"]
            or self.options["commands"]["rename"]
        ):
            logger.error("This archive is not writable")
            return

        if self.options["commands"]["print"]:
            self.print(ca)

        elif self.options["commands"]["delete"]:
            self.delete(ca)

        elif self.options["commands"]["copy"] is not None:
            self.copy(ca)

        elif self.options["commands"]["save"]:
            self.save(ca, match_results)

        elif self.options["commands"]["rename"]:
            self.rename(ca)

        elif self.options["commands"]["export_to_zip"]:
            self.export(ca)
