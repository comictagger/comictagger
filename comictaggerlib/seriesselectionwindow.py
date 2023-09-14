"""A PyQT4 dialog to select specific series/volume from list"""
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

import itertools
import logging
from collections import deque

import natsort
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QUrl, pyqtSignal

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import ComicSeries, GenericMetadata
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.issueidentifier import IssueIdentifier
from comictaggerlib.issueselectionwindow import IssueSelectionWindow
from comictaggerlib.matchselectionwindow import MatchSelectionWindow
from comictaggerlib.progresswindow import IDProgressWindow
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import new_web_view, reduce_widget_font_size
from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


class SearchThread(QtCore.QThread):
    searchComplete = pyqtSignal()
    progressUpdate = pyqtSignal(int, int)

    def __init__(
        self, talker: ComicTalker, series_name: str, refresh: bool, literal: bool = False, series_match_thresh: int = 90
    ) -> None:
        QtCore.QThread.__init__(self)
        self.talker = talker
        self.series_name = series_name
        self.refresh: bool = refresh
        self.error_e: TalkerError
        self.ct_error = False
        self.ct_search_results: list[ComicSeries] = []
        self.literal = literal
        self.series_match_thresh = series_match_thresh

    def run(self) -> None:
        try:
            self.ct_error = False
            self.ct_search_results = self.talker.search_for_series(
                self.series_name, self.prog_callback, self.refresh, self.literal, self.series_match_thresh
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


class SeriesSelectionWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        series_name: str,
        issue_number: str,
        year: int | None,
        issue_count: int | None,
        cover_index_list: list[int],
        comic_archive: ComicArchive | None,
        config: ct_ns,
        talker: ComicTalker,
        autoselect: bool = False,
        literal: bool = False,
    ) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "seriesselectionwindow.ui", self)

        self.imageWidget = CoverImageWidget(
            self.imageContainer, CoverImageWidget.URLMode, config.Runtime_Options_config.user_cache_dir, talker
        )
        gridlayout = QtWidgets.QGridLayout(self.imageContainer)
        gridlayout.addWidget(self.imageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.teDetails: QtWidgets.QWidget
        webengine = new_web_view(self)
        if webengine:
            self.teDetails.hide()
            self.teDetails.deleteLater()
            # I don't know how to replace teDetails, this is the result of teDetails.height() once rendered
            webengine.resize(webengine.width(), 141)
            self.splitter.addWidget(webengine)
            self.teDetails = webengine

        reduce_widget_font_size(self.teDetails, 1)
        reduce_widget_font_size(self.twList)

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.config = config
        self.series_name = series_name
        self.issue_number = issue_number
        self.issue_id: str = ""
        self.year = year
        self.issue_count = issue_count
        self.series_id: str = ""
        self.comic_archive = comic_archive
        self.immediate_autoselect = autoselect
        self.cover_index_list = cover_index_list
        self.series_list: dict[str, ComicSeries] = {}
        self.literal = literal
        self.ii: IssueIdentifier | None = None
        self.iddialog: IDProgressWindow | None = None
        self.id_thread: IdentifyThread | None = None
        self.progdialog: QtWidgets.QProgressDialog | None = None
        self.search_thread: SearchThread | None = None

        self.use_filter = self.config.Issue_Identifier_always_use_publisher_filter

        # Load to retrieve settings
        self.talker = talker

        # Display talker logo and set url
        self.lblSourceName.setText(talker.attribution)

        self.imageSourceWidget = CoverImageWidget(
            self.imageSourceLogo,
            CoverImageWidget.URLMode,
            config.Runtime_Options_config.user_cache_dir,
            talker,
            False,
        )
        self.imageSourceWidget.showControls = False
        gridlayoutSourceLogo = QtWidgets.QGridLayout(self.imageSourceLogo)
        gridlayoutSourceLogo.addWidget(self.imageSourceWidget)
        gridlayoutSourceLogo.setContentsMargins(0, 2, 0, 0)
        self.imageSourceWidget.set_url(talker.logo_url)

        # Set the minimum row height to the default.
        # this way rows will be more consistent when resizeRowsToContents is called
        self.twList.verticalHeader().setMinimumSectionSize(self.twList.verticalHeader().defaultSectionSize())
        self.twList.currentItemChanged.connect(self.current_item_changed)
        self.twList.cellDoubleClicked.connect(self.cell_double_clicked)
        self.btnRequery.clicked.connect(self.requery)
        self.btnIssues.clicked.connect(self.show_issues)
        self.btnAutoSelect.clicked.connect(self.auto_select)

        self.cbxFilter.setChecked(self.use_filter)
        self.cbxFilter.toggled.connect(self.filter_toggled)

        self.update_buttons()
        self.twList.selectRow(0)

        self.leFilter.textChanged.connect(self.filter)

    def filter(self, text: str) -> None:
        rows = set(range(self.twList.rowCount()))
        for r in rows:
            self.twList.showRow(r)
        if text.strip():
            shown_rows = {x.row() for x in self.twList.findItems(text, QtCore.Qt.MatchFlag.MatchContains)}
            for r in rows - shown_rows:
                self.twList.hideRow(r)

    def update_buttons(self) -> None:
        enabled = bool(self.series_list)

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

        self.ii = IssueIdentifier(self.comic_archive, self.config, self.talker)

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
                    self, matches, self.comic_archive, talker=self.talker, config=self.config
                )
                selector.setModal(True)
                selector.exec()
                if selector.result():
                    # we should now have a list index
                    found_match = selector.current_match()

            if found_match is not None:
                self.iddialog.accept()

                self.series_id = utils.xlate(found_match["series_id"]) or ""
                self.issue_number = found_match["issue_number"]
                self.select_by_id()
                self.show_issues()

    def show_issues(self) -> None:
        selector = IssueSelectionWindow(self, self.config, self.talker, self.series_id, self.issue_number)
        title = ""
        for series in self.series_list.values():
            if series.id == self.series_id:
                title = f"{series.name} ({series.start_year:04}) - " if series.start_year else f"{series.name} - "
                break

        selector.setWindowTitle(title + "Select Issue")
        selector.setModal(True)
        selector.exec()
        if selector.result():
            # we should now have a series ID
            self.issue_number = selector.issue_number
            self.issue_id = selector.issue_id
            self.accept()
        else:
            self.imageWidget.update_content()

    def select_by_id(self) -> None:
        for r in range(self.twList.rowCount()):
            if self.series_id == self.twList.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole):
                self.twList.selectRow(r)
                break

    def perform_query(self, refresh: bool = False) -> None:
        self.search_thread = SearchThread(
            self.talker,
            self.series_name,
            refresh,
            self.literal,
            self.config.Issue_Identifier_series_match_search_thresh,
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
            self.progdialog = None
        if self.search_thread is not None and self.search_thread.ct_error:
            # TODO Currently still opens the window
            QtWidgets.QMessageBox.critical(
                self,
                f"{self.search_thread.error_e.source} {self.search_thread.error_e.code_name} Error",
                f"{self.search_thread.error_e}",
            )
            return

        tmp_list = self.search_thread.ct_search_results if self.search_thread is not None else []
        self.series_list = {x.id: x for x in tmp_list}
        # filter the publishers if enabled set
        if self.use_filter:
            try:
                publisher_filter = {s.strip().casefold() for s in self.config.Issue_Identifier_publisher_filter}
                # use '' as publisher name if None
                self.series_list = dict(
                    filter(
                        lambda d: ("" if d[1].publisher is None else str(d[1].publisher).casefold())
                        not in publisher_filter,
                        self.series_list.items(),
                    )
                )
            except Exception:
                logger.exception("bad data error filtering publishers")

        # pre sort the data - so that we can put exact matches first afterwards
        # compare as str in case extra chars ie. '1976?'
        # - missing (none) values being converted to 'None' - consistent with prior behaviour in v1.2.3
        # sort by start_year if set
        if self.config.Issue_Identifier_sort_series_by_year:
            try:
                self.series_list = dict(
                    natsort.natsorted(
                        self.series_list.items(),
                        key=lambda i: (str(i[1].start_year), str(i[1].count_of_issues)),
                        reverse=True,
                    )
                )
            except Exception:
                logger.exception("bad data error sorting results by start_year,count_of_issues")
        else:
            try:
                self.series_list = dict(
                    natsort.natsorted(self.series_list.items(), key=lambda i: str(i[1].count_of_issues), reverse=True)
                )
            except Exception:
                logger.exception("bad data error sorting results by count_of_issues")

        # move sanitized matches to the front
        if self.config.Issue_Identifier_exact_series_matches_first:
            try:
                sanitized = utils.sanitize_title(self.series_name, False).casefold()
                sanitized_no_articles = utils.sanitize_title(self.series_name, True).casefold()

                deques: list[deque[tuple[str, ComicSeries]]] = [deque(), deque(), deque()]

                def categorize(result: ComicSeries) -> int:
                    # We don't remove anything on this one so that we only get exact matches
                    if utils.sanitize_title(result.name, True).casefold() == sanitized_no_articles:
                        return 0

                    # this ensures that 'The Joker' is near the top even if you search 'Joker'
                    if utils.sanitize_title(result.name, False).casefold() in sanitized:
                        return 1
                    return 2

                for comic in self.series_list.items():
                    deques[categorize(comic[1])].append(comic)
                logger.info("Length: %d, %d, %d", len(deques[0]), len(deques[1]), len(deques[2]))
                self.series_list = dict(itertools.chain.from_iterable(deques))
            except Exception:
                logger.exception("bad data error filtering exact/near matches")

        self.update_buttons()

        self.twList.setSortingEnabled(False)

        self.twList.setRowCount(0)

        for row, series in enumerate(self.series_list.values()):
            self.twList.insertRow(row)
            for i in range(4):
                self.twList.setItem(row, i, QtWidgets.QTableWidgetItem())

            self.update_row(row, series)

        self.twList.setSortingEnabled(True)
        self.twList.selectRow(0)
        self.twList.resizeColumnsToContents()
        # Get the width of the issues, year and publisher columns
        owidth = self.twList.columnWidth(1) + self.twList.columnWidth(2) + self.twList.columnWidth(3)
        # Get the remaining width after they fill the tableWidget
        rwidth = self.twList.contentsRect().width() - owidth

        # Default the tableWidget to truncate series names
        self.twList.setColumnWidth(0, rwidth)

        # Resize row height so the whole series can still be seen
        self.twList.resizeRowsToContents()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self.perform_query()
        if not self.series_list:
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

    def set_description(self, widget: QtWidgets.QWidget, text: str) -> None:
        if isinstance(widget, QtWidgets.QTextEdit):
            widget.setText(text.replace("</figure>", "</div>").replace("<figure", "<div"))
        else:
            html = text
            widget.setHtml(html, QUrl(self.talker.website))

    def update_row(self, row: int, series: ComicSeries) -> None:
        item_text = series.name
        item = self.twList.item(row, 0)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, series.id)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        item_text = str(series.start_year)
        item = self.twList.item(row, 1)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        item_text = str(series.count_of_issues)
        item = self.twList.item(row, 2)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setData(QtCore.Qt.ItemDataRole.DisplayRole, series.count_of_issues)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        if series.publisher is not None:
            item_text = series.publisher
            item = self.twList.item(row, 3)
            item.setText(item_text)
            item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

    def current_item_changed(self, curr: QtCore.QModelIndex | None, prev: QtCore.QModelIndex | None) -> None:
        if curr is None:
            return
        if prev is not None and prev.row() == curr.row():
            return

        row = curr.row()
        self.series_id = self.twList.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)

        # list selection was changed, update the info on the series
        series = self.series_list[self.series_id]
        if not (
            series.name
            and series.start_year
            and series.count_of_issues
            and series.publisher
            and series.description
            and series.image_url
        ):
            QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
            # Changing of usernames and passwords with using cache can cause talker errors to crash out
            try:
                series = self.talker.fetch_series(self.series_id)
            except TalkerError:
                pass
        QtWidgets.QApplication.restoreOverrideCursor()

        if series.description is None:
            self.set_description(self.teDetails, "")
        else:
            self.set_description(self.teDetails, series.description)
        self.imageWidget.set_url(series.image_url)

        # Update current record information
        self.update_row(row, series)
