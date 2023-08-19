"""A PyQT4 dialog to select specific issue from list"""
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

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import new_web_view, reduce_widget_font_size
from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class IssueNumberTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other: object) -> bool:
        assert isinstance(other, QtWidgets.QTableWidgetItem)
        self_str: str = self.data(QtCore.Qt.ItemDataRole.DisplayRole)
        other_str: str = other.data(QtCore.Qt.ItemDataRole.DisplayRole)
        return (IssueString(self_str).as_float() or 0) < (IssueString(other_str).as_float() or 0)


class IssueSelectionWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        config: ct_ns,
        talker: ComicTalker,
        series_id: str,
        issue_number: str,
    ) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "issueselectionwindow.ui", self)

        self.coverWidget = CoverImageWidget(
            self.coverImageContainer, CoverImageWidget.AltCoverMode, config.runtime_config.user_cache_dir, talker
        )
        gridlayout = QtWidgets.QGridLayout(self.coverImageContainer)
        gridlayout.addWidget(self.coverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.teDescription: QtWidgets.QWidget
        webengine = new_web_view(self)
        if webengine:
            self.teDescription.hide()
            self.teDescription.deleteLater()
            # I don't know how to replace teDescription, this is the result of teDescription.height() once rendered
            webengine.resize(webengine.width(), 141)
            self.splitter.addWidget(webengine)
            self.teDescription = webengine
            logger.info("successfully loaded QWebEngineView")
        else:
            logger.info("failed to open QWebEngineView")

        reduce_widget_font_size(self.twList)
        reduce_widget_font_size(self.teDescription, 1)

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.series_id = series_id
        self.issue_id: str = ""
        self.config = config
        self.talker = talker
        self.url_fetch_thread = None
        self.issue_list: list[GenericMetadata] = []

        # Display talker logo and set url
        self.lblIssuesSourceName.setText(talker.attribution)

        self.imageIssuesSourceWidget = CoverImageWidget(
            self.imageIssuesSourceLogo,
            CoverImageWidget.URLMode,
            config.runtime_config.user_cache_dir,
            talker,
            False,
        )
        self.imageIssuesSourceWidget.showControls = False
        gridlayoutIssuesSourceLogo = QtWidgets.QGridLayout(self.imageIssuesSourceLogo)
        gridlayoutIssuesSourceLogo.addWidget(self.imageIssuesSourceWidget)
        gridlayoutIssuesSourceLogo.setContentsMargins(0, 2, 0, 0)
        self.imageIssuesSourceWidget.set_url(talker.logo_url)

        if issue_number is None or issue_number == "":
            self.issue_number = "1"
        else:
            self.issue_number = issue_number

        self.initial_id: str = ""
        self.perform_query()

        self.twList.resizeColumnsToContents()
        self.twList.currentItemChanged.connect(self.current_item_changed)
        self.twList.cellDoubleClicked.connect(self.cell_double_clicked)

        # now that the list has been sorted, find the initial record, and
        # select it
        if not self.initial_id:
            self.twList.selectRow(0)
        else:
            for r in range(0, self.twList.rowCount()):
                issue_id = self.twList.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
                if issue_id == self.initial_id:
                    self.twList.selectRow(r)
                    break

        self.leFilter.textChanged.connect(self.filter)

    def filter(self, text: str) -> None:
        rows = set(range(self.twList.rowCount()))
        for r in rows:
            self.twList.showRow(r)
        if text.strip():
            shown_rows = {x.row() for x in self.twList.findItems(text, QtCore.Qt.MatchFlag.MatchContains)}
            for r in rows - shown_rows:
                self.twList.hideRow(r)

    def perform_query(self) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))

        try:
            self.issue_list = self.talker.fetch_issues_in_series(self.series_id)
        except TalkerError as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            QtWidgets.QMessageBox.critical(self, f"{e.source} {e.code_name} Error", f"{e}")
            return

        self.twList.setRowCount(0)

        self.twList.setSortingEnabled(False)

        for row, issue in enumerate(self.issue_list):
            self.twList.insertRow(row)

            item_text = issue.issue or ""
            item = IssueNumberTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, issue.issue_id)
            item.setData(QtCore.Qt.ItemDataRole.DisplayRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, item)

            item_text = ""
            if issue.year is not None:
                item_text = f"{issue.year:04}"
            if issue.month is not None:
                item_text = f"{issue.month:02}"

            qtw_item = QtWidgets.QTableWidgetItem(item_text)
            qtw_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            qtw_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, qtw_item)

            item_text = issue.title or ""
            qtw_item = QtWidgets.QTableWidgetItem(item_text)
            qtw_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            qtw_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, qtw_item)

            if IssueString(issue.issue).as_string().casefold() == IssueString(self.issue_number).as_string().casefold():
                self.initial_id = issue.issue_id or ""

        self.twList.setSortingEnabled(True)
        self.twList.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)

        QtWidgets.QApplication.restoreOverrideCursor()

    def cell_double_clicked(self, r: int, c: int) -> None:
        self.accept()

    def set_description(self, widget: QtWidgets.QWidget, text: str) -> None:
        if isinstance(widget, QtWidgets.QTextEdit):
            widget.setText(text.replace("</figure>", "</div>").replace("<figure", "<div"))
        else:
            html = text
            widget.setHtml(html, QtCore.QUrl(self.talker.website))

    def current_item_changed(self, curr: QtCore.QModelIndex | None, prev: QtCore.QModelIndex | None) -> None:
        if curr is None:
            return
        if prev is not None and prev.row() == curr.row():
            return

        self.issue_id = self.twList.item(curr.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)

        # list selection was changed, update the the issue cover
        issue = self.issue_list[curr.row()]
        if not all((issue.issue, issue.year, issue.month, issue.cover_image)):  # issue.title, issue.description
            issue = self.talker.fetch_comic_data(issue_id=self.issue_id)
        self.issue_number = issue.issue or ""
        self.coverWidget.set_issue_details(self.issue_id, [issue.cover_image or "", *issue.alternate_images])
        if issue.description is None:
            self.set_description(self.teDescription, "")
        else:
            self.set_description(self.teDescription, issue.description)
