#!/usr/bin/python
"""ComicTagger CLI functions"""
#
# Copyright 2013 ComicTagger Authors
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

import dataclasses
import json
import logging
import os
import pathlib
import sys
from collections.abc import Collection
from datetime import datetime
from typing import Any, TextIO

from comicapi import utils
from comicapi.comicarchive import ComicArchive, MetaDataStyle
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import ctversion
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.filerenamer import FileRenamer, get_rename_dir
from comictaggerlib.graphics import graphics_path
from comictaggerlib.issueidentifier import IssueIdentifier
from comictaggerlib.resulttypes import IssueResult, OnlineMatchResults, Result, Status
from comictalker.comictalker import ComicTalker, TalkerError
from comictalker.talker_utils import cleanup_html

logger = logging.getLogger(__name__)


class OutputEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        print(obj)
        if isinstance(obj, pathlib.Path):
            return str(obj)
        if not isinstance(obj, str) and isinstance(obj, Collection):
            return list(obj)

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class CLI:
    def __init__(self, config: ct_ns, talkers: dict[str, ComicTalker]) -> None:
        self.config = config
        self.talkers = talkers
        self.batch_mode = False
        self.output_file = sys.stdout
        if config.Runtime_Options__json:
            self.output_file = sys.stderr

    def current_talker(self) -> ComicTalker:
        if self.config.Sources__source in self.talkers:
            return self.talkers[self.config.Sources__source]
        logger.error("Could not find the '%s' talker", self.config.Sources__source)
        raise SystemExit(2)

    def output(self, *args: Any, file: TextIO | None = None, **kwargs: Any) -> None:
        if file is None:
            file = self.output_file
        if not args:
            log_args: tuple[Any, ...] = ("",)
        elif isinstance(args[0], str):
            log_args = (args[0].strip("\n"), *args[1:])
        else:
            log_args = args
        logger.info(*log_args, **kwargs)
        if self.config.Runtime_Options__verbose > 0:
            return
        if not self.config.Runtime_Options__quiet:
            print(*args, **kwargs, file=file)

    def run(self) -> None:
        if len(self.config.Runtime_Options__files) < 1:
            logger.error("You must specify at least one filename.  Use the -h option for more info")
            return

        results: list[Result] = []
        match_results = OnlineMatchResults()
        self.batch_mode = len(self.config.Runtime_Options__files) > 1

        for f in self.config.Runtime_Options__files:
            results.append(self.process_file_cli(f, match_results))
            if self.config.Runtime_Options__json:
                print(dataclasses.asdict(results[-1]))
                print(json.dumps(dataclasses.asdict(results[-1]), cls=OutputEncoder, indent=2))
            sys.stdout.flush()
            sys.stderr.flush()

        self.post_process_matches(match_results)

        if self.config.Runtime_Options__online:
            self.output(
                f"\nFiles tagged with metadata provided by {self.current_talker().name} {self.current_talker().website}",
            )

    def actual_issue_data_fetch(self, issue_id: str) -> GenericMetadata:
        # now get the particular issue data
        try:
            ct_md = self.current_talker().fetch_comic_data(issue_id)
        except TalkerError as e:
            logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
            return GenericMetadata()

        if self.config.Comic_Book_Lover__apply_transform_on_import:
            ct_md = CBLTransformer(ct_md, self.config).apply()

        return ct_md

    def actual_metadata_save(self, ca: ComicArchive, md: GenericMetadata) -> bool:
        if not self.config.Runtime_Options__dryrun:
            for metadata_style in self.config.Runtime_Options__type:
                # write out the new data
                if not ca.write_metadata(md, metadata_style):
                    logger.error("The tag save seemed to fail for style: %s!", MetaDataStyle.name[metadata_style])
                    return False

            self.output("Save complete.")
        else:
            if self.config.Runtime_Options__quiet:
                self.output("dry-run option was set, so nothing was written")
            else:
                self.output("dry-run option was set, so nothing was written, but here is the final set of tags:")
                self.output(f"{md}")
        return True

    def display_match_set_for_choice(self, label: str, match_set: Result) -> None:
        self.output(f"{match_set.original_path} -- {label}:")

        # sort match list by year
        match_set.online_results.sort(key=lambda k: k.year or 0)

        for counter, m in enumerate(match_set.online_results, 1):
            self.output(
                "    {}. {} #{} [{}] ({}/{}) - {}".format(
                    counter,
                    m.series,
                    m.issue_number,
                    m.publisher,
                    m.month,
                    m.year,
                    m.issue_title,
                )
            )
        if self.config.Runtime_Options__interactive:
            while True:
                i = input("Choose a match #, or 's' to skip: ")
                if (i.isdigit() and int(i) in range(1, len(match_set.online_results) + 1)) or i == "s":
                    break
            if i != "s":
                # save the data!
                # we know at this point, that the file is all good to go
                ca = ComicArchive(match_set.original_path)
                md = self.create_local_metadata(ca)
                ct_md = self.actual_issue_data_fetch(match_set.online_results[int(i) - 1].issue_id)
                if self.config.Issue_Identifier__clear_metadata_on_import:
                    md = ct_md
                else:
                    notes = (
                        f"Tagged with ComicTagger {ctversion.version} using info from {self.current_talker().name} on"
                        f" {datetime.now():%Y-%m-%d %H:%M:%S}.  [Issue ID {ct_md.issue_id}]"
                    )
                    md.overlay(ct_md.replace(notes=utils.combine_notes(md.notes, notes, "Tagged with ComicTagger")))

                if self.config.Issue_Identifier__auto_imprint:
                    md.fix_publisher()

                match_set.md = md

                self.actual_metadata_save(ca, md)

    def post_process_matches(self, match_results: OnlineMatchResults) -> None:
        def print_header(header: str) -> None:
            self.output()
            self.output(header)
            self.output("------------------")

        # now go through the match results
        if self.config.Runtime_Options__summary:
            if len(match_results.good_matches) > 0:
                print_header("Successful matches:")
                for f in match_results.good_matches:
                    self.output(f)

            if len(match_results.no_matches) > 0:
                print_header("No matches:")
                for f in match_results.no_matches:
                    self.output(f)

            if len(match_results.write_failures) > 0:
                print_header("File Write Failures:")
                for f in match_results.write_failures:
                    self.output(f)

            if len(match_results.fetch_data_failures) > 0:
                print_header("Network Data Fetch Failures:")
                for f in match_results.fetch_data_failures:
                    self.output(f)

        if not self.config.Runtime_Options__summary and not self.config.Runtime_Options__interactive:
            # just quit if we're not interactive or showing the summary
            return

        if len(match_results.multiple_matches) > 0:
            self.output("\nArchives with multiple high-confidence matches:\n------------------")
            for match_set in match_results.multiple_matches:
                self.display_match_set_for_choice("Multiple high-confidence matches", match_set)

        if len(match_results.low_confidence_matches) > 0:
            self.output("\nArchives with low-confidence matches:\n------------------")
            for match_set in match_results.low_confidence_matches:
                if len(match_set.online_results) == 1:
                    label = "Single low-confidence match"
                else:
                    label = "Multiple low-confidence matches"

                self.display_match_set_for_choice(label, match_set)

    def create_local_metadata(self, ca: ComicArchive) -> GenericMetadata:
        md = GenericMetadata()
        md.set_default_page_list(ca.get_number_of_pages())

        # now, overlay the parsed filename info
        if self.config.Runtime_Options__parse_filename:
            f_md = ca.metadata_from_filename(
                self.config.Filename_Parsing__complicated_parser,
                self.config.Filename_Parsing__remove_c2c,
                self.config.Filename_Parsing__remove_fcbd,
                self.config.Filename_Parsing__remove_publisher,
                self.config.Runtime_Options__split_words,
            )

            md.overlay(f_md)

        for metadata_style in self.config.Runtime_Options__type:
            if ca.has_metadata(metadata_style):
                try:
                    t_md = ca.read_metadata(metadata_style)
                    md.overlay(t_md)
                    break
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        # finally, use explicit stuff
        md.overlay(self.config.Runtime_Options__metadata)

        return md

    def print(self, ca: ComicArchive) -> Result:
        if not self.config.Runtime_Options__type:
            page_count = ca.get_number_of_pages()

            brief = ""

            if self.batch_mode:
                brief = f"{ca.path}: "

            brief += ca.archiver.name() + " archive "

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

            self.output(brief)

        if self.config.Runtime_Options__quiet:
            return Result(ca.path, None, [], Status.success)

        self.output()

        raw: str | bytes = ""
        md = None
        if not self.config.Runtime_Options__type or MetaDataStyle.CIX in self.config.Runtime_Options__type:
            if ca.has_metadata(MetaDataStyle.CIX):
                self.output("--------- ComicRack tags ---------")
                try:
                    if self.config.Runtime_Options__raw:
                        raw = ca.read_raw_cix()
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        self.output(raw)
                    else:
                        md = ca.read_cix()
                        self.output(md)
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        if not self.config.Runtime_Options__type or MetaDataStyle.CBI in self.config.Runtime_Options__type:
            if ca.has_metadata(MetaDataStyle.CBI):
                self.output("------- ComicBookLover tags -------")
                try:
                    if self.config.Runtime_Options__raw:
                        raw = ca.read_raw_cbi()
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        self.output(raw)
                    else:
                        md = ca.read_cbi()
                        self.output(md)
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        if not self.config.Runtime_Options__type or MetaDataStyle.COMET in self.config.Runtime_Options__type:
            if ca.has_metadata(MetaDataStyle.COMET):
                self.output("----------- CoMet tags -----------")
                try:
                    if self.config.Runtime_Options__raw:
                        raw = ca.read_raw_comet()
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        self.output(raw)
                    else:
                        md = ca.read_comet()
                        self.output(md)
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        return Result(ca.path, None, [], Status.success, md=md)

    def delete_style(self, ca: ComicArchive, style: int) -> Status:
        style_name = MetaDataStyle.name[style]

        if ca.has_metadata(style):
            if not self.config.Runtime_Options__dryrun:
                if ca.remove_metadata(style):
                    self.output(f"{ca.path}: Removed {style_name} tags.")
                    return Status.success
                else:
                    self.output(f"{ca.path}: Tag removal seemed to fail!")
                    return Status.write_failure
            else:
                self.output(f"{ca.path}: dry-run. {style_name} tags not removed")
                return Status.success
        self.output(f"{ca.path}: This archive doesn't have {style_name} tags to remove.")
        return Status.success

    def delete(self, ca: ComicArchive) -> Result:
        res = Result(ca.path, None, status=Status.success)
        for metadata_style in self.config.Runtime_Options__type:
            status = self.delete_style(ca, metadata_style)
            if status == Status.success:
                res.tags_removed.append(metadata_style)
            else:
                res.status = status
        return res

    def copy_style(self, ca: ComicArchive, md: GenericMetadata, style: int) -> Status:
        dst_style_name = MetaDataStyle.name[style]
        if not self.config.Runtime_Options__overwrite and ca.has_metadata(style):
            self.output(f"{ca.path}: Already has {dst_style_name} tags. Not overwriting.")
            return Status.existing_tags
        if self.config.Commands__copy == style:
            self.output(f"{ca.path}: Destination and source are same: {dst_style_name}. Nothing to do.")
            return Status.existing_tags

        src_style_name = MetaDataStyle.name[self.config.Commands__copy]
        if ca.has_metadata(self.config.Commands__copy):
            if not self.config.Runtime_Options__dryrun:
                if self.config.Comic_Book_Lover__apply_transform_on_bulk_operation == MetaDataStyle.CBI:
                    md = CBLTransformer(md, self.config).apply()

                if ca.write_metadata(md, style):
                    self.output(f"{ca.path}: Copied {src_style_name} tags to {dst_style_name}.")
                    return Status.success
                else:
                    self.output(f"{ca.path}: Tag copy seemed to fail!")
                    return Status.write_failure
            else:
                self.output(f"{ca.path}: dry-run.  {src_style_name} tags not copied")
                return Status.success
        self.output(f"{ca.path}: This archive doesn't have {src_style_name} tags to copy.")
        return Status.read_failure

    def copy(self, ca: ComicArchive) -> Result:
        res = Result(ca.path, None)
        try:
            res.md = ca.read_metadata(self.config.Commands__copy)
        except Exception as e:
            logger.error("Failed to load metadata for %s: %s", ca.path, e)
            return res
        for metadata_style in self.config.Runtime_Options__type:
            status = self.copy_style(ca, res.md, metadata_style)
            if status == Status.success:
                res.tags_saved.append(metadata_style)
            else:
                res.status = status
        return res

    def save(self, ca: ComicArchive, match_results: OnlineMatchResults) -> Result:
        if not self.config.Runtime_Options__overwrite:
            for metadata_style in self.config.Runtime_Options__type:
                if ca.has_metadata(metadata_style):
                    self.output(f"{ca.path}: Already has {MetaDataStyle.name[metadata_style]} tags. Not overwriting.")
                    return Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=[],
                        status=Status.existing_tags,
                        tags_saved=self.config.Runtime_Options__type,
                    )

        if self.batch_mode:
            self.output(f"Processing {utils.path_to_short_str(ca.path)}...")

        md = self.create_local_metadata(ca)
        if md.issue is None or md.issue == "":
            if self.config.Auto_Tag__assume_1_if_no_issue_num:
                md.issue = "1"

        matches: list[IssueResult] = []
        # now, search online
        if self.config.Runtime_Options__online:
            if self.config.Runtime_Options__issue_id is not None:
                # we were given the actual issue ID to search with
                try:
                    ct_md = self.current_talker().fetch_comic_data(self.config.Runtime_Options__issue_id)
                except TalkerError as e:
                    logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
                    res = Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=[],
                        status=Status.fetch_data_failure,
                        tags_saved=self.config.Runtime_Options__type,
                    )
                    match_results.fetch_data_failures.append(res)
                    return res

                if ct_md is None:
                    logger.error("No match for ID %s was found.", self.config.Runtime_Options__issue_id)
                    res = Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=[],
                        status=Status.no_match,
                        tags_saved=self.config.Runtime_Options__type,
                    )
                    match_results.no_matches.append(res)
                    return res

                if self.config.Comic_Book_Lover__apply_transform_on_import:
                    ct_md = CBLTransformer(ct_md, self.config).apply()
            else:
                if md is None or md.is_empty:
                    logger.error("No metadata given to search online with!")
                    res = Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=[],
                        status=Status.no_match,
                        tags_saved=self.config.Runtime_Options__type,
                    )
                    match_results.no_matches.append(res)
                    return res

                ii = IssueIdentifier(ca, self.config, self.current_talker())

                def myoutput(text: str) -> None:
                    if self.config.Runtime_Options__verbose:
                        self.output(text)

                # use our overlaid MD struct to search
                ii.set_additional_metadata(md)
                ii.only_use_additional_meta_data = True
                # ii.set_output_function(myoutput)
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
                        res = Result(
                            original_path=ca.path,
                            renamed_path=None,
                            online_results=matches,
                            status=Status.low_confidence_match,
                            tags_saved=self.config.Runtime_Options__type,
                        )
                        match_results.low_confidence_matches.append(res)
                        return res

                    logger.error("Online search: Multiple good matches. Save aborted")
                    res = Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=matches,
                        status=Status.multiple_match,
                        tags_saved=self.config.Runtime_Options__type,
                    )
                    match_results.multiple_matches.append(res)
                    return res
                if low_confidence and self.config.Runtime_Options__abort_on_low_confidence:
                    logger.error("Online search: Low confidence match. Save aborted")
                    res = Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=matches,
                        status=Status.low_confidence_match,
                        tags_saved=self.config.Runtime_Options__type,
                    )
                    match_results.low_confidence_matches.append(res)
                    return res
                if not found_match:
                    logger.error("Online search: No match found. Save aborted")
                    res = Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=matches,
                        status=Status.no_match,
                        tags_saved=self.config.Runtime_Options__type,
                    )
                    match_results.no_matches.append(res)
                    return res

                # we got here, so we have a single match

                # now get the particular issue data
                ct_md = self.actual_issue_data_fetch(matches[0].issue_id)
                if ct_md.is_empty:
                    res = Result(
                        original_path=ca.path,
                        renamed_path=None,
                        online_results=matches,
                        status=Status.fetch_data_failure,
                        tags_saved=self.config.Runtime_Options__type,
                    )
                    match_results.fetch_data_failures.append(res)
                    return res

            if self.config.Issue_Identifier__clear_metadata_on_import:
                md = GenericMetadata()

            notes = (
                f"Tagged with ComicTagger {ctversion.version} using info from {self.current_talker().name} on"
                + f" {datetime.now():%Y-%m-%d %H:%M:%S}.  [Issue ID {ct_md.issue_id}]"
            )
            md.overlay(
                ct_md.replace(
                    notes=utils.combine_notes(md.notes, notes, "Tagged with ComicTagger"),
                    description=cleanup_html(ct_md.description, self.config.Sources__remove_html_tables),
                )
            )

            if self.config.Issue_Identifier__auto_imprint:
                md.fix_publisher()

        res = Result(
            original_path=ca.path,
            renamed_path=None,
            online_results=matches,
            status=Status.success,
            md=md,
            tags_saved=self.config.Runtime_Options__type,
        )
        # ok, done building our metadata. time to save
        if self.actual_metadata_save(ca, md):
            match_results.good_matches.append(res)
        else:
            res.status = Status.write_failure
            match_results.write_failures.append(res)
        return res

    def rename(self, ca: ComicArchive) -> Result:
        original_path = ca.path
        msg_hdr = ""
        if self.batch_mode:
            msg_hdr = f"{ca.path}: "

        md = self.create_local_metadata(ca)

        if md.series is None:
            logger.error(msg_hdr + "Can't rename without series name")
            return Result(original_path, None, [], Status.no_match)

        new_ext = ""  # default
        if self.config.File_Rename__set_extension_based_on_archive:
            new_ext = ca.extension()

        renamer = FileRenamer(
            md,
            platform="universal" if self.config.File_Rename__strict else "auto",
            replacements=self.config.File_Rename__replacements,
        )
        renamer.set_template(self.config.File_Rename__template)
        renamer.set_issue_zero_padding(self.config.File_Rename__issue_number_padding)
        renamer.set_smart_cleanup(self.config.File_Rename__use_smart_string_cleanup)
        renamer.move = self.config.File_Rename__move_to_dir

        try:
            new_name = renamer.determine_name(ext=new_ext)
        except ValueError:
            logger.exception(
                msg_hdr
                + "Invalid format string!\n"
                + "Your rename template is invalid!\n\n"
                + "%s\n\n"
                + "Please consult the template help in the settings "
                + "and the documentation on the format at "
                + "https://docs.python.org/3/library/string.html#format-string-syntax",
                self.config.File_Rename__template,
            )
            return Result(original_path, None, [], Status.rename_failure, md=md)
        except Exception:
            logger.exception("Formatter failure: %s metadata: %s", self.config.File_Rename__template, renamer.metadata)
            return Result(original_path, None, [], Status.rename_failure, md=md)

        folder = get_rename_dir(ca, self.config.File_Rename__dir if self.config.File_Rename__move_to_dir else None)

        full_path = folder / new_name

        if full_path == ca.path:
            self.output(msg_hdr + "Filename is already good!")
            return Result(original_path, full_path, [], Status.existing_tags, md=md)

        suffix = ""
        if not self.config.Runtime_Options__dryrun:
            # rename the file
            try:
                ca.rename(utils.unique_file(full_path))
            except OSError:
                logger.exception("Failed to rename comic archive: %s", ca.path)
                return Result(original_path, full_path, [], Status.write_failure, md=md)
        else:
            suffix = " (dry-run, no change)"

        self.output(f"renamed '{original_path.name}' -> '{new_name}' {suffix}")
        return Result(original_path, None, [], Status.success, md=md)

    def export(self, ca: ComicArchive) -> None:
        msg_hdr = ""
        if self.batch_mode:
            msg_hdr = f"{ca.path}: "

        if ca.is_zip():
            logger.error(msg_hdr + "Archive is already a zip file.")
            return

        filename_path = ca.path
        new_file = filename_path.with_suffix(".cbz")

        if self.config.Runtime_Options__abort_on_conflict and new_file.exists():
            self.output(msg_hdr + f"{new_file.name} already exists in the that folder.")
            return

        new_file = utils.unique_file(new_file)

        delete_success = False
        export_success = False
        if not self.config.Runtime_Options__dryrun:
            if ca.export_as_zip(new_file):
                export_success = True
                if self.config.Runtime_Options__delete_after_zip_export:
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
            if self.config.Runtime_Options__delete_after_zip_export:
                msg += " and delete original."
            self.output(msg)
            return

        msg = msg_hdr
        if export_success:
            msg += f"Archive exported successfully to: {os.path.split(new_file)[1]}"
            if self.config.Runtime_Options__delete_after_zip_export and delete_success:
                msg += " (Original deleted) "
        else:
            msg += "Archive failed to export!"

        self.output(msg)

    def process_file_cli(self, filename: str, match_results: OnlineMatchResults) -> Result:
        if not os.path.lexists(filename):
            logger.error("Cannot find %s", filename)
            return Result(pathlib.Path(filename), None, [], Status.read_failure)

        ca = ComicArchive(filename, str(graphics_path / "nocover.png"))

        if not ca.seems_to_be_a_comic_archive():
            logger.error("Sorry, but %s is not a comic archive!", filename)
            return Result(ca.path, None, [], Status.read_failure)

        if not ca.is_writable() and (
            self.config.Commands__delete
            or self.config.Commands__copy
            or self.config.Commands__save
            or self.config.Commands__rename
        ):
            logger.error("This archive is not writable")
            return Result(ca.path, None, [], Status.write_permission_failure)

        if self.config.Commands__print:
            return self.print(ca)

        elif self.config.Commands__delete:
            return self.delete(ca)

        elif self.config.Commands__copy is not None:
            return self.copy(ca)

        elif self.config.Commands__save:
            return self.save(ca, match_results)

        elif self.config.Commands__rename:
            return self.rename(ca)

        elif self.config.Commands__export_to_zip:
            return self.export(ca)
