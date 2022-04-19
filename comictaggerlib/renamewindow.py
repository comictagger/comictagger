"""A PyQT4 dialog to confirm rename"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
from typing import List

from PyQt5 import QtCore, QtWidgets, uic

import comicapi.comicarchive
from comicapi import utils
from comicapi.comicarchive import MetaDataStyle
from comictaggerlib.filerenamer import FileRenamer, FileRenamer2
from comictaggerlib.settings import ComicTaggerSettings
from comictaggerlib.settingswindow import SettingsWindow
from comictaggerlib.ui.qtutils import center_window_on_parent

logger = logging.getLogger(__name__)


class RenameWindow(QtWidgets.QDialog):
    def __init__(self, parent, comic_archive_list: List[comicapi.comicarchive.ComicArchive], data_style, settings):
        super().__init__(parent)

        uic.loadUi(ComicTaggerSettings.get_ui_file("renamewindow.ui"), self)
        self.label.setText(f"Preview (based on {MetaDataStyle.name[data_style]} tags):")

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.settings = settings
        self.comic_archive_list = comic_archive_list
        self.data_style = data_style
        self.rename_list = []

        self.btnSettings.clicked.connect(self.modify_settings)
        if self.settings.rename_new_renamer:
            self.renamer = FileRenamer2(None)
        else:
            self.renamer = FileRenamer(None)

        self.config_renamer()
        self.do_preview()

    def config_renamer(self):
        self.renamer.set_template(self.settings.rename_template)
        self.renamer.set_issue_zero_padding(self.settings.rename_issue_number_padding)
        self.renamer.set_smart_cleanup(self.settings.rename_use_smart_string_cleanup)

    def do_preview(self):
        while self.twList.rowCount() > 0:
            self.twList.removeRow(0)

        self.twList.setSortingEnabled(False)

        for ca in self.comic_archive_list:

            new_ext = None  # default
            if self.settings.rename_extension_based_on_archive:
                if ca.is_sevenzip():
                    new_ext = ".cb7"
                elif ca.is_zip():
                    new_ext = ".cbz"
                elif ca.is_rar():
                    new_ext = ".cbr"

            md = ca.read_metadata(self.data_style)
            if md.is_empty:
                md = ca.metadata_from_filename(self.settings.parse_scan_info)
            self.renamer.set_metadata(md)
            self.renamer.move = self.settings.rename_move_dir

            try:
                new_name = self.renamer.determine_name(new_ext)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Invalid format string!",
                    "Your rename template is invalid!"
                    "<br/><br/>{}<br/><br/>"
                    "Please consult the template help in the "
                    "settings and the documentation on the format at "
                    "<a href='https://docs.python.org/3/library/string.html#format-string-syntax'>"
                    "https://docs.python.org/3/library/string.html#format-string-syntax</a>".format(e),
                )
                return

            row = self.twList.rowCount()
            self.twList.insertRow(row)
            folder_item = QtWidgets.QTableWidgetItem()
            old_name_item = QtWidgets.QTableWidgetItem()
            new_name_item = QtWidgets.QTableWidgetItem()

            item_text = os.path.split(ca.path)[0]
            folder_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, folder_item)
            folder_item.setText(item_text)
            folder_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            item_text = os.path.split(ca.path)[1]
            old_name_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, old_name_item)
            old_name_item.setText(item_text)
            old_name_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            new_name_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, new_name_item)
            new_name_item.setText(new_name)
            new_name_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, new_name)

            dict_item = {}
            dict_item["archive"] = ca
            dict_item["new_name"] = new_name
            self.rename_list.append(dict_item)

        # Adjust column sizes
        self.twList.setVisible(False)
        self.twList.resizeColumnsToContents()
        self.twList.setVisible(True)
        if self.twList.columnWidth(0) > 200:
            self.twList.setColumnWidth(0, 200)

        self.twList.setSortingEnabled(True)

    def modify_settings(self):
        settingswin = SettingsWindow(self, self.settings)
        settingswin.setModal(True)
        settingswin.show_rename_tab()
        settingswin.exec()
        if settingswin.result():
            self.config_renamer()
            self.do_preview()

    def accept(self):

        prog_dialog = QtWidgets.QProgressDialog("", "Cancel", 0, len(self.rename_list), self)
        prog_dialog.setWindowTitle("Renaming Archives")
        prog_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        prog_dialog.setMinimumDuration(100)
        center_window_on_parent(prog_dialog)
        QtCore.QCoreApplication.processEvents()

        for idx, item in enumerate(self.rename_list):

            QtCore.QCoreApplication.processEvents()
            if prog_dialog.wasCanceled():
                break
            idx += 1
            prog_dialog.setValue(idx)
            prog_dialog.setLabelText(item["new_name"])
            center_window_on_parent(prog_dialog)
            QtCore.QCoreApplication.processEvents()

            folder = os.path.dirname(os.path.abspath(item["archive"].path))
            if self.settings.rename_move_dir and len(self.settings.rename_dir.strip()) > 3:
                folder = self.settings.rename_dir.strip()

            new_abs_path = utils.unique_file(os.path.join(folder, item["new_name"]))

            if os.path.join(folder, item["new_name"]) == item["archive"].path:
                print(item["new_name"], "Filename is already good!")
                logger.info(item["new_name"], "Filename is already good!")
                continue

            if not item["archive"].is_writable(check_rar_status=False):
                continue

            os.makedirs(os.path.dirname(new_abs_path), 0o777, True)
            os.rename(item["archive"].path, new_abs_path)

            item["archive"].rename(new_abs_path)

        prog_dialog.hide()
        QtCore.QCoreApplication.processEvents()

        QtWidgets.QDialog.accept(self)
