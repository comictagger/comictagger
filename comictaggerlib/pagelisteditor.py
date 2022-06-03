"""A PyQt5 widget for editing the page list info"""
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

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comicapi.comicarchive import ComicArchive, MetaDataStyle
from comicapi.genericmetadata import ImageMetadata, PageType
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.settings import ComicTaggerSettings

logger = logging.getLogger(__name__)


def item_move_events(widget: QtWidgets.QWidget) -> QtCore.pyqtBoundSignal:
    class Filter(QtCore.QObject):

        mysignal = QtCore.pyqtSignal(str)

        def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:

            if obj == widget:
                if event.type() == QtCore.QEvent.Type.ChildRemoved:
                    self.mysignal.emit("finish")
                if event.type() == QtCore.QEvent.Type.ChildAdded:
                    self.mysignal.emit("start")
                    return True

            return False

    filt = Filter(widget)
    widget.installEventFilter(filt)
    return filt.mysignal


class PageListEditor(QtWidgets.QWidget):
    firstFrontCoverChanged = QtCore.pyqtSignal(int)
    listOrderChanged = QtCore.pyqtSignal()
    modified = QtCore.pyqtSignal()

    pageTypeNames = {
        PageType.FrontCover: "Front Cover",
        PageType.InnerCover: "Inner Cover",
        PageType.Advertisement: "Advertisement",
        PageType.Roundup: "Roundup",
        PageType.Story: "Story",
        PageType.Editorial: "Editorial",
        PageType.Letters: "Letters",
        PageType.Preview: "Preview",
        PageType.BackCover: "Back Cover",
        PageType.Other: "Other",
        PageType.Deleted: "Deleted",
    }

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        uic.loadUi(ComicTaggerSettings.get_ui_file("pagelisteditor.ui"), self)

        self.pageWidget = CoverImageWidget(self.pageContainer, CoverImageWidget.ArchiveMode)
        gridlayout = QtWidgets.QGridLayout(self.pageContainer)
        gridlayout.addWidget(self.pageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)
        self.pageWidget.showControls = False

        self.reset_page()

        # Add the entries to the page type combobox
        self.add_page_type_item("", "", "Alt+0", False)
        self.add_page_type_item(self.pageTypeNames[PageType.FrontCover], PageType.FrontCover, "Alt+F")
        self.add_page_type_item(self.pageTypeNames[PageType.InnerCover], PageType.InnerCover, "Alt+I")
        self.add_page_type_item(self.pageTypeNames[PageType.Advertisement], PageType.Advertisement, "Alt+A")
        self.add_page_type_item(self.pageTypeNames[PageType.Roundup], PageType.Roundup, "Alt+R")
        self.add_page_type_item(self.pageTypeNames[PageType.Story], PageType.Story, "Alt+S")
        self.add_page_type_item(self.pageTypeNames[PageType.Editorial], PageType.Editorial, "Alt+E")
        self.add_page_type_item(self.pageTypeNames[PageType.Letters], PageType.Letters, "Alt+L")
        self.add_page_type_item(self.pageTypeNames[PageType.Preview], PageType.Preview, "Alt+P")
        self.add_page_type_item(self.pageTypeNames[PageType.BackCover], PageType.BackCover, "Alt+B")
        self.add_page_type_item(self.pageTypeNames[PageType.Other], PageType.Other, "Alt+O")
        self.add_page_type_item(self.pageTypeNames[PageType.Deleted], PageType.Deleted, "Alt+X")

        self.listWidget.itemSelectionChanged.connect(self.change_page)
        item_move_events(self.listWidget).connect(self.item_move_event)
        self.cbPageType.activated.connect(self.change_page_type)
        self.chkDoublePage.clicked.connect(self.toggle_double_page)
        self.leBookmark.editingFinished.connect(self.save_bookmark)
        self.btnUp.clicked.connect(self.move_current_up)
        self.btnDown.clicked.connect(self.move_current_down)
        self.pre_move_row = -1
        self.first_front_page: int | None = None

        self.comic_archive: ComicArchive | None = None
        self.pages_list: list[ImageMetadata] = []

    def reset_page(self) -> None:
        self.pageWidget.clear()
        self.cbPageType.setDisabled(True)
        self.chkDoublePage.setDisabled(True)
        self.leBookmark.setDisabled(True)
        self.comic_archive = None
        self.pages_list = []

    def add_page_type_item(self, text: str, user_data: str, shortcut: str, show_shortcut: bool = True) -> None:
        if show_shortcut:
            text = text + " (" + shortcut + ")"
        self.cbPageType.addItem(text, user_data)
        actionItem = QtWidgets.QAction(shortcut, self)
        actionItem.triggered.connect(lambda: self.select_page_type_item(self.cbPageType.findData(user_data)))
        actionItem.setShortcut(shortcut)
        self.addAction(actionItem)

    def select_page_type_item(self, idx: int) -> None:
        if self.cbPageType.isEnabled():
            self.cbPageType.setCurrentIndex(idx)
            self.change_page_type(idx)

    def get_new_indexes(self, movement: int) -> list[tuple[int, int]]:
        selection = self.listWidget.selectionModel().selectedRows()
        selection.sort(reverse=movement > 0)
        newindexes: list[int] = []
        oldindexes: list[int] = []
        for x in selection:
            current = x.row()
            oldindexes.append(current)
            if 0 <= current + movement <= self.listWidget.count() - 1:
                if len(newindexes) < 1 or current + movement != newindexes[-1]:
                    current += movement

            newindexes.append(current)
        oldindexes.sort()
        newindexes.sort()
        return list(zip(newindexes, oldindexes))

    def set_selection(self, indexes: list[tuple[int, int]]) -> list[tuple[int, int]]:
        selection_ranges: list[tuple[int, int]] = []
        first = 0
        for i, sel in enumerate(indexes):
            if i == 0:
                first = sel[0]
                continue

            if sel[0] != indexes[i - 1][0] + 1:
                selection_ranges.append((first, indexes[i - 1][0]))
                first = sel[0]

        selection_ranges.append((first, indexes[-1][0]))
        selection = QtCore.QItemSelection()
        for x in selection_ranges:
            selection.merge(
                QtCore.QItemSelection(self.listWidget.model().index(x[0], 0), self.listWidget.model().index(x[1], 0)),
                QtCore.QItemSelectionModel.SelectionFlag.Select,
            )

        self.listWidget.selectionModel().select(selection, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
        return selection_ranges

    def move_current_up(self) -> None:
        row = self.listWidget.currentRow()
        selection = self.get_new_indexes(-1)
        for sel in selection:
            item = self.listWidget.takeItem(sel[1])
            self.listWidget.insertItem(sel[0], item)

        if row > 0:
            self.listWidget.setCurrentRow(row - 1)
        self.set_selection(selection)
        self.listOrderChanged.emit()
        self.emit_front_cover_change()
        self.modified.emit()

    def move_current_down(self) -> None:
        row = self.listWidget.currentRow()
        selection = self.get_new_indexes(1)
        selection.sort(reverse=True)
        for sel in selection:
            item = self.listWidget.takeItem(sel[1])
            self.listWidget.insertItem(sel[0], item)

        if row < self.listWidget.count() - 1:
            self.listWidget.setCurrentRow(row + 1)
        self.listOrderChanged.emit()
        self.emit_front_cover_change()
        self.set_selection(selection)
        self.modified.emit()

    def item_move_event(self, s: str) -> None:
        if s == "start":
            self.pre_move_row = self.listWidget.currentRow()
        if s == "finish":
            if self.pre_move_row != self.listWidget.currentRow():
                self.listOrderChanged.emit()
                self.emit_front_cover_change()
                self.modified.emit()

    def change_page_type(self, i: int) -> None:
        new_type = self.cbPageType.itemData(i)
        if self.get_current_page_type() != new_type:
            self.set_current_page_type(new_type)
            self.emit_front_cover_change()
            self.modified.emit()

    def change_page(self) -> None:
        row = self.listWidget.currentRow()
        pagetype = self.get_current_page_type()

        i = self.cbPageType.findData(pagetype)
        self.cbPageType.setCurrentIndex(i)

        self.chkDoublePage.setChecked("DoublePage" in self.listWidget.item(row).data(QtCore.Qt.UserRole)[0])

        if "Bookmark" in self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]:
            self.leBookmark.setText(self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]["Bookmark"])
        else:
            self.leBookmark.setText("")

        idx = int(self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)[0]["Image"])

        if self.comic_archive is not None:
            self.pageWidget.set_archive(self.comic_archive, idx)

    def get_first_front_cover(self) -> int:
        front_cover = 0
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_dict: ImageMetadata = item.data(QtCore.Qt.ItemDataRole.UserRole)[0]
            if "Type" in page_dict and page_dict["Type"] == PageType.FrontCover:
                front_cover = int(page_dict["Image"])
                break
        return front_cover

    def get_current_page_type(self) -> str:
        row = self.listWidget.currentRow()
        page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)[0]
        if "Type" in page_dict:
            return page_dict["Type"]

        return ""

    def set_current_page_type(self, t: str) -> None:
        row = self.listWidget.currentRow()
        page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)[0]

        if t == "":
            if "Type" in page_dict:
                del page_dict["Type"]
        else:
            page_dict["Type"] = t

        item = self.listWidget.item(row)
        # wrap the dict in a tuple to keep from being converted to QtWidgets.QStrings
        item.setData(QtCore.Qt.ItemDataRole.UserRole, (page_dict,))
        item.setText(self.list_entry_text(page_dict))

    def toggle_double_page(self) -> None:
        row = self.listWidget.currentRow()
        page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]

        cbx = self.sender()

        if isinstance(cbx, QtWidgets.QCheckBox) and cbx.isChecked():
            if "DoublePage" not in page_dict:
                page_dict["DoublePage"] = True
                self.modified.emit()
        elif "DoublePage" in page_dict:
            del page_dict["DoublePage"]
            self.modified.emit()

        item = self.listWidget.item(row)
        # wrap the dict in a tuple to keep from being converted to QStrings
        item.setData(QtCore.Qt.UserRole, (page_dict,))
        item.setText(self.list_entry_text(page_dict))

        self.listWidget.setFocus()

    def save_bookmark(self) -> None:
        row = self.listWidget.currentRow()
        page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]

        current_bookmark = ""
        if "Bookmark" in page_dict:
            current_bookmark = page_dict["Bookmark"]

        if self.leBookmark.text().strip():
            new_bookmark = str(self.leBookmark.text().strip())
            if current_bookmark != new_bookmark:
                page_dict["Bookmark"] = new_bookmark
                self.modified.emit()
        elif current_bookmark != "":
            del page_dict["Bookmark"]
            self.modified.emit()

        item = self.listWidget.item(row)
        # wrap the dict in a tuple to keep from being converted to QStrings
        item.setData(QtCore.Qt.UserRole, (page_dict,))
        item.setText(self.list_entry_text(page_dict))

        self.listWidget.setFocus()

    def set_data(self, comic_archive: ComicArchive, pages_list: list[ImageMetadata]) -> None:
        self.comic_archive = comic_archive
        self.pages_list = pages_list
        if pages_list is not None and len(pages_list) > 0:
            self.cbPageType.setDisabled(False)
            self.chkDoublePage.setDisabled(False)
            self.leBookmark.setDisabled(False)

        self.listWidget.itemSelectionChanged.disconnect(self.change_page)

        self.listWidget.clear()
        for p in pages_list:
            item = QtWidgets.QListWidgetItem(self.list_entry_text(p))
            # wrap the dict in a tuple to keep from being converted to QtWidgets.QStrings
            item.setData(QtCore.Qt.ItemDataRole.UserRole, (p,))

            self.listWidget.addItem(item)
        self.first_front_page = self.get_first_front_cover()
        self.listWidget.itemSelectionChanged.connect(self.change_page)
        self.listWidget.setCurrentRow(0)

    def list_entry_text(self, page_dict: ImageMetadata) -> str:
        text = str(int(page_dict["Image"]) + 1)
        if "Type" in page_dict:
            if page_dict["Type"] in self.pageTypeNames:
                text += " (" + self.pageTypeNames[page_dict["Type"]] + ")"
            else:
                text += " (Error: " + page_dict["Type"] + ")"
        if "DoublePage" in page_dict:
            text += " " + "\U00002461"
        if "Bookmark" in page_dict:
            text += " " + "\U0001F516"
        return text

    def get_page_list(self) -> list[ImageMetadata]:
        page_list = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_list.append(item.data(QtCore.Qt.ItemDataRole.UserRole)[0])
        return page_list

    def emit_front_cover_change(self) -> None:
        if self.first_front_page != self.get_first_front_cover():
            self.first_front_page = self.get_first_front_cover()
            self.firstFrontCoverChanged.emit(self.first_front_page)

    def set_metadata_style(self, data_style: int) -> None:
        # depending on the current data style, certain fields are disabled

        inactive_color = QtGui.QColor(255, 170, 150)
        active_palette = self.cbPageType.palette()

        inactive_palette3 = self.cbPageType.palette()
        inactive_palette3.setColor(QtGui.QPalette.ColorRole.Base, inactive_color)

        if data_style == MetaDataStyle.CIX:
            self.btnUp.setEnabled(True)
            self.btnDown.setEnabled(True)
            self.cbPageType.setEnabled(True)
            self.chkDoublePage.setEnabled(True)
            self.leBookmark.setEnabled(True)
            self.listWidget.setEnabled(True)

            self.leBookmark.setPalette(active_palette)
            self.listWidget.setPalette(active_palette)

        elif data_style == MetaDataStyle.CBI:
            self.btnUp.setEnabled(False)
            self.btnDown.setEnabled(False)
            self.cbPageType.setEnabled(False)
            self.chkDoublePage.setEnabled(False)
            self.leBookmark.setEnabled(False)
            self.listWidget.setEnabled(False)

            self.leBookmark.setPalette(inactive_palette3)
            self.listWidget.setPalette(inactive_palette3)

        elif data_style == MetaDataStyle.COMET:
            pass

        # make sure combo is disabled when no list
        if self.comic_archive is None:
            self.cbPageType.setEnabled(False)
            self.chkDoublePage.setEnabled(False)
            self.leBookmark.setEnabled(False)
