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
import logging
import operator
import os
import pickle
import platform
import re
import sys
import webbrowser
from typing import Any, Callable, cast

import natsort
import settngs
from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets, uic

import comictaggerlib.ui
from comicapi import utils
from comicapi.comicarchive import ComicArchive, metadata_styles
from comicapi.filenameparser import FileNameParser
from comicapi.genericmetadata import GenericMetadata
from comicapi.issuestring import IssueString
from comictaggerlib import ctsettings, ctversion
from comictaggerlib.applicationlogwindow import ApplicationLogWindow, QTextEditLogger
from comictaggerlib.autotagmatchwindow import AutoTagMatchWindow
from comictaggerlib.autotagprogresswindow import AutoTagProgressWindow
from comictaggerlib.autotagstartwindow import AutoTagStartWindow
from comictaggerlib.cbltransformer import CBLTransformer
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.crediteditorwindow import CreditEditorWindow
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.exportwindow import ExportConflictOpts, ExportWindow
from comictaggerlib.fileselectionlist import FileSelectionList
from comictaggerlib.graphics import graphics_path
from comictaggerlib.issueidentifier import IssueIdentifier
from comictaggerlib.logwindow import LogWindow
from comictaggerlib.md import prepare_metadata
from comictaggerlib.optionalmsgdialog import OptionalMessageDialog
from comictaggerlib.pagebrowser import PageBrowserWindow
from comictaggerlib.pagelisteditor import PageListEditor
from comictaggerlib.renamewindow import RenameWindow
from comictaggerlib.resulttypes import Action, MatchStatus, OnlineMatchResults, Result, Status
from comictaggerlib.seriesselectionwindow import SeriesSelectionWindow
from comictaggerlib.settingswindow import SettingsWindow
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import center_window_on_parent, enable_widget, reduce_widget_font_size
from comictaggerlib.versionchecker import VersionChecker
from comictalker.comictalker import ComicTalker, TalkerError

logger = logging.getLogger(__name__)


def execute(f: Callable[[], Any]) -> None:
    f()


class TaggerWindow(QtWidgets.QMainWindow):
    appName = "ComicTagger"
    version = ctversion.version

    def __init__(
        self,
        file_list: list[str],
        config: settngs.Config[ct_ns],
        talkers: dict[str, ComicTalker],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        with (ui_path / "taggerwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.md_attributes = {
            "tag_origin": None,
            "issue_id": None,
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
            "credits.person": 2,
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

        # prevent multiple instances
        socket = QtNetwork.QLocalSocket(self)
        socket.connectToServer(config[0].internal__install_id)
        alive = socket.waitForConnected(3000)
        if alive:
            logger.setLevel(logging.INFO)
            logger.info("Another application with key [%s] is already running", config[0].internal__install_id)
            # send file list to other instance
            if file_list:
                socket.write(pickle.dumps(file_list))
                if not socket.waitForBytesWritten(3000):
                    logger.error(socket.errorString())
            socket.disconnectFromServer()
            sys.exit()
        else:
            # listen on a socket to prevent multiple instances
            self.socketServer = QtNetwork.QLocalServer(self)
            self.socketServer.newConnection.connect(self.on_incoming_socket_connection)
            ok = self.socketServer.listen(config[0].internal__install_id)
            if not ok:
                if self.socketServer.serverError() == QtNetwork.QAbstractSocket.SocketError.AddressInUseError:
                    self.socketServer.removeServer(config[0].internal__install_id)
                    ok = self.socketServer.listen(config[0].internal__install_id)
                if not ok:
                    logger.error(
                        "Cannot start local socket with key [%s]. Reason: %s",
                        config[0].internal__install_id,
                        self.socketServer.errorString(),
                    )
                    sys.exit()

        self.archiveCoverWidget = CoverImageWidget(self.coverImageContainer, CoverImageWidget.ArchiveMode, None, None)
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

        # we can't specify relative font sizes in the UI designer, so
        # walk through all the labels in the main form, and make them
        # a smidge smaller TODO: there has to be a better way to do this
        for child in self.scrollAreaWidgetContents.children():
            if isinstance(child, QtWidgets.QLabel):
                f = child.font()
                if f.pointSize() > 10:
                    f.setPointSize(f.pointSize() - 2)
                f.setItalic(True)
                child.setFont(f)

        self.scrollAreaWidgetContents.adjustSize()

        self.setWindowIcon(QtGui.QIcon(str(graphics_path / "app.png")))

        # respect the command line option tag type
        if config[0].Runtime_Options__type_modify:
            config[0].internal__save_data_style = config[0].Runtime_Options__type_modify
        if config[0].Runtime_Options__type_read:
            config[0].internal__load_data_style = config[0].Runtime_Options__type_read

        for style in config[0].internal__save_data_style:
            if style not in metadata_styles:
                config[0].internal__save_data_style.remove(style)
        for style in config[0].internal__load_data_style:
            if style not in metadata_styles:
                config[0].internal__load_data_style.remove(style)
        self.save_data_styles: list[str] = config[0].internal__save_data_style
        self.load_data_styles: list[str] = reversed(config[0].internal__load_data_style)

        self.setAcceptDrops(True)
        self.view_tag_actions, self.remove_tag_actions = self.tag_actions()
        self.config_menus()
        self.statusBar()
        self.populate_combo_boxes()

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

        # TODO set up an RE validator for issueNum that allows for all sorts of wacky things

        # tweak some control fonts
        reduce_widget_font_size(self.lblFilename, 1)
        reduce_widget_font_size(self.lblArchiveType)
        reduce_widget_font_size(self.lblTagList)
        reduce_widget_font_size(self.lblPageCount)

        # make sure some editable comboboxes don't take drop actions
        self.cbFormat.lineEdit().setAcceptDrops(False)
        self.cbMaturityRating.lineEdit().setAcceptDrops(False)

        # hook up the callbacks
        self.cbLoadDataStyle.itemChanged.connect(self.set_load_data_style)
        self.cbSaveDataStyle.itemChecked.connect(self.set_save_data_style)
        self.cbx_sources.currentIndexChanged.connect(self.set_source)
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

        self.update_metadata_style_tweaks()

        self.show()
        self.set_app_position()
        if self.config[0].internal__form_width != -1:
            self.splitter.setSizes([self.config[0].internal__form_width, self.config[0].internal__list_width])
        self.raise_()
        QtCore.QCoreApplication.processEvents()
        self.resizeEvent(None)

        self.splitter.splitterMoved.connect(self.splitter_moved_event)

        self.fileSelectionList.add_app_action(self.actionAutoIdentify)
        self.fileSelectionList.add_app_action(self.actionAutoTag)
        self.fileSelectionList.add_app_action(self.actionCopyTags)
        self.fileSelectionList.add_app_action(self.actionRename)
        self.fileSelectionList.add_app_action(self.actionRemoveAuto)
        self.fileSelectionList.add_app_action(self.actionRepackage)

        if file_list:
            self.fileSelectionList.add_path_list(file_list)

        if self.config[0].Dialog_Flags__show_disclaimer:
            checked = OptionalMessageDialog.msg(
                self,
                "Welcome!",
                """
                Thanks for trying ComicTagger!<br><br>
                Be aware that this is beta-level software, and consider it experimental.
                You should use it very carefully when modifying your data files.  As the
                license says, it's "AS IS!"<br><br>
                Also, be aware that writing tags to comic archives will change their file hashes,
                which has implications with respect to other software packages.  It's best to
                use ComicTagger on local copies of your comics.<br><br>
                COMIC VINE NOTE: Using the default API key will serverly limit search and tagging
                times. A personal API key will allow for a <b>5 times increase</b> in online search speed. See the
                <a href='https://github.com/comictagger/comictagger/wiki/UserGuide#comic-vine'>Wiki page</a>
                for more information.<br><br>
                Have fun!
                """,
            )
            self.config[0].Dialog_Flags__show_disclaimer = not checked

        if self.config[0].General__check_for_new_version:
            self.check_latest_version_online()

    def tag_actions(self) -> tuple[dict[str, QtGui.QAction], dict[str, QtGui.QAction]]:
        view_raw_tags = {}
        remove_raw_tags = {}
        for style in metadata_styles.values():
            view_raw_tags[style.short_name] = self.menuViewRawTags.addAction(f"View Raw {style.name()} Tags")
            view_raw_tags[style.short_name].setStatusTip(f"View raw {style.name()} tag block from file")
            view_raw_tags[style.short_name].triggered.connect(functools.partial(self.view_raw_tags, style.short_name))

            remove_raw_tags[style.short_name] = self.menuRemove.addAction(f"Remove Raw {style.name()} Tags")
            remove_raw_tags[style.short_name].setStatusTip(f"Remove {style.name()} tags from comic archive")
            remove_raw_tags[style.short_name].triggered.connect(functools.partial(self.remove_tags, style.short_name))

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
        self.setWindowIcon(QtGui.QIcon(str(graphics_path / "app.png")))

        if self.comic_archive is None:
            self.setWindowTitle(self.appName)
        else:
            mod_str = ""
            ro_str = ""

            if self.dirty_flag:
                mod_str = " [modified]"

            if not self.comic_archive.is_writable():
                ro_str = " [read only]"

            self.setWindowTitle(f"{self.appName} - {self.comic_archive.path}{mod_str}{ro_str}")

    def config_menus(self) -> None:
        # File Menu
        self.actionExit.setShortcut("Ctrl+Q")
        self.actionExit.setStatusTip("Exit application")
        self.actionExit.triggered.connect(self.close)

        self.actionLoad.setShortcut("Ctrl+O")
        self.actionLoad.setStatusTip("Load comic archive")
        self.actionLoad.triggered.connect(self.select_file)

        self.actionLoadFolder.setShortcut("Ctrl+Shift+O")
        self.actionLoadFolder.setStatusTip("Load folder with comic archives")
        self.actionLoadFolder.triggered.connect(self.select_folder)

        self.actionOpenFolderAsComic.setShortcut("Ctrl+Shift+Alt+O")
        self.actionOpenFolderAsComic.setStatusTip("Load folder as a comic archives")
        self.actionOpenFolderAsComic.triggered.connect(self.select_folder_archive)

        self.actionWrite_Tags.setShortcut("Ctrl+S")
        self.actionWrite_Tags.setStatusTip("Save tags to comic archive")
        self.actionWrite_Tags.triggered.connect(self.commit_metadata)

        self.actionAutoTag.setShortcut("Ctrl+T")
        self.actionAutoTag.setStatusTip("Auto-tag multiple archives")
        self.actionAutoTag.triggered.connect(self.auto_tag)

        self.actionCopyTags.setShortcut("Ctrl+C")
        self.actionCopyTags.setStatusTip("Copy one tag style tags to enabled modify style(s)")
        self.actionCopyTags.triggered.connect(self.copy_tags)

        self.actionRemoveAuto.setShortcut("Ctrl+D")
        self.actionRemoveAuto.setStatusTip("Remove currently selected modify tag style(s) from the archive")
        self.actionRemoveAuto.triggered.connect(self.remove_auto)

        self.actionRepackage.setShortcut("Ctrl+E")
        self.actionRepackage.setStatusTip("Re-create archive as CBZ")
        self.actionRepackage.triggered.connect(self.repackage_archive)

        self.actionRename.setShortcut("Ctrl+N")
        self.actionRename.setStatusTip("Rename archive based on tags")
        self.actionRename.triggered.connect(self.rename_archive)

        self.actionSettings.setShortcut("Ctrl+Shift+S")
        self.actionSettings.setStatusTip("Configure ComicTagger")
        self.actionSettings.triggered.connect(self.show_settings)

        # Tag Menu
        self.actionParse_Filename.setShortcut("Ctrl+F")
        self.actionParse_Filename.setStatusTip("Try to extract tags from filename")
        self.actionParse_Filename.triggered.connect(self.use_filename)

        self.actionParse_Filename_split_words.setShortcut("Ctrl+Shift+F")
        self.actionParse_Filename_split_words.setStatusTip("Try to extract tags from filename and split words")
        self.actionParse_Filename_split_words.triggered.connect(self.use_filename_split)

        self.actionSearchOnline.setShortcut("Ctrl+W")
        self.actionSearchOnline.setStatusTip("Search online for tags")
        self.actionSearchOnline.triggered.connect(self.query_online)

        self.actionAutoImprint.triggered.connect(self.auto_imprint)

        self.actionAutoIdentify.setShortcut("Ctrl+I")
        self.actionAutoIdentify.triggered.connect(self.auto_identify_search)

        self.actionLiteralSearch.triggered.connect(self.literal_search)

        self.actionApplyCBLTransform.setShortcut("Ctrl+L")
        self.actionApplyCBLTransform.setStatusTip("Modify tags specifically for CBL format")
        self.actionApplyCBLTransform.triggered.connect(self.apply_cbl_transform)

        self.actionReCalcPageDims.setShortcut("Ctrl+R")
        self.actionReCalcPageDims.setStatusTip(
            "Trigger re-calculating image size, height and width for all pages on the next save"
        )
        self.actionReCalcPageDims.triggered.connect(self.recalc_page_dimensions)

        self.actionClearEntryForm.setShortcut("Ctrl+Shift+C")
        self.actionClearEntryForm.setStatusTip("Clear all the data on the screen")
        self.actionClearEntryForm.triggered.connect(self.clear_form)

        # Window Menu
        self.actionPageBrowser.setShortcut("Ctrl+P")
        self.actionPageBrowser.setStatusTip("Show the page browser")
        self.actionPageBrowser.triggered.connect(self.show_page_browser)
        self.actionLogWindow.setShortcut("Ctrl+Shift+L")
        self.actionLogWindow.setStatusTip("Show the log window")
        self.actionLogWindow.triggered.connect(self.log_window.show)

        # Help Menu
        self.actionAbout.setStatusTip("Show the " + self.appName + " info")
        self.actionAbout.triggered.connect(self.about_app)
        self.actionWiki.triggered.connect(self.show_wiki)
        self.actionReportBug.triggered.connect(self.report_bug)
        self.actionComicTaggerForum.triggered.connect(self.show_forum)

        # Notes Menu
        self.btnOpenWebLink.setIcon(QtGui.QIcon(str(graphics_path / "open.png")))

        # ToolBar
        self.actionLoad.setIcon(QtGui.QIcon(str(graphics_path / "open.png")))
        self.actionLoadFolder.setIcon(QtGui.QIcon(str(graphics_path / "longbox.png")))
        self.actionOpenFolderAsComic.setIcon(QtGui.QIcon(str(graphics_path / "open.png")))
        self.actionWrite_Tags.setIcon(QtGui.QIcon(str(graphics_path / "save.png")))
        self.actionParse_Filename.setIcon(QtGui.QIcon(str(graphics_path / "parse.png")))
        self.actionParse_Filename_split_words.setIcon(QtGui.QIcon(str(graphics_path / "parse.png")))
        self.actionSearchOnline.setIcon(QtGui.QIcon(str(graphics_path / "search.png")))
        self.actionLiteralSearch.setIcon(QtGui.QIcon(str(graphics_path / "search.png")))
        self.actionAutoIdentify.setIcon(QtGui.QIcon(str(graphics_path / "auto.png")))
        self.actionAutoTag.setIcon(QtGui.QIcon(str(graphics_path / "autotag.png")))
        self.actionAutoImprint.setIcon(QtGui.QIcon(str(graphics_path / "autotag.png")))
        self.actionClearEntryForm.setIcon(QtGui.QIcon(str(graphics_path / "clear.png")))
        self.actionPageBrowser.setIcon(QtGui.QIcon(str(graphics_path / "browse.png")))

        self.toolBar.addAction(self.actionLoad)
        self.toolBar.addAction(self.actionLoadFolder)
        self.toolBar.addAction(self.actionWrite_Tags)
        self.toolBar.addAction(self.actionSearchOnline)
        self.toolBar.addAction(self.actionLiteralSearch)
        self.toolBar.addAction(self.actionAutoIdentify)
        self.toolBar.addAction(self.actionAutoTag)
        self.toolBar.addAction(self.actionClearEntryForm)
        self.toolBar.addAction(self.actionPageBrowser)
        self.toolBar.addAction(self.actionAutoImprint)

        self.leWebLink.addAction(self.actionAddWebLink)
        self.leWebLink.addAction(self.actionRemoveWebLink)

        self.actionAddWebLink.triggered.connect(self.add_weblink_item)
        self.actionRemoveWebLink.triggered.connect(self.remove_weblink_item)

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
        non_zip_count = 0
        zip_list = []
        for ca in ca_list:
            if not ca.is_zip():
                non_zip_count += 1
            else:
                zip_list.append(ca)

        if non_zip_count == 0:
            QtWidgets.QMessageBox.information(
                self, self.tr("Export as Zip Archive"), self.tr("Only ZIP archives are selected!")
            )
            logger.warning("Export as Zip Archive. Only ZIP archives are selected")
            return

        if not self.dirty_flag_verification(
            "Export as Zip Archive",
            "If you export archives as Zip now, unsaved data in the form may be lost.  Are you sure?",
        ):
            return

        if non_zip_count != 0:
            EW = ExportWindow(
                self,
                (
                    f"You have selected {non_zip_count} archive(s) to export  to Zip format. "
                    """ New archives will be created in the same folder as the original.

   Please choose config below, and select OK.
   """
                ),
            )
            EW.adjustSize()
            EW.setModal(True)
            if not EW.exec():
                return

            prog_dialog = QtWidgets.QProgressDialog("", "Cancel", 0, non_zip_count, self)
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

            for prog_idx, ca in enumerate(zip_list, 1):
                QtCore.QCoreApplication.processEvents()
                if prog_dialog.wasCanceled():
                    break
                prog_dialog.setValue(prog_idx)
                prog_dialog.setLabelText(str(ca.path))
                QtCore.QCoreApplication.processEvents()

                export_name = ca.path.with_suffix(".cbz")
                export = True

                if export_name.exists():
                    if EW.fileConflictBehavior == ExportConflictOpts.dontCreate:
                        export = False
                        skipped_list.append(ca.path)
                    elif EW.fileConflictBehavior == ExportConflictOpts.createUnique:
                        export_name = utils.unique_file(export_name)

                if export:
                    if ca.export_as_zip(export_name):
                        success_count += 1
                        if EW.addToList:
                            new_archives_to_add.append(str(export_name))
                        if EW.deleteOriginal:
                            archives_to_remove.append(ca)
                            ca.path.unlink(missing_ok=True)

                    else:
                        # last export failed, so remove the zip, if it exists
                        failed_list.append(ca.path)
                        if export_name.exists():
                            export_name.unlink(missing_ok=True)

            prog_dialog.hide()
            QtCore.QCoreApplication.processEvents()
            self.fileSelectionList.add_path_list(new_archives_to_add)
            self.fileSelectionList.remove_archive_list(archives_to_remove)

            summary = f"Successfully created {success_count} Zip archive(s)."
            if len(skipped_list) > 0:
                summary += (
                    f"\n\nThe following {len(skipped_list)} archive(s) were skipped due to file name conflicts:\n"
                )
                for f in skipped_list:
                    summary += f"\t{f}\n"
            if len(failed_list) > 0:
                summary += (
                    f"\n\nThe following {len(failed_list)} archive(s) failed to export due to read/write errors:\n"
                )
                for f in failed_list:
                    summary += f"\t{f}\n"

            logger.info(summary)
            dlg = LogWindow(self)
            dlg.set_text(summary)
            dlg.setWindowTitle("Archive Export to Zip Summary")
            dlg.exec()

    def about_app(self) -> None:
        website = "https://github.com/comictagger/comictagger"
        email = "comictagger@gmail.com"
        license_link = "http://www.apache.org/licenses/LICENSE-2.0"
        license_name = "Apache License 2.0"

        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle("About " + self.appName)
        msg_box.setTextFormat(QtCore.Qt.TextFormat.RichText)
        msg_box.setIconPixmap(QtGui.QPixmap(str(graphics_path / "about.png")))
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

        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.exec()

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

        if self.comic_archive is not None:
            self.page_list_editor.set_data(self.comic_archive, self.metadata.pages)
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
        self.actionReCalcPageDims.setEnabled(enabled)
        self.actionRemoveAuto.setEnabled(enabled)
        self.actionRename.setEnabled(enabled)
        self.actionRepackage.setEnabled(enabled)

        self.menuRemove.setEnabled(enabled)
        self.menuViewRawTags.setEnabled(enabled)
        if self.comic_archive is not None:
            for style in metadata_styles:
                self.view_tag_actions[style].setEnabled(self.comic_archive.has_metadata(style))
                self.remove_tag_actions[style].setEnabled(self.comic_archive.has_metadata(style))

        self.actionWrite_Tags.setEnabled(writeable)

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

        supported_md = ca.get_supported_metadata()
        tag_info = ""
        for md in supported_md:
            if ca.has_metadata(md):
                tag_info += "• " + metadata_styles[md].name() + "\n"

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
                # if the role-person pair already exists, just skip adding it to the list
                if self.is_dupe_credit(credit["role"].title(), credit["person"]):
                    continue

                self.add_new_credit_entry(
                    row, credit["role"].title(), credit["person"], (credit["primary"] if "primary" in credit else False)
                )

        self.twCredits.setSortingEnabled(True)
        self.update_metadata_credit_colors()

    def add_new_credit_entry(self, row: int, role: str, name: str, primary_flag: bool = False) -> None:
        self.twCredits.insertRow(row)

        item_text = role
        item = QtWidgets.QTableWidgetItem(item_text)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        self.twCredits.setItem(row, 1, item)

        item_text = name
        item = QtWidgets.QTableWidgetItem(item_text)
        item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.twCredits.setItem(row, 2, item)

        item = QtWidgets.QTableWidgetItem("")
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.twCredits.setItem(row, 0, item)
        self.update_credit_primary_flag(row, primary_flag)

    def is_dupe_credit(self, role: str, name: str) -> bool:
        for r in range(self.twCredits.rowCount()):
            if self.twCredits.item(r, 1).text() == role and self.twCredits.item(r, 2).text() == name:
                return True

        return False

    def form_to_metadata(self) -> None:
        # copy the data from the form into the metadata
        md = GenericMetadata()
        md.is_empty = False
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
        md.maturity_rating = self.cbMaturityRating.currentText()

        md.critical_rating = utils.xlate_float(self.dsbCriticalRating.cleanText())
        if md.critical_rating == 0.0:
            md.critical_rating = None

        md.story_arcs = utils.split(self.leStoryArc.text(), ",")
        md.scan_info = utils.xlate(self.leScanInfo.text())
        md.series_groups = utils.split(self.leSeriesGroup.text(), ",")
        md.alternate_series = self.leAltSeries.text()
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
            role = self.twCredits.item(row, 1).text()
            name = self.twCredits.item(row, 2).text()
            primary_flag = self.twCredits.item(row, 0).text() != ""

            md.add_credit(name, role, bool(primary_flag))

        md.pages = self.page_list_editor.get_page_list()
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
            self.metadata.overlay(new_metadata)
            self.metadata_to_form()

    def use_filename_split(self) -> None:
        self._use_filename(True)

    def select_folder(self) -> None:
        self.select_file(folder_mode=True)

    def select_folder_archive(self) -> None:
        dialog = self.file_dialog(folder_mode=True)
        if dialog.exec():
            file_list = dialog.selectedFiles()
            if file_list:
                self.fileSelectionList.twList.selectRow(self.fileSelectionList.add_path_item(file_list[0]))

    def select_file(self, folder_mode: bool = False) -> None:
        dialog = self.file_dialog(folder_mode=folder_mode)
        if dialog.exec():
            file_list = dialog.selectedFiles()
            self.fileSelectionList.add_path_list(file_list)

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
            QtWidgets.QMessageBox.warning(self, "Automatic Identify Search", "You need to load a comic first!")
            return

        self.query_online(autoselect=True)

    def literal_search(self) -> None:
        self.query_online(autoselect=False, literal=True)

    def query_online(self, autoselect: bool = False, literal: bool = False) -> None:
        issue_number = str(self.leIssueNum.text()).strip()

        # Only need this check is the source has issue level data.
        if autoselect and issue_number == "":
            QtWidgets.QMessageBox.information(
                self,
                "Automatic Identify Search",
                "Can't auto-identify without an issue number. The auto-tag function has the 'If no issue number, assume \"1\"' option if desired.",
            )
            return

        if str(self.leSeries.text()).strip() != "":
            series_name = str(self.leSeries.text()).strip()
        else:
            QtWidgets.QMessageBox.information(self, "Online Search", "Need to enter a series name to search.")
            return

        year = utils.xlate_int(self.lePubYear.text())

        issue_count = utils.xlate_int(self.leIssueCount.text())

        cover_index_list = self.metadata.get_cover_page_index_list()
        selector = SeriesSelectionWindow(
            self,
            series_name,
            issue_number,
            year,
            issue_count,
            cover_index_list,
            self.comic_archive,
            self.config[0],
            self.current_talker(),
            autoselect,
            literal,
        )

        selector.setWindowTitle(f"Search: '{series_name}' - Select Series")

        selector.setModal(True)
        selector.exec()

        if selector.result():
            # we should now have a series ID
            QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))

            # copy the form onto metadata object
            self.form_to_metadata()

            try:
                new_metadata = self.current_talker().fetch_comic_data(
                    issue_id=selector.issue_id, series_id=selector.series_id, issue_number=selector.issue_number
                )
            except TalkerError as e:
                QtWidgets.QApplication.restoreOverrideCursor()
                QtWidgets.QMessageBox.critical(self, f"{e.source} {e.code_name} Error", f"{e}")
                return
            QtWidgets.QApplication.restoreOverrideCursor()

            if new_metadata is None or new_metadata.is_empty:
                QtWidgets.QMessageBox.critical(
                    self, "Search", f"Could not find an issue {selector.issue_number} for that series"
                )
                return

            self.metadata = prepare_metadata(self.metadata, new_metadata, self.config[0])
            # Now push the new combined data into the edit controls
            self.metadata_to_form()

    def commit_metadata(self) -> None:
        if self.metadata is not None and self.comic_archive is not None:
            if self.config[0].General__prompt_on_save:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Save Tags",
                    f"Are you sure you wish to save {', '.join([metadata_styles[style].name() for style in self.save_data_styles])} tags to this archive?",
                    QtWidgets.QMessageBox.StandardButton.Yes,
                    QtWidgets.QMessageBox.StandardButton.No,
                )
            else:
                reply = QtWidgets.QMessageBox.StandardButton.Yes

            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
            self.form_to_metadata()

            failed_style: str = ""
            # Save each style
            for style in self.save_data_styles:
                success = self.comic_archive.write_metadata(self.metadata, style)
                if not success:
                    failed_style = metadata_styles[style].name()
                    break

            self.comic_archive.load_cache(set(metadata_styles))
            QtWidgets.QApplication.restoreOverrideCursor()

            if failed_style:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Save failed",
                    f"The tag save operation seemed to fail for: {failed_style}",
                )
            else:
                self.clear_dirty_flag()
                self.update_info_box()
                self.update_menus()
            self.fileSelectionList.update_current_row()

            self.metadata, success = self.overlay_ca_read_style(self.load_data_styles, self.comic_archive)
            self.update_ui_for_archive()
        else:
            QtWidgets.QMessageBox.information(self, "Whoops!", "No data to commit!")

    def set_load_data_style(self) -> None:
        if self.dirty_flag_verification(
            "Change Tag Read Style",
            "If you change read tag style(s) now, data in the form will be lost.  Are you sure?",
        ):
            self.load_data_styles = reversed(self.cbLoadDataStyle.currentData())
            self.update_menus()
            if self.comic_archive is not None:
                self.load_archive(self.comic_archive)
        else:
            self.cbLoadDataStyle.itemChanged.disconnect()
            self.adjust_load_style_combo()
            self.cbLoadDataStyle.itemChanged.connect(self.set_load_data_style)

    def set_save_data_style(self) -> None:
        self.save_data_styles = self.cbSaveDataStyle.currentData()
        self.config[0].internal__save_data_style = self.save_data_styles
        self.update_metadata_style_tweaks()
        self.update_menus()

    def set_source(self, s: int) -> None:
        self.config[0].Sources__source = self.cbx_sources.itemData(s)

    def update_metadata_credit_colors(self) -> None:
        styles = [metadata_styles[style] for style in self.save_data_styles]
        enabled = set()
        for style in styles:
            enabled.update(style.supported_attributes)

        credit_attributes = [x for x in self.md_attributes.items() if "credits." in x[0]]

        for r in range(self.twCredits.rowCount()):
            w = self.twCredits.item(r, 1)
            supports_role = any(style.supports_credit_role(str(w.text())) for style in styles)
            for credit in credit_attributes:
                widget_enabled = credit[0] in enabled
                widget = self.twCredits.item(r, credit[1])
                if credit[0] == "credits.role":
                    widget_enabled = widget_enabled and supports_role
                enable_widget(widget, widget_enabled)

    def update_metadata_style_tweaks(self) -> None:
        # depending on the current data style, certain fields are disabled
        enabled_widgets = set()
        for style in self.save_data_styles:
            enabled_widgets.update(metadata_styles[style].supported_attributes)

        for metadata, widget in self.md_attributes.items():
            if widget is not None and not isinstance(widget, (int)):
                enable_widget(widget, metadata in enabled_widgets)

        self.update_metadata_credit_colors()
        self.page_list_editor.set_metadata_style(self.save_data_styles)

    def cell_double_clicked(self, r: int, c: int) -> None:
        self.edit_credit()

    def add_credit(self) -> None:
        self.modify_credits(False)

    def edit_credit(self) -> None:
        if self.twCredits.currentRow() > -1:
            self.modify_credits(True)

    def update_credit_primary_flag(self, row: int, primary: bool) -> None:
        # if we're clearing a flag do it and quit
        if not primary:
            self.twCredits.item(row, 0).setText("")
            return

        # otherwise, we need to check for, and clear, other primaries with same role
        role = str(self.twCredits.item(row, 1).text())
        r = 0
        for r in range(self.twCredits.rowCount()):
            if (
                self.twCredits.item(r, 0).text() != ""
                and str(self.twCredits.item(r, 1).text()).casefold() == role.casefold()
            ):
                self.twCredits.item(r, 0).setText("")

        # Now set our new primary
        self.twCredits.item(row, 0).setText("Yes")

    def modify_credits(self, edit: bool) -> None:
        if edit:
            row = self.twCredits.currentRow()
            role = self.twCredits.item(row, 1).text()
            name = self.twCredits.item(row, 2).text()
            primary = self.twCredits.item(row, 0).text() != ""
        else:
            row = self.twCredits.rowCount()
            role = ""
            name = ""
            primary = False

        editor = CreditEditorWindow(self, CreditEditorWindow.ModeEdit, role, name, primary)
        editor.setModal(True)
        editor.exec()
        if editor.result():
            new_role, new_name, new_primary = editor.get_credits()

            if new_name == name and new_role == role and new_primary == primary:
                # nothing has changed, just quit
                return

            # name and role is the same, but primary flag changed
            if new_name == name and new_role == role:
                self.update_credit_primary_flag(row, new_primary)
                return

            # check for dupes
            ok_to_mod = True
            if self.is_dupe_credit(new_role, new_name):
                # delete the dupe credit from list
                qmsg = QtWidgets.QMessageBox()
                qmsg.setText("Duplicate Credit!")
                qmsg.setInformativeText(
                    "This will create a duplicate credit entry. Would you like to merge the entries, or create a duplicate?"
                )
                qmsg.addButton("Merge", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
                qmsg.addButton("Duplicate", QtWidgets.QMessageBox.ButtonRole.NoRole)

                if qmsg.exec() == 0:
                    # merge
                    if edit:
                        # just remove the row that would be same
                        self.twCredits.removeRow(row)
                        # TODO -- need to find the row of the dupe, and possible change the primary flag

                    ok_to_mod = False

            if ok_to_mod:
                # modify it
                if edit:
                    self.twCredits.item(row, 1).setText(new_role)
                    self.twCredits.item(row, 2).setText(new_name)
                    self.update_credit_primary_flag(row, new_primary)
                else:
                    # add new entry
                    row = self.twCredits.rowCount()
                    self.add_new_credit_entry(row, new_role, new_name, new_primary)

            self.update_metadata_credit_colors()
            self.set_dirty_flag()

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
            QtWidgets.QMessageBox.warning(self, "Web Link", "Web Link is invalid.")

    def show_settings(self) -> None:
        settingswin = SettingsWindow(self, self.config, self.talkers)
        settingswin.setModal(True)
        settingswin.exec()
        settingswin.result()
        self.adjust_source_combo()

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

    def adjust_load_style_combo(self) -> None:
        # select the enabled styles
        unchecked = set(metadata_styles.keys()) - set(self.load_data_styles)
        for i, style in enumerate(self.load_data_styles):
            item_idx = self.cbLoadDataStyle.findData(style)
            self.cbLoadDataStyle.setItemChecked(item_idx, True)
            # Order matters, move items to list order
            self.cbLoadDataStyle.moveItem(item_idx, row=i)
        for style in unchecked:
            self.cbLoadDataStyle.setItemChecked(self.cbLoadDataStyle.findData(style), False)

    def adjust_save_style_combo(self) -> None:
        # select the current style
        unchecked = set(metadata_styles.keys()) - set(self.save_data_styles)
        for style in self.save_data_styles:
            self.cbSaveDataStyle.setItemChecked(self.cbSaveDataStyle.findData(style), True)
        for style in unchecked:
            self.cbSaveDataStyle.setItemChecked(self.cbSaveDataStyle.findData(style), False)
        self.update_metadata_style_tweaks()

    def populate_style_names(self) -> None:
        # First clear all entries (called from settingswindow.py)
        self.cbSaveDataStyle.clear()
        self.cbLoadDataStyle.emptyTable()
        # Add the entries to the tag style combobox
        for style in metadata_styles.values():
            if self.config[0].General__use_short_metadata_names:
                self.cbSaveDataStyle.addItem(style.short_name.upper(), style.short_name)
                self.cbLoadDataStyle.addItem(style.short_name.upper(), style.short_name)
            else:
                self.cbSaveDataStyle.addItem(style.name(), style.short_name)
                self.cbLoadDataStyle.addItem(style.name(), style.short_name)

    def populate_combo_boxes(self) -> None:
        self.populate_style_names()

        self.adjust_load_style_combo()
        self.adjust_save_style_combo()

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
        self.remove_tags(self.save_data_styles)

    def remove_tags(self, styles: list[str]) -> None:
        # remove the indicated tags from the archive
        ca_list = self.fileSelectionList.get_selected_archive_list()
        has_md_count = 0
        file_md_count = {}
        for style in styles:
            file_md_count[style] = 0
        for ca in ca_list:
            for style in styles:
                if ca.has_metadata(style):
                    has_md_count += 1
                    file_md_count[style] += 1

        if has_md_count == 0:
            QtWidgets.QMessageBox.information(
                self,
                "Remove Tags",
                f"No archives with {', '.join([metadata_styles[style].name() for style in styles])} tags selected!",
            )
            return

        if has_md_count != 0 and not self.dirty_flag_verification(
            "Remove Tags", "If you remove tags now, unsaved data in the form will be lost.  Are you sure?"
        ):
            return

        if has_md_count != 0:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Remove Tags",
                f"Are you sure you wish to remove {', '.join([f'{metadata_styles[style].name()} tags from {count} files' for style, count in file_md_count.items()])} removing a total of {has_md_count} tag(s)?",
                QtWidgets.QMessageBox.StandardButton.Yes,
                QtWidgets.QMessageBox.StandardButton.No,
            )

            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                progdialog = QtWidgets.QProgressDialog("", "Cancel", 0, has_md_count, self)
                progdialog.setWindowTitle("Removing Tags")
                progdialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                progdialog.setMinimumDuration(300)
                center_window_on_parent(progdialog)
                QtCore.QCoreApplication.processEvents()

                failed_list = []
                success_count = 0
                for prog_idx, ca in enumerate(ca_list, 1):
                    QtCore.QCoreApplication.processEvents()
                    if progdialog.wasCanceled():
                        break
                    progdialog.setValue(prog_idx)
                    progdialog.setLabelText(str(ca.path))
                    QtCore.QCoreApplication.processEvents()
                    for style in styles:
                        if ca.has_metadata(style) and ca.is_writable():
                            if ca.remove_metadata(style):
                                success_count += 1
                            else:
                                failed_list.append(ca.path)
                                # Abandon any further tag removals to prevent any greater damage to archive
                                break
                    ca.reset_cache()
                    ca.load_cache(set(metadata_styles))

                progdialog.hide()
                QtCore.QCoreApplication.processEvents()
                self.fileSelectionList.update_selected_rows()
                self.update_info_box()
                self.update_menus()

                summary = f"Successfully removed {success_count} tags in archive(s)."
                if len(failed_list) > 0:
                    summary += f"\n\nThe remove operation failed in the following {len(failed_list)} archive(s):\n"
                    for f in failed_list:
                        summary += f"\t{f}\n"

                dlg = LogWindow(self)
                dlg.set_text(summary)
                dlg.setWindowTitle("Tag Remove Summary")
                dlg.exec()

    def copy_tags(self) -> None:
        # copy the indicated tags in the archive
        ca_list = self.fileSelectionList.get_selected_archive_list()
        has_src_count = 0

        src_styles: list[str] = self.load_data_styles
        dest_styles: list[str] = self.save_data_styles

        if len(src_styles) == 1 and src_styles[0] in dest_styles:
            # Remove the read style from the write style
            dest_styles.remove(src_styles[0])

        if not dest_styles:
            QtWidgets.QMessageBox.information(
                self, "Copy Tags", "Can't copy tag style onto itself.  Read style and modify style must be different."
            )
            return

        for ca in ca_list:
            for style in src_styles:
                if ca.has_metadata(style):
                    has_src_count += 1
                    continue

        if has_src_count == 0:
            QtWidgets.QMessageBox.information(
                self,
                "Copy Tags",
                f"No archives with {', '.join([metadata_styles[style].name() for style in src_styles])} tags selected!",
            )
            return

        if has_src_count != 0 and not self.dirty_flag_verification(
            "Copy Tags", "If you copy tags now, unsaved data in the form may be lost.  Are you sure?"
        ):
            return

        if has_src_count != 0:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Copy Tags",
                f"Are you sure you wish to copy the combined (with overlay order) tags of "
                f"{', '.join([metadata_styles[style].name() for style in src_styles])} "
                f"to {', '.join([metadata_styles[style].name() for style in dest_styles])} tags in "
                f"{has_src_count} archive(s)?",
                QtWidgets.QMessageBox.StandardButton.Yes,
                QtWidgets.QMessageBox.StandardButton.No,
            )

            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                prog_dialog = QtWidgets.QProgressDialog("", "Cancel", 0, has_src_count, self)
                prog_dialog.setWindowTitle("Copying Tags")
                prog_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                prog_dialog.setMinimumDuration(300)
                center_window_on_parent(prog_dialog)
                QtCore.QCoreApplication.processEvents()

                failed_list = []
                success_count = 0
                for prog_idx, ca in enumerate(ca_list, 1):
                    ca_saved = False
                    md, success = self.overlay_ca_read_style(src_styles, ca)
                    if md.is_empty:
                        continue

                    for style in dest_styles:
                        if ca.has_metadata(style):
                            QtCore.QCoreApplication.processEvents()
                            if prog_dialog.wasCanceled():
                                break

                            prog_dialog.setValue(prog_idx)
                            prog_dialog.setLabelText(str(ca.path))
                            center_window_on_parent(prog_dialog)
                            QtCore.QCoreApplication.processEvents()

                        if style == "cbi" and self.config[0].Comic_Book_Lover__apply_transform_on_bulk_operation:
                            md = CBLTransformer(md, self.config[0]).apply()

                        if ca.write_metadata(md, style):
                            if not ca_saved:
                                success_count += 1
                                ca_saved = True
                        else:
                            failed_list.append(ca.path)

                    ca.reset_cache()
                    ca.load_cache({*self.load_data_styles, *self.save_data_styles})

                prog_dialog.hide()
                QtCore.QCoreApplication.processEvents()
                self.fileSelectionList.update_selected_rows()
                self.update_info_box()
                self.update_menus()

                summary = f"Successfully copied tags in {success_count} archive(s)."
                if len(failed_list) > 0:
                    summary += f"\n\nThe copy operation failed in the following {len(failed_list)} archive(s):\n"
                    for f in failed_list:
                        summary += f"\t{f}\n"

                dlg = LogWindow(self)
                dlg.set_text(summary)
                dlg.setWindowTitle("Tag Copy Summary")
                dlg.exec()

    def auto_tag_log(self, text: str) -> None:
        if self.atprogdialog is not None:
            self.atprogdialog.textEdit.append(text.rstrip())
            self.atprogdialog.textEdit.ensureCursorVisible()
            QtCore.QCoreApplication.processEvents()
            QtCore.QCoreApplication.processEvents()
            QtCore.QCoreApplication.processEvents()

    def identify_and_tag_single_archive(
        self, ca: ComicArchive, match_results: OnlineMatchResults, dlg: AutoTagStartWindow
    ) -> tuple[bool, OnlineMatchResults]:
        def metadata_save() -> bool:
            for style in self.save_data_styles:
                # write out the new data
                if not ca.write_metadata(md, style):
                    self.auto_tag_log(
                        f"{metadata_styles[style].name()} save failed! Aborting any additional style saves.\n"
                    )
                    return False
            return True

        success = False
        ii = IssueIdentifier(ca, self.config[0], self.current_talker())

        # read in metadata, and parse file name if not there
        md, success = self.overlay_ca_read_style(self.load_data_styles, ca)

        if md.is_empty:
            md = ca.metadata_from_filename(
                self.config[0].Filename_Parsing__filename_parser,
                self.config[0].Filename_Parsing__remove_c2c,
                self.config[0].Filename_Parsing__remove_fcbd,
                self.config[0].Filename_Parsing__remove_publisher,
                dlg.split_words,
                self.config[0].Filename_Parsing__allow_issue_start_with_letter,
                self.config[0].Filename_Parsing__protofolius_issue_number_scheme,
            )
            if dlg.ignore_leading_digits_in_filename and md.series is not None:
                # remove all leading numbers
                md.series = re.sub(r"([\d.]*)(.*)", r"\2", md.series)

        # use the dialog specified search string
        if dlg.search_string:
            md.series = dlg.search_string

        if md is None or md.is_empty:
            logger.error("No metadata given to search online with!")
            return False, match_results

        if dlg.dont_use_year:
            md.year = None
        if md.issue is None or md.issue == "":
            if dlg.assume_issue_one:
                md.issue = "1"
            else:
                md.issue = utils.xlate(md.volume)

        ii.set_output_function(self.auto_tag_log)
        if self.atprogdialog is not None:
            ii.set_cover_url_callback(self.atprogdialog.set_test_image)
        ii.set_name_series_match_threshold(dlg.name_length_match_tolerance)

        result, matches = ii.identify(ca, md)

        found_match = False
        choices = False
        low_confidence = False

        if result == ii.result_no_matches:
            pass
        elif result == ii.result_found_match_but_bad_cover_score:
            low_confidence = True
            found_match = True
        elif result == ii.result_found_match_but_not_first_page:
            found_match = True
        elif result == ii.result_multiple_matches_with_bad_image_scores:
            low_confidence = True
            choices = True
        elif result == ii.result_one_good_match:
            found_match = True
        elif result == ii.result_multiple_good_matches:
            choices = True

        if choices:
            if low_confidence:
                self.auto_tag_log("Online search: Multiple low-confidence matches.  Save aborted\n")
                match_results.low_confidence_matches.append(
                    Result(
                        Action.save,
                        Status.match_failure,
                        ca.path,
                        online_results=matches,
                        match_status=MatchStatus.low_confidence_match,
                    )
                )
            else:
                self.auto_tag_log("Online search: Multiple matches.  Save aborted\n")
                match_results.multiple_matches.append(
                    Result(
                        Action.save,
                        Status.match_failure,
                        ca.path,
                        online_results=matches,
                        match_status=MatchStatus.multiple_match,
                    )
                )
        elif low_confidence and not dlg.auto_save_on_low:
            self.auto_tag_log("Online search: Low confidence match.  Save aborted\n")
            match_results.low_confidence_matches.append(
                Result(
                    Action.save,
                    Status.match_failure,
                    ca.path,
                    online_results=matches,
                    match_status=MatchStatus.low_confidence_match,
                )
            )
        elif not found_match:
            self.auto_tag_log("Online search: No match found.  Save aborted\n")
            match_results.no_matches.append(
                Result(
                    Action.save,
                    Status.match_failure,
                    ca.path,
                    online_results=matches,
                    match_status=MatchStatus.no_match,
                )
            )
        else:
            # a single match!
            if low_confidence:
                self.auto_tag_log("Online search: Low confidence match, but saving anyways, as indicated...\n")

            # now get the particular issue data
            QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))

            try:

                ct_md = self.current_talker().fetch_comic_data(matches[0].issue_id)
            except TalkerError:
                logger.exception("Save aborted.")
                return False, match_results

            QtWidgets.QApplication.restoreOverrideCursor()

            if ct_md is None or ct_md.is_empty:
                match_results.fetch_data_failures.append(
                    Result(
                        Action.save,
                        Status.fetch_data_failure,
                        ca.path,
                        online_results=matches,
                        match_status=MatchStatus.good_match,
                    )
                )

            if ct_md is not None:
                temp_opts = cast(ct_ns, settngs.get_namespace(self.config, True, True, True, False)[0])
                if dlg.cbxRemoveMetadata.isChecked():
                    temp_opts.Issue_Identifier__clear_metadata

                md = prepare_metadata(md, ct_md, temp_opts)

                res = Result(
                    Action.save,
                    status=Status.success,
                    original_path=ca.path,
                    online_results=matches,
                    match_status=MatchStatus.good_match,
                    md=md,
                    tags_written=self.save_data_styles,
                )

                # Save styles
                if metadata_save():
                    match_results.good_matches.append(res)
                    success = True
                    self.auto_tag_log("Save complete!\n")
                else:
                    res.status = Status.write_failure
                    match_results.write_failures.append(res)

                ca.reset_cache()
                ca.load_cache({*self.load_data_styles, *self.save_data_styles})

        return success, match_results

    def auto_tag(self) -> None:
        ca_list = self.fileSelectionList.get_selected_archive_list()
        styles = self.save_data_styles

        if len(ca_list) == 0:
            QtWidgets.QMessageBox.information(self, "Auto-Tag", "No archives selected!")
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
                + ", ".join([metadata_styles[style].name() for style in styles])
                + " tags to.\n\nPlease choose config below, and select OK to Auto-Tag."
            ),
        )

        atstartdlg.adjustSize()
        atstartdlg.setModal(True)
        if not atstartdlg.exec():
            return

        self.atprogdialog = AutoTagProgressWindow(self, self.current_talker())
        self.atprogdialog.setModal(True)
        self.atprogdialog.show()
        self.atprogdialog.progressBar.setMaximum(len(ca_list))
        self.atprogdialog.setWindowTitle("Auto-Tagging")
        center_window_on_parent(self.atprogdialog)

        self.auto_tag_log("==========================================================================\n")
        self.auto_tag_log(f"Auto-Tagging Started for {len(ca_list)} items\n")

        match_results = OnlineMatchResults()
        archives_to_remove = []
        for prog_idx, ca in enumerate(ca_list):
            self.auto_tag_log("==========================================================================\n")
            self.auto_tag_log(f"Auto-Tagging {prog_idx} of {len(ca_list)}\n")
            self.auto_tag_log(f"{ca.path}\n")
            try:
                cover_idx = ca.read_metadata(self.load_data_styles[0]).get_cover_page_index_list()[0]
            except Exception as e:
                cover_idx = 0
                logger.error("Failed to load metadata for %s: %s", ca.path, e)
            image_data = ca.get_page(cover_idx)
            self.atprogdialog.set_archive_image(image_data)
            self.atprogdialog.set_test_image(b"")

            QtCore.QCoreApplication.processEvents()
            if self.atprogdialog.isdone:
                break
            self.atprogdialog.progressBar.setValue(prog_idx)

            self.atprogdialog.label.setText(str(ca.path))
            QtCore.QCoreApplication.processEvents()

            if ca.is_writable():
                success, match_results = self.identify_and_tag_single_archive(ca, match_results, atstartdlg)

                if success and atstartdlg.remove_after_success:
                    archives_to_remove.append(ca)

        self.atprogdialog.close()

        if atstartdlg.remove_after_success:
            self.fileSelectionList.remove_archive_list(archives_to_remove)
        self.fileSelectionList.update_selected_rows()

        new_ca = self.fileSelectionList.get_current_archive()
        if new_ca is not None:
            self.load_archive(new_ca)
        self.atprogdialog = None

        summary = ""
        summary += f"Successfully added {', '.join([metadata_styles[style].name() for style in self.save_data_styles])} tags to {len(match_results.good_matches)} archive(s)\n"

        if len(match_results.multiple_matches) > 0:
            summary += f"Archives with multiple matches: {len(match_results.multiple_matches)}\n"
        if len(match_results.low_confidence_matches) > 0:
            summary += (
                f"Archives with one or more low-confidence matches: {len(match_results.low_confidence_matches)}\n"
            )
        if len(match_results.no_matches) > 0:
            summary += f"Archives with no matches: {len(match_results.no_matches)}\n"
        if len(match_results.fetch_data_failures) > 0:
            summary += f"Archives that failed due to data fetch errors: {len(match_results.fetch_data_failures)}\n"
        if len(match_results.write_failures) > 0:
            summary += f"Archives that failed due to file writing errors: {len(match_results.write_failures)}\n"

        self.auto_tag_log(summary)

        sum_selectable = len(match_results.multiple_matches) + len(match_results.low_confidence_matches)
        if sum_selectable > 0:
            summary += (
                "\n\nDo you want to manually select the ones with multiple matches and/or low-confidence matches now?"
            )

            reply = QtWidgets.QMessageBox.question(
                self,
                "Auto-Tag Summary",
                summary,
                QtWidgets.QMessageBox.StandardButton.Yes,
                QtWidgets.QMessageBox.StandardButton.No,
            )

            match_results.multiple_matches.extend(match_results.low_confidence_matches)
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                matchdlg = AutoTagMatchWindow(
                    self,
                    match_results.multiple_matches,
                    styles,
                    lambda match: self.current_talker().fetch_comic_data(match.issue_id),
                    self.config[0],
                    self.current_talker(),
                )
                matchdlg.setModal(True)
                matchdlg.exec()
                self.fileSelectionList.update_selected_rows()
                new_ca = self.fileSelectionList.get_current_archive()
                if new_ca is not None:
                    self.load_archive(new_ca)

        else:
            QtWidgets.QMessageBox.information(self, self.tr("Auto-Tag Summary"), self.tr(summary))
        logger.info(summary)

    def exception(self, message: str) -> None:
        errorbox = QtWidgets.QMessageBox()
        errorbox.setText(message)
        errorbox.exec()

    def dirty_flag_verification(self, title: str, desc: str) -> bool:
        if self.dirty_flag:
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
                self.commit_metadata()
                return True
            return False
        return True

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
            self.config[0].internal__load_data_style = self.cbLoadDataStyle.currentData()
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

    def view_raw_tags(self, style: str) -> None:
        if self.comic_archive is not None and self.comic_archive.has_metadata(style):
            md_style = metadata_styles[style]
            dlg = LogWindow(self)
            dlg.set_text(self.comic_archive.read_metadata_string(style))
            dlg.setWindowTitle(f"Raw {md_style.name()} Tag View")
            dlg.exec()

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

    def recalc_page_dimensions(self) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        for p in self.metadata.pages:
            if "size" in p:
                del p["size"]
            if "height" in p:
                del p["height"]
            if "width" in p:
                del p["width"]
        self.set_dirty_flag()
        QtWidgets.QApplication.restoreOverrideCursor()

    def rename_archive(self) -> None:
        ca_list = self.fileSelectionList.get_selected_archive_list()

        if len(ca_list) == 0:
            QtWidgets.QMessageBox.information(self, "Rename", "No archives selected!")
            return

        if self.dirty_flag_verification(
            "File Rename", "If you rename files now, unsaved data in the form will be lost.  Are you sure?"
        ):
            dlg = RenameWindow(self, ca_list, self.load_data_styles, self.config, self.talkers)
            dlg.setModal(True)
            if dlg.exec() and self.comic_archive is not None:
                self.fileSelectionList.update_selected_rows()
                self.load_archive(self.comic_archive)

    def load_archive(self, comic_archive: ComicArchive) -> None:
        self.comic_archive = None
        self.clear_form()
        self.metadata = GenericMetadata()

        if not os.path.exists(comic_archive.path):
            self.fileSelectionList.dirty_flag = False
            self.fileSelectionList.remove_archive_list([comic_archive])
            QtCore.QTimer.singleShot(1, self.fileSelectionList.revert_selection)
            return

        self.config[0].internal__last_opened_folder = os.path.abspath(os.path.split(comic_archive.path)[0])
        self.comic_archive = comic_archive

        self.metadata, success = self.overlay_ca_read_style(self.load_data_styles, self.comic_archive)
        if not success:
            self.exception(f"Failed to load metadata for {self.comic_archive.path}, see log for details\n\n")

        self.update_ui_for_archive()

    def overlay_ca_read_style(self, load_data_styles: list[str], ca: ComicArchive) -> tuple[GenericMetadata, bool]:
        md = GenericMetadata()
        success = True
        try:
            for style in load_data_styles:
                metadata = ca.read_metadata(style)
                md.overlay(metadata)
        except Exception as e:
            logger.error("Failed to load metadata for %s: %s", self.ca.path, e)
            success = False

        return md, success

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

    def check_latest_version_online(self) -> None:
        version_checker = VersionChecker()
        self.version_check_complete(version_checker.get_latest_version(self.config[0].internal__install_id))

    def version_check_complete(self, new_version: tuple[str, str]) -> None:
        if new_version[0] not in (self.version, self.config[0].Dialog_Flags__dont_notify_about_this_version):
            website = "https://github.com/comictagger/comictagger"
            checked = OptionalMessageDialog.msg(
                self,
                "New version available!",
                f"New version ({new_version[1]}) available!<br>(You are currently running {self.version})<br><br>"
                f"Visit <a href='{website}/releases/latest'>{website}/releases/latest</a> for more info.<br><br>",
                False,
                "Don't tell me about this version again",
            )
            if checked:
                self.config[0].Dialog_Flags__dont_notify_about_this_version = new_version[0]

    def on_incoming_socket_connection(self) -> None:
        # Accept connection from other instance.
        # Read in the file list if they're giving it, and add to our own list
        local_socket = self.socketServer.nextPendingConnection()
        if local_socket.waitForReadyRead(3000):
            byte_array = local_socket.readAll().data()
            if len(byte_array) > 0:
                obj = pickle.loads(byte_array)
                local_socket.disconnectFromServer()
                if isinstance(obj, list):
                    self.fileSelectionList.add_path_list(obj)

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
            QtCore.QCoreApplication.processEvents()
            self.setWindowFlags(flags)
            self.show()

    def auto_imprint(self) -> None:
        self.form_to_metadata()
        self.metadata.fix_publisher()
        self.metadata_to_form()
