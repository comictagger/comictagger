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
from typing import Callable

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comicapi.comicarchive import ComicArchive, metadata_styles
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.resulttypes import IssueResult, Result
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import reduce_widget_font_size
from comictalker.comictalker import ComicTalker

logger = logging.getLogger(__name__)


class AutoTagMatchWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        match_set_list: list[Result],
        styles: list[str],
        fetch_func: Callable[[IssueResult], GenericMetadata],
        config: ct_ns,
        talker: ComicTalker,
    ) -> None:
        super().__init__(parent)

        with (ui_path / "matchselectionwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.config = config

        self.current_match_set: Result = match_set_list[0]

        self.altCoverWidget = CoverImageWidget(
            self.altCoverContainer, CoverImageWidget.AltCoverMode, config.Runtime_Options__config.user_cache_dir, talker
        )
        gridlayout = QtWidgets.QGridLayout(self.altCoverContainer)
        gridlayout.addWidget(self.altCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.archiveCoverWidget = CoverImageWidget(self.archiveCoverContainer, CoverImageWidget.ArchiveMode, None, None)
        gridlayout = QtWidgets.QGridLayout(self.archiveCoverContainer)
        gridlayout.addWidget(self.archiveCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        reduce_widget_font_size(self.twList)
        reduce_widget_font_size(self.teDescription, 1)

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
        self._styles = styles
        self.fetch_func = fetch_func

        self.current_match_set_idx = 0

        self.twList.currentItemChanged.connect(self.current_item_changed)
        self.twList.cellDoubleClicked.connect(self.cell_double_clicked)
        self.skipButton.clicked.connect(self.skip_to_next)

        self.update_data()

    def update_data(self) -> None:
        self.current_match_set = self.match_set_list[self.current_match_set_idx]

        if self.current_match_set_idx + 1 == len(self.match_set_list):
            self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setDisabled(True)
            self.skipButton.setText("Skip")

        self.set_cover_image()
        self.populate_table()
        self.twList.resizeColumnsToContents()
        self.twList.selectRow(0)

        path = self.current_match_set.original_path
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

        for row, match in enumerate(self.current_match_set.online_results):
            self.twList.insertRow(row)

            item_text = match.series
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, (match,))
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, item)

            if match.publisher is not None:
                item_text = str(match.publisher)
            else:
                item_text = "Unknown"
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, item)

            month_str = ""
            year_str = "????"
            if match.month is not None:
                month_str = f"-{int(match.month):02d}"
            if match.year is not None:
                year_str = str(match.year)

            item_text = year_str + month_str
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, item)

            item_text = match.issue_title
            if item_text is None:
                item_text = ""
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
        self.altCoverWidget.set_issue_details(match.issue_id, [match.image_url, *match.alt_image_urls])
        if match.description is None:
            self.teDescription.setText("")
        else:
            self.teDescription.setText(match.description)

    def set_cover_image(self) -> None:
        ca = ComicArchive(self.current_match_set.original_path)
        self.archiveCoverWidget.set_archive(ca)

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
        reply = QtWidgets.QMessageBox.question(
            self,
            "Cancel Matching",
            "Are you sure you wish to cancel the matching process?",
            QtWidgets.QMessageBox.StandardButton.Yes,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.No:
            return

        QtWidgets.QDialog.reject(self)

    def save_match(self) -> None:
        match = self.current_match()
        ca = ComicArchive(self.current_match_set.original_path)

        md = ca.read_metadata(self.config.internal__load_data_style)
        if md.is_empty:
            md = ca.metadata_from_filename(
                self.config.Filename_Parsing__complicated_parser,
                self.config.Filename_Parsing__remove_c2c,
                self.config.Filename_Parsing__remove_fcbd,
                self.config.Filename_Parsing__remove_publisher,
            )

        # now get the particular issue data
        self.current_match_set.md = ct_md = self.fetch_func(match)
        if ct_md is None:
            QtWidgets.QMessageBox.critical(self, "Network Issue", "Could not retrieve issue details!")
            return

        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        md.overlay(ct_md)
        for style in self._styles:
            success = ca.write_metadata(md, style)
            QtWidgets.QApplication.restoreOverrideCursor()
            if not success:
                QtWidgets.QMessageBox.warning(self, "Write Error", "Saving the tags to the archive seemed to fail!")

        ca.load_cache(list(metadata_styles))
