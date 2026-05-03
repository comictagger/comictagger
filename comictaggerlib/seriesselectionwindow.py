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

import difflib
import itertools
import logging
import traceback
from abc import ABCMeta, abstractmethod

import natsort
from PyQt6 import QtCore, QtGui, QtWidgets, uic
from PyQt6.QtCore import Qt, QUrl, pyqtSignal

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import ComicSeries, GenericMetadata
from comictalker.comictalker import ComicTalker, RLCallBack, TalkerError

from .optionalmsgdialog import OptionalMessageDialog
from .coverimagewidget import CoverImageWidget
from .ctsettings import ct_ns
from .ctsettings.settngs_namespace import SettngsNS
from .issueidentifier import IssueIdentifier, IssueIdentifierOptions
from .issueidentifier import Result as IIResult
from .matchselectionwindow import MatchSelectionWindow
from .progresswindow import IDProgressWindow
from .resulttypes import IssueResult
from .ui import qtutils, ui_path

logger = logging.getLogger(__name__)


class SearchThread(QtCore.QThread):  # TODO: Evaluate thread semantics. Specifically with signals
    searchComplete = pyqtSignal()
    progressUpdate = pyqtSignal(int, int)
    ratelimit = pyqtSignal(float, float)

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
                self.series_name,
                callback=self.prog_callback,
                refresh_cache=self.refresh,
                literal=self.literal,
                series_match_thresh=self.series_match_thresh,
                on_rate_limit=RLCallBack(self.on_ratelimit, 10),
            )
        except TalkerError as e:
            self.ct_search_results = []
            self.ct_error = True
            self.error_e = e

        finally:
            self.searchComplete.emit()

    def prog_callback(self, current: int, total: int) -> None:
        self.progressUpdate.emit(current, total)

    def on_ratelimit(self, full_time: float, sleep_time: float) -> None:
        self.ratelimit.emit(full_time, sleep_time)


class IdentifyThread(QtCore.QThread):  # TODO: Evaluate thread semantics. Specifically with signals
    ratelimit = pyqtSignal(float, float)
    identifyComplete = pyqtSignal(IIResult, list)
    identifyLogMsg = pyqtSignal(str)
    identifyProgress = pyqtSignal(int, int)

    def __init__(self, ca: ComicArchive, config: SettngsNS, talker: ComicTalker, md: GenericMetadata) -> None:
        QtCore.QThread.__init__(self)
        iio = IssueIdentifierOptions(
            series_match_search_thresh=config.Issue_Identifier__series_match_search_thresh,
            series_match_identify_thresh=config.Issue_Identifier__series_match_identify_thresh,
            use_publisher_filter=config.Auto_Tag__use_publisher_filter,
            publisher_filter=config.Auto_Tag__publisher_filter,
            quiet=config.Runtime_Options__quiet,
            cache_dir=config.Runtime_Options__config.user_cache_dir,
            border_crop_percent=config.Issue_Identifier__border_crop_percent,
            talker=talker,
        )
        self.identifier = IssueIdentifier(
            iio,
            on_rate_limit=RLCallBack(self.on_ratelimit, 10),
            output=self.log_output,
            on_progress=self.progress_callback,
        )
        self.ca = ca
        self.md = md

    def log_output(self, text: str) -> None:
        self.identifyLogMsg.emit(str(text))

    def progress_callback(self, cur: int, total: int, image: bytes) -> None:
        self.identifyProgress.emit(cur, total)

    def run(self) -> None:
        self.identifyComplete.emit(*self.identifier.identify(self.ca, self.md))

    def cancel(self) -> None:
        self.identifier.cancel = True

    def on_ratelimit(self, full_time: float, sleep_time: float) -> None:
        self.ratelimit.emit(full_time, sleep_time)


class SelectionWindow(QtWidgets.QDialog):
    __metaclass__ = ABCMeta
    ui_file = ui_path / "seriesselectionwindow.ui"
    CoverImageMode = CoverImageWidget.URLMode
    ratelimit = pyqtSignal(float, float)

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        config: ct_ns,
        talker: ComicTalker,
        series_name: str = "",
        issue_number: str = "",
        comic_archive: ComicArchive | None = None,
        year: int | None = None,
        issue_count: int | None = None,
        autoselect: bool = False,
        literal: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        with self.ui_file.open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.cover_widget = CoverImageWidget(
            self.coverImageContainer,
            self.CoverImageMode,
            config.Runtime_Options__config.user_cache_dir,
        )
        gridlayout = QtWidgets.QGridLayout(self.coverImageContainer)
        gridlayout.addWidget(self.cover_widget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.teDescription: QtWidgets.QWidget
        webengine = qtutils.new_web_view(self)
        if webengine:
            self.teDescription = qtutils.replaceWidget(self.splitter, self.teDescription, webengine)
            logger.info("successfully loaded QWebEngineView")
        else:
            logger.info("failed to open QWebEngineView")

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.config = config
        self.talker = talker
        self.issue_id: str = ""

        # Display talker logo and set url
        self.lblIssuesSourceName.setText(talker.attribution)

        self.imageSourceWidget = CoverImageWidget(
            self.imageSourceLogo,
            CoverImageWidget.URLMode,
            config.Runtime_Options__config.user_cache_dir,
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
        self.twList.resizeColumnsToContents()
        self.twList.currentItemChanged.connect(self.current_item_changed)
        self.twList.cellDoubleClicked.connect(self.cell_double_clicked)
        self.leFilter.textChanged.connect(self.filter)
        self.twList.selectRow(0)
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    @abstractmethod
    def perform_query(self, refresh: bool = False) -> None: ...

    @abstractmethod
    def cell_double_clicked(self, r: int, c: int) -> None: ...

    @abstractmethod
    def update_row(self, row: int, series: ComicSeries) -> None: ...

    def set_description(self, widget: QtWidgets.QWidget, text: str) -> None:
        if isinstance(widget, QtWidgets.QTextEdit):
            widget.setText(text.replace("</figure>", "</div>").replace("<figure", "<div"))
        else:
            html = text
            widget.setHtml(html, QUrl(self.talker.website))

    def filter(self, text: str) -> None:
        rows = set(range(self.twList.rowCount()))
        for r in rows:
            self.twList.showRow(r)
        if text.strip():
            shown_rows = {x.row() for x in self.twList.findItems(text, QtCore.Qt.MatchFlag.MatchContains)}
            for r in rows - shown_rows:
                self.twList.hideRow(r)

    @abstractmethod
    def _fetch(self, row: int) -> ComicSeries: ...

    def on_ratelimit(self, full_time: float, sleep_time: float) -> None:
        self.ratelimit.emit(full_time, sleep_time)

    def current_item_changed(self, curr: QtCore.QModelIndex | None, prev: QtCore.QModelIndex | None) -> None:
        if curr is None:
            return
        if prev is not None and prev.row() == curr.row():
            return

        row = curr.row()

        item = self._fetch(row)
        QtWidgets.QApplication.restoreOverrideCursor()

        # Update current record information
        self.update_row(row, item)


class SeriesSelectionWindow(SelectionWindow):
    ui_file = ui_path / "seriesselectionwindow.ui"
    CoverImageMode = CoverImageWidget.URLMode

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        config: ct_ns,
        talker: ComicTalker,
        series_name: str = "",
        issue_number: str = "",
        comic_archive: ComicArchive | None = None,
        year: int | None = None,
        issue_count: int | None = None,
        autoselect: bool = False,
        literal: bool = False,
    ) -> None:
        from comictaggerlib.issueselectionwindow import IssueSelectionWindow

        super().__init__(
            parent,
            config,
            talker,
            series_name,
            issue_number,
            comic_archive,
            year,
            issue_count,
            autoselect,
            literal,
        )
        self.count = 0
        self.series_name = series_name
        self.issue_number = issue_number
        self.year = year
        self.issue_count = issue_count
        self.series_id: str = ""
        self.comic_archive = comic_archive
        self.immediate_autoselect = autoselect
        self.series_list: dict[str, ComicSeries] = {}
        self.literal = literal
        self.iddialog: IDProgressWindow | None = None
        self.id_thread: IdentifyThread | None = None
        self.progdialog: QtWidgets.QProgressDialog | None = None
        self.search_thread: SearchThread | None = None

        self.use_publisher_filter = self.config.Auto_Tag__use_publisher_filter

        self.btnRequery.clicked.connect(self.requery)
        self.btnIssues.clicked.connect(self.show_issues)
        self.btnAutoSelect.clicked.connect(self.auto_select)

        self.cbxPublisherFilter.setChecked(self.use_publisher_filter)
        self.cbxPublisherFilter.toggled.connect(self.publisher_filter_toggled)

        self.ratelimit.connect(self.ratelimit_message)

        self.update_buttons()

        self.selector = IssueSelectionWindow(self, self.config, self.talker, self.series_id, self.issue_number)
        self.selector.ratelimit.connect(self.ratelimit)
        self.selector.finished.connect(self.issue_selected)

    def perform_query(self, refresh: bool = False) -> None:
        self.search_thread = SearchThread(
            self.talker,
            self.series_name,
            refresh,
            self.literal,
            self.config.Issue_Identifier__series_match_search_thresh,
        )
        self.search_thread.searchComplete.connect(self.search_complete)
        self.search_thread.progressUpdate.connect(self.search_progress_update)
        self.search_thread.ratelimit.connect(self.ratelimit)
        self.search_thread.start()

        self.progdialog = QtWidgets.QProgressDialog("Searching Online", "Cancel", 0, 100, self)
        self.progdialog.setWindowTitle("Online Search")
        self.progdialog.canceled.connect(self.search_canceled)
        self.progdialog.setModal(True)
        self.progdialog.setMinimumDuration(300)

        if refresh or self.search_thread.isRunning():
            self.progdialog.open()
        else:
            self.progdialog = None

    def cell_double_clicked(self, r: int, c: int) -> None:
        self.show_issues()

    def update_row(self, row: int, series: ComicSeries) -> None:
        item_text = series.name
        item = self.twList.item(row, 0)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, series.id)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        item_text = f"{series.start_year:04}" if series.start_year is not None else ""
        item = self.twList.item(row, 1)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        item_text = f"{series.count_of_issues:04}" if series.count_of_issues is not None else ""
        item = self.twList.item(row, 2)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setData(QtCore.Qt.ItemDataRole.DisplayRole, series.count_of_issues)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

        item_text = series.publisher if series.publisher is not None else ""
        item = self.twList.item(row, 3)
        item.setText(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)

    def set_description(self, widget: QtWidgets.QWidget, text: str) -> None:
        if isinstance(widget, QtWidgets.QTextEdit):
            widget.setText(text.replace("</figure>", "</div>").replace("<figure", "<div"))
        else:
            html = text
            widget.setHtml(html, QUrl(self.talker.website))

    def filter(self, text: str) -> None:
        rows = set(range(self.twList.rowCount()))
        for r in rows:
            self.twList.showRow(r)
        if text.strip():
            shown_rows = {x.row() for x in self.twList.findItems(text, QtCore.Qt.MatchFlag.MatchContains)}
            for r in rows - shown_rows:
                self.twList.hideRow(r)

    def _fetch(self, row: int) -> ComicSeries:
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
            try:
                series = self.talker.fetch_series(self.series_id, on_rate_limit=RLCallBack(self.on_ratelimit, 10))
            except TalkerError:
                pass
        self.set_description(self.teDescription, series.description or "")
        series_link = ""
        if series.web_links:
            url = (
                series.web_links[0]
                .url.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("'", "&apos;")
                .replace('"', "&quot;")
            )

            series_link = f'<a href="{url}">Link To Series</a>'
        self.lblSeriesLink.setText(series_link)
        self.cover_widget.set_url(series.image_url)
        return series

    def update_buttons(self) -> None:
        enabled = bool(self.series_list)

        self.btnRequery.setEnabled(enabled)

        self.btnIssues.setEnabled(enabled)
        self.btnAutoSelect.setEnabled(enabled)

        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(enabled)

    def requery(self) -> None:
        self.perform_query(refresh=True)
        self.twList.selectRow(0)

    def publisher_filter_toggled(self) -> None:
        self.use_publisher_filter = self.cbxPublisherFilter.isChecked()
        self.perform_query(refresh=False)

    def auto_select(self) -> None:
        if self.comic_archive is None:
            OptionalMessageDialog.information(self, "Auto-Select", "You need to load a comic first!")
            return

        if self.issue_number is None or self.issue_number == "":
            OptionalMessageDialog.information(self, "Auto-Select", "Can't auto-select without an issue number (yet!)")
            return
        self.iddialog = IDProgressWindow(self)

        md = GenericMetadata()
        md.series = self.series_name
        md.issue = self.issue_number
        md.year = self.year
        md.issue_count = self.issue_count

        self.id_thread = IdentifyThread(self.comic_archive, self.config, self.talker, md)
        self.id_thread.identifyComplete.connect(self.identify_complete)
        self.id_thread.identifyLogMsg.connect(self.log_output)
        self.id_thread.identifyProgress.connect(self.identify_progress)
        self.id_thread.ratelimit.connect(self.ratelimit)
        self.iddialog.rejected.connect(self.id_thread.cancel)

        self.id_thread.start()

        self.iddialog.open()

    def log_output(self, text: str) -> None:
        if self.iddialog is None:
            return
        self.iddialog.textEdit.append(text.rstrip())
        self.iddialog.textEdit.ensureCursorVisible()
        QtCore.QCoreApplication.processEvents()

    def identify_progress(self, cur: int, total: int) -> None:
        if self.iddialog is None:
            return
        self.iddialog.progressBar.setMaximum(total)
        self.iddialog.progressBar.setValue(cur)

    def identify_complete(self, result: IIResult, issues: list[IssueResult]) -> None:
        if self.iddialog is None or self.comic_archive is None:
            return

        if result == IIResult.single_good_match:
            return self.update_match(issues[0])

        info_text = " Manual interaction needed :-("

        if result == IIResult.no_matches:
            info_text = " No matches found :-("
            OptionalMessageDialog.information(parent=self.iddialog, title="Auto-Select Result", text=info_text)
            return

        if result == IIResult.single_bad_cover_score:
            info_text = " Found a match, but cover doesn't seem the same. Verify before committing!"
            qmsg = OptionalMessageDialog.information(parent=self.iddialog, title="Auto-Select Result", text=info_text)
            qmsg.finished.connect(lambda: self.update_match(issues[0]))
            return

        selector = MatchSelectionWindow(self, issues, self.comic_archive, talker=self.talker, config=self.config)
        selector.match_selected.connect(self.update_match)

        if result == IIResult.multiple_bad_cover_scores:
            info_text = " Found some possibilities, but no confidence. Proceed manually."
        elif result == IIResult.multiple_good_matches:
            info_text = " Found multiple likely matches. Please select."
        qmsg = OptionalMessageDialog.information(parent=self.iddialog, title="Auto-Select Result", text=info_text)

        qmsg.finished.connect(selector.open)

    def update_match(self, match: IssueResult) -> None:
        if self.iddialog is not None:
            self.iddialog.close()

        assert match.md.issue
        self.series_id = match.series.id
        self.issue_number = match.md.issue
        self.select_by_id()
        self.show_issues()

    def show_issues(self) -> None:
        title = ""
        for series in self.series_list.values():
            if series.id == self.series_id:
                title = f"{series.name} ({series.start_year:04}) - " if series.start_year else f"{series.name} - "
                break
        self.selector.setWindowTitle(title + "Select Issue")
        self.selector.series_id = self.series_id

        self.selector.perform_query()

    def issue_selected(self, result: list[GenericMetadata]) -> None:
        if not result or not self.selector:
            self.cover_widget.update_content()
            return
        # we should now have a series ID
        self.issue_number = self.selector.issue_number
        self.issue_id = self.selector.issue_id
        self.accept()

    def select_by_id(self) -> None:
        for r in range(self.twList.rowCount()):
            if self.series_id == self.twList.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole):
                self.twList.selectRow(r)
                break

    def search_canceled(self) -> None:
        if self.progdialog is None:
            return
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
        if self.progdialog is None:
            return
        try:
            QtCore.QCoreApplication.processEvents()
            self.progdialog.setMaximum(total)
            self.progdialog.setValue(min(current + 1, total))
            QtCore.QCoreApplication.processEvents()
        except Exception:
            ...

    def search_complete(self) -> None:
        if self.progdialog is not None:
            self.progdialog.accept()
            self.progdialog.deleteLater()
            self.progdialog = None
        if self.search_thread is not None and self.search_thread.ct_error:
            parent = self.parent()
            if not isinstance(parent, QtWidgets.QWidget):
                parent = None
            e = self.search_thread.error_e
            OptionalMessageDialog.critical(
                parent,
                f"{e.source} {e.code_name} Error",
                f"{e}",
                details="\n".join(traceback.format_exception(type(e), e, e.__traceback__)),
            )
            return

        tmp_list = self.search_thread.ct_search_results if self.search_thread is not None else []
        self.series_list = {x.id: x for x in tmp_list}
        # filter the publishers if enabled set
        if self.use_publisher_filter:
            try:
                publisher_filter = {s.strip().casefold() for s in self.config.Auto_Tag__publisher_filter}
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

        sanitized_full = utils.sanitize_title(self.series_name, False).casefold()
        sanitized_basic = utils.sanitize_title(self.series_name, True).casefold()
        matcher_full = difflib.SequenceMatcher(None, sanitized_basic)
        matcher_basic = difflib.SequenceMatcher(None, sanitized_full)

        def score(result: tuple[str, ComicSeries]) -> float:
            matcher_full.set_seq2(utils.sanitize_title(result[1].name, False).casefold())
            return matcher_full.ratio()

        self.series_list = dict(sorted(self.series_list.items(), key=score, reverse=True))

        # pre sort the data - so that we can put exact matches first afterwards
        # compare as str in case extra chars ie. '1976?'
        # - missing (none) values being converted to 'None' - consistent with prior behaviour in v1.2.3
        # sort by start_year if set
        if self.config.Issue_Identifier__sort_series_by_year:
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

            try:

                deques: list[list[tuple[str, ComicSeries]]] = [list(), list(), list()]

                def categorize(result: ComicSeries) -> int:
                    matcher_full.set_seq2(utils.sanitize_title(result.name, False).casefold())
                    matcher_basic.set_seq2(utils.sanitize_title(result.name, True).casefold())
                    ratio_full = matcher_full.ratio()
                    ratio_basic = matcher_basic.ratio()
                    logger.info("%s: %.3f, %.3f", result.name, ratio_full, ratio_basic)
                    # here basic means partial sanitization meaning that less things will match
                    if ratio_basic > 0.9:
                        return 0

                    # this ensures that 'The Joker' is near the top even if you search 'Joker'
                    # here full means full sanitization meaning that more things will match
                    if ratio_full > 0.9:
                        return 1
                    return 2

                for comic in self.series_list.items():
                    deques[categorize(comic[1])].append(comic)
                logger.info("Length: %d, %d, %d", len(deques[0]), len(deques[1]), len(deques[2]))
                self.series_list = dict(itertools.chain.from_iterable(deques))
            except Exception:
                logger.exception("error filtering exact/near matches: bad data")

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

        if not self.series_list:
            OptionalMessageDialog.information(self, "Search Result", "No matches found!\nSeriesSelectionWindow")
            return

        elif self.immediate_autoselect:
            # defer the immediate autoselect so this dialog has time to pop up
            self.show()
            QtCore.QTimer.singleShot(10, self.do_immediate_autoselect)
        else:
            self.show()

    def do_immediate_autoselect(self) -> None:
        self.immediate_autoselect = False
        self.auto_select()

    def current_item_changed(self, curr: QtCore.QModelIndex | None, prev: QtCore.QModelIndex | None) -> None:
        if curr is None:
            return
        if prev is not None and prev.row() == curr.row():
            return

        row = curr.row()

        item = self._fetch(row)
        QtWidgets.QApplication.restoreOverrideCursor()

        # Update current record information
        self.update_row(row, item)

    def ratelimit_message(self, full_time: float, sleep_time: float) -> None:
        self.log_output(
            f"Rate limit reached: {full_time:.0f}s until next request. Waiting {sleep_time:.0f}s for ratelimit"
        )
