"""A PyQT4 dialog to confirm rename"""
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

import settngs
from PyQt5 import QtCore, QtWidgets, uic

from comicapi import utils
from comicapi.comicarchive import ComicArchive, MetaDataStyle
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib.filerenamer import FileRenamer, get_rename_dir
from comictaggerlib.settingswindow import SettingsWindow
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import center_window_on_parent
from comictalker.talkerbase import ComicTalker

logger = logging.getLogger(__name__)


class RenameWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        comic_archive_list: list[ComicArchive],
        data_style: int,
        options: settngs.Config,
        talker_api: ComicTalker,
    ) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "renamewindow.ui", self)
        self.label.setText(f"Preview (based on {MetaDataStyle.name[data_style]} tags):")

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.options = options
        self.talker_api = talker_api
        self.comic_archive_list = comic_archive_list
        self.data_style = data_style
        self.rename_list: list[str] = []

        self.btnSettings.clicked.connect(self.modify_settings)
        platform = "universal" if self.options[0]["filename"]["rename_strict"] else "auto"
        self.renamer = FileRenamer(None, platform=platform, replacements=self.options[0]["rename"]["replacements"])

        self.do_preview()

    def config_renamer(self, ca: ComicArchive, md: GenericMetadata | None = None) -> str:
        self.renamer.set_template(self.options[0]["filename"]["rename_template"])
        self.renamer.set_issue_zero_padding(self.options[0]["filename"]["rename_issue_number_padding"])
        self.renamer.set_smart_cleanup(self.options[0]["filename"]["rename_use_smart_string_cleanup"])
        self.renamer.replacements = self.options[0]["rename"]["replacements"]

        new_ext = ca.path.suffix  # default
        if self.options[0]["filename"]["rename_set_extension_based_on_archive"]:
            if ca.is_sevenzip():
                new_ext = ".cb7"
            elif ca.is_zip():
                new_ext = ".cbz"
            elif ca.is_rar():
                new_ext = ".cbr"

        if md is None:
            md = ca.read_metadata(self.data_style)
            if md.is_empty:
                md = ca.metadata_from_filename(
                    self.options[0]["filename"]["complicated_parser"],
                    self.options[0]["filename"]["remove_c2c"],
                    self.options[0]["filename"]["remove_fcbd"],
                    self.options[0]["filename"]["remove_publisher"],
                )
        self.renamer.set_metadata(md)
        self.renamer.move = self.options[0]["filename"]["rename_move_to_dir"]
        return new_ext

    def do_preview(self) -> None:
        self.twList.setRowCount(0)

        self.twList.setSortingEnabled(False)

        for ca in self.comic_archive_list:
            new_ext = self.config_renamer(ca)
            try:
                new_name = self.renamer.determine_name(new_ext)
            except ValueError as e:
                logger.exception("Invalid format string: %s", self.options[0]["filename"]["rename_template"])
                QtWidgets.QMessageBox.critical(
                    self,
                    "Invalid format string!",
                    "Your rename template is invalid!"
                    f"<br/><br/>{e}<br/><br/>"
                    "Please consult the template help in the "
                    "settings and the documentation on the format at "
                    "<a href='https://docs.python.org/3/library/string.html#format-string-syntax'>"
                    "https://docs.python.org/3/library/string.html#format-string-syntax</a>",
                )
                return
            except Exception as e:
                logger.exception(
                    "Formatter failure: %s metadata: %s",
                    self.options[0]["filename"]["rename_template"],
                    self.renamer.metadata,
                )
                QtWidgets.QMessageBox.critical(
                    self,
                    "The formatter had an issue!",
                    "The formatter has experienced an unexpected error!"
                    f"<br/><br/>{type(e).__name__}: {e}<br/><br/>"
                    "Please open an issue at "
                    "<a href='https://github.com/comictagger/comictagger'>"
                    "https://github.com/comictagger/comictagger</a>",
                )

            row = self.twList.rowCount()
            self.twList.insertRow(row)
            folder_item = QtWidgets.QTableWidgetItem()
            old_name_item = QtWidgets.QTableWidgetItem()
            new_name_item = QtWidgets.QTableWidgetItem()

            item_text = str(ca.path.parent)
            folder_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, folder_item)
            folder_item.setText(item_text)
            folder_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            item_text = str(ca.path.name)
            old_name_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, old_name_item)
            old_name_item.setText(item_text)
            old_name_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            new_name_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, new_name_item)
            new_name_item.setText(new_name)
            new_name_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, new_name)

            self.rename_list.append(new_name)

        # Adjust column sizes
        self.twList.setVisible(False)
        self.twList.resizeColumnsToContents()
        self.twList.setVisible(True)
        if self.twList.columnWidth(0) > 200:
            self.twList.setColumnWidth(0, 200)

        self.twList.setSortingEnabled(True)

    def modify_settings(self) -> None:
        settingswin = SettingsWindow(self, self.options, self.talker_api)
        settingswin.setModal(True)
        settingswin.show_rename_tab()
        settingswin.exec()
        if settingswin.result():
            self.do_preview()

    def accept(self) -> None:

        prog_dialog = QtWidgets.QProgressDialog("", "Cancel", 0, len(self.rename_list), self)
        prog_dialog.setWindowTitle("Renaming Archives")
        prog_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        prog_dialog.setMinimumDuration(100)
        center_window_on_parent(prog_dialog)
        QtCore.QCoreApplication.processEvents()

        try:
            for idx, comic in enumerate(zip(self.comic_archive_list, self.rename_list)):

                QtCore.QCoreApplication.processEvents()
                if prog_dialog.wasCanceled():
                    break
                idx += 1
                prog_dialog.setValue(idx)
                prog_dialog.setLabelText(comic[1])
                center_window_on_parent(prog_dialog)
                QtCore.QCoreApplication.processEvents()

                folder = get_rename_dir(
                    comic[0],
                    self.options[0]["filename"]["rename_dir"]
                    if self.options[0]["filename"]["rename_move_to_dir"]
                    else None,
                )

                full_path = folder / comic[1]

                if full_path == comic[0].path:
                    logger.info("%s: Filename is already good!", comic[1])
                    continue

                if not comic[0].is_writable(check_rar_status=False):
                    continue

                comic[0].rename(utils.unique_file(full_path))
        except Exception as e:
            logger.exception("Failed to rename comic archive: %s", comic[0].path)
            QtWidgets.QMessageBox.critical(
                self,
                "There was an issue when renaming!",
                f"Renaming failed!<br/><br/>{type(e).__name__}: {e}<br/><br/>",
            )

        prog_dialog.hide()
        QtCore.QCoreApplication.processEvents()

        QtWidgets.QDialog.accept(self)
