"""A PyQT4 dialog to show ID log and progress"""

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

import logging
import pathlib
import re

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comictalker.comictalker import ComicTalker, RLCallBack

from . import ctversion
from .coverimagewidget import CoverImageWidget
from .ctsettings.settngs_namespace import SettngsNS
from .issueidentifier import IssueIdentifierCancelled
from .md import read_selected_tags
from .optionalmsgdialog import OptionalMessageDialog
from .resulttypes import Action, OnlineMatchResults, Result, Status
from .tag import identify_comic
from .ui import ui_path

logger = logging.getLogger(__name__)


class AutoTagThread(QtCore.QThread):  # TODO: re-check thread semantics. Specifically with signals
    autoTagComplete = QtCore.pyqtSignal(OnlineMatchResults, list)
    autoTagLogMsg = QtCore.pyqtSignal(str)
    autoTagProgress = QtCore.pyqtSignal(object, object, object, bytes, bytes)  # see progress_callback
    ratelimit = QtCore.pyqtSignal(float, float)

    def __init__(
        self,
        series_override: str,
        ca_list: list[ComicArchive],
        config: SettngsNS,
        talker: ComicTalker,
    ) -> None:
        QtCore.QThread.__init__(self)
        self.series_override = series_override
        self.ca_list = ca_list
        self.config = config
        self.talker = talker
        self.canceled = False

    def log_output(self, text: str) -> None:
        if self.canceled:
            raise IssueIdentifierCancelled
        self.autoTagLogMsg.emit(str(text))

    def progress_callback(
        self, cur: int | None, total: int | None, path: pathlib.Path | None, archive_image: bytes, remote_image: bytes
    ) -> None:
        self.autoTagProgress.emit(cur, total, path, archive_image, remote_image)

    def run(self) -> None:
        match_results = OnlineMatchResults()
        archives_to_remove = []
        try:
            for prog_idx, ca in enumerate(self.ca_list):
                if self.canceled:
                    return
                self.log_output("==========================================================================\n")
                self.log_output(f"Auto-Tagging {prog_idx} of {len(self.ca_list)}\n")
                self.log_output(f"{ca.path}\n")
                try:
                    cover_idx = ca.read_tags(self.config.Runtime_Options__tags_read[0]).get_cover_page_index_list()[0]
                except Exception as e:
                    cover_idx = 0
                    logger.debug(
                        "Failed to load metadata for %s: %s", ca.path, e
                    )  # This is only used for progress callback
                image_data = ca.get_page(cover_idx)
                self.progress_callback(prog_idx, len(self.ca_list), ca.path, image_data, b"")
                if self.canceled:
                    return

                if ca.is_writable():
                    success, match_results = self.identify_and_tag_single_archive(ca, match_results)
                    if self.canceled:
                        return

                    if success and self.config.internal__remove_archive_after_successful_match:
                        archives_to_remove.append(ca)
        finally:
            self.autoTagComplete.emit(match_results, archives_to_remove)

    def on_rate_limit(self, full_time: float, sleep_time: float) -> None:
        if self.canceled:
            raise IssueIdentifierCancelled
        self.log_output(
            f"Rate limit reached: {full_time:.0f}s until next request. Waiting {sleep_time:.0f}s for ratelimit"
        )
        self.ratelimit.emit(full_time, sleep_time)

    def identify_and_tag_single_archive(
        self, ca: ComicArchive, match_results: OnlineMatchResults
    ) -> tuple[Result, OnlineMatchResults]:

        ratelimit_callback = RLCallBack(
            self.on_rate_limit,
            60,
        )

        # read in tags, and parse file name if not there
        md, tags_used, error = read_selected_tags(
            self.config.Runtime_Options__tags_read,
            ca,
            self.config.Metadata_Options__tag_merge,
            self.config.Metadata_Options__tag_merge_lists,
        )
        if error is not None:
            OptionalMessageDialog.critical(
                None,
                "Aborting...",
                f"One or more of the read tags failed to load for {ca.path}. Aborting to prevent any possible further damage. Check log for details.",
            )
            logger.error("Failed to load tags from %s: %s", ca.path, error)
            return (
                Result(
                    Action.save,
                    original_path=ca.path,
                    status=Status.read_failure,
                ),
                match_results,
            )

        if md.is_empty:
            md = ca.metadata_from_filename(
                self.config.Filename_Parsing__filename_parser,
                self.config.Filename_Parsing__remove_c2c,
                self.config.Filename_Parsing__remove_fcbd,
                self.config.Filename_Parsing__remove_publisher,
                self.config.Filename_Parsing__split_words,
                self.config.Filename_Parsing__allow_issue_start_with_letter,
                self.config.Filename_Parsing__protofolius_issue_number_scheme,
            )
            if self.config.Auto_Tag__ignore_leading_numbers_in_filename and md.series is not None:
                # remove all leading numbers
                md.series = re.sub(r"(^[\d.]*)(.*)", r"\2", md.series)

        # use the dialog specified search string
        if self.series_override:
            md.series = self.series_override

        if not self.config.Auto_Tag__use_year_when_identifying:
            md.year = None
        # If it's empty we need it to stay empty for identify_comic to report the correct error
        if (md.issue is None or md.issue == "") and not md.is_empty:
            if self.config.Auto_Tag__assume_issue_one:
                md.issue = "1"
            else:
                md.issue = utils.xlate(md.volume)

        def on_progress(x: int, y: int, image: bytes) -> None:
            # We don't (currently) care about the progress of an individual comic here we just want the cover for the autotagprogresswindow
            self.progress_callback(None, None, None, b"", image)

        if self.canceled:
            return (
                Result(
                    Action.save,
                    original_path=ca.path,
                    status=Status.read_failure,
                ),
                match_results,
            )

        try:
            res, match_results = identify_comic(
                ca,
                md,
                tags_used,
                match_results,
                self.config,
                self.talker,
                self.log_output,
                on_rate_limit=ratelimit_callback,
                on_progress=on_progress,
            )
        except IssueIdentifierCancelled:
            return (
                Result(
                    Action.save,
                    original_path=ca.path,
                    status=Status.fetch_data_failure,
                ),
                match_results,
            )
        if self.canceled:
            return res, match_results

        if res.status == Status.success:
            assert res.md

            def write_tags(ca: ComicArchive, md: GenericMetadata) -> bool:
                for tag in self.config.Runtime_Options__tags_write:
                    res.tags_written.append(tag.id)
                    # write out the new data
                    try:
                        ca.write_tags(ctversion.version, md, tag)  # TODO: Put proper version in
                    except Exception as e:
                        self.log_output(f"{tag.name} save failed! {e}\nAborting any additional tag saves.\n")

                        return False
                return True

            # Save tags
            if write_tags(ca, res.md):
                match_results.good_matches.append(res)
                self.log_output("Save complete!\n")
            else:
                res.status = Status.write_failure
                match_results.write_failures.append(res)

            ca.reset_cache()

        return res, match_results

    def cancel(self) -> None:
        self.canceled = True


class AutoTagProgressWindow(QtWidgets.QDialog):
    cancel = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget, talker: ComicTalker) -> None:
        super().__init__(parent)

        with (ui_path / "autotagprogresswindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.lblSourceName.setText(talker.attribution)

        self.archiveCoverWidget = CoverImageWidget(self.archiveCoverContainer, CoverImageWidget.DataMode, None, False)
        gridlayout = QtWidgets.QGridLayout(self.archiveCoverContainer)
        gridlayout.addWidget(self.archiveCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.testCoverWidget = CoverImageWidget(self.testCoverContainer, CoverImageWidget.DataMode, None, False)
        gridlayout = QtWidgets.QGridLayout(self.testCoverContainer)
        gridlayout.addWidget(self.testCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    def set_archive_image(self, img_data: bytes) -> None:
        self.set_cover_image(img_data, self.archiveCoverWidget)

    def set_test_image(self, img_data: bytes) -> None:
        self.set_cover_image(img_data, self.testCoverWidget)

    def set_cover_image(self, img_data: bytes, widget: CoverImageWidget) -> None:
        widget.set_image_data(img_data)
        QtCore.QCoreApplication.processEvents()

    # @QtCore.pyqtSlot(int, int, 'Optional[pathlib.Path]', bytes, bytes)
    def on_progress(
        self, x: int | None, y: int | None, title: pathlib.Path | None, archive_image: bytes, remote_image: bytes
    ) -> None:
        if x is not None and y is not None:
            self.progressBar: QtWidgets.QProgressBar
            self.progressBar.setValue(x)
            self.progressBar.setMaximum(y)
        if title:
            self.setWindowTitle(str(title))
        if archive_image:
            self.set_archive_image(archive_image)
        if remote_image:
            self.set_test_image(remote_image)

    def reject(self) -> None:
        self.cancel.emit()
