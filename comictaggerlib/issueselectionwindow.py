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
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictalker.comictalker import ComicTalker, RLCallBack, TalkerError

from .coverimagewidget import CoverImageWidget
from .ctsettings import ct_ns
from .seriesselectionwindow import SelectionWindow
from .ui import ui_path
from .ui.qtutils import center_window_on_parent

if TYPE_CHECKING:
    from PyQt6.QtWebEngineWidgets import QWebEngineView


logger = logging.getLogger(__name__)


class IssueNumberTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other: object) -> bool:
        assert isinstance(other, QtWidgets.QTableWidgetItem)
        self_str: str = self.data(QtCore.Qt.ItemDataRole.DisplayRole)
        other_str: str = other.data(QtCore.Qt.ItemDataRole.DisplayRole)
        return (IssueString(self_str).as_float() or 0) < (IssueString(other_str).as_float() or 0)


class QueryThread(QtCore.QThread):  # TODO: Evaluate thread semantics. Specifically with signals
    finish = QtCore.pyqtSignal(list)
    ratelimit = QtCore.pyqtSignal(float, float)

    def __init__(
        self,
        talker: ComicTalker,
        series_id: str,
    ) -> None:
        super().__init__()
        self.series_id = series_id
        self.talker = talker

    def run(self) -> None:

        try:
            issue_list = [
                x
                for x in self.talker.fetch_issues_in_series(
                    self.series_id, on_rate_limit=RLCallBack(lambda x, y: self.ratelimit.emit(x, y), 10)
                )
                if x.issue_id is not None
            ]
        except TalkerError as e:
            logger.exception("Failed to retrieve issue list: %s", e)
            return

        self.finish.emit(issue_list)


class IssueSelectionWindow(SelectionWindow):
    ui_file = ui_path / "issueselectionwindow.ui"
    CoverImageMode = CoverImageWidget.AltCoverMode
    finish = QtCore.pyqtSignal(list)

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        config: ct_ns,
        talker: ComicTalker,
        series_id: str = "",
        issue_number: str = "",
    ) -> None:
        super().__init__(parent, config, talker)
        self.series_id = series_id
        self.issue_list: dict[str, GenericMetadata] = {}

        self.issue_number = issue_number
        if issue_number is None or issue_number == "":
            self.issue_number = "1"

        self.initial_id: str = ""
        self.leFilter.textChanged.connect(self.filter)
        self.finish.connect(self.query_finished)
        self.prog_dialog = None

    def perform_query(self) -> None:  # type: ignore[override]
        if self.prog_dialog:
            self.prog_dialog.deleteLater()
        self.prog_dialog = QtWidgets.QProgressDialog("Retrieving issues", "Cancel", 0, 100, self)
        assert self.prog_dialog  # Silence mypy
        self.prog_dialog.setWindowTitle("Retrieving issues")
        self.prog_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.prog_dialog.setMinimumDuration(1000)
        center_window_on_parent(self.prog_dialog)
        self.prog_dialog.show()

        self.querythread = QueryThread(
            self.talker,
            self.series_id,
        )
        self.querythread.finish.connect(self.finish)
        self.querythread.finish.connect(self.prog_dialog.close)
        self.querythread.ratelimit.connect(self.ratelimit)
        self.querythread.start()

    def query_finished(self, issues: list[GenericMetadata]) -> None:
        self.twList.setRowCount(0)

        self.twList.setSortingEnabled(False)
        self.issue_list = {i.issue_id: i for i in issues if i.issue_id is not None}
        self.twList.clear()
        for row, issue in enumerate(issues):
            self.twList.insertRow(row)
            self.twList.setItem(row, 0, IssueNumberTableWidgetItem())
            self.twList.setItem(row, 1, QtWidgets.QTableWidgetItem())
            self.twList.setItem(row, 2, QtWidgets.QTableWidgetItem())

            self.update_row(row, issue)

            if IssueString(issue.issue).as_string().casefold() == IssueString(self.issue_number).as_string().casefold():
                self.initial_id = issue.issue_id or ""

        self.twList.setSortingEnabled(True)
        self.twList.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)
        self.twList: QtWidgets.QTableWidget
        if self.initial_id:
            for r in range(0, self.twList.rowCount()):
                item = self.twList.item(r, 0)
                issue_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if issue_id == self.initial_id:
                    self.twList.selectRow(r)
                    self.twList.scrollToItem(item, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)
                    break
        self.show()

    def cell_double_clicked(self, r: int, c: int) -> None:
        self.accept()

    def set_description(self, widget: QtWidgets.QTextEdit | QWebEngineView, text: str) -> None:
        if isinstance(widget, QtWidgets.QTextEdit):
            widget.setText(text.replace("</figure>", "</div>").replace("<figure", "<div"))
        else:
            widget.setContent(text.encode("utf-8"), "text/html;charset=UTF-8", QtCore.QUrl(self.talker.website))

    def update_row(self, row: int, issue: GenericMetadata) -> None:  # type: ignore[override]
        self.twList.setStyleSheet(self.twList.styleSheet())
        item_text = issue.issue or ""
        item = self.twList.item(row, 0)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, issue.issue_id)
        item.setData(QtCore.Qt.ItemDataRole.DisplayRole, item_text)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        item_text = ""
        if issue.year is not None:
            item_text += f"-{issue.year:04}"
        if issue.month is not None:
            item_text += f"-{issue.month:02}"

        qtw_item = self.twList.item(row, 1)
        qtw_item.setText(item_text.strip("-"))
        qtw_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        qtw_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        item_text = issue.title or ""
        qtw_item = self.twList.item(row, 2)
        qtw_item.setText(item_text)
        qtw_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        qtw_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

    def _fetch(self, row: int) -> GenericMetadata:  # type: ignore[override]
        self.issue_id = self.twList.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        # list selection was changed, update the issue cover
        issue = self.issue_list[self.issue_id]
        if not (issue.issue and issue.year and issue.month and issue._cover_image and issue.title):
            QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
            try:
                issue = self.talker.fetch_comic_data(
                    issue_id=self.issue_id, on_rate_limit=RLCallBack(self.on_ratelimit, 10)
                )
            except TalkerError:
                pass
        self.issue_number = issue.issue or ""
        # We don't currently have a way to display hashes to the user
        # TODO: display the hash to the user so they know it will be used for cover matching
        alt_images = [url.URL for url in issue._alternate_images]
        cover = issue._cover_image.URL if issue._cover_image else ""
        self.cover_widget.set_issue_details(self.issue_id, [cover, *alt_images])
        self.set_description(self.teDescription, issue.description or "")
        series_link = ""
        if issue.web_links:
            url = (
                issue.web_links[0]
                .url.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("'", "&apos;")
                .replace('"', "&quot;")
            )

            series_link = f'<a href="{url}">Link To Issue</a>'
        self.lblIssueLink.setText(series_link)
        return issue
