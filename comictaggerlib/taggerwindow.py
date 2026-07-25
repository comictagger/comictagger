"""The main window of the ComicTagger app"""

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

import functools
import hashlib
import json
import logging
import operator
import os
import platform
import sys
import textwrap
import traceback
import webbrowser
from collections.abc import Callable, Sequence
from typing import Any

import natsort
import settngs
from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets, uic

import comicapi.merge
import comictaggerlib.ui
from comicapi import utils
from comicapi.comicarchive import ComicArchive, tags
from comicapi.filenameparser import FileNameParser
from comicapi.genericmetadata import Credit, FileHash, GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib import ctsettings, ctversion
from comictaggerlib.applicationlogwindow import ApplicationLogWindow, QTextEditLogger
from comictaggerlib.autotagmatchwindow import AutoTagMatchWindow
from comictaggerlib.autotagprogresswindow import AutoTagProgressWindow, AutoTagThread
from comictaggerlib.autotagstartwindow import AutoTagSettings, AutoTagStartWindow
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.crediteditorwindow import CreditEditorWindow
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.exportwindow import ExportConfig, ExportConflictOpts, ExportWindow
from comictaggerlib.fileselectionlist import FileSelectionList
from comictaggerlib.graphics import graphics_path
from comictaggerlib.gtinvalidator import is_valid_gtin
from comictaggerlib.logwindow import LogWindow
from comictaggerlib.md import prepare_metadata, read_selected_tags
from comictaggerlib.optionalmsgdialog import OptionalMessageDialog
from comictaggerlib.pagebrowser import PageBrowserWindow
from comictaggerlib.pagelisteditor import PageListEditor
from comictaggerlib.renamewindow import RenameWindow
from comictaggerlib.resulttypes import OnlineMatchResults
from comictaggerlib.seriesselectionwindow import SeriesSelectionWindow
from comictaggerlib.settingswindow import SettingsWindow
from comictaggerlib.ui import qtutils, ui_path
from comictaggerlib.ui.pyqttoast import Toast, ToastPreset
from comictaggerlib.ui.qtutils import center_window_on_parent, enable_widget
from comictaggerlib.versionchecker import VersionChecker
from comictalker.comictalker import ComicTalker, RLCallBack, TalkerError

logger = logging.getLogger(__name__)


def execute(f: Callable[[], Any]) -> None:
    f()


class QueryThread(QtCore.QThread):  # TODO: Evaluate thread semantics. Specifically with signals
    finish = QtCore.pyqtSignal(GenericMetadata)
    ratelimit = QtCore.pyqtSignal(float, float)

    def __init__(
        self,
        talker: ComicTalker,
        issue_id: str,
        series_id: str,
        issue_number: str,
    ) -> None:
        super().__init__()
        self.issue_id = issue_id
        self.series_id = series_id
        self.issue_number = issue_number
        self.talker = talker

    def run(self) -> None:
        try:
            new_metadata = self.talker.fetch_comic_data(
                issue_id=self.issue_id,
                series_id=self.series_id,
                issue_number=self.issue_number,
                on_rate_limit=RLCallBack(lambda x, y: self.ratelimit.emit(x, y), 60),
            )
        except TalkerError as e:
            OptionalMessageDialog.critical(None, f"{e.source} {e.code_name} Error", f"{e}")
            return
        self.finish.emit(new_metadata)


class TaggerWindow(QtWidgets.QMainWindow):
    appName = "ComicTagger"
    version = ctversion.version
    ratelimit = QtCore.pyqtSignal(float, float)
    query_finished = QtCore.pyqtSignal(GenericMetadata)

    def __init__(
        self,
        config: settngs.Config[ct_ns],
        talkers: dict[str, ComicTalker],
        socket_server: QtNetwork.QLocalServer,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        with (ui_path / "taggerwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.md_attributes = {
            "data_origin": None,
            "issue_id": None,
            "original_hash": (self.cbHashName, self.leOriginalHash),
            "series": self.leSeries,
            "issue": self.leIssueNum,
            "title": self.leTitle,
            "publisher": self.lePublisher,
            "month": self.lePubMonth,
            "year": self.lePubYear,
            "day": self.lePubDay,
            "issue_count": self.leIssueCount,
            "volume": self.leVolumeNum,
            "genres": self.leGenre,
            "language": self.cbLanguage,
            "description": self.teComments,
            "volume_count": self.leVolumeCount,
            "critical_rating": self.dsbCriticalRating,
            "country": self.cbCountry,
            "alternate_series": self.leAltSeries,
            "alternate_number": self.leAltIssueNum,
            "alternate_count": self.leAltIssueCount,
            "gtin": self.leGtin,
            "imprint": self.leImprint,
            "notes": self.teNotes,
            "web_links": (self.leWebLink, self.btnOpenWebLink, self.btnAddWebLink, self.btnRemoveWebLink),
            "format": self.cbFormat,
            "manga": self.cbManga,
            "black_and_white": self.cbBW,
            "page_count": None,
            "maturity_rating": self.cbMaturityRating,
            "story_arcs": self.leStoryArc,
            "series_groups": self.leSeriesGroup,
            "scan_info": self.leScanInfo,
            "characters": self.teCharacters,
            "teams": self.teTeams,
            "locations": self.teLocations,
            "credits": (self.twCredits, self.btnAddCredit, self.btnEditCredit, self.btnRemoveCredit),
            "credits.person": 3,
            "credits.language": 2,
            "credits.role": 1,
            "credits.primary": 0,
            "tags": self.teTags,
            "pages": None,
            "page.type": None,
            "page.bookmark": None,
            "page.double_page": None,
            "page.image_index": None,
            "page.size": None,
            "page.height": None,
            "page.width": None,
            "price": None,
            "is_version_of": None,
            "rights": None,
            "identifier": None,
            "last_mark": None,
        }
        comictaggerlib.ui.qtutils.active_palette = self.leSeries.palette()
        self.config = config
        self.talkers = talkers
        self.log_window = self.setup_logger()

        self.archiveCoverWidget = CoverImageWidget(self.coverImageContainer, CoverImageWidget.ArchiveMode, None)
        grid_layout = QtWidgets.QGridLayout(self.coverImageContainer)
        grid_layout.addWidget(self.archiveCoverWidget)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        self.page_list_editor = PageListEditor(self.tabPages)
        grid_layout = QtWidgets.QGridLayout(self.tabPages)
        grid_layout.addWidget(self.page_list_editor)

        self.fileSelectionList = FileSelectionList(self.widgetListHolder, self.config[0], self.dirty_flag_verification)
        grid_layout = QtWidgets.QGridLayout(self.widgetListHolder)
        grid_layout.addWidget(self.fileSelectionList)

        self.fileSelectionList.selectionChanged.connect(self.load_archive)
        self.fileSelectionList.listCleared.connect(self.file_list_cleared)
        self.fileSelectionList.set_sorting(
            self.config[0].internal__sort_column, QtCore.Qt.SortOrder(self.config[0].internal__sort_direction)
        )
        self.socket_server = socket_server
        self.socket_server.newConnection.connect(self.on_incoming_socket_connection)

        # we can't specify relative font sizes in the UI designer, so
        # walk through all the labels in the main form, and make them
        # a smidge smaller TODO: there has to be a better way to do this
        try:
            for child in self.scrollAreaWidgetContents.children():
                if isinstance(child, QtWidgets.QLabel):
                    f = child.font()
                    if f.pointSize() > 10:
                        f.setPointSize(f.pointSize() - 2)
                    f.setItalic(True)
                    child.setFont(f)
            self.scrollAreaWidgetContents.adjustSize()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = "".join(traceback.format_tb(exc_traceback))
            logger.exception("Failed to adjust sizes")
            OptionalMessageDialog.critical(self, "Failed to adjust sizes", "", trace_back)

        try:
            self.qicon = QtGui.QIcon(str(graphics_path / "app.png"))
            self.setWindowIcon(self.qicon)
            # See self._toast for more info
            self.tray = QtWidgets.QSystemTrayIcon(self)
            self.tray.show()
            self.tray.hide()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = "".join(traceback.format_tb(exc_traceback))
            logger.exception("Failed to create a tray icon")
            OptionalMessageDialog.critical(self, "Failed to create a tray icon", "", trace_back)

        # If no tags on CLI, use last tags
        if not config[0].Runtime_Options__tags_write:
            config[0].Runtime_Options__tags_write = config[0].internal__write_tags

        if not config[0].Runtime_Options__tags_read:
            config[0].Runtime_Options__tags_read = config[0].internal__read_tags

        # Ensure we have tags at all
        config[0].Runtime_Options__tags_write = config[0].Runtime_Options__tags_write or list(self.enabled_tags())
        config[0].Runtime_Options__tags_read = config[0].Runtime_Options__tags_read or list(self.enabled_tags())

        # Remove any tags we don't know about
        for tag_id in config[0].Runtime_Options__tags_write.copy():
            if tag_id not in self.enabled_tags():
                config[0].Runtime_Options__tags_write.remove(tag_id)

        for tag_id in config[0].Runtime_Options__tags_read.copy():
            if tag_id not in self.enabled_tags():
                config[0].Runtime_Options__tags_read.remove(tag_id)

        if not self.config[0].Runtime_Options__preferred_hash:
            self.config[0].Runtime_Options__preferred_hash = self.config[0].internal__embedded_hash_type

        self.setAcceptDrops(True)
        self.view_tag_actions, self.remove_tag_actions = self.tag_actions()
        try:
            self.config_menus()
            self.statusBar()
            self.populate_combo_boxes()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = "".join(traceback.format_tb(exc_traceback))
            logger.exception("Failed to populate forms")
            OptionalMessageDialog.critical(self, "Failed to populate forms", "", trace_back)

        self.page_browser: PageBrowserWindow | None = None
        self.comic_archive: ComicArchive | None = None
        self.dirty_flag = False
        self.droppedFile = None
        self.page_loader = None
        self.droppedFiles: list[str] = []
        self.metadata = GenericMetadata()
        self.atprogdialog: AutoTagProgressWindow | None = None
        self.reset_app()

        # set up some basic field validators
        validator = QtGui.QIntValidator(1900, 2099, self)
        self.lePubYear.setValidator(validator)

        validator = QtGui.QIntValidator(1, 12, self)
        self.lePubMonth.setValidator(validator)

        # TODO: for now keep it simple, ideally we should check the full date
        validator = QtGui.QIntValidator(1, 31, self)
        self.lePubDay.setValidator(validator)

        validator = QtGui.QIntValidator(1, 99999, self)
        self.leIssueCount.setValidator(validator)
        self.leVolumeNum.setValidator(validator)
        self.leVolumeCount.setValidator(validator)
        self.leAltIssueNum.setValidator(validator)
        self.leAltIssueCount.setValidator(validator)

        # make sure some editable comboboxes don't take drop actions
        self.cbFormat.lineEdit().setAcceptDrops(False)
        self.cbMaturityRating.lineEdit().setAcceptDrops(False)

        # hook up the callbacks
        self.cbSelectedReadTags.dropdownClosed.connect(self.select_read_tags)
        self.cbSelectedWriteTags.itemChecked.connect(self.select_write_tags)
        self.cbx_sources.currentIndexChanged.connect(self.select_source)
        self.btnEditCredit.clicked.connect(self.edit_credit)
        self.btnAddCredit.clicked.connect(self.add_credit)
        self.btnRemoveCredit.clicked.connect(self.remove_credit)
        self.twCredits.cellDoubleClicked.connect(self.edit_credit)
        self.btnOpenWebLink.clicked.connect(self.open_web_link)
        self.connect_dirty_flag_signals()
        self.page_list_editor.modified.connect(self.set_dirty_flag)
        self.page_list_editor.firstFrontCoverChanged.connect(self.front_cover_changed)
        self.page_list_editor.listOrderChanged.connect(self.page_list_order_changed)
        self.tabWidget.currentChanged.connect(self.tab_changed)
        self.leGtin.textChanged.connect(self.gtin_changed)

        self.page_list_editor.set_blur(self.config[0].General__blur)

        self.ratelimit.connect(self.on_ratelimit)
        self.query_finished.connect(self.apply_query_metadata)

        def _sync_blur(*args: Any) -> None:
            self.config[0].General__blur = self.page_list_editor.blur

        self.page_list_editor.cbxBlur.clicked.connect(_sync_blur)

        self.splitter.splitterMoved.connect(self.splitter_moved_event)

        self.fileSelectionList.add_app_action(self.actionAutoIdentify)
        self.fileSelectionList.add_app_action(self.actionAutoTag)
        self.fileSelectionList.add_app_action(self.actionCopyTags)
        self.fileSelectionList.add_app_action(self.actionRename)
        self.fileSelectionList.add_app_action(self.actionRemoveAuto)
        self.fileSelectionList.add_app_action(self.actionRepackage)
        self.export_window = ExportWindow(self)
        self.export_window.export.connect(self._repackage_archive)
        if self.enabled_tags():
            # This should never be false
            self.selected_write_tags = [self.enabled_tags()[0]]
            self.selected_read_tags = [self.enabled_tags()[0]]

    def _post_show(self, file_list: list[str]) -> None:
        try:
            self.update_tag_tweaks()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = "".join(traceback.format_tb(exc_traceback))
            logger.exception("Failed to update form for current tags")
            OptionalMessageDialog.warning(self, "Failed to update form for current tags", "", trace_back)

        try:
            if file_list:
                self.fileSelectionList.add_path_list(file_list)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = "".join(traceback.format_tb(exc_traceback))
            logger.exception("Failed to load comics")
            OptionalMessageDialog.warning(self, "Failed to load comics", "", trace_back)

        self.set_app_position()
        if self.config[0].internal__form_width != -1:
            self.splitter.setSizes([self.config[0].internal__form_width, self.config[0].internal__list_width])
        self.raise_()
        QtCore.QCoreApplication.processEvents()
        self.resizeEvent(None)

        connection_type = QtCore.Qt.ConnectionType.SingleShotConnection

        def show_welcome() -> None:
            if not self.config[0].Dialog_Flags__show_disclaimer:
                show_plugin_notice()
                return

            def set_checked(checked: bool) -> None:
                self.config[0].Dialog_Flags__show_disclaimer = not checked

            dialog = OptionalMessageDialog.msg(
                self,
                "Welcome!",
                textwrap.dedent(
                    """
                Thanks for trying ComicTagger!

                Be aware that this is beta-level software, and consider it experimental.

                You should use it very carefully when modifying your data files.  As the
                license says, it's "AS IS!"

                Also, be aware that writing tags to comic archives will change their file hashes,
                which has implications with respect to other software packages.  It's best to
                use ComicTagger on local copies of your comics.

                Additional metadata sources are listed [here] along with links to available plugins.

                COMIC VINE NOTE: Using the default API key will serverly limit search and tagging
                times. A personal API key will allow for a **5 times increase** in online search speed. See the
                [Wiki page]
                for more information.

                Have fun!

                [here]: https://github.com/comictagger/comictagger/wiki/Comic-and-Manga-Information-Sources
                [Wiki page]: https://github.com/comictagger/comictagger/wiki/UserGuide#comic-vine
                    """
                ),
            )
            dialog.check_status.connect(set_checked)
            dialog.finished.connect(
                lambda _result: QtCore.QTimer.singleShot(0, show_plugin_notice), type=connection_type
            )

        def show_plugin_notice() -> None:
            if not self.config[0].Dialog_Flags__notify_plugin_changes:
                check_for_new_version()
                return

            def set_checked(checked: bool) -> None:
                self.config[0].Dialog_Flags__notify_plugin_changes = not checked

            self.dlg = OptionalMessageDialog.msg(
                self,
                "Plugins Have moved!",
                textwrap.dedent(
                    f"""
                Due to techinical issues the Metron is not supported anymore and the GCD plugin is no longer bundled in ComicTagger!

                You will need to download the .zip or .whl from the GitHub release page to:
                ```plain
                {str(self.config[0].Runtime_Options__config.user_plugin_dir)}
                ```
                GCD: https://github.com/comictagger/gcd_talker/releases

                For more information on installing plugins see the wiki page:

                https://github.com/comictagger/comictagger/wiki/Installing-plugins
                """
                ),
            )
            self.dlg.check_status.connect(set_checked)
            self.dlg.finished.connect(
                lambda _result: QtCore.QTimer.singleShot(0, check_for_new_version), type=connection_type
            )

        def check_for_new_version() -> None:
            try:
                if self.config[0].General__check_for_new_version:
                    self.check_latest_version_online()
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                trace_back = "".join(traceback.format_tb(exc_traceback))
                logger.exception("Failed to check for new version")
                OptionalMessageDialog.critical(
                    self, "Failed to check for new version", "Failed to check for new version", trace_back
                )

        show_welcome()

        self.export_window = ExportWindow(self)
        self.export_window.export.connect(self._repackage_archive)

    def enabled_tags(self) -> Sequence[str]:
        return [tag.id for tag in tags.values() if tag.enabled]

    def tag_actions(self) -> tuple[dict[str, QtGui.QAction], dict[str, QtGui.QAction]]:
        view_raw_tags: dict[str, QtGui.QAction] = {}
        remove_raw_tags: dict[str, QtGui.QAction] = {}
        for tag in tags.values():
            view_raw_tags[tag.id] = self.menuViewRawTags.addAction(f"View Raw {tag.name()} Tags")
            view_raw_tags[tag.id].setEnabled(tag.enabled)
            view_raw_tags[tag.id].setStatusTip(f"View raw {tag.name()} tag block from file")
            view_raw_tags[tag.id].triggered.connect(functools.partial(self.view_raw_tags, tag.id))

            remove_raw_tags[tag.id] = self.menuRemove.addAction(f"Remove Raw {tag.name()} Tags")
            remove_raw_tags[tag.id].setEnabled(tag.enabled)
            remove_raw_tags[tag.id].setStatusTip(f"Remove {tag.name()} tags from comic archive")
            remove_raw_tags[tag.id].triggered.connect(functools.partial(self.prompt_remove_tags, [tag.id]))

        return view_raw_tags, remove_raw_tags

    def current_talker(self) -> ComicTalker:
        if self.config[0].Sources__source in self.talkers:
            return self.talkers[self.config[0].Sources__source]
        logger.error("Could not find the '%s' talker", self.config[0].Sources__source)
        raise SystemExit(2)

    def open_file_event(self, url: QtCore.QUrl) -> None:
        logger.info(url.toLocalFile())
        self.fileSelectionList.add_path_list([url.toLocalFile()])

    def sigint_handler(self, *args: Any) -> None:
        # defer the actual close in the app loop thread
        QtCore.QTimer.singleShot(200, lambda: execute(self.close))

    def setup_logger(self) -> ApplicationLogWindow:
        try:
            current_logs = (self.config[0].Runtime_Options__config.user_log_dir / "ComicTagger.log").read_text("utf-8")
        except Exception:
            current_logs = ""
        root_logger = logging.getLogger()
        qapplogwindow = ApplicationLogWindow(
            self.config[0].Runtime_Options__config.user_log_dir,
            QTextEditLogger(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"), logging.DEBUG),
            parent=self,
        )
        qapplogwindow.addAction(self.actionExit)
        qapplogwindow.textEdit.append(current_logs.strip())
        root_logger.addHandler(qapplogwindow.log_handler)
        return qapplogwindow

    def reset_app(self) -> None:
        self.archiveCoverWidget.clear()
        self.comic_archive = None
        self.dirty_flag = False
        self.clear_form()
        self.page_list_editor.reset_page()
        if self.page_browser is not None:
            self.page_browser.reset()
        self.update_app_title()
        self.update_menus()
        self.update_info_box()

        self.droppedFile = None
        self.page_loader = None

    def update_app_title(self) -> None:
        if self.comic_archive is None:
            self.setWindowTitle(self.appName)
            return

        mod_str = ""
        ro_str = ""

        if self.dirty_flag:
            mod_str = " [modified]"

        if not self.comic_archive.is_writable():
            ro_str = " [read only]"

        self.setWindowTitle(f"{self.appName} - {self.comic_archive.path}{mod_str}{ro_str}")

    def toggle_enable_embedding_hashes(self) -> None:
        self.config[0].Runtime_Options__enable_embedding_hashes = self.actionEnableEmbeddingHashes.isChecked()
        enabled_widgets = set()
        for tag_id in self.config[0].Runtime_Options__tags_write:
            if not tags[tag_id].enabled:
                continue
            enabled_widgets.update(tags[tag_id].supported_attributes)
        enable_widget(
            self.md_attributes["original_hash"],
            self.config[0].Runtime_Options__enable_embedding_hashes and "original_hash" in enabled_widgets,
        )
        if not self.leOriginalHash.text().strip():
            self.cbHashName.setCurrentText(self.config[0].internal__embedded_hash_type)
        if self.config[0].Runtime_Options__enable_embedding_hashes:
            self.config[0].Runtime_Options__preferred_hash = self.config[0].internal__embedded_hash_type
        else:
            self.config[0].Runtime_Options__preferred_hash = ""

    def config_menus(self) -> None:
        # File Menu
        self.actionAutoTag.triggered.connect(self.auto_tag)
        self.actionCopyTags.triggered.connect(self.prompt_copy_tags)
        self.actionExit.triggered.connect(self.close)
        self.actionExit.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)  # Doesn't work
        self.actionLoad.triggered.connect(self.select_file)
        self.actionLoadFolder.triggered.connect(self.select_folder)
        self.actionOpenFolderAsComic.triggered.connect(self.select_folder_archive)
        self.actionRemoveAuto.triggered.connect(self.remove_auto)
        self.actionRename.triggered.connect(self.rename_archive)
        self.actionRepackage.triggered.connect(self.repackage_archive)
        self.actionSettings.triggered.connect(self.show_settings)
        self.actionWrite_Tags.triggered.connect(self.prompt_write_tags)
        # Tag Menu
        self.actionApplyCBLTransform.triggered.connect(self.apply_cbl_transform)
        self.actionAutoIdentify.triggered.connect(self.auto_identify_search)
        self.actionAutoImprint.triggered.connect(self.auto_imprint)
        self.actionClearEntryForm.triggered.connect(self.clear_form)
        self.actionLiteralSearch.triggered.connect(self.literal_search)
        self.actionParse_Filename.triggered.connect(self.use_filename)
        self.actionParse_Filename_split_words.triggered.connect(self.use_filename_split)
        self.actionReCalcArchiveInfo.triggered.connect(self.recalc_archive_info)
        self.actionSearchOnline.triggered.connect(self.query_online)
        self.actionEnableEmbeddingHashes: QtGui.QAction
        self.actionEnableEmbeddingHashes.triggered.connect(self.toggle_enable_embedding_hashes)
        self.actionEnableEmbeddingHashes.setChecked(self.config[0].Runtime_Options__enable_embedding_hashes)
        # Window Menu
        self.actionLogWindow.triggered.connect(self.log_window.show)
        self.actionPageBrowser.triggered.connect(self.show_page_browser)
        # Help Menu
        self.actionAbout.triggered.connect(self.about_app)
        self.actionComicTaggerForum.triggered.connect(self.show_forum)
        self.actionReportBug.triggered.connect(self.report_bug)
        self.actionWiki.triggered.connect(self.show_wiki)

        self.actionAddWebLink.triggered.connect(self.add_weblink_item)
        self.actionRemoveWebLink.triggered.connect(self.remove_weblink_item)

        self.leWebLink.addAction(self.actionAddWebLink)
        self.leWebLink.addAction(self.actionRemoveWebLink)

    def add_weblink_item(self, url: str = "") -> None:
        item = ""
        if isinstance(url, str):
            item = url
        self.leWebLink.addItem(item)
        self.leWebLink.item(self.leWebLink.count() - 1).setFlags(
            QtCore.Qt.ItemFlag.ItemIsEditable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsDragEnabled
            | QtCore.Qt.ItemFlag.ItemIsSelectable
        )
        self.leWebLink.item(self.leWebLink.count() - 1).setSelected(True)
        if not url:
            self.leWebLink.editItem(self.leWebLink.item(self.leWebLink.count() - 1))

    def remove_weblink_item(self) -> None:
        item = self.leWebLink.takeItem(self.leWebLink.currentRow())
        del item

    def repackage_archive(self) -> None:
        ca_list = self.fileSelectionList.get_selected_archive_list()
        to_zip = [ca for ca in ca_list if not ca.is_zip()]

        if not to_zip:
            logger.warning("Export as Zip Archive. Only ZIP archives are selected")
            OptionalMessageDialog.information(self, "Export as Zip Archive", "Only ZIP archives are selected!")
            return

        if not self.dirty_flag_verification(
            "Export as Zip Archive",
            "If you export archives as Zip now, unsaved data in the form may be lost.  Are you sure?",
        ):
            return

        self.export_window.show(len(to_zip))

    def _repackage_archive(self, export_config: ExportConfig) -> None:
        largest_page_size = 0
        ca_list = self.fileSelectionList.get_selected_archive_list()
        to_zip = []
        for ca in ca_list:
            if not ca.is_zip():
                to_zip.append(ca)
            if ca.get_number_of_pages() > largest_page_size:
                largest_page_size = ca.get_number_of_pages()

        prog_dialog = None
        if len(to_zip) > 3 or largest_page_size > 24:
            prog_dialog = QtWidgets.QProgressDialog("", "Cancel", 0, len(to_zip), self)
            prog_dialog.setWindowTitle("Exporting as ZIP")
            prog_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            prog_dialog.setMinimumDuration(300)
            center_window_on_parent(prog_dialog)
        QtCore.QCoreApplication.processEvents()

        new_archives_to_add = []
        archives_to_remove = []
        skipped_list = []
        failed_list = []
        success_count = 0
        logger.debug("Exporting %d comics to zip", len(to_zip))

        for prog_idx, ca in enumerate(to_zip, 1):
            logger.debug("Exporting comic %d: %s", prog_idx, ca.path)
            if prog_dialog is not None:
                if prog_dialog.wasCanceled():
                    break
                if prog_idx % 10 == 0 or len(ca_list) < 50:
                    prog_dialog.setValue(prog_idx)
                    prog_dialog.setLabelText(str(ca.path))
                    QtCore.QCoreApplication.processEvents()

            export_name = ca.path.with_suffix(".cbz")
            export = True

            if export_config.conflict == ExportConflictOpts.DONT_CREATE:
                export = False
                skipped_list.append(ca.path)
            elif export_config.conflict == ExportConflictOpts.CREATE_UNIQUE:
                export_name = utils.unique_file(export_name)

            if export:
                logger.debug("Exporting %s to %s", ca.path, export_name)
                if ca.export_as_zip(export_name):
                    success_count += 1
                    if export_config.add_to_list:
                        new_archives_to_add.append(str(export_name))
                    if export_config.delete_original:
                        archives_to_remove.append(ca)
                        ca.path.unlink(missing_ok=True)

                else:
                    # last export failed, so remove the zip, if it exists
                    failed_list.append(ca.path)
                    if export_name.exists():
                        export_name.unlink(missing_ok=True)

        if prog_dialog is not None:
            prog_dialog.hide()
        self.fileSelectionList.remove_archive_list(archives_to_remove)

        summary = f"Successfully created {success_count} Zip archive(s)."
        if skipped_list:
            summary += f"\n\nThe following {len(skipped_list)} archive(s) were skipped due to file name conflicts:\n"
            for f in skipped_list:
                summary += f"\t{f}\n"
        if failed_list:
            summary += f"\n\nThe following {len(failed_list)} archive(s) failed to export due to read/write errors:\n"
            for f in failed_list:
                summary += f"\t{f}\n"

        logger.info(summary)
        dlg = LogWindow(self)
        dlg.set_text(summary)
        dlg.setWindowTitle("Archive Export to Zip Summary")
        dlg.show()
        self.fileSelectionList.add_path_list(new_archives_to_add)

    def about_app(self) -> None:
        website = "https://github.com/comictagger/comictagger"
        email = "comictagger@gmail.com"
        license_link = "http://www.apache.org/licenses/LICENSE-2.0"
        license_name = "Apache License 2.0"

        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("About " + self.appName)
        msg_box.setTextFormat(QtCore.Qt.TextFormat.RichText)
        msg_box.setIconPixmap(QtGui.QPixmap(":/graphics/about.png"))
        msg_box.setText(
            "<br><br><br>"
            + self.appName
            + f" v{self.version}"
            + "<br>"
            + "&copy;2014-2022 ComicTagger Devs<br><br>"
            + f"<a href='{website}'>{website}</a><br><br>"
            + f"<a href='mailto:{email}'>{email}</a><br><br>"
            + f"License: <a href='{license_link}'>{license_name}</a>"
        )
        msg_box.addAction(self.actionExit)

        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.show()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        self.droppedFiles = []
        if event.mimeData().hasUrls():
            # walk through the URL list and build a file list
            for url in event.mimeData().urls():
                if url.isValid() and url.scheme() == "file":
                    self.droppedFiles.append(url.toLocalFile())

            if self.droppedFiles is not None:
                event.accept()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        control_pressed = event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier

        if control_pressed:
            for folder_archive in self.droppedFiles:
                self.fileSelectionList.twList.selectRow(self.fileSelectionList.add_path_item(folder_archive)[0])
        else:
            self.fileSelectionList.add_path_list(self.droppedFiles)
        event.accept()

    def update_ui_for_archive(self, parse_filename: bool = True) -> None:
        if self.comic_archive is not None:
            if self.metadata.is_empty and parse_filename:
                self.use_filename()

            self.metadata.apply_default_page_list(self.comic_archive.get_page_name_list())

        self.update_cover_image()

        if self.page_browser is not None and self.comic_archive is not None:
            self.page_browser.set_comic_archive(self.comic_archive)
            self.page_browser.metadata = self.metadata

        self.metadata_to_form()
        self.clear_dirty_flag()  # also updates the app title
        self.update_info_box()
        self.update_menus()
        self.update_app_title()

    def update_cover_image(self) -> None:
        cover_idx = self.metadata.get_cover_page_index_list()[0]
        if self.comic_archive is not None:
            self.archiveCoverWidget.set_archive(self.comic_archive, cover_idx)

    def update_menus(self) -> None:
        enabled = self.comic_archive is not None
        writeable = self.comic_archive is not None and self.comic_archive.is_writable()
        self.actionApplyCBLTransform.setEnabled(enabled)
        self.actionAutoIdentify.setEnabled(enabled)
        self.actionAutoTag.setEnabled(enabled)
        self.actionCopyTags.setEnabled(enabled)
        self.actionParse_Filename.setEnabled(enabled)
        self.actionParse_Filename_split_words.setEnabled(enabled)
        self.actionReCalcArchiveInfo.setEnabled(enabled)
        self.actionRemoveAuto.setEnabled(enabled)
        self.actionRename.setEnabled(enabled)
        self.actionRepackage.setEnabled(enabled)

        self.menuRemove.setEnabled(enabled)
        self.menuViewRawTags.setEnabled(enabled)
        if self.comic_archive is not None:
            for tag_id in tags:
                self.view_tag_actions[tag_id].setEnabled(tags[tag_id].enabled and self.comic_archive.has_tags(tag_id))
                self.remove_tag_actions[tag_id].setEnabled(tags[tag_id].enabled and self.comic_archive.has_tags(tag_id))

            if writeable:
                self.actionWrite_Tags
                self.actionWrite_Tags.triggered.disconnect()
                self.actionWrite_Tags.triggered.connect(self.prompt_write_tags)
                self.actionWrite_Tags.setToolTip("")
                self.actionWrite_Tags.setStatusTip("")
            else:
                self.actionWrite_Tags.triggered.disconnect()
                self.actionWrite_Tags.triggered.connect(
                    functools.partial(
                        self._toast,
                        "Unable to write Tags",
                        f"Archive is not writeable\n{self.comic_archive.path}",
                        5000,
                    )
                )
                self.actionWrite_Tags.setToolTip("Archive is not writeable")
                self.actionWrite_Tags.setStatusTip("Archive is not writeable")

    def update_info_box(self) -> None:
        ca = self.comic_archive

        if ca is None:
            self.lblFilename.setText("")
            self.lblArchiveType.setText("")
            self.lblTagList.setText("")
            self.lblPageCount.setText("")
            return

        filename = os.path.basename(ca.path)
        filename = os.path.splitext(filename)[0]
        filename = FileNameParser().fix_spaces(filename, False)

        self.lblFilename.setText(filename)

        self.lblArchiveType.setText(ca.archiver.name() + " archive")

        page_count = f" ({ca.get_number_of_pages()} pages)"
        self.lblPageCount.setText(page_count)

        supported_md = ca.get_supported_tags()
        tag_info = ""
        for md in supported_md:
            if ca.has_tags(md):
                tag_info += "• " + tags[md].name() + "\n"

        self.lblTagList.setText(tag_info)

    def set_dirty_flag(self) -> None:
        if not self.dirty_flag:
            self.dirty_flag = True
            self.fileSelectionList.set_modified_flag(True)
            self.update_app_title()

    def clear_dirty_flag(self) -> None:
        if self.dirty_flag:
            self.dirty_flag = False
            self.fileSelectionList.set_modified_flag(False)
            self.update_app_title()

    def connect_dirty_flag_signals(self) -> None:
        # recursively connect the tab form child slots
        self.connect_child_dirty_flag_signals(self.tabWidget)

    def connect_child_dirty_flag_signals(self, widget: QtCore.QObject) -> None:
        if isinstance(widget, QtWidgets.QLineEdit):
            widget.textEdited.connect(self.set_dirty_flag)
        if isinstance(widget, QtWidgets.QTextEdit):
            widget.textChanged.connect(self.set_dirty_flag)
        if isinstance(widget, QtWidgets.QComboBox):
            widget.currentIndexChanged.connect(self.set_dirty_flag)
        if isinstance(widget, QtWidgets.QCheckBox):
            widget.stateChanged.connect(self.set_dirty_flag)
        if isinstance(widget, QtWidgets.QListWidget):
            widget.itemChanged.connect(self.set_dirty_flag)

        # recursive call on children
        for child in widget.children():
            if child != self.page_list_editor:
                self.connect_child_dirty_flag_signals(child)

    def clear_form(self) -> None:
        # get a minty fresh metadata object
        self.metadata = GenericMetadata()

        # recursively clear the tab form
        self.clear_children(self.tabWidget)

        # clear the dirty flag, since there is nothing in there now to lose
        self.clear_dirty_flag()
        self.update_ui_for_archive(parse_filename=False)

    def clear_children(self, widget: QtCore.QObject) -> None:
        if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit)):
            widget.setText("")
        if isinstance(widget, QtWidgets.QComboBox):
            widget.setCurrentIndex(0)
        if isinstance(widget, QtWidgets.QCheckBox):
            widget.setChecked(False)
        if isinstance(widget, QtWidgets.QTableWidget):
            widget.setRowCount(0)
        if isinstance(widget, QtWidgets.QListWidget):
            widget.clear()

        # recursive call on children
        for child in widget.children():
            self.clear_children(child)

    # Copy all of the metadata object into the form.
    # Merging of metadata should be done via the overlay function
    def metadata_to_form(self) -> None:
        def assign_text(field: QtWidgets.QLineEdit | QtWidgets.QTextEdit, value: Any) -> None:
            if value is not None:
                if isinstance(field, QtWidgets.QTextEdit) and False:
                    field.setPlainText(str(value))
                else:
                    field.setText(str(value))

        md = self.metadata

        original_hash = md.original_hash or FileHash("", "")
        self.cbHashName.setCurrentText(original_hash.name or self.config[0].internal__embedded_hash_type)
        assign_text(self.leOriginalHash, original_hash.hash)
        assign_text(self.leSeries, md.series)
        assign_text(self.leIssueNum, md.issue)
        assign_text(self.leIssueCount, md.issue_count)
        assign_text(self.leVolumeNum, md.volume)
        assign_text(self.leVolumeCount, md.volume_count)
        assign_text(self.leTitle, md.title)
        assign_text(self.lePublisher, md.publisher)
        assign_text(self.lePubMonth, md.month)
        assign_text(self.lePubYear, md.year)
        assign_text(self.lePubDay, md.day)
        assign_text(self.leGenre, ",".join(md.genres))
        assign_text(self.leImprint, md.imprint)
        assign_text(self.teComments, md.description)
        assign_text(self.teNotes, md.notes)
        assign_text(self.leStoryArc, ",".join(md.story_arcs))
        assign_text(self.leScanInfo, md.scan_info)
        assign_text(self.leSeriesGroup, ",".join(md.series_groups))
        assign_text(self.leAltSeries, md.alternate_series)
        assign_text(self.leAltIssueNum, md.alternate_number)
        assign_text(self.leAltIssueCount, md.alternate_count)
        self.leWebLink.clear()
        for u in md.web_links:
            self.add_weblink_item(u.url)
        assign_text(self.teCharacters, "\n".join(md.characters))
        assign_text(self.teTeams, "\n".join(md.teams))
        assign_text(self.teLocations, "\n".join(md.locations))

        assign_text(self.leGtin, md.gtin)

        self.dsbCriticalRating.setValue(md.critical_rating or 0.0)

        if md.format is not None and md.format != "":
            i = self.cbFormat.findText(md.format)
            if i == -1:
                self.cbFormat.setEditText(md.format)
            else:
                self.cbFormat.setCurrentIndex(i)

        if md.maturity_rating is not None and md.maturity_rating != "":
            i = self.cbMaturityRating.findText(md.maturity_rating)
            if i == -1:
                self.cbMaturityRating.setEditText(md.maturity_rating)
            else:
                self.cbMaturityRating.setCurrentIndex(i)
        else:
            self.cbMaturityRating.setCurrentIndex(0)

        if md.language is not None:
            i = self.cbLanguage.findData(md.language)
            self.cbLanguage.setCurrentIndex(i)
        else:
            self.cbLanguage.setCurrentIndex(0)

        if md.country is not None:
            i = self.cbCountry.findText(md.country)
            self.cbCountry.setCurrentIndex(i)
        else:
            self.cbCountry.setCurrentIndex(0)

        if md.manga is not None:
            i = self.cbManga.findData(md.manga)
            self.cbManga.setCurrentIndex(i)
        else:
            self.cbManga.setCurrentIndex(0)

        if md.black_and_white:
            self.cbBW.setChecked(True)
        else:
            self.cbBW.setChecked(False)

        self.teTags.setText(", ".join(md.tags))

        self.twCredits.setRowCount(0)

        if md.credits is not None and len(md.credits) != 0:
            self.twCredits.setSortingEnabled(False)

            for row, credit in enumerate(md.credits):
                # Always add to the list. We don't want to accidentally remove credits a user may want
                self.add_new_credit_entry(row, credit)
        if self.comic_archive:
            self.page_list_editor.set_data(self.comic_archive, self.metadata.pages)

        self.twCredits.setSortingEnabled(True)
        self.update_credit_colors()
        self.toggle_enable_embedding_hashes()

    def add_new_credit_entry(self, row: int, credit: Credit) -> None:
        self.twCredits.insertRow(row)

        item = QtWidgets.QTableWidgetItem(credit.role)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, credit.role)
        self.twCredits.setItem(row, self.md_attributes["credits.role"], item)

        language = utils.get_language_from_iso(credit.language) or credit.language
        item = QtWidgets.QTableWidgetItem(language)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, credit.language)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, credit.language)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.twCredits.setItem(row, self.md_attributes["credits.language"], item)

        item = QtWidgets.QTableWidgetItem(credit.person)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, credit.person)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.twCredits.setItem(row, self.md_attributes["credits.person"], item)

        item = QtWidgets.QTableWidgetItem("")
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.twCredits.setItem(row, self.md_attributes["credits.primary"], item)
        self.update_credit_primary_flag(row, credit.primary)

    def get_dupe_credit(self, row: int | None, role: str, name: str) -> int:
        for r in range(self.twCredits.rowCount()):
            if r == row:
                continue

            if (
                self.twCredits.item(r, self.md_attributes["credits.role"]).text() == role
                and self.twCredits.item(r, self.md_attributes["credits.person"]).text() == name
            ):
                return r

        return -1

    def form_to_metadata(self) -> None:
        # copy the data from the form into the metadata
        md = GenericMetadata()
        md.is_empty = False

        if utils.xlate(self.cbHashName.currentText()) and utils.xlate(self.leOriginalHash.text()):
            md.original_hash = FileHash(
                utils.xlate(self.cbHashName.currentText()) or "", utils.xlate(self.leOriginalHash.text()) or ""
            )
        md.alternate_number = utils.xlate(IssueString(self.leAltIssueNum.text()).as_string())
        md.issue = utils.xlate(IssueString(self.leIssueNum.text()).as_string())
        md.issue_count = utils.xlate_int(self.leIssueCount.text())
        md.volume = utils.xlate_int(self.leVolumeNum.text())
        md.volume_count = utils.xlate_int(self.leVolumeCount.text())
        md.month = utils.xlate_int(self.lePubMonth.text())
        md.year = utils.xlate_int(self.lePubYear.text())
        md.day = utils.xlate_int(self.lePubDay.text())
        md.alternate_count = utils.xlate_int(self.leAltIssueCount.text())

        md.series = utils.xlate(self.leSeries.text())
        md.title = utils.xlate(self.leTitle.text())
        md.publisher = utils.xlate(self.lePublisher.text())
        md.genres = set(utils.split(self.leGenre.text(), ","))
        md.imprint = utils.xlate(self.leImprint.text())
        md.description = utils.xlate(self.teComments.toPlainText())
        md.notes = utils.xlate(self.teNotes.toPlainText())
        md.maturity_rating = utils.xlate(self.cbMaturityRating.currentText())

        md.critical_rating = utils.xlate_float(self.dsbCriticalRating.cleanText())
        if md.critical_rating == 0.0:
            md.critical_rating = None

        md.story_arcs = utils.split(self.leStoryArc.text(), ",")
        md.scan_info = utils.xlate(self.leScanInfo.text())
        md.series_groups = utils.split(self.leSeriesGroup.text(), ",")
        md.alternate_series = utils.xlate(self.leAltSeries.text())
        md.gtin = utils.xlate(self.leGtin.text())
        md.web_links = [utils.parse_url(self.leWebLink.item(i).text()) for i in range(self.leWebLink.count())]
        md.characters = set(utils.split(self.teCharacters.toPlainText(), "\n"))
        md.teams = set(utils.split(self.teTeams.toPlainText(), "\n"))
        md.locations = set(utils.split(self.teLocations.toPlainText(), "\n"))

        md.format = utils.xlate(self.cbFormat.currentText())
        md.country = utils.xlate(self.cbCountry.currentText())

        md.language = utils.xlate(self.cbLanguage.itemData(self.cbLanguage.currentIndex()))

        md.manga = utils.xlate(self.cbManga.itemData(self.cbManga.currentIndex()))

        # Make a list from the comma delimited tags string
        md.tags = set(utils.split(self.teTags.toPlainText(), ","))

        md.black_and_white = self.cbBW.isChecked()

        # get the credits from the table
        md.credits = []

        for row in range(self.twCredits.rowCount()):
            role = self.twCredits.item(row, self.md_attributes["credits.role"]).text()
            lang = (
                self.twCredits.item(row, self.md_attributes["credits.language"]).data(QtCore.Qt.ItemDataRole.UserRole)
                or self.twCredits.item(row, self.md_attributes["credits.language"]).text()
            )
            name = self.twCredits.item(row, self.md_attributes["credits.person"]).text()
            primary_flag = self.twCredits.item(row, self.md_attributes["credits.primary"]).text() != ""

            md.add_credit(name, role, bool(primary_flag), lang)

        md.pages = self.page_list_editor.get_page_list()

        # Preserve hidden md values
        md.data_origin = self.metadata.data_origin
        md.issue_id = self.metadata.issue_id
        md.series_id = self.metadata.series_id

        md.price = self.metadata.price
        md.identifier = self.metadata.identifier
        md.rights = self.metadata.rights

        self.metadata = md

    def use_filename(self) -> None:
        self._use_filename()

    def _use_filename(self, split_words: bool = False) -> None:
        if self.comic_archive is not None:
            # copy the form onto metadata object
            self.form_to_metadata()
            new_metadata = self.comic_archive.metadata_from_filename(
                self.config[0].Filename_Parsing__filename_parser,
                self.config[0].Filename_Parsing__remove_c2c,
                self.config[0].Filename_Parsing__remove_fcbd,
                self.config[0].Filename_Parsing__remove_publisher,
                split_words,
                self.config[0].Filename_Parsing__allow_issue_start_with_letter,
                self.config[0].Filename_Parsing__protofolius_issue_number_scheme,
            )
            self.metadata.overlay(new_metadata, mode=comicapi.merge.Mode.OVERLAY, merge_lists=False)
            self.metadata_to_form()

    def use_filename_split(self) -> None:
        self._use_filename(True)

    def select_folder(self) -> None:
        self.select_file(folder_mode=True)

    def select_folder_archive(self) -> None:
        self.select_file(folder_mode=True, recursive=False)

    def select_file(self, folder_mode: bool = False, recursive: bool = True) -> None:
        dialog = self.file_dialog(folder_mode=folder_mode)
        if recursive:
            dialog.filesSelected.connect(self._load_files)
        else:
            dialog.fileSelected.connect(self._load_single_file)
        dialog.open()

    def _load_single_file(self, file: str) -> None:
        if file:
            self.fileSelectionList.twList.selectRow(self.fileSelectionList.add_path_item(file)[0])

    def _load_files(self, files: list[str]) -> None:
        if files:
            self.fileSelectionList.add_path_list(files)

    def file_dialog(self, folder_mode: bool = False) -> QtWidgets.QFileDialog:
        dialog = QtWidgets.QFileDialog(self)
        if folder_mode:
            dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        else:
            archive_filter = "Comic archive files (*.cbz *.zip *.cbr *.rar *.cb7 *.7z)"
            filters = [archive_filter, "Any files (*)"]
            dialog.setNameFilters(filters)
            dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)

        if os.environ.get("XDG_SESSION_DESKTOP", "") == "KDE":
            dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog)

        if self.config[0].internal__last_opened_folder is not None:
            dialog.setDirectory(self.config[0].internal__last_opened_folder)
        return dialog

    def auto_identify_search(self) -> None:
        if self.comic_archive is None:
            OptionalMessageDialog.warning(self, "Automatic Identify Search", "You need to load a comic first!")
            return

        self.query_online(autoselect=True)

    def literal_search(self) -> None:
        self.query_online(autoselect=False, literal=True)

    def query_online(self, autoselect: bool = False, literal: bool = False) -> None:
        issue_number = str(self.leIssueNum.text()).strip()

        # Only need this check is the source has issue level data.
        if autoselect and issue_number == "":
            OptionalMessageDialog.information(
                self,
                "Automatic Identify Search",
                "Can't auto-identify without an issue number. The auto-tag function has the 'If no issue number, assume \"1\"' option if desired.",
            )
            return

        if str(self.leSeries.text()).strip() != "":
            series_name = str(self.leSeries.text()).strip()
        else:
            OptionalMessageDialog.information(self, "Online Search", "Need to enter a series name to search.")
            return

        year = utils.xlate_int(self.lePubYear.text())

        issue_count = utils.xlate_int(self.leIssueCount.text())

        self.selector = SeriesSelectionWindow(
            self,
            self.config[0],
            self.current_talker(),
            series_name,
            issue_number,
            self.comic_archive,
            year,
            issue_count,
            autoselect,
            literal,
        )
        self.selector.ratelimit.connect(self.on_ratelimit)

        self.selector.setWindowTitle(f"Search: '{series_name}' - Select Series")
        self.selector.finished.connect(self.finish_query)

        self.selector.perform_query()

    def finish_query(self, result: list[GenericMetadata]) -> None:
        if not (result and self.selector):
            return

        self.querythread = QueryThread(
            self.current_talker(),
            self.selector.issue_id,
            self.selector.series_id,
            self.selector.issue_number,
        )
        self.querythread.finish.connect(self.query_finished)
        self.querythread.ratelimit.connect(self.ratelimit)
        self.querythread.start()

    def apply_query_metadata(self, new_metadata: GenericMetadata) -> None:
        QtWidgets.QApplication.restoreOverrideCursor()

        # copy the form onto metadata object
        self.form_to_metadata()

        if new_metadata is None or new_metadata.is_empty:
            OptionalMessageDialog.critical(self, "Search", f"Could not find an issue {new_metadata} for that series")
            return

        self.metadata = prepare_metadata(self.metadata, new_metadata, self.config[0])
        # Now push the new combined data into the edit controls
        self.metadata_to_form()

    def on_ratelimit(self, full_time: float, sleep_time: float) -> None:
        self._toast(
            "Rate Limit Hit!",
            f"Rate limit reached: {full_time:.0f}s until next request. Waiting {sleep_time:.0f}s for ratelimit",
            abs(int(sleep_time * 1000) + 200),
        )

    def _toast(self, title: str, text: str, duration: int) -> None:
        # QT doesn't initialize QSystemTrayIcon until you call show. on_ratelimit calls .show, .showMessage, and then .hide so that a tray item is not persistent.
        # Specifically macOS will make an invisible tray icon if you keep it visible, even without an icon
        # macOS wil also not popup the notification if the tray icon is hidden immediately after sending a message
        # testing indicates 200ms wait is needed to let the popup show

        if QtWidgets.QSystemTrayIcon.supportsMessages():
            self.tray.show()
            self.tray.showMessage(
                title,
                text,
                self.windowIcon(),
                abs(duration),
            )
            QtCore.QTimer.singleShot(200, self.tray.hide)
            return
        self.toast = Toast(self)
        # self.toast.__position_relative_to_widget = self
        if qtutils.is_dark_mode():
            self.toast.applyPreset(ToastPreset.WARNING_DARK)
        else:
            self.toast.applyPreset(ToastPreset.WARNING)

        # Convert to milliseconds, add 200ms because python is slow
        self.toast.setDuration(abs(duration))
        self.toast.setResetDurationOnHover(False)
        self.toast.setFadeOutDuration(50)
        self.toast.setTitle(title)
        self.toast.setText(text)
        self.toast.setAlwaysOnMainScreen(True)
        self.toast.show()

    def prompt_write_tags(self) -> None:
        if self.metadata is None or self.comic_archive is None:
            OptionalMessageDialog.information(self, "Whoops!", "No data to write!")
            return
        if not self.comic_archive.is_writable():
            self._toast("Unable to write Tags", f"Archive is not writeable\n{self.comic_archive.path}", 5000)
            return

        if not self.config[0].General__prompt_on_save:
            return self.write_tags()

        qmsg = OptionalMessageDialog.msg(
            parent=self,
            title="Save Tags",
            msg=f"Are you sure you wish to save {', '.join([tags[tag_id].name() for tag_id in self.config[0].Runtime_Options__tags_write])} tags to this archive?",
            icon=OptionalMessageDialog.Icon.Question,
        )
        qmsg.accepted.connect(self.write_tags)
        qmsg.check_status.connect(self._update_prompt_on_save)

    def _update_prompt_on_save(self, check: bool) -> None:
        self.config[0].General__prompt_on_save = not check

    def write_tags(self) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        self.form_to_metadata()
        assert self.comic_archive
        failed_tag: str = ""
        # Save each tag
        for tag_id in self.config[0].Runtime_Options__tags_write:
            success = self.comic_archive.write_tags(self.metadata, tag_id)
            if not success:
                failed_tag = tags[tag_id].name()
                break

        self.comic_archive.load_cache(set(tags))
        QtWidgets.QApplication.restoreOverrideCursor()

        if failed_tag:
            OptionalMessageDialog.warning(
                self,
                "Save failed",
                f"The tag save operation seemed to fail for: {failed_tag}",
            )
        else:
            self.clear_dirty_flag()
            self.update_info_box()
            self.update_menus()

            # Only try to read if write was successful
            self.metadata, _, error = self.read_selected_tags(
                self.config[0].Runtime_Options__tags_read, self.comic_archive
            )
            if error is not None:
                logger.error("Failed to load metadata for %s: %s", self.comic_archive.path, error)
                OptionalMessageDialog.warning(
                    self,
                    "Read Failed!",
                    f"One or more of the selected read tags failed to load for {self.comic_archive.path}, check log for details",
                )

        self.fileSelectionList.update_current_row()
        self.update_ui_for_archive()

    def select_read_tags(self, tag_ids: list[str]) -> None:
        """Should only be called from the combobox signal"""
        if self.dirty_flag_verification(
            "Change Read Tags",
            "If you change read tag(s) now, data in the form will be lost.  Are you sure?",
        ):
            # Tags are reversed for display to the user
            self.config[0].Runtime_Options__tags_read = list(reversed(tag_ids))
            self.update_menus()
            if self.comic_archive is not None:
                self.load_archive(self.comic_archive)
        else:
            self.cbSelectedReadTags.dropdownClosed.disconnect()
            self.adjust_tags_combo()
            self.cbSelectedReadTags.dropdownClosed.connect(self.select_read_tags)

    def select_write_tags(self) -> None:
        self.config[0].Runtime_Options__tags_write = self.cbSelectedWriteTags.currentData()
        self.update_tag_tweaks()
        self.update_menus()

    def select_source(self, s: int) -> None:
        self.config[0].Sources__source = self.cbx_sources.itemData(s)

    def update_credit_colors(self) -> None:
        selected_tags = [tags[tag_id] for tag_id in self.config[0].Runtime_Options__tags_write]
        enabled = set()
        for tag in selected_tags:
            enabled.update(tag.supported_attributes)

        credit_attributes = [x for x in self.md_attributes.items() if "credits." in x[0]]

        for r in range(self.twCredits.rowCount()):
            w = self.twCredits.item(r, 1)
            supports_role = any(tag.supports_credit_role(str(w.text())) for tag in selected_tags)
            for credit in credit_attributes:
                widget_enabled = credit[0] in enabled
                widget = self.twCredits.item(r, credit[1])
                if credit[0] == "credits.role":
                    widget_enabled = widget_enabled and supports_role
                enable_widget(widget, widget_enabled)

    def update_tag_tweaks(self) -> None:
        # depending on the current data tag, certain fields are disabled
        enabled_widgets = set()
        for tag_id in self.config[0].Runtime_Options__tags_write:
            if not tags[tag_id].enabled:
                continue
            enabled_widgets.update(tags[tag_id].supported_attributes)

        for md_field, widget in self.md_attributes.items():
            if widget is not None and not isinstance(widget, (int)):
                enable_widget(widget, md_field in enabled_widgets)

        self.update_credit_colors()
        self.page_list_editor.select_write_tags(self.config[0].Runtime_Options__tags_write)
        self.toggle_enable_embedding_hashes()

    def add_credit(self) -> None:
        row = self.twCredits.rowCount()
        editor = CreditEditorWindow(self, self.config[0].Runtime_Options__tags_write, row, Credit())
        editor.creditChanged.connect(self._credit_added)
        editor.show()

    def edit_credit(self) -> None:
        if self.twCredits.currentRow() < 0:
            return
        row = self.twCredits.currentRow()
        lang = str(
            self.twCredits.item(row, self.md_attributes["credits.language"]).data(QtCore.Qt.ItemDataRole.UserRole)
            or utils.get_language_iso(self.twCredits.item(row, self.md_attributes["credits.language"]).text())
        )
        old = Credit(
            self.twCredits.item(row, self.md_attributes["credits.person"]).text(),
            self.twCredits.item(row, self.md_attributes["credits.role"]).text(),
            self.twCredits.item(row, self.md_attributes["credits.primary"]).text() != "",
            lang,
        )
        editor = CreditEditorWindow(self, self.config[0].Runtime_Options__tags_write, row, old, "Edit Credit")
        editor.creditChanged.connect(self._credit_changed)
        editor.show()

    def update_credit_primary_flag(self, row: int, primary: bool) -> None:
        # if we're clearing a flag do it and quit
        if not primary:
            self.twCredits.item(row, self.md_attributes["credits.primary"]).setText("")
            return

        # otherwise, we need to check for, and clear, other primaries with same role
        role = str(self.twCredits.item(row, self.md_attributes["credits.role"]).text())
        r = 0
        for r in range(self.twCredits.rowCount()):
            if (
                self.twCredits.item(r, self.md_attributes["credits.primary"]).text() != ""
                and str(self.twCredits.item(r, self.md_attributes["credits.role"]).text()).casefold() == role.casefold()
            ):
                self.twCredits.item(r, self.md_attributes["credits.primary"]).setText("")

        # Now set our new primary
        self.twCredits.item(row, self.md_attributes["credits.primary"]).setText("Yes")

    def _update_credit(self, credit: Credit, row: int) -> None:
        assert isinstance(row, int)
        lang = utils.get_language_from_iso(credit.language) or credit.language
        self.twCredits.item(row, self.md_attributes["credits.role"]).setText(credit.role)
        self.twCredits.item(row, self.md_attributes["credits.person"]).setText(credit.person)
        self.twCredits.item(row, self.md_attributes["credits.language"]).setText(lang)
        self.twCredits.item(row, self.md_attributes["credits.language"]).setData(
            QtCore.Qt.ItemDataRole.UserRole, credit.language
        )
        self.update_credit_primary_flag(row, credit.primary)

        self.update_credit_colors()
        self.set_dirty_flag()

    def _add_credit(self, credit: Credit) -> None:
        # add new entry
        row = self.twCredits.rowCount()
        self.add_new_credit_entry(row, credit)

        self.update_credit_colors()
        self.set_dirty_flag()

    def _credit_changed(self, credit: Credit, row: int) -> None:
        dupe_index = self.get_dupe_credit(row, credit.role, credit.person)
        if dupe_index < 0:
            return self._update_credit(credit, row)
        # delete the dupe credit from list
        qmsg = QtWidgets.QMessageBox(parent=self)
        qmsg.addAction(self.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(qmsg.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)
        qmsg.setText("Duplicate Credit!")
        qmsg.setInformativeText(
            "This will create a duplicate credit entry. Would you like to merge the entries, or create a duplicate?"
        )
        qmsg.addButton("Merge", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        qmsg.addButton("Duplicate", QtWidgets.QMessageBox.ButtonRole.ActionRole)

        def _merge(credit: Credit, row: int, existing: int) -> None:
            self.twCredits.removeRow(row)
            self._update_credit(credit, existing)

        qmsg.accepted.connect(functools.partial(_merge, credit, row, dupe_index))
        qmsg.finished.connect(functools.partial(self._credit_finished, credit=credit, row=row))

        qmsg.show()

    def _credit_finished(self, code: int, *, credit: Credit, row: int) -> None:
        if code in (QtWidgets.QDialog.DialogCode.Rejected, QtWidgets.QDialog.DialogCode.Accepted):
            return
        self._update_credit(credit, row)

    def _credit_added(self, credit: Credit) -> None:
        dupe_index = self.get_dupe_credit(None, credit.role, credit.person)
        if dupe_index < 0:
            self._add_credit(credit)
            return
        # delete the dupe credit from list
        qmsg = QtWidgets.QMessageBox(parent=self)
        qmsg.addAction(self.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(qmsg.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)
        qmsg.setText("Duplicate Credit!")
        qmsg.setInformativeText(
            "This will create a duplicate credit entry. Would you like to merge the entries, or create a duplicate?"
        )
        qmsg.addButton("Merge", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        qmsg.addButton("Duplicate", QtWidgets.QMessageBox.ButtonRole.ActionRole)
        qmsg.accepted.connect(functools.partial(self._update_credit, credit, dupe_index))
        qmsg.finished.connect(functools.partial(self._credit_added_finished, credit=credit))
        qmsg.show()

    def _credit_added_finished(self, code: int, *, credit: Credit) -> None:
        if code in (QtWidgets.QDialog.DialogCode.Rejected, QtWidgets.QDialog.DialogCode.Accepted):
            return
        self._add_credit(credit)

    def remove_credit(self) -> None:
        row = self.twCredits.currentRow()
        if row != -1:
            self.twCredits.removeRow(row)
        self.set_dirty_flag()

    def open_web_link(self) -> None:
        row = self.leWebLink.currentRow()
        if row < 0:
            if self.leWebLink.count() < 1:
                return
            row = 0
        web_link = self.leWebLink.item(row).text()
        try:
            utils.parse_url(web_link)
            webbrowser.open_new_tab(web_link)
        except utils.LocationParseError:
            OptionalMessageDialog.warning(self, "Web Link", "Web Link is invalid.")

    def show_settings(self) -> None:
        self.settingswin = SettingsWindow(self, self.config, self.talkers)
        self.settingswin.finished.connect(self.adjust_source_combo)
        self.settingswin.accepted.connect(self.settings_accept)
        self.settingswin.show()

    def settings_accept(self) -> None:
        self.config = self.settingswin.config

    def set_app_position(self) -> None:
        if self.config[0].internal__window_width != 0:
            self.move(self.config[0].internal__window_x, self.config[0].internal__window_y)
            self.resize(self.config[0].internal__window_width, self.config[0].internal__window_height)
        else:
            screen = QtGui.QGuiApplication.primaryScreen().geometry()
            size = self.frameGeometry()
            self.move(int((screen.width() - size.width()) / 2), int((screen.height() - size.height()) / 2))

    def adjust_source_combo(self) -> None:
        self.cbx_sources.setCurrentIndex(self.cbx_sources.findData(self.config[0].Sources__source))

    def adjust_tags_combo(self) -> None:
        """Select the enabled tags. Since tags are merged in an overlay fashion the last item in the list takes priority. We reverse the order for display to the user"""
        unchecked = set(self.enabled_tags()) - set(self.config[0].Runtime_Options__tags_read)
        for i, tag_id in enumerate(reversed(self.config[0].Runtime_Options__tags_read)):
            if not tags[tag_id].enabled:
                continue
            item_idx = self.cbSelectedReadTags.findData(tag_id)
            self.cbSelectedReadTags.setItemChecked(item_idx, True)
            # Order matters, move items to list order
            if item_idx != i:
                self.cbSelectedReadTags.moveItem(item_idx, row=i)
        for tag_id in unchecked:
            self.cbSelectedReadTags.setItemChecked(self.cbSelectedReadTags.findData(tag_id), False)

        # select the current tag_id
        unchecked = set(self.enabled_tags()) - set(self.config[0].Runtime_Options__tags_write)
        for tag_id in self.config[0].Runtime_Options__tags_write:
            if not tags[tag_id].enabled:
                continue
            self.cbSelectedWriteTags.setItemChecked(self.cbSelectedWriteTags.findData(tag_id), True)
        for tag_id in unchecked:
            self.cbSelectedWriteTags.setItemChecked(self.cbSelectedWriteTags.findData(tag_id), False)
        self.update_tag_tweaks()

    def populate_tag_names(self) -> None:
        # First clear all entries (called from settingswindow.py)
        self.cbSelectedWriteTags.clear()
        self.cbSelectedReadTags.clear()
        # Add the entries to the tag comboboxes
        for tag in tags.values():
            if not tag.enabled:
                continue
            if self.config[0].Metadata_Options__use_short_tag_names:
                self.cbSelectedWriteTags.addItem(tag.id.upper(), tag.id)
                self.cbSelectedReadTags.addItem(tag.id.upper(), tag.id)
            else:
                self.cbSelectedWriteTags.addItem(tag.name(), tag.id)
                self.cbSelectedReadTags.addItem(tag.name(), tag.id)

    def populate_combo_boxes(self) -> None:
        self.populate_tag_names()

        self.adjust_tags_combo()

        self.cbHashName: QtWidgets.QComboBox
        self.cbHashName.addItems(sorted(hashlib.algorithms_available))

        # Add talker entries
        for t_id, talker in self.talkers.items():
            self.cbx_sources.addItem(talker.name, t_id)
        self.adjust_source_combo()

        # Add the entries to the country combobox
        self.cbCountry.addItem("", "")
        for f in natsort.humansorted(utils.countries().items(), operator.itemgetter(1)):
            self.cbCountry.addItem(f[1], f[0])

        # Add the entries to the language combobox
        self.cbLanguage.addItem("", "")

        for f in natsort.humansorted(utils.languages().items(), operator.itemgetter(1)):
            self.cbLanguage.addItem(f[1], f[0])

        # Add the entries to the manga combobox
        self.cbManga.addItem("", "")
        self.cbManga.addItem("Yes", "Yes")
        self.cbManga.addItem("Yes (Right to Left)", "YesAndRightToLeft")
        self.cbManga.addItem("No", "No")

        # Add the entries to the maturity combobox
        self.cbMaturityRating.addItem("", "")
        self.cbMaturityRating.addItem("Everyone", "")
        self.cbMaturityRating.addItem("G", "")
        self.cbMaturityRating.addItem("Early Childhood", "")
        self.cbMaturityRating.addItem("Everyone 10+", "")
        self.cbMaturityRating.addItem("PG", "")
        self.cbMaturityRating.addItem("Kids to Adults", "")
        self.cbMaturityRating.addItem("Teen", "")
        self.cbMaturityRating.addItem("M", "")
        self.cbMaturityRating.addItem("MA15+", "")
        self.cbMaturityRating.addItem("Mature 17+", "")
        self.cbMaturityRating.addItem("R18+", "")
        self.cbMaturityRating.addItem("X18+", "")
        self.cbMaturityRating.addItem("Adults Only 18+", "")
        self.cbMaturityRating.addItem("Rating Pending", "")

        # Add entries to the format combobox
        self.cbFormat.addItem("")
        self.cbFormat.addItem(".1")
        self.cbFormat.addItem("-1")
        self.cbFormat.addItem("1 Shot")
        self.cbFormat.addItem("1/2")
        self.cbFormat.addItem("1-Shot")
        self.cbFormat.addItem("Annotation")
        self.cbFormat.addItem("Annotations")
        self.cbFormat.addItem("Annual")
        self.cbFormat.addItem("Anthology")
        self.cbFormat.addItem("B&W")
        self.cbFormat.addItem("B/W")
        self.cbFormat.addItem("B&&W")
        self.cbFormat.addItem("Black & White")
        self.cbFormat.addItem("Box Set")
        self.cbFormat.addItem("Box-Set")
        self.cbFormat.addItem("Crossover")
        self.cbFormat.addItem("Director's Cut")
        self.cbFormat.addItem("Epilogue")
        self.cbFormat.addItem("Event")
        self.cbFormat.addItem("FCBD")
        self.cbFormat.addItem("Flyer")
        self.cbFormat.addItem("Giant")
        self.cbFormat.addItem("Giant Size")
        self.cbFormat.addItem("Giant-Size")
        self.cbFormat.addItem("Graphic Novel")
        self.cbFormat.addItem("Hardcover")
        self.cbFormat.addItem("Hard-Cover")
        self.cbFormat.addItem("King")
        self.cbFormat.addItem("King Size")
        self.cbFormat.addItem("King-Size")
        self.cbFormat.addItem("Limited Series")
        self.cbFormat.addItem("Magazine")
        self.cbFormat.addItem("-1")
        self.cbFormat.addItem("NSFW")
        self.cbFormat.addItem("One Shot")
        self.cbFormat.addItem("One-Shot")
        self.cbFormat.addItem("Point 1")
        self.cbFormat.addItem("Preview")
        self.cbFormat.addItem("Prologue")
        self.cbFormat.addItem("Reference")
        self.cbFormat.addItem("Review")
        self.cbFormat.addItem("Reviewed")
        self.cbFormat.addItem("Scanlation")
        self.cbFormat.addItem("Script")
        self.cbFormat.addItem("Series")
        self.cbFormat.addItem("Sketch")
        self.cbFormat.addItem("Special")
        self.cbFormat.addItem("TPB")
        self.cbFormat.addItem("Trade Paper Back")
        self.cbFormat.addItem("WebComic")
        self.cbFormat.addItem("Web Comic")
        self.cbFormat.addItem("Year 1")
        self.cbFormat.addItem("Year One")

    def remove_auto(self) -> None:
        self.prompt_remove_tags(self.config[0].Runtime_Options__tags_write)

    def prompt_remove_tags(self, tag_ids: list[str]) -> None:
        # remove the indicated tag_ids from the archive
        ca_list = self.fileSelectionList.get_selected_archive_list()
        md_count = 0
        file_md_count = {}
        for tag_id in tag_ids:
            file_md_count[tag_id] = 0
        for ca in ca_list:
            for tag_id in tag_ids:
                if ca.has_tags(tag_id):
                    md_count += 1
                    file_md_count[tag_id] += 1

        if md_count == 0:
            OptionalMessageDialog.information(
                self,
                "Remove Tags",
                f"No archives with {', '.join([tags[tag_id].name() for tag_id in tag_ids])} tags selected!",
            )
            return

        if md_count != 0 and not self.dirty_flag_verification(
            "Remove Tags", "If you remove tags now, unsaved data in the form will be lost.  Are you sure?"
        ):
            return

        OptionalMessageDialog.question(
            self,
            "Remove Tags",
            f"Are you sure you wish to remove {', '.join([f'{tags[tag_id].name()} tags from {count} files' for tag_id, count in file_md_count.items()])} removing a total of {md_count} tag(s)?",
            check_text=None,
        ).accepted.connect(functools.partial(self.remove_tags, tag_ids, md_count))

    def remove_tags(self, tag_ids: list[str], md_count: int) -> None:
        progdialog = QtWidgets.QProgressDialog("", "Cancel", 0, md_count, self)
        progdialog.setWindowTitle("Removing Tags")
        progdialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progdialog.setMinimumDuration(300)
        center_window_on_parent(progdialog)

        ca_list = self.fileSelectionList.get_selected_archive_list()

        failed_list = []
        success_count = 0
        for prog_idx, ca in enumerate(ca_list, 1):
            if prog_idx % 10 == 0:
                QtCore.QCoreApplication.processEvents()
            if progdialog.wasCanceled():
                break
            progdialog.setValue(prog_idx)
            progdialog.setLabelText(str(ca.path))
            for tag_id in tag_ids:
                if ca.has_tags(tag_id) and ca.is_writable():
                    if ca.remove_tags(tag_id):
                        success_count += 1
                    else:
                        failed_list.append(ca.path)
                        # Abandon any further tag removals to prevent any greater damage to archive
                        break
            ca.reset_cache()
            ca.load_cache(self.enabled_tags())

        progdialog.hide()
        QtCore.QCoreApplication.processEvents()
        self._reload_page()
        self.update_info_box()
        self.update_menus()

        summary = f"Successfully removed {success_count} tags in archive(s)."
        if failed_list:
            summary += f"\n\nThe remove operation failed in the following {len(failed_list)} archive(s):\n"
            for f in failed_list:
                summary += f"\t{f}\n"

        dlg = LogWindow(self)
        dlg.set_text(summary)
        dlg.setWindowTitle("Tag Remove Summary")
        dlg.show()

    def prompt_copy_tags(self) -> None:
        # copy the indicated tags in the archive
        ca_list = self.fileSelectionList.get_selected_archive_list()
        src_count = 0

        src_tag_ids: list[str] = self.config[0].Runtime_Options__tags_read
        dest_tag_ids: list[str] = self.config[0].Runtime_Options__tags_write

        if len(src_tag_ids) == 1 and src_tag_ids[0] in dest_tag_ids:
            # Remove the read tag from the write tag
            dest_tag_ids.remove(src_tag_ids[0])

        if not dest_tag_ids:
            OptionalMessageDialog.information(
                self, "Copy Tags", "Can't copy tag tag onto itself.  Read tag and modify tag must be different."
            )
            return

        for ca in ca_list:
            for tag_id in src_tag_ids:
                if ca.has_tags(tag_id):
                    src_count += 1
                    continue

        if src_count == 0:
            OptionalMessageDialog.information(
                self,
                "Copy Tags",
                f"No archives with {', '.join([tags[tag_id].name() for tag_id in src_tag_ids])} tags selected!",
            )
            return

        if src_count != 0 and not self.dirty_flag_verification(
            "Copy Tags", "If you copy tags now, unsaved data in the form may be lost.  Are you sure?"
        ):
            return

        details = (
            f"Are you sure you wish to copy the combined (with overlay order) tags of "
            f"{', '.join([tags[tag_id].name() for tag_id in src_tag_ids])} "
            f"to {', '.join([tags[tag_id].name() for tag_id in dest_tag_ids])} tags in "
            f"{src_count} archive(s)?"
        )

        OptionalMessageDialog.question(
            self,
            "Copy Tags",
            details,
            icon=OptionalMessageDialog.Icon.Question,
            check_text=None,
        ).accepted.connect(functools.partial(self.copy_tags, src_tag_ids, dest_tag_ids, src_count))

    def copy_tags(self, src_tag_ids: list[str], dest_tag_ids: list[str], src_count: int) -> None:
        ca_list = self.fileSelectionList.get_selected_archive_list()
        prog_dialog = QtWidgets.QProgressDialog("", "Cancel", 0, src_count, self)
        prog_dialog.setWindowTitle("Copying Tags")
        prog_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        prog_dialog.setMinimumDuration(1000)
        center_window_on_parent(prog_dialog)
        QtCore.QCoreApplication.processEvents()

        failed_list = []
        success_count = 0
        for prog_idx, ca in enumerate(ca_list, 1):
            if prog_idx % 10 == 0:
                QtCore.QCoreApplication.processEvents()
            ca_saved = False
            md, _, error = self.read_selected_tags(src_tag_ids, ca)
            if error is not None:
                failed_list.append(ca.path)
                continue
            if md.is_empty:
                continue

            for tag_id in dest_tag_ids:
                if ca.has_tags(tag_id):
                    if prog_dialog.wasCanceled():
                        break

                    prog_dialog.setValue(prog_idx)
                    prog_dialog.setLabelText(str(ca.path))
                    center_window_on_parent(prog_dialog)

                if tag_id == "cbi" and self.config[0].Metadata_Options__apply_transform_on_bulk_operation:
                    md = CBLTransformer(md, self.config[0]).apply()

                if ca.write_tags(md, tag_id):
                    if not ca_saved:
                        success_count += 1
                        ca_saved = True
                else:
                    failed_list.append(ca.path)

            ca.reset_cache()
            ca.load_cache({*self.config[0].Runtime_Options__tags_read, *self.config[0].Runtime_Options__tags_write})

        prog_dialog.hide()
        QtCore.QCoreApplication.processEvents()
        self._reload_page()
        self.update_info_box()
        self.update_menus()

        summary = f"Successfully copied tags in {success_count} archive(s)."
        if failed_list:
            summary += f"\n\nThe copy operation failed in the following {len(failed_list)} archive(s):\n"
            for f in failed_list:
                summary += f"\t{f}\n"

        dlg = LogWindow(self)
        dlg.set_text(summary)
        dlg.setWindowTitle("Tag Copy Summary")
        dlg.show()

    def auto_tag_log(self, text: str) -> None:
        if self.atprogdialog is not None:
            self.atprogdialog.textEdit.append(text.rstrip())
            self.atprogdialog.textEdit.ensureCursorVisible()
            QtCore.QCoreApplication.processEvents()

    def auto_tag(self) -> None:
        ca_list = self.fileSelectionList.get_selected_archive_list()
        tag_names = ", ".join([tags[tag_id].name() for tag_id in self.config[0].Runtime_Options__tags_write])

        if not ca_list:
            OptionalMessageDialog.information(self, "Auto-Tag", "No archives selected!")
            return

        if not self.dirty_flag_verification(
            "Auto-Tag", "If you auto-tag now, unsaved data in the form will be lost.  Are you sure?"
        ):
            return

        atstartdlg = AutoTagStartWindow(
            self,
            self.config[0],
            (
                f"You have selected {len(ca_list)} archive(s) to automatically identify and write "
                + f"{tag_names} tags to.\n\nPlease choose config below, and select OK to Auto-Tag."
            ),
        )

        atstartdlg.startAutoTag.connect(self._start_auto_tag)

        atstartdlg.open()

    def _start_auto_tag(self, auto_tag: AutoTagSettings) -> None:
        # persist some settings because it's probably going to be used next time
        self.config[0].Auto_Tag__save_on_low_confidence = auto_tag.settings["save_on_low_confidence"]
        self.config[0].Auto_Tag__use_year_when_identifying = auto_tag.settings["use_year_when_identifying"]
        self.config[0].Auto_Tag__assume_issue_one = auto_tag.settings["assume_issue_one"]
        self.config[0].Auto_Tag__ignore_leading_numbers_in_filename = auto_tag.settings[
            "ignore_leading_numbers_in_filename"
        ]
        self.config[0].internal__remove_archive_after_successful_match = auto_tag.remove_after_success

        ca_list = self.fileSelectionList.get_selected_archive_list()
        self.atprogdialog = AutoTagProgressWindow(self, self.current_talker())
        self.atprogdialog.progressBar.setMaximum(len(ca_list))
        self.atprogdialog.setWindowTitle("Auto-Tagging")

        center_window_on_parent(self.atprogdialog)
        temp_config = auto_tag.new_settings(self.config[0])
        self.autotagthread = AutoTagThread(auto_tag.search_string, ca_list, temp_config, self.current_talker())

        self.autotagthread.autoTagComplete.connect(functools.partial(self.auto_tag_finished, config=temp_config))
        self.autotagthread.autoTagLogMsg.connect(self.auto_tag_log)
        self.autotagthread.autoTagProgress.connect(self.atprogdialog.on_progress)
        self.autotagthread.ratelimit.connect(self.ratelimit)

        # We don't use rejected as that closes the dialog
        self.atprogdialog.cancel.connect(self.autotagthread.cancel)

        self.auto_tag_log("==========================================================================\n")
        self.auto_tag_log(f"Auto-Tagging Started for {len(ca_list)} items\n")
        self.autotagthread.start()
        self.atprogdialog.open()

    def auto_tag_finished(
        self, match_results: OnlineMatchResults, archives_to_remove: list[ComicArchive], *, config: ct_ns
    ) -> None:
        tag_names = ", ".join([tags[tag_id].name() for tag_id in self.config[0].Runtime_Options__tags_write])
        if self.atprogdialog:
            self.atprogdialog.accept()

        self.fileSelectionList.remove_archive_list(archives_to_remove)
        self._reload_page()
        self.atprogdialog = None

        summary = f"<p>{self.current_talker().attribution}</p>"
        summary += f"Successfully added {tag_names} tags to {len(match_results.good_matches)} archive(s)<br/>"

        if match_results.multiple_matches:
            summary += f"Archives with multiple matches: {len(match_results.multiple_matches)}<br/>"
        if match_results.low_confidence_matches:
            summary += (
                f"Archives with one or more low-confidence matches: {len(match_results.low_confidence_matches)}<br/>"
            )
        if match_results.no_matches:
            summary += f"Archives with no matches: {len(match_results.no_matches)}<br/>"
        if match_results.fetch_data_failures:
            summary += f"Archives that failed due to data fetch errors: {len(match_results.fetch_data_failures)}<br/>"
        if match_results.write_failures:
            summary += f"Archives that failed due to file writing errors: {len(match_results.write_failures)}<br/>"

        self.auto_tag_log(summary)

        selectable = match_results.multiple_matches or match_results.low_confidence_matches

        title = "Auto-Tag Summary"
        if not selectable:
            logger.info(summary)
            OptionalMessageDialog.msg_no_checkbox(
                self,
                title,
                summary,
                icon=OptionalMessageDialog.Icon.Information,
            )
            return

        summary += (
            "\n\nDo you want to manually select the ones with multiple matches and/or low-confidence matches now?"
        )
        logger.info(summary)
        OptionalMessageDialog.question(
            self,
            title,
            summary,
            check_text=None,
        ).accepted.connect(functools.partial(self.open_auto_tag_match_window, match_results, config=config))
        # TODO: Validate that open_auto_tag_match_window still works

    def open_auto_tag_match_window(self, match_results: OnlineMatchResults, *, config: ct_ns) -> None:
        match_results.multiple_matches.extend(match_results.low_confidence_matches)
        auto_tagged_archives = {a.path: a for a in self.fileSelectionList.get_selected_archive_list()}
        matchdlg = AutoTagMatchWindow(
            self,
            [(m, auto_tagged_archives[m.original_path]) for m in match_results.multiple_matches],
            config,
            self.current_talker(),
        )

        matchdlg.open()
        matchdlg.finished.connect(self._reload_page)
        matchdlg.matched_files.connect(self.fileSelectionList.remove_archive_list)

    def _reload_page(self) -> None:
        self.fileSelectionList.update_selected_rows()
        new_ca = self.fileSelectionList.get_current_archive()
        if new_ca is not None:
            self.load_archive(new_ca)

    def dirty_flag_verification(self, title: str, desc: str) -> bool:
        if not self.dirty_flag:
            return True
        reply = QtWidgets.QMessageBox.question(
            self,
            title,
            desc,
            (
                QtWidgets.QMessageBox.StandardButton.Save
                | QtWidgets.QMessageBox.StandardButton.Cancel
                | QtWidgets.QMessageBox.StandardButton.Discard
            ),
            QtWidgets.QMessageBox.StandardButton.Cancel,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Discard:
            return True
        if reply == QtWidgets.QMessageBox.StandardButton.Save:
            self.prompt_write_tags()
            return True
        return False

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.dirty_flag_verification(
            f"Exit {self.appName}", "If you quit now, data in the form will be lost.  Are you sure?"
        ):
            appsize = self.size()
            self.config[0].internal__window_width = appsize.width()
            self.config[0].internal__window_height = appsize.height()
            self.config[0].internal__window_x = self.x()
            self.config[0].internal__window_y = self.y()
            self.config[0].internal__form_width = self.splitter.sizes()[0]
            self.config[0].internal__list_width = self.splitter.sizes()[1]
            (
                self.config[0].internal__sort_column,
                self.config[0].internal__sort_direction,
            ) = self.fileSelectionList.get_sorting()
            self.config[0].internal__write_tags = self.config[0].Runtime_Options__tags_write
            self.config[0].internal__read_tags = self.config[0].Runtime_Options__tags_read
            ctsettings.save_file(self.config, self.config[0].Runtime_Options__config.user_config_dir / "settings.json")

            event.accept()
        else:
            event.ignore()

    def show_page_browser(self) -> None:
        if self.page_browser is None:
            self.page_browser = PageBrowserWindow(self, self.metadata)
            if self.comic_archive is not None:
                self.page_browser.set_comic_archive(self.comic_archive)
            self.page_browser.finished.connect(self.page_browser_closed)

    def page_browser_closed(self) -> None:
        self.page_browser = None

    def view_raw_tags(self, tag_id: str) -> None:
        tag = tags[tag_id]
        if self.comic_archive is not None and self.comic_archive.has_tags(tag.id):
            dlg = LogWindow(self)
            dlg.set_text(self.comic_archive.read_raw_tags(tag.id))
            dlg.setWindowTitle(f"Raw {tag.name()} Tag View")
            dlg.open()

    def show_wiki(self) -> None:
        webbrowser.open("https://github.com/comictagger/comictagger/wiki")

    def report_bug(self) -> None:
        webbrowser.open("https://github.com/comictagger/comictagger/issues")

    def show_forum(self) -> None:
        webbrowser.open("https://github.com/comictagger/comictagger/discussions")

    def front_cover_changed(self) -> None:
        self.metadata.pages = self.page_list_editor.get_page_list()
        self.update_cover_image()

    def page_list_order_changed(self) -> None:
        self.metadata.pages = self.page_list_editor.get_page_list()

    def apply_cbl_transform(self) -> None:
        self.form_to_metadata()
        self.metadata = CBLTransformer(self.metadata, self.config[0]).apply()
        self.metadata_to_form()

    def recalc_archive_info(self) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        for p in self.metadata.pages:
            p.byte_size = None
            p.height = None
            p.width = None
        if self.comic_archive and self.config[0].Runtime_Options__preferred_hash:
            self.metadata.original_hash = None
            self.comic_archive.apply_archive_info_to_metadata(
                self.metadata, True, hash_archive=self.cbHashName.currentText()
            )
            original_hash = self.metadata.original_hash or FileHash("", "")
            self.leOriginalHash.setText(original_hash.hash)
            self.cbHashName.setCurrentText(original_hash.name or self.config[0].internal__embedded_hash_type)
            self.page_list_editor.set_data(self.comic_archive, self.metadata.pages)

        self.set_dirty_flag()
        QtWidgets.QApplication.restoreOverrideCursor()

    def rename_archive(self) -> None:
        ca_list = self.fileSelectionList.get_selected_archive_list()

        if not ca_list:
            OptionalMessageDialog.information(self, "Rename", "No archives selected!")
            return

        if self.dirty_flag_verification(
            "File Rename", "If you rename files now, unsaved data in the form will be lost.  Are you sure?"
        ):
            self.rename_window = RenameWindow(
                self, ca_list, self.config[0].Runtime_Options__tags_read, self.config, self.talkers
            )
            self.rename_window.finished.connect(self._reload_page)
            self.rename_window.finished.connect(self._rename_finished)
            self.rename_window.open()

    def _rename_finished(self) -> None:
        # We may have edited the config during renaming
        self.config = self.rename_window.config

    def load_archive(self, comic_archive: ComicArchive) -> None:
        self.comic_archive = None
        self.clear_form()
        self.metadata = GenericMetadata()

        if not os.path.exists(comic_archive.path):
            self.fileSelectionList.dirty_flag = False
            self.fileSelectionList.remove_deleted()
            return

        self.config[0].internal__last_opened_folder = os.path.abspath(os.path.split(comic_archive.path)[0])
        self.comic_archive = comic_archive

        self.metadata, _, error = self.read_selected_tags(self.config[0].Runtime_Options__tags_read, self.comic_archive)
        if error is not None:
            logger.error("Failed to load tags from %s: %s", self.comic_archive.path, error, exc_info=error)
            trace = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))
            OptionalMessageDialog.critical(
                parent=self,
                title="Failed to load tags",
                text=f"Failed to load tags from {error}, see log for details",
                details=trace,
            )

        self.update_ui_for_archive()

    def read_selected_tags(
        self, tag_ids: list[str], ca: ComicArchive
    ) -> tuple[GenericMetadata, list[str], Exception | None]:
        return read_selected_tags(
            tag_ids, ca, self.config[0].Metadata_Options__tag_merge, self.config[0].Metadata_Options__tag_merge_lists
        )

    def file_list_cleared(self) -> None:
        self.reset_app()

    def splitter_moved_event(self, w1: int, w2: int) -> None:
        scrollbar_w = 0
        if self.scrollArea.verticalScrollBar().isVisible():
            scrollbar_w = self.scrollArea.verticalScrollBar().width()

        new_w = self.scrollArea.width() - scrollbar_w - 5
        self.scrollAreaWidgetContents.resize(new_w, self.scrollAreaWidgetContents.height())

    def resizeEvent(self, ev: QtGui.QResizeEvent | None) -> None:
        self.splitter_moved_event(0, 0)

    def tab_changed(self, idx: int) -> None:
        if idx == 0:
            self.splitter_moved_event(0, 0)

    def gtin_changed(self) -> None:
        # GTIN changed, so we check if it's valid
        gtin = self.leGtin.text().strip()
        is_valid = is_valid_gtin(gtin) if gtin else True
        if is_valid:
            self.leGtin.setStyleSheet("")
        else:
            self.leGtin.setStyleSheet("background-color: salmon;")

    def check_latest_version_online(self) -> None:
        version_checker = VersionChecker()
        self.version_check_complete(version_checker.get_latest_version())

    def version_check_complete(self, new_version: tuple[str, str]) -> None:
        if new_version[0] not in (self.version, self.config[0].Dialog_Flags__dont_notify_about_this_version):
            from packaging.version import parse

            if parse(new_version[0]) <= parse(self.version):
                return
            website = "https://github.com/comictagger/comictagger"

            def set_checked(checked: bool) -> None:
                if checked:
                    self.config[0].Dialog_Flags__dont_notify_about_this_version = new_version[0]

            OptionalMessageDialog.msg(
                self,
                "New version available!",
                f"New version ({new_version[1]}) available!<br>(You are currently running {self.version})<br><br>"
                f"Visit <a href='{website}/releases/latest'>{website}/releases/latest</a> for more info.<br><br>",
                checked=False,
                check_text="Don't tell me about this version again",
            ).check_status.connect(set_checked)

    def on_incoming_socket_connection(self) -> None:
        # Accept connection from other instance.
        # Read in the file list if they're giving it, and add to our own list
        while local_socket := self.socket_server.nextPendingConnection():
            try:
                if not local_socket.waitForReadyRead(3000):
                    continue
                byte_array = local_socket.readAll().data()
                if not byte_array:
                    continue
                obj = json.loads(byte_array)
                if not isinstance(obj, list):
                    continue
                self.fileSelectionList.add_path_list(obj)
            finally:
                local_socket.disconnectFromServer()

        self.bring_to_top()

    def bring_to_top(self) -> None:
        if platform.system() == "Windows":
            self.showNormal()
            self.raise_()
            self.activateWindow()
            try:
                import win32con
                import win32gui

                hwnd = self.effectiveWinId()
                rect = win32gui.GetWindowRect(hwnd)
                x = rect[0]
                y = rect[1]
                w = rect[2] - x
                h = rect[3] - y
                # mark it "always on top", just for a moment, to force it to
                # the top
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, x, y, w, h, 0)
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, x, y, w, h, 0)
            except Exception:
                logger.exception("Fail to bring window to top")
        elif platform.system() == "Darwin":
            self.raise_()
            self.showNormal()
            self.activateWindow()
        else:
            flags = QtCore.Qt.WindowType(self.windowFlags())
            self.setWindowFlags(
                flags | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            )
            self.setWindowFlags(flags)
            self.show()

    def auto_imprint(self) -> None:
        self.form_to_metadata()
        self.metadata.fix_publisher()
        self.metadata_to_form()
