"""A PyQT4 dialog to select from automated issue matches"""

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
import os

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from comicapi.comicarchive import ComicArchive, tags
from comicapi.utils import PublisherManager
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.md import prepare_metadata, read_selected_tags
from comictaggerlib.optionalmsgdialog import OptionalMessageDialog
from comictaggerlib.resulttypes import IssueResult, Result
from comictaggerlib.ui import ui_path
from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class AutoTagMatchWindow(QtWidgets.QDialog):
    matched_files = QtCore.pyqtSignal(list)

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        match_set_list: list[tuple[Result, ComicArchive]],
        config: ct_ns,
        talker: ComicTalker,
        publishers: PublisherManager,
    ) -> None:
        super().__init__(parent)

        with (ui_path / "matchselectionwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.config: ct_ns = config
        self.publishers = publishers
        self.matched_comics: list[ComicArchive] = []

        self.current_match_set: tuple[Result, ComicArchive] = match_set_list[0]

        self.altCoverWidget = CoverImageWidget(
            self.altCoverContainer, CoverImageWidget.AltCoverMode, config.Runtime_Options__config.user_cache_dir
        )
        gridlayout = QtWidgets.QGridLayout(self.altCoverContainer)
        gridlayout.addWidget(self.altCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.archiveCoverWidget = CoverImageWidget(self.archiveCoverContainer, CoverImageWidget.ArchiveMode, None)
        gridlayout = QtWidgets.QGridLayout(self.archiveCoverContainer)
        gridlayout.addWidget(self.archiveCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.skipButton = QtWidgets.QPushButton("Skip to Next")
        self.buttonBox.addButton(self.skipButton, QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Accept and Write Tags")

        self.match_set_list = match_set_list
        self.talker = talker

        self.current_match_set_idx = 0

        self.twList.currentItemChanged.connect(self.current_item_changed)
        self.twList.cellDoubleClicked.connect(self.cell_double_clicked)
        self.skipButton.clicked.connect(self.skip_to_next)

        self.update_data()
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)
        self.finished.connect(self.comic_list_emit)

    def comic_list_emit(self) -> None:
        self.matched_files.emit(self.matched_comics.copy())
        self.matched_comics = []

    def update_data(self) -> None:
        self.current_match_set = self.match_set_list[self.current_match_set_idx]

        if self.current_match_set_idx + 1 == len(self.match_set_list):
            self.skipButton.setText("Skip")

        self.set_cover_image()
        self.populate_table()
        self.twList.resizeColumnsToContents()
        self.twList.selectRow(0)

        path = self.current_match_set[0].original_path
        self.setWindowTitle(
            "Select correct match or skip ({} of {}): {}".format(
                self.current_match_set_idx + 1,
                len(self.match_set_list),
                os.path.split(path)[1],
            )
        )

    def populate_table(self) -> None:
        if not self.current_match_set:
            return

        self.twList.setRowCount(0)

        self.twList.setSortingEnabled(False)

        for row, match in enumerate(self.current_match_set[0].online_results):
            self.twList.insertRow(row)

            item_text = match.series.name
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, (match,))
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, item)

            if match.series.publisher is not None:
                item_text = str(match.series.publisher)
            else:
                item_text = "Unknown"
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, item)

            month_str = ""
            year_str = "????"
            if match.md.month is not None:
                month_str = f"-{int(match.md.month):02d}"
            if match.md.year is not None:
                year_str = str(match.md.year)

            item_text = year_str + month_str
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, item)

            item_text = match.md.title or ""
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 3, item)

        self.twList.resizeColumnsToContents()
        self.twList.setSortingEnabled(True)
        self.twList.sortItems(2, QtCore.Qt.SortOrder.AscendingOrder)
        self.twList.selectRow(0)
        self.twList.resizeColumnsToContents()
        self.twList.horizontalHeader().setStretchLastSection(True)

    def cell_double_clicked(self, r: int, c: int) -> None:
        self.accept()

    def current_item_changed(self, curr: QtCore.QModelIndex, prev: QtCore.QModelIndex) -> None:
        if curr is None:
            return None
        if prev is not None and prev.row() == curr.row():
            return None

        match = self.current_match()
        assert match.md.issue_id
        self.altCoverWidget.set_issue_details(
            match.md.issue_id, [x.URL for x in [match.md._cover_image, *match.md._alternate_images] if x]
        )
        if match.md.description is None:
            self.teDescription.setText("")
        else:
            self.teDescription.setText(match.md.description)

    def set_cover_image(self) -> None:
        self.archiveCoverWidget.set_archive(self.current_match_set[1])

    def current_match(self) -> IssueResult:
        row = self.twList.currentRow()
        match: IssueResult = self.twList.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)[0]
        return match

    def accept(self) -> None:
        self.save_match()
        self.current_match_set_idx += 1

        if self.current_match_set_idx == len(self.match_set_list):
            # no more items
            QtWidgets.QDialog.accept(self)
        else:
            self.update_data()

    def skip_to_next(self) -> None:
        self.current_match_set_idx += 1

        if self.current_match_set_idx == len(self.match_set_list):
            # no more items
            QtWidgets.QDialog.reject(self)
        else:
            self.update_data()

    def reject(self) -> None:
        qmsg = OptionalMessageDialog.msg_no_checkbox(
            self,
            "Cancel Matching",
            "Are you sure you wish to cancel the matching process?",
            icon=OptionalMessageDialog.Icon.Warning,
        )
        qmsg.accepted.connect(self._cancel)
        qmsg.show()

    def _cancel(self) -> None:
        QtWidgets.QDialog.reject(self)

    def save_match(self) -> None:
        match = self.current_match()
        ca = self.current_match_set[1]
        md, _, error = read_selected_tags(
            self.config.Runtime_Options__tags_read,
            ca,
            self.config.Metadata_Options__tag_merge,
            self.config.Metadata_Options__tag_merge_lists,
        )
        if error is not None:
            logger.error("Failed to load tags for %s: %s", ca.path, error)

            QtWidgets.QApplication.restoreOverrideCursor()
            OptionalMessageDialog.critical(
                self,
                "Read Failed!",
                f"One or more of the read tags failed to load for {ca.path}, check log for details",
            )
            return

        if md.is_empty:
            md = ca.metadata_from_filename(
                self.config.Filename_Parsing__filename_parser,
                self.config.Filename_Parsing__remove_c2c,
                self.config.Filename_Parsing__remove_fcbd,
                self.config.Filename_Parsing__remove_publisher,
                self.config.Filename_Parsing__split_words,
                self.config.Filename_Parsing__allow_issue_start_with_letter,
                self.config.Filename_Parsing__protofolius_issue_number_scheme,
                publishers=self.publishers.publishers,
            )

        # now get the particular issue data

        try:
            assert match.md.issue_id
            self.current_match_set[0].md = ct_md = self.talker.fetch_comic_data(issue_id=match.md.issue_id)
        except TalkerError as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            OptionalMessageDialog.critical(self, f"{e.source} {e.code_name} Error", str(e))
            return

        if ct_md is None or ct_md.is_empty:
            OptionalMessageDialog.critical(self, "Network Issue", "Could not retrieve issue details!")
            return

        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        md = prepare_metadata(md, ct_md, self.publishers, self.config)
        for tag_id in self.config.Runtime_Options__tags_write:
            success = ca.write_tags(md, tag_id)
            QtWidgets.QApplication.restoreOverrideCursor()
            if not success:
                OptionalMessageDialog.warning(
                    self,
                    "Write Error",
                    f"Saving {tags[tag_id].name()} the tags to the archive seemed to fail!",
                )
                break
        self.matched_comics.append(ca)

        ca.reset_cache()
