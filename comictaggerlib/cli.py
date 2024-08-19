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
import functools
import json
import logging
import os
import pathlib
import re
import sys
from collections.abc import Collection
from typing import Any, TextIO

from comicapi import merge, utils
from comicapi.comicarchive import ComicArchive, tags
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.filerenamer import FileRenamer, get_rename_dir
from comictaggerlib.graphics import graphics_path
from comictaggerlib.issueidentifier import IssueIdentifier
from comictaggerlib.md import prepare_metadata
from comictaggerlib.quick_tag import QuickTag
from comictaggerlib.resulttypes import Action, IssueResult, MatchStatus, OnlineMatchResults, Result, Status
from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class OutputEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
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

    def output(
        self,
        *args: Any,
        file: TextIO | None = None,
        force_output: bool = False,
        already_logged: bool = False,
        **kwargs: Any,
    ) -> None:
        if file is None:
            file = self.output_file
        if not args:
            log_args: tuple[Any, ...] = ("",)
        elif isinstance(args[0], str):
            log_args = (args[0].strip("\n"), *args[1:])
        else:
            log_args = args
        if not already_logged:
            logger.info(*log_args, **kwargs)
        if self.config.Runtime_Options__verbose > 0:
            return
        if not self.config.Runtime_Options__quiet or force_output:
            print(*args, **kwargs, file=file)

    def run(self) -> int:
        if len(self.config.Runtime_Options__files) < 1:
            logger.error("You must specify at least one filename.  Use the -h option for more info")
            return 1
        return_code = 0

        results: list[Result] = []
        match_results = OnlineMatchResults()
        self.batch_mode = len(self.config.Runtime_Options__files) > 1

        for f in self.config.Runtime_Options__files:
            res, match_results = self.process_file_cli(self.config.Commands__command, f, match_results)
            results.append(res)
            if results[-1].status != Status.success:
                return_code = 3
            if self.config.Runtime_Options__json:
                print(json.dumps(dataclasses.asdict(results[-1]), cls=OutputEncoder, indent=2))
            sys.stdout.flush()
            sys.stderr.flush()

        self.post_process_matches(match_results)

        if self.config.Auto_Tag__online:
            self.output(
                f"\nFiles tagged with metadata provided by {self.current_talker().name} {self.current_talker().website}",
            )
        return return_code

    def fetch_metadata(self, issue_id: str) -> GenericMetadata:
        # now get the particular issue data
        try:
            ct_md = self.current_talker().fetch_comic_data(issue_id)
        except TalkerError as e:
            logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
            return GenericMetadata()

        if self.config.Metadata_Options__apply_transform_on_import:
            ct_md = CBLTransformer(ct_md, self.config).apply()

        return ct_md

    def write_tags(self, ca: ComicArchive, md: GenericMetadata) -> bool:
        if not self.config.Runtime_Options__dryrun:
            for tag_id in self.config.Runtime_Options__tags_write:
                # write out the new data
                if not ca.write_tags(md, tag_id):
                    logger.error("The tag save seemed to fail for: %s!", tags[tag_id].name())
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
        self.output(f"{match_set.original_path} -- {label}:", force_output=True)

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
                ),
                force_output=True,
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
                md, match_set.tags_read = self.create_local_metadata(ca, self.config.Runtime_Options__tags_read)
                ct_md = self.fetch_metadata(match_set.online_results[int(i) - 1].issue_id)

                match_set.md = prepare_metadata(md, ct_md, self.config)

                self.write_tags(ca, match_set.md)

    def post_process_matches(self, match_results: OnlineMatchResults) -> None:
        def print_header(header: str) -> None:
            self.output("", force_output=True)
            self.output(header, force_output=True)
            self.output("------------------", force_output=True)

        # now go through the match results
        if self.config.Runtime_Options__summary:
            if len(match_results.good_matches) > 0:
                print_header("Successful matches:")
                for f in match_results.good_matches:
                    self.output(f, force_output=True)

            if len(match_results.no_matches) > 0:
                print_header("No matches:")
                for f in match_results.no_matches:
                    self.output(f, force_output=True)

            if len(match_results.write_failures) > 0:
                print_header("File Write Failures:")
                for f in match_results.write_failures:
                    self.output(f, force_output=True)

            if len(match_results.fetch_data_failures) > 0:
                print_header("Network Data Fetch Failures:")
                for f in match_results.fetch_data_failures:
                    self.output(f, force_output=True)

        if not self.config.Runtime_Options__summary and not self.config.Runtime_Options__interactive:
            # just quit if we're not interactive or showing the summary
            return

        if len(match_results.multiple_matches) > 0:
            self.output("\nArchives with multiple high-confidence matches:\n------------------", force_output=True)
            for match_set in match_results.multiple_matches:
                self.display_match_set_for_choice("Multiple high-confidence matches", match_set)

        if len(match_results.low_confidence_matches) > 0:
            self.output("\nArchives with low-confidence matches:\n------------------", force_output=True)
            for match_set in match_results.low_confidence_matches:
                if len(match_set.online_results) == 1:
                    label = "Single low-confidence match"
                else:
                    label = "Multiple low-confidence matches"

                self.display_match_set_for_choice(label, match_set)

    def create_local_metadata(
        self, ca: ComicArchive, tags_to_read: list[str], /, tags_only: bool = False
    ) -> tuple[GenericMetadata, list[str]]:
        md = GenericMetadata()
        md.apply_default_page_list(ca.get_page_name_list())
        filename_md = GenericMetadata()

        # now, overlay the parsed filename info
        if self.config.Auto_Tag__parse_filename and not tags_only:
            filename_md = ca.metadata_from_filename(
                self.config.Filename_Parsing__filename_parser,
                self.config.Filename_Parsing__remove_c2c,
                self.config.Filename_Parsing__remove_fcbd,
                self.config.Filename_Parsing__remove_publisher,
                self.config.Filename_Parsing__split_words,
                self.config.Filename_Parsing__allow_issue_start_with_letter,
                self.config.Filename_Parsing__protofolius_issue_number_scheme,
            )

        file_md = GenericMetadata()
        tags_used = []
        for tag_id in tags_to_read:
            if ca.has_tags(tag_id):
                try:
                    t_md = ca.read_tags(tag_id)
                    if not t_md.is_empty:
                        file_md.overlay(
                            t_md,
                            self.config.Metadata_Options__tag_merge,
                            self.config.Metadata_Options__tag_merge_lists,
                        )
                        tags_used.append(tag_id)
                except Exception as e:
                    logger.error("Failed to load metadata for %s: %s", ca.path, e)

        filename_merge = merge.Mode.ADD_MISSING
        if self.config.Auto_Tag__prefer_filename:
            filename_merge = merge.Mode.OVERLAY

        md.overlay(file_md, mode=merge.Mode.OVERLAY, merge_lists=False)
        if not tags_only:
            md.overlay(filename_md, mode=filename_merge, merge_lists=False)
            # finally, use explicit stuff (always 'overlay' mode)
            md.overlay(self.config.Auto_Tag__metadata, mode=merge.Mode.OVERLAY, merge_lists=True)

        return (md, tags_used)

    def print(self, ca: ComicArchive) -> Result:
        if not self.config.Runtime_Options__tags_read:
            page_count = ca.get_number_of_pages()

            brief = ""

            if self.batch_mode:
                brief = f"{ca.path}: "

            brief += ca.archiver.name() + " archive "

            brief += f"({page_count: >3} pages)"
            brief += "  tags:[ "

            tag_names = [tags[tag_id].name() for tag_id in tags if ca.has_tags(tag_id)]
            brief += " ".join(tag_names)
            brief += " ]"

            self.output(brief)

        if self.config.Runtime_Options__quiet:
            return Result(Action.print, Status.success, ca.path)

        self.output()

        md = None
        for tag_id, tag in tags.items():
            if not self.config.Runtime_Options__tags_read or tag_id in self.config.Runtime_Options__tags_read:
                if ca.has_tags(tag_id):
                    self.output(f"--------- {tag.name()} tags ---------")
                    try:
                        if self.config.Runtime_Options__raw:
                            self.output(ca.read_raw_tags(tag_id))
                        else:
                            md = ca.read_tags(tag_id)
                            self.output(md)
                    except Exception as e:
                        logger.error("Failed to read tags from %s: %s", ca.path, e)
        return Result(Action.print, Status.success, ca.path, md=md)

    def delete_tags(self, ca: ComicArchive, tag_id: str) -> Status:
        tag_name = tags[tag_id].name()

        if ca.has_tags(tag_id):
            if not self.config.Runtime_Options__dryrun:
                if ca.remove_tags(tag_id):
                    self.output(f"{ca.path}: Removed {tag_name} tags.")
                    return Status.success
                else:
                    self.output(f"{ca.path}: Tag removal seemed to fail!")
                    return Status.write_failure
            else:
                self.output(f"{ca.path}: dry-run. {tag_name} tags not removed")
                return Status.success
        self.output(f"{ca.path}: This archive doesn't have {tag_name} tags to remove.")
        return Status.success

    def delete(self, ca: ComicArchive) -> Result:
        res = Result(Action.delete, Status.success, ca.path)
        for tag_id in self.config.Runtime_Options__tags_write:
            status = self.delete_tags(ca, tag_id)
            if status == Status.success:
                res.tags_deleted.append(tag_id)
            else:
                res.status = status
        return res

    def _copy_tags(self, ca: ComicArchive, md: GenericMetadata, source_names: str, dst_tag_id: str) -> Status:
        dst_tag_name = tags[dst_tag_id].name()
        if self.config.Runtime_Options__skip_existing_tags and ca.has_tags(dst_tag_id):
            self.output(f"{ca.path}: Already has {dst_tag_name} tags. Not overwriting.")
            return Status.existing_tags

        if len(self.config.Commands__copy) == 1 and dst_tag_id in self.config.Commands__copy:
            self.output(f"{ca.path}: Destination and source are same: {dst_tag_name}. Nothing to do.")
            return Status.existing_tags

        if not self.config.Runtime_Options__dryrun:
            if self.config.Metadata_Options__apply_transform_on_bulk_operation and dst_tag_id == "cbi":
                md = CBLTransformer(md, self.config).apply()

            if ca.write_tags(md, dst_tag_id):
                self.output(f"{ca.path}: Copied {source_names} tags to {dst_tag_name}.")
            else:
                self.output(f"{ca.path}: Tag copy seemed to fail!")
                return Status.write_failure
        else:
            self.output(f"{ca.path}: dry-run.  {source_names} tags not copied")
        return Status.success

    def copy(self, ca: ComicArchive) -> Result:
        res = Result(Action.copy, Status.success, ca.path)
        src_tag_names = []
        for src_tag_id in self.config.Commands__copy:
            src_tag_names.append(tags[src_tag_id].name())
            if ca.has_tags(src_tag_id):
                res.tags_read.append(src_tag_id)

        if not res.tags_read:
            self.output(f"{ca.path}: This archive doesn't have any {', '.join(src_tag_names)} tags to copy.")
            res.status = Status.read_failure
            return res
        try:
            res.md, res.tags_read = self.create_local_metadata(ca, res.tags_read, tags_only=True)
        except Exception as e:
            logger.error("Failed to read tags from %s: %s", ca.path, e)
            return res

        for dst_tag_id in self.config.Runtime_Options__tags_write:
            if dst_tag_id in self.config.Commands__copy:
                continue

            status = self._copy_tags(ca, res.md, ", ".join(src_tag_names), dst_tag_id)
            if status == Status.success:
                res.tags_written.append(dst_tag_id)
            else:
                res.status = status
        return res

    def try_quick_tag(self, ca: ComicArchive, md: GenericMetadata) -> GenericMetadata | None:
        if not self.config.Runtime_Options__enable_quick_tag:
            self.output("skipping quick tag")
            return None
        self.output("starting quick tag")
        try:
            qt = QuickTag(
                self.config.Quick_Tag__url,
                str(utils.parse_url(self.current_talker().website).host),
                self.current_talker(),
                self.config,
                self.output,
            )
            ct_md = qt.id_comic(
                ca,
                md,
                self.config.Quick_Tag__simple,
                set(self.config.Quick_Tag__hash),
                self.config.Quick_Tag__skip_non_exact,
                self.config.Runtime_Options__interactive,
                self.config.Quick_Tag__aggressive_filtering,
                self.config.Quick_Tag__max,
            )
            if ct_md is None:
                ct_md = GenericMetadata()
            return ct_md
        except Exception:
            logger.exception("Quick Tagging failed")
        return None

    def normal_tag(
        self, ca: ComicArchive, tags_read: list[str], md: GenericMetadata, match_results: OnlineMatchResults
    ) -> tuple[GenericMetadata, list[IssueResult], Result | None, OnlineMatchResults]:
        # ct_md, results, matches, match_results
        if md is None or md.is_empty:
            logger.error("No metadata given to search online with!")
            res = Result(
                Action.save,
                status=Status.match_failure,
                original_path=ca.path,
                match_status=MatchStatus.no_match,
                tags_written=self.config.Runtime_Options__tags_write,
                tags_read=tags_read,
            )
            match_results.no_matches.append(res)
            return GenericMetadata(), [], res, match_results

        ii = IssueIdentifier(ca, self.config, self.current_talker())

        ii.set_output_function(functools.partial(self.output, already_logged=True))
        if not self.config.Auto_Tag__use_year_when_identifying:
            md.year = None
        if self.config.Auto_Tag__ignore_leading_numbers_in_filename and md.series is not None:
            md.series = re.sub(r"^([\d.]+)(.*)", r"\2", md.series)
        result, matches = ii.identify(ca, md)

        found_match = False
        choices = False
        low_confidence = False

        if result == IssueIdentifier.result_no_matches:
            pass
        elif result == IssueIdentifier.result_found_match_but_bad_cover_score:
            low_confidence = True
            found_match = True
        elif result == IssueIdentifier.result_found_match_but_not_first_page:
            found_match = True
        elif result == IssueIdentifier.result_multiple_matches_with_bad_image_scores:
            low_confidence = True
            choices = True
        elif result == IssueIdentifier.result_one_good_match:
            found_match = True
        elif result == IssueIdentifier.result_multiple_good_matches:
            choices = True

        if choices:
            if low_confidence:
                logger.error("Online search: Multiple low confidence matches. Save aborted")
                res = Result(
                    Action.save,
                    status=Status.match_failure,
                    original_path=ca.path,
                    online_results=matches,
                    match_status=MatchStatus.low_confidence_match,
                    tags_written=self.config.Runtime_Options__tags_write,
                    tags_read=tags_read,
                )
                match_results.low_confidence_matches.append(res)
                return GenericMetadata(), matches, res, match_results

            logger.error("Online search: Multiple good matches. Save aborted")
            res = Result(
                Action.save,
                status=Status.match_failure,
                original_path=ca.path,
                online_results=matches,
                match_status=MatchStatus.multiple_match,
                tags_written=self.config.Runtime_Options__tags_write,
                tags_read=tags_read,
            )
            match_results.multiple_matches.append(res)
            return GenericMetadata(), matches, res, match_results
        if low_confidence and self.config.Runtime_Options__abort_on_low_confidence:
            logger.error("Online search: Low confidence match. Save aborted")
            res = Result(
                Action.save,
                status=Status.match_failure,
                original_path=ca.path,
                online_results=matches,
                match_status=MatchStatus.low_confidence_match,
                tags_written=self.config.Runtime_Options__tags_write,
                tags_read=tags_read,
            )
            match_results.low_confidence_matches.append(res)
            return GenericMetadata(), matches, res, match_results
        if not found_match:
            logger.error("Online search: No match found. Save aborted")
            res = Result(
                Action.save,
                status=Status.match_failure,
                original_path=ca.path,
                online_results=matches,
                match_status=MatchStatus.no_match,
                tags_written=self.config.Runtime_Options__tags_write,
                tags_read=tags_read,
            )
            match_results.no_matches.append(res)
            return GenericMetadata(), matches, res, match_results

        # we got here, so we have a single match

        # now get the particular issue data
        ct_md = self.fetch_metadata(matches[0].issue_id)
        if ct_md.is_empty:
            res = Result(
                Action.save,
                status=Status.fetch_data_failure,
                original_path=ca.path,
                online_results=matches,
                match_status=MatchStatus.good_match,
                tags_written=self.config.Runtime_Options__tags_write,
                tags_read=tags_read,
            )
            match_results.fetch_data_failures.append(res)
            return GenericMetadata(), matches, res, match_results
        return ct_md, matches, None, match_results

    def save(self, ca: ComicArchive, match_results: OnlineMatchResults) -> tuple[Result, OnlineMatchResults]:
        if self.config.Runtime_Options__skip_existing_tags:
            for tag_id in self.config.Runtime_Options__tags_write:
                if ca.has_tags(tag_id):
                    self.output(f"{ca.path}: Already has {tags[tag_id].name()} tags. Not overwriting.")
                    return (
                        Result(
                            Action.save,
                            original_path=ca.path,
                            status=Status.existing_tags,
                            tags_written=self.config.Runtime_Options__tags_write,
                        ),
                        match_results,
                    )

        if self.batch_mode:
            self.output(f"Processing {utils.path_to_short_str(ca.path)}...")

        md, tags_read = self.create_local_metadata(ca, self.config.Runtime_Options__tags_read)
        if md.issue is None or md.issue == "":
            if self.config.Auto_Tag__assume_issue_one:
                md.issue = "1"

        matches: list[IssueResult] = []
        # now, search online

        ct_md = GenericMetadata()
        if self.config.Auto_Tag__online:
            if self.config.Auto_Tag__issue_id is not None:
                # we were given the actual issue ID to search with
                try:
                    ct_md = self.current_talker().fetch_comic_data(self.config.Auto_Tag__issue_id)
                except TalkerError as e:
                    logger.exception(f"Error retrieving issue details. Save aborted.\n{e}")
                    res = Result(
                        Action.save,
                        original_path=ca.path,
                        status=Status.fetch_data_failure,
                        tags_written=self.config.Runtime_Options__tags_write,
                        tags_read=tags_read,
                    )
                    match_results.fetch_data_failures.append(res)
                    return res, match_results

                if ct_md is None or ct_md.is_empty:
                    logger.error("No match for ID %s was found.", self.config.Auto_Tag__issue_id)
                    res = Result(
                        Action.save,
                        status=Status.match_failure,
                        original_path=ca.path,
                        match_status=MatchStatus.no_match,
                        tags_written=self.config.Runtime_Options__tags_write,
                        tags_read=tags_read,
                    )
                    match_results.no_matches.append(res)
                    return res, match_results

            else:
                qt_md = self.try_quick_tag(ca, md)
                if qt_md is None or qt_md.is_empty:
                    if qt_md is not None:
                        self.output("Failed to find match via quick tag")
                    ct_md, matches, res, match_results = self.normal_tag(ca, tags_read, md, match_results)  # type: ignore[assignment]
                    if res is not None:
                        return res, match_results
                else:
                    self.output("Successfully matched via quick tag")
                    ct_md = qt_md
                    matches = [
                        IssueResult(
                            series=ct_md.series or "",
                            distance=-1,
                            issue_number=ct_md.issue or "",
                            issue_count=ct_md.issue_count,
                            url_image_hash=-1,
                            issue_title=ct_md.title or "",
                            issue_id=ct_md.issue_id or "",
                            series_id=ct_md.issue_id or "",
                            month=ct_md.month,
                            year=ct_md.year,
                            publisher=None,
                            image_url=ct_md._cover_image or "",
                            alt_image_urls=[],
                            description=ct_md.description or "",
                        )
                    ]

        res = Result(
            Action.save,
            status=Status.success,
            original_path=ca.path,
            online_results=matches,
            match_status=MatchStatus.good_match,
            md=prepare_metadata(md, ct_md, self.config),
            tags_written=self.config.Runtime_Options__tags_write,
            tags_read=tags_read,
        )
        assert res.md
        # ok, done building our metadata. time to save
        if self.write_tags(ca, res.md):
            match_results.good_matches.append(res)
        else:
            res.status = Status.write_failure
            match_results.write_failures.append(res)
        return res, match_results

    def rename(self, ca: ComicArchive) -> Result:
        original_path = ca.path
        msg_hdr = ""
        if self.batch_mode:
            msg_hdr = f"{ca.path}: "

        md, tags_read = self.create_local_metadata(ca, self.config.Runtime_Options__tags_read)

        if md.series is None:
            logger.error(msg_hdr + "Can't rename without series name")
            return Result(Action.rename, Status.read_failure, original_path)

        new_ext = ""  # default
        if self.config.File_Rename__auto_extension:
            new_ext = ca.extension()

        renamer = FileRenamer(
            None,
            platform="universal" if self.config.File_Rename__strict_filenames else "auto",
            replacements=self.config.File_Rename__replacements,
        )
        renamer.set_metadata(md, ca.path.name)
        renamer.set_template(self.config.File_Rename__template)
        renamer.set_issue_zero_padding(self.config.File_Rename__issue_number_padding)
        renamer.set_smart_cleanup(self.config.File_Rename__use_smart_string_cleanup)
        renamer.move = self.config.File_Rename__move
        renamer.move_only = self.config.File_Rename__only_move

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
            return Result(Action.rename, Status.rename_failure, original_path, md=md)
        except Exception:
            logger.exception("Formatter failure: %s metadata: %s", self.config.File_Rename__template, renamer.metadata)
            return Result(Action.rename, Status.rename_failure, original_path, md=md)

        folder = get_rename_dir(ca, self.config.File_Rename__dir if self.config.File_Rename__move else None)

        full_path = folder / new_name

        if full_path == ca.path:
            self.output(msg_hdr + "Filename is already good!")
            return Result(Action.rename, Status.success, original_path, full_path, md=md)

        suffix = ""
        if not self.config.Runtime_Options__dryrun:
            # rename the file
            try:
                ca.rename(utils.unique_file(full_path))
            except OSError:
                logger.exception("Failed to rename comic archive: %s", ca.path)
                return Result(Action.rename, Status.write_failure, original_path, full_path, md=md)
        else:
            suffix = " (dry-run, no change)"

        self.output(f"renamed '{original_path.name}' -> '{new_name}' {suffix}")
        return Result(Action.rename, Status.success, original_path, tags_read=tags_read, md=md)

    def export(self, ca: ComicArchive) -> Result:
        msg_hdr = ""
        if self.batch_mode:
            msg_hdr = f"{ca.path}: "

        if ca.is_zip():
            logger.error(msg_hdr + "Archive is already a zip file.")
            return Result(Action.export, Status.success, ca.path)

        filename_path = ca.path
        new_file = filename_path.with_suffix(".cbz")

        if self.config.Runtime_Options__abort_on_conflict and new_file.exists():
            self.output(msg_hdr + f"{new_file.name} already exists in the that folder.")
            return Result(Action.export, Status.write_failure, ca.path)

        new_file = utils.unique_file(new_file)

        delete_success = False
        export_success = False
        if not self.config.Runtime_Options__dryrun:
            if ca.export_as_zip(new_file):
                export_success = True
                if self.config.Runtime_Options__delete_original:
                    try:
                        filename_path.unlink(missing_ok=True)
                        delete_success = True
                    except OSError:
                        logger.exception(msg_hdr + "Error deleting original archive after export")
            else:
                # last export failed, so remove the zip, if it exists
                new_file.unlink(missing_ok=True)
        else:
            msg = msg_hdr + f"Dry-run:  Would try to create {os.path.split(new_file)[1]}"
            if self.config.Runtime_Options__delete_original:
                msg += " and delete original."
            self.output(msg)
            return Result(Action.export, Status.success, ca.path, new_file)

        msg = msg_hdr
        if export_success:
            msg += f"Archive exported successfully to: {os.path.split(new_file)[1]}"
            if self.config.Runtime_Options__delete_original and delete_success:
                msg += " (Original deleted) "
        else:
            msg += "Archive failed to export!"

        self.output(msg)

        return Result(Action.export, Status.success, ca.path, new_file)

    def process_file_cli(
        self, command: Action, filename: str, match_results: OnlineMatchResults
    ) -> tuple[Result, OnlineMatchResults]:
        if not os.path.lexists(filename):
            logger.error("Cannot find %s", filename)
            return Result(command, Status.read_failure, pathlib.Path(filename)), match_results

        ca = ComicArchive(filename, str(graphics_path / "nocover.png"))

        if not ca.seems_to_be_a_comic_archive():
            logger.error("Sorry, but %s is not a comic archive!", filename)
            return Result(Action.rename, Status.read_failure, ca.path), match_results

        if not ca.is_writable() and (command in (Action.delete, Action.copy, Action.save, Action.rename)):
            logger.error("This archive is not writable")
            return Result(command, Status.write_permission_failure, ca.path), match_results

        if command == Action.print:
            return self.print(ca), match_results

        elif command == Action.delete:
            return self.delete(ca), match_results

        elif command == Action.copy is not None:
            return self.copy(ca), match_results

        elif command == Action.save:
            return self.save(ca, match_results)

        elif command == Action.rename:
            return self.rename(ca), match_results

        elif command == Action.export:
            return self.export(ca), match_results
        return Result(None, Status.read_failure, ca.path), match_results  # type: ignore[arg-type]
