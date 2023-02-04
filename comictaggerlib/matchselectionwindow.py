"""A PyQT4 dialog to select from automated issue matches"""
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

import logging
import os

import settngs
from PyQt5 import QtCore, QtWidgets, uic

from comicapi.comicarchive import ComicArchive
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.resulttypes import IssueResult
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import reduce_widget_font_size
from comictalker.comictalker import ComicTalker

logger = logging.getLogger(__name__)


class MatchSelectionWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        matches: list[IssueResult],
        comic_archive: ComicArchive,
        config: settngs.Namespace,
        talker: ComicTalker,
    ) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "matchselectionwindow.ui", self)

        self.altCoverWidget = CoverImageWidget(
            self.altCoverContainer, CoverImageWidget.AltCoverMode, config.runtime_config.user_cache_dir, talker
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

        self.matches: list[IssueResult] = matches
        self.comic_archive = comic_archive

        self.twList.currentItemChanged.connect(self.current_item_changed)
        self.twList.cellDoubleClicked.connect(self.cell_double_clicked)

        self.update_data()

    def update_data(self) -> None:
        self.set_cover_image()
        self.populate_table()
        self.twList.resizeColumnsToContents()
        self.twList.selectRow(0)

        path = self.comic_archive.path
        self.setWindowTitle(f"Select correct match: {os.path.split(path)[1]}")

    def populate_table(self) -> None:
        self.twList.setRowCount(0)

        self.twList.setSortingEnabled(False)

        row = 0
        for match in self.matches:
            self.twList.insertRow(row)

            item_text = match["series"]
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, (match,))
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, item)

            if match["publisher"] is not None:
                item_text = str(match["publisher"])
            else:
                item_text = "Unknown"
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, item)

            month_str = ""
            year_str = "????"
            if match["month"] is not None:
                month_str = f"-{int(match['month']):02d}"
            if match["year"] is not None:
                year_str = str(match["year"])

            item_text = year_str + month_str
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, item)

            item_text = match["issue_title"]
            if item_text is None:
                item_text = ""
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 3, item)

            row += 1

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
            return
        if prev is not None and prev.row() == curr.row():
            return

        self.altCoverWidget.set_issue_details(
            self.current_match()["issue_id"],
            [self.current_match()["image_url"], *self.current_match()["alt_image_urls"]],
        )
        if self.current_match()["description"] is None:
            self.teDescription.setText("")
        else:
            self.teDescription.setText(self.current_match()["description"])

    def set_cover_image(self) -> None:
        self.archiveCoverWidget.set_archive(self.comic_archive)

    def current_match(self) -> IssueResult:
        row = self.twList.currentRow()
        match: IssueResult = self.twList.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)[0]
        return match
