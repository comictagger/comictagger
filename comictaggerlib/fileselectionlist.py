"""A PyQt5 widget for managing list of comic archive files"""
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
import os
import platform
from typing import Callable, cast

from PyQt5 import QtCore, QtWidgets, uic

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.graphics import graphics_path
from comictaggerlib.optionalmsgdialog import OptionalMessageDialog
from comictaggerlib.settingswindow import linuxRarHelp, macRarHelp, windowsRarHelp
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import center_window_on_parent, reduce_widget_font_size

logger = logging.getLogger(__name__)


class FileTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other: object) -> bool:
        return self.data(QtCore.Qt.ItemDataRole.UserRole) < other.data(QtCore.Qt.ItemDataRole.UserRole)  # type: ignore


class FileInfo:
    def __init__(self, ca: ComicArchive) -> None:
        self.ca: ComicArchive = ca


class FileSelectionList(QtWidgets.QWidget):
    selectionChanged = QtCore.pyqtSignal(QtCore.QVariant)
    listCleared = QtCore.pyqtSignal()

    fileColNum = 0
    CRFlagColNum = 1
    CBLFlagColNum = 2
    typeColNum = 3
    readonlyColNum = 4
    folderColNum = 5
    dataColNum = fileColNum

    def __init__(
        self, parent: QtWidgets.QWidget, config: ct_ns, dirty_flag_verification: Callable[[str, str], bool]
    ) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "fileselectionlist.ui", self)

        self.config = config

        reduce_widget_font_size(self.twList)

        self.twList.setColumnCount(6)
        self.twList.currentItemChanged.connect(self.current_item_changed_cb)

        self.currentItem = None
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        self.dirty_flag = False

        select_all_action = QtWidgets.QAction("Select All", self)
        remove_action = QtWidgets.QAction("Remove Selected Items", self)
        self.separator = QtWidgets.QAction("", self)
        self.separator.setSeparator(True)

        select_all_action.setShortcut("Ctrl+A")
        remove_action.setShortcut("Ctrl+X")

        select_all_action.triggered.connect(self.select_all)
        remove_action.triggered.connect(self.remove_selection)

        self.addAction(select_all_action)
        self.addAction(remove_action)
        self.addAction(self.separator)

        self.dirty_flag_verification = dirty_flag_verification
        self.rar_ro_shown = False

    def get_sorting(self) -> tuple[int, int]:
        col = self.twList.horizontalHeader().sortIndicatorSection()
        order = self.twList.horizontalHeader().sortIndicatorOrder()
        return int(col), int(order)

    def set_sorting(self, col: int, order: QtCore.Qt.SortOrder) -> None:
        self.twList.horizontalHeader().setSortIndicator(col, order)

    def add_app_action(self, action: QtWidgets.QAction) -> None:
        self.insertAction(QtWidgets.QAction(), action)

    def set_modified_flag(self, modified: bool) -> None:
        self.dirty_flag = modified

    def select_all(self) -> None:
        self.twList.setRangeSelected(QtWidgets.QTableWidgetSelectionRange(0, 0, self.twList.rowCount() - 1, 5), True)

    def deselect_all(self) -> None:
        self.twList.setRangeSelected(QtWidgets.QTableWidgetSelectionRange(0, 0, self.twList.rowCount() - 1, 5), False)

    def remove_archive_list(self, ca_list: list[ComicArchive]) -> None:
        self.twList.setSortingEnabled(False)
        current_removed = False
        for ca in ca_list:
            for row in range(self.twList.rowCount()):
                row_ca = self.get_archive_by_row(row)
                if row_ca == ca:
                    if row == self.twList.currentRow():
                        current_removed = True
                    self.twList.removeRow(row)
                    break
        self.twList.setSortingEnabled(True)

        if self.twList.rowCount() > 0 and current_removed:
            # since on a removal, we select row 0, make sure callback occurs if
            # we're already there
            if self.twList.currentRow() == 0:
                self.current_item_changed_cb(self.twList.currentItem(), None)
            self.twList.selectRow(0)
        elif self.twList.rowCount() <= 0:
            self.listCleared.emit()

    def get_archive_by_row(self, row: int) -> ComicArchive | None:
        if row >= 0:
            fi: FileInfo = self.twList.item(row, FileSelectionList.dataColNum).data(QtCore.Qt.ItemDataRole.UserRole)
            return fi.ca
        return None

    def get_current_archive(self) -> ComicArchive | None:
        return self.get_archive_by_row(self.twList.currentRow())

    def remove_selection(self) -> None:
        row_list = []
        for item in self.twList.selectedItems():
            if item.column() == 0:
                row_list.append(item.row())

        if len(row_list) == 0:
            return

        if self.twList.currentRow() in row_list:
            if not self.dirty_flag_verification(
                "Remove Archive", "If you close this archive, data in the form will be lost.  Are you sure?"
            ):
                return

        row_list.sort()
        row_list.reverse()

        self.twList.currentItemChanged.disconnect(self.current_item_changed_cb)
        self.twList.setSortingEnabled(False)

        for i in row_list:
            self.twList.removeRow(i)

        self.twList.setSortingEnabled(True)
        self.twList.currentItemChanged.connect(self.current_item_changed_cb)

        if self.twList.rowCount() > 0:
            # since on a removal, we select row 0, make sure callback occurs if
            # we're already there
            if self.twList.currentRow() == 0:
                self.current_item_changed_cb(self.twList.currentItem(), None)
            self.twList.selectRow(0)
        else:
            self.listCleared.emit()

    def add_path_list(self, pathlist: list[str]) -> None:
        filelist = utils.get_recursive_filelist(pathlist)
        # we now have a list of files to add

        # Prog dialog on Linux flakes out for small range, so scale up
        progdialog = QtWidgets.QProgressDialog("", "Cancel", 0, len(filelist), parent=self)
        progdialog.setWindowTitle("Adding Files")
        progdialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        progdialog.setMinimumDuration(300)
        center_window_on_parent(progdialog)

        QtCore.QCoreApplication.processEvents()
        first_added = None
        rar_added_ro = False
        self.twList.setSortingEnabled(False)
        for idx, f in enumerate(filelist):
            QtCore.QCoreApplication.processEvents()
            if progdialog.wasCanceled():
                break
            progdialog.setValue(idx + 1)
            progdialog.setLabelText(f)
            center_window_on_parent(progdialog)
            QtCore.QCoreApplication.processEvents()
            row = self.add_path_item(f)
            if row is not None:
                ca = self.get_archive_by_row(row)
                rar_added_ro = bool(ca and ca.archiver.name() == "RAR" and not ca.archiver.is_writable())
                if first_added is None:
                    first_added = row

        progdialog.hide()
        QtCore.QCoreApplication.processEvents()

        if first_added is not None:
            self.twList.selectRow(first_added)
        else:
            if len(pathlist) == 1 and os.path.isfile(pathlist[0]):
                QtWidgets.QMessageBox.information(
                    self, "File Open", "Selected file doesn't seem to be a comic archive."
                )
            else:
                QtWidgets.QMessageBox.information(self, "File/Folder Open", "No readable comic archives were found.")

        if rar_added_ro:
            self.rar_ro_message()

        self.twList.setSortingEnabled(True)

        # Adjust column size
        self.twList.resizeColumnsToContents()
        self.twList.setColumnWidth(FileSelectionList.CRFlagColNum, 35)
        self.twList.setColumnWidth(FileSelectionList.CBLFlagColNum, 35)
        self.twList.setColumnWidth(FileSelectionList.readonlyColNum, 35)
        self.twList.setColumnWidth(FileSelectionList.typeColNum, 45)
        if self.twList.columnWidth(FileSelectionList.fileColNum) > 250:
            self.twList.setColumnWidth(FileSelectionList.fileColNum, 250)
        if self.twList.columnWidth(FileSelectionList.folderColNum) > 200:
            self.twList.setColumnWidth(FileSelectionList.folderColNum, 200)

    def rar_ro_message(self) -> None:
        if not self.rar_ro_shown:
            if platform.system() == "Windows":
                rar_help = windowsRarHelp

            elif platform.system() == "Darwin":
                rar_help = macRarHelp

            else:
                rar_help = linuxRarHelp

            OptionalMessageDialog.msg_no_checkbox(
                self,
                "RAR Files are Read-Only",
                "It looks like you have opened a RAR/CBR archive,\n"
                "however ComicTagger cannot currently write to them without the rar program and are marked read only!\n\n"
                f"{rar_help}",
            )
            self.rar_ro_shown = True

    def is_list_dupe(self, path: str) -> bool:
        return self.get_current_list_row(path) >= 0

    def get_current_list_row(self, path: str) -> int:
        for r in range(self.twList.rowCount()):
            ca = cast(ComicArchive, self.get_archive_by_row(r))
            if str(ca.path) == path:
                return r

        return -1

    def add_path_item(self, path: str) -> int:
        path = str(path)
        path = os.path.abspath(path)

        if self.is_list_dupe(path):
            return self.get_current_list_row(path)

        ca = ComicArchive(path, str(graphics_path / "nocover.png"))

        if ca.seems_to_be_a_comic_archive():
            row: int = self.twList.rowCount()
            self.twList.insertRow(row)

            fi = FileInfo(ca)

            filename_item = QtWidgets.QTableWidgetItem()
            folder_item = QtWidgets.QTableWidgetItem()
            cix_item = FileTableWidgetItem()
            cbi_item = FileTableWidgetItem()
            readonly_item = FileTableWidgetItem()
            type_item = QtWidgets.QTableWidgetItem()

            filename_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            filename_item.setData(QtCore.Qt.ItemDataRole.UserRole, fi)
            self.twList.setItem(row, FileSelectionList.fileColNum, filename_item)

            folder_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, FileSelectionList.folderColNum, folder_item)

            type_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, FileSelectionList.typeColNum, type_item)

            cix_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            cix_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
            self.twList.setItem(row, FileSelectionList.CRFlagColNum, cix_item)

            cbi_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            cbi_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
            self.twList.setItem(row, FileSelectionList.CBLFlagColNum, cbi_item)

            readonly_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            readonly_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
            self.twList.setItem(row, FileSelectionList.readonlyColNum, readonly_item)

            self.update_row(row)

            return row
        return -1

    def update_row(self, row: int) -> None:
        if row >= 0:
            fi: FileInfo = self.twList.item(row, FileSelectionList.dataColNum).data(QtCore.Qt.ItemDataRole.UserRole)

            filename_item = self.twList.item(row, FileSelectionList.fileColNum)
            folder_item = self.twList.item(row, FileSelectionList.folderColNum)
            cix_item = self.twList.item(row, FileSelectionList.CRFlagColNum)
            cbi_item = self.twList.item(row, FileSelectionList.CBLFlagColNum)
            type_item = self.twList.item(row, FileSelectionList.typeColNum)
            readonly_item = self.twList.item(row, FileSelectionList.readonlyColNum)

            item_text = os.path.split(fi.ca.path)[0]
            folder_item.setText(item_text)
            folder_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            item_text = os.path.split(fi.ca.path)[1]
            filename_item.setText(item_text)
            filename_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            item_text = fi.ca.archiver.name()
            type_item.setText(item_text)
            type_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            if fi.ca.has_cix():
                cix_item.setCheckState(QtCore.Qt.CheckState.Checked)
                cix_item.setData(QtCore.Qt.ItemDataRole.UserRole, True)
            else:
                cix_item.setData(QtCore.Qt.ItemDataRole.UserRole, False)
                cix_item.setCheckState(QtCore.Qt.CheckState.Unchecked)

            if fi.ca.has_cbi():
                cbi_item.setCheckState(QtCore.Qt.CheckState.Checked)
                cbi_item.setData(QtCore.Qt.ItemDataRole.UserRole, True)
            else:
                cbi_item.setData(QtCore.Qt.ItemDataRole.UserRole, False)
                cbi_item.setCheckState(QtCore.Qt.CheckState.Unchecked)

            if not fi.ca.is_writable():
                readonly_item.setCheckState(QtCore.Qt.CheckState.Checked)
                readonly_item.setData(QtCore.Qt.ItemDataRole.UserRole, True)
            else:
                readonly_item.setData(QtCore.Qt.ItemDataRole.UserRole, False)
                readonly_item.setCheckState(QtCore.Qt.CheckState.Unchecked)

            # Reading these will force them into the ComicArchive's cache
            try:
                fi.ca.read_cix()
            except Exception:
                pass
            fi.ca.has_cbi()

    def get_selected_archive_list(self) -> list[ComicArchive]:
        ca_list: list[ComicArchive] = []
        for r in range(self.twList.rowCount()):
            item = self.twList.item(r, FileSelectionList.dataColNum)
            if item.isSelected():
                fi: FileInfo = item.data(QtCore.Qt.ItemDataRole.UserRole)
                ca_list.append(fi.ca)

        return ca_list

    def update_current_row(self) -> None:
        self.update_row(self.twList.currentRow())

    def update_selected_rows(self) -> None:
        self.twList.setSortingEnabled(False)
        for r in range(self.twList.rowCount()):
            item = self.twList.item(r, FileSelectionList.dataColNum)
            if item.isSelected():
                self.update_row(r)
        self.twList.setSortingEnabled(True)

    def current_item_changed_cb(self, curr: QtCore.QModelIndex | None, prev: QtCore.QModelIndex | None) -> None:
        if curr is not None:
            new_idx = curr.row()
            old_idx = -1
            if prev is not None:
                old_idx = prev.row()

            if old_idx == new_idx:
                return

            # don't allow change if modified
            if prev is not None and new_idx != old_idx:
                if not self.dirty_flag_verification(
                    "Change Archive", "If you change archives now, data in the form will be lost.  Are you sure?"
                ):
                    self.twList.currentItemChanged.disconnect(self.current_item_changed_cb)
                    self.twList.setCurrentItem(prev)
                    self.twList.currentItemChanged.connect(self.current_item_changed_cb)
                    # Need to defer this revert selection, for some reason
                    QtCore.QTimer.singleShot(1, self.revert_selection)
                    return

            fi = self.twList.item(new_idx, FileSelectionList.dataColNum).data(QtCore.Qt.ItemDataRole.UserRole)
            self.selectionChanged.emit(QtCore.QVariant(fi))

    def revert_selection(self) -> None:
        self.twList.selectRow(self.twList.currentRow())
