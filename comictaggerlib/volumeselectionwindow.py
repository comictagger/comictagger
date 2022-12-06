"""A PyQT4 dialog to select specific series/volume from list"""
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

import itertools
import logging
from collections import deque

from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib import settings
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.issueidentifier import IssueIdentifier
from comictaggerlib.issueselectionwindow import IssueSelectionWindow
from comictaggerlib.matchselectionwindow import MatchSelectionWindow
from comictaggerlib.progresswindow import IDProgressWindow
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import reduce_widget_font_size
from comictalker.resulttypes import ComicVolume
from comictalker.talkerbase import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class SearchThread(QtCore.QThread):
    searchComplete = pyqtSignal()
    progressUpdate = pyqtSignal(int, int)

    def __init__(
        self,
        talker_api: ComicTalker,
        series_name: str,
        refresh: bool,
        literal: bool = False,
        series_match_thresh: int = 90,
    ) -> None:
        QtCore.QThread.__init__(self)
        self.talker_api = talker_api
        self.series_name = series_name
        self.refresh: bool = refresh
        self.error_e: TalkerError
        self.ct_error = False
        self.ct_search_results: list[ComicVolume] = []
        self.literal = literal
        self.series_match_thresh = series_match_thresh

    def run(self) -> None:
        try:
            self.ct_error = False
            self.ct_search_results = self.talker_api.search_for_series(
                self.series_name, self.prog_callback, self.refresh, self.literal
            )
        except TalkerError as e:
            self.ct_search_results = []
            self.ct_error = True
            self.error_e = e

        finally:
            self.searchComplete.emit()

    def prog_callback(self, current: int, total: int) -> None:
        self.progressUpdate.emit(current, total)


class IdentifyThread(QtCore.QThread):
    identifyComplete = pyqtSignal()
    identifyLogMsg = pyqtSignal(str)
    identifyProgress = pyqtSignal(int, int)

    def __init__(self, identifier: IssueIdentifier) -> None:
        QtCore.QThread.__init__(self)
        self.identifier = identifier
        self.identifier.set_output_function(self.log_output)
        self.identifier.set_progress_callback(self.progress_callback)

    def log_output(self, text: str) -> None:
        self.identifyLogMsg.emit(str(text))

    def progress_callback(self, cur: int, total: int) -> None:
        self.identifyProgress.emit(cur, total)

    def run(self) -> None:
        self.identifier.search()
        self.identifyComplete.emit()


class VolumeSelectionWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        series_name: str,
        issue_number: str,
        year: int | None,
        issue_count: int,
        cover_index_list: list[int],
        comic_archive: ComicArchive | None,
        options: settings.OptionValues,
        talker_api: ComicTalker,
        autoselect: bool = False,
        literal: bool = False,
    ) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "volumeselectionwindow.ui", self)

        self.imageWidget = CoverImageWidget(
            self.imageContainer, CoverImageWidget.URLMode, options["runtime"]["config"].user_cache_dir, talker_api
        )
        gridlayout = QtWidgets.QGridLayout(self.imageContainer)
        gridlayout.addWidget(self.imageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        reduce_widget_font_size(self.teDetails, 1)
        reduce_widget_font_size(self.twList)

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.options = options
        self.series_name = series_name
        self.issue_number = issue_number
        self.issue_id: int | None = None
        self.year = year
        self.issue_count = issue_count
        self.volume_id = 0
        self.comic_archive = comic_archive
        self.immediate_autoselect = autoselect
        self.cover_index_list = cover_index_list
        self.ct_search_results: list[ComicVolume] = []
        self.literal = literal
        self.ii: IssueIdentifier | None = None
        self.iddialog: IDProgressWindow | None = None
        self.id_thread: IdentifyThread | None = None
        self.progdialog: QtWidgets.QProgressDialog | None = None
        self.search_thread: SearchThread | None = None

        self.use_filter = self.options["comicvine"]["always_use_publisher_filter"]

        # Load to retrieve settings
        self.talker_api = talker_api

        self.twList.resizeColumnsToContents()
        self.twList.currentItemChanged.connect(self.current_item_changed)
        self.twList.cellDoubleClicked.connect(self.cell_double_clicked)
        self.btnRequery.clicked.connect(self.requery)
        self.btnIssues.clicked.connect(self.show_issues)
        self.btnAutoSelect.clicked.connect(self.auto_select)

        self.cbxFilter.setChecked(self.use_filter)
        self.cbxFilter.toggled.connect(self.filter_toggled)

        self.update_buttons()
        self.twList.selectRow(0)

    def update_buttons(self) -> None:
        enabled = bool(self.ct_search_results)

        self.btnRequery.setEnabled(enabled)

        self.btnIssues.setEnabled(enabled)
        self.btnAutoSelect.setEnabled(enabled)

        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(enabled)

    def requery(self) -> None:
        self.perform_query(refresh=True)
        self.twList.selectRow(0)

    def filter_toggled(self) -> None:
        self.use_filter = not self.use_filter
        self.perform_query(refresh=False)

    def auto_select(self) -> None:

        if self.comic_archive is None:
            QtWidgets.QMessageBox.information(self, "Auto-Select", "You need to load a comic first!")
            return

        if self.issue_number is None or self.issue_number == "":
            QtWidgets.QMessageBox.information(self, "Auto-Select", "Can't auto-select without an issue number (yet!)")
            return

        self.iddialog = IDProgressWindow(self)
        self.iddialog.setModal(True)
        self.iddialog.rejected.connect(self.identify_cancel)
        self.iddialog.show()

        self.ii = IssueIdentifier(self.comic_archive, self.options, self.talker_api)

        md = GenericMetadata()
        md.series = self.series_name
        md.issue = self.issue_number
        md.year = self.year
        md.issue_count = self.issue_count

        self.ii.set_additional_metadata(md)
        self.ii.only_use_additional_meta_data = True

        self.ii.cover_page_index = int(self.cover_index_list[0])

        self.id_thread = IdentifyThread(self.ii)
        self.id_thread.identifyComplete.connect(self.identify_complete)
        self.id_thread.identifyLogMsg.connect(self.log_id_output)
        self.id_thread.identifyProgress.connect(self.identify_progress)

        self.id_thread.start()

        self.iddialog.exec()

    def log_id_output(self, text: str) -> None:
        if self.iddialog is not None:
            print(text, end=" ")  # noqa: T201
            self.iddialog.textEdit.ensureCursorVisible()
            self.iddialog.textEdit.insertPlainText(text)

    def identify_progress(self, cur: int, total: int) -> None:
        if self.iddialog is not None:
            self.iddialog.progressBar.setMaximum(total)
            self.iddialog.progressBar.setValue(cur)

    def identify_cancel(self) -> None:
        if self.ii is not None:
            self.ii.cancel = True

    def identify_complete(self) -> None:
        if self.ii is not None and self.iddialog is not None and self.comic_archive is not None:

            matches = self.ii.match_list
            result = self.ii.search_result

            found_match = None
            choices = False
            if result == self.ii.result_no_matches:
                QtWidgets.QMessageBox.information(self, "Auto-Select Result", " No matches found :-(")
            elif result == self.ii.result_found_match_but_bad_cover_score:
                QtWidgets.QMessageBox.information(
                    self,
                    "Auto-Select Result",
                    " Found a match, but cover doesn't seem the same.  Verify before committing!",
                )
                found_match = matches[0]
            elif result == self.ii.result_found_match_but_not_first_page:
                QtWidgets.QMessageBox.information(
                    self, "Auto-Select Result", " Found a match, but not with the first page of the archive."
                )
                found_match = matches[0]
            elif result == self.ii.result_multiple_matches_with_bad_image_scores:
                QtWidgets.QMessageBox.information(
                    self, "Auto-Select Result", " Found some possibilities, but no confidence. Proceed manually."
                )
                choices = True
            elif result == self.ii.result_one_good_match:
                found_match = matches[0]
            elif result == self.ii.result_multiple_good_matches:
                QtWidgets.QMessageBox.information(
                    self, "Auto-Select Result", " Found multiple likely matches.  Please select."
                )
                choices = True

            if choices:
                selector = MatchSelectionWindow(
                    self, matches, self.comic_archive, talker_api=self.talker_api, options=self.options
                )
                selector.setModal(True)
                selector.exec()
                if selector.result():
                    # we should now have a list index
                    found_match = selector.current_match()

            if found_match is not None:
                self.iddialog.accept()

                self.volume_id = utils.xlate(found_match["volume_id"])
                self.issue_number = found_match["issue_number"]
                self.select_by_id()
                self.show_issues()

    def show_issues(self) -> None:
        selector = IssueSelectionWindow(self, self.options, self.talker_api, self.volume_id, self.issue_number)
        title = ""
        for record in self.ct_search_results:
            if record["id"] == self.volume_id:
                title = record["name"]
                title += " (" + str(record["start_year"]) + ")"
                title += " - "
                break

        selector.setWindowTitle(title + "Select Issue")
        selector.setModal(True)
        selector.exec()
        if selector.result():
            # we should now have a volume ID
            self.issue_number = selector.issue_number
            self.issue_id = selector.issue_id
            self.accept()

    def select_by_id(self) -> None:
        for r in range(0, self.twList.rowCount()):
            volume_id = self.twList.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
            if volume_id == self.volume_id:
                self.twList.selectRow(r)
                break

    def perform_query(self, refresh: bool = False) -> None:

        self.search_thread = SearchThread(
            self.talker_api,
            self.series_name,
            refresh,
            self.literal,
            self.options["comicvine"]["series_match_search_thresh"],
        )
        self.search_thread.searchComplete.connect(self.search_complete)
        self.search_thread.progressUpdate.connect(self.search_progress_update)
        self.search_thread.start()

        self.progdialog = QtWidgets.QProgressDialog("Searching Online", "Cancel", 0, 100, self)
        self.progdialog.setWindowTitle("Online Search")
        self.progdialog.canceled.connect(self.search_canceled)
        self.progdialog.setModal(True)
        self.progdialog.setMinimumDuration(300)

        if refresh or self.search_thread.isRunning():
            self.progdialog.exec()
        else:
            self.progdialog = None

    def search_canceled(self) -> None:
        if self.progdialog is not None:
            logger.info("query cancelled")
            if self.search_thread is not None:
                self.search_thread.searchComplete.disconnect()
                self.search_thread.progressUpdate.disconnect()
            self.progdialog.canceled.disconnect()
            self.progdialog.reject()
            QtCore.QTimer.singleShot(200, self.close_me)

    def close_me(self) -> None:
        self.reject()

    def search_progress_update(self, current: int, total: int) -> None:
        if self.progdialog is not None:
            self.progdialog.setMaximum(total)
            self.progdialog.setValue(current + 1)

    def search_complete(self) -> None:
        if self.progdialog is not None:
            self.progdialog.accept()
            del self.progdialog
        if self.search_thread is not None and self.search_thread.ct_error:
            # TODO Currently still opens the window
            QtWidgets.QMessageBox.critical(
                self,
                f"{self.search_thread.error_e.source} {self.search_thread.error_e.code_name} Error",
                f"{self.search_thread.error_e}",
            )
            return

        self.ct_search_results = self.search_thread.ct_search_results if self.search_thread is not None else []
        # filter the publishers if enabled set
        if self.use_filter:
            try:
                publisher_filter = {s.strip().casefold() for s in self.options["identifier"]["publisher_filter"]}
                # use '' as publisher name if None
                self.ct_search_results = list(
                    filter(
                        lambda d: ("" if d["publisher"] is None else str(d["publisher"]).casefold())
                        not in publisher_filter,
                        self.ct_search_results,
                    )
                )
            except Exception:
                logger.exception("bad data error filtering publishers")

        # pre sort the data - so that we can put exact matches first afterwards
        # compare as str in case extra chars ie. '1976?'
        # - missing (none) values being converted to 'None' - consistent with prior behaviour in v1.2.3
        # sort by start_year if set
        if self.options["comicvine"]["sort_series_by_year"]:
            try:
                self.ct_search_results = sorted(
                    self.ct_search_results,
                    key=lambda i: (str(i["start_year"]), str(i["count_of_issues"])),
                    reverse=True,
                )
            except Exception:
                logger.exception("bad data error sorting results by start_year,count_of_issues")
        else:
            try:
                self.ct_search_results = sorted(
                    self.ct_search_results, key=lambda i: str(i["count_of_issues"]), reverse=True
                )
            except Exception:
                logger.exception("bad data error sorting results by count_of_issues")

        # move sanitized matches to the front
        if self.options["comicvine"]["exact_series_matches_first"]:
            try:
                sanitized = utils.sanitize_title(self.series_name, False).casefold()
                sanitized_no_articles = utils.sanitize_title(self.series_name, True).casefold()

                deques: list[deque[ComicVolume]] = [deque(), deque(), deque()]

                def categorize(result: ComicVolume) -> int:
                    # We don't remove anything on this one so that we only get exact matches
                    if utils.sanitize_title(result["name"], True).casefold() == sanitized_no_articles:
                        return 0

                    # this ensures that 'The Joker' is near the top even if you search 'Joker'
                    if utils.sanitize_title(result["name"], False).casefold() in sanitized:
                        return 1
                    return 2

                for comic in self.ct_search_results:
                    deques[categorize(comic)].append(comic)
                logger.info("Length: %d, %d, %d", len(deques[0]), len(deques[1]), len(deques[2]))
                self.ct_search_results = list(itertools.chain.from_iterable(deques))
            except Exception:
                logger.exception("bad data error filtering exact/near matches")

        self.update_buttons()

        self.twList.setSortingEnabled(False)

        self.twList.setRowCount(0)

        row = 0
        for record in self.ct_search_results:
            self.twList.insertRow(row)

            item_text = record["name"]
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, record["id"])
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, item)

            item_text = str(record["start_year"])
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, item)

            item_text = str(record["count_of_issues"])
            item = QtWidgets.QTableWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setData(QtCore.Qt.ItemDataRole.DisplayRole, record["count_of_issues"])
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, item)

            if record["publisher"] is not None:
                item_text = record["publisher"]
                item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
                item = QtWidgets.QTableWidgetItem(item_text)
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.twList.setItem(row, 3, item)

            row += 1

        self.twList.setSortingEnabled(True)
        self.twList.selectRow(0)
        self.twList.resizeColumnsToContents()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self.perform_query()
        if not self.ct_search_results:
            QtCore.QCoreApplication.processEvents()
            QtWidgets.QMessageBox.information(self, "Search Result", "No matches found!")
            QtCore.QTimer.singleShot(200, self.close_me)

        elif self.immediate_autoselect:
            # defer the immediate autoselect so this dialog has time to pop up
            QtCore.QCoreApplication.processEvents()
            QtCore.QTimer.singleShot(10, self.do_immediate_autoselect)

    def do_immediate_autoselect(self) -> None:
        self.immediate_autoselect = False
        self.auto_select()

    def cell_double_clicked(self, r: int, c: int) -> None:
        self.show_issues()

    def current_item_changed(self, curr: QtCore.QModelIndex | None, prev: QtCore.QModelIndex | None) -> None:

        if curr is None:
            return
        if prev is not None and prev.row() == curr.row():
            return

        self.volume_id = self.twList.item(curr.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)

        # list selection was changed, update the info on the volume
        for record in self.ct_search_results:
            if record["id"] == self.volume_id:
                if record["description"] is None:
                    self.teDetails.setText("")
                else:
                    self.teDetails.setText(record["description"])
                self.imageWidget.set_url(record["image_url"])
                break
