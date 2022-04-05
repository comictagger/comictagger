"""A PyQt5 widget for editing the page list info"""

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
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comicapi.comicarchive import ComicArchive, MetaDataStyle
from comicapi.genericmetadata import PageType
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.settings import ComicTaggerSettings

logger = logging.getLogger(__name__)


def item_move_events(widget):
    class Filter(QtCore.QObject):

        mysignal = QtCore.pyqtSignal(str)

        def eventFilter(self, obj, event):

            if obj == widget:
                # print(event.type())
                if event.type() == QtCore.QEvent.Type.ChildRemoved:
                    # print("ChildRemoved")
                    self.mysignal.emit("finish")
                if event.type() == QtCore.QEvent.Type.ChildAdded:
                    # print("ChildAdded")
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

    def __init__(self, parent):
        super().__init__(parent)

        uic.loadUi(ComicTaggerSettings.get_ui_file("pagelisteditor.ui"), self)

        self.pageWidget = CoverImageWidget(self.pageContainer, CoverImageWidget.ArchiveMode)
        gridlayout = QtWidgets.QGridLayout(self.pageContainer)
        gridlayout.addWidget(self.pageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)
        self.pageWidget.showControls = False

        self.reset_page()

        # Add the entries to the manga combobox
        self.comboBox.addItem("", "")
        self.comboBox.addItem(self.pageTypeNames[PageType.FrontCover], PageType.FrontCover)
        self.comboBox.addItem(self.pageTypeNames[PageType.InnerCover], PageType.InnerCover)
        self.comboBox.addItem(self.pageTypeNames[PageType.Advertisement], PageType.Advertisement)
        self.comboBox.addItem(self.pageTypeNames[PageType.Roundup], PageType.Roundup)
        self.comboBox.addItem(self.pageTypeNames[PageType.Story], PageType.Story)
        self.comboBox.addItem(self.pageTypeNames[PageType.Editorial], PageType.Editorial)
        self.comboBox.addItem(self.pageTypeNames[PageType.Letters], PageType.Letters)
        self.comboBox.addItem(self.pageTypeNames[PageType.Preview], PageType.Preview)
        self.comboBox.addItem(self.pageTypeNames[PageType.BackCover], PageType.BackCover)
        self.comboBox.addItem(self.pageTypeNames[PageType.Other], PageType.Other)
        self.comboBox.addItem(self.pageTypeNames[PageType.Deleted], PageType.Deleted)

        self.listWidget.itemSelectionChanged.connect(self.change_page)
        item_move_events(self.listWidget).connect(self.item_move_event)
        self.comboBox.activated.connect(self.change_page_type)
        self.chkDoublePage.toggled.connect(self.toggle_double_page)
        self.leBookmark.editingFinished.connect(self.save_bookmark)
        self.btnUp.clicked.connect(self.move_current_up)
        self.btnDown.clicked.connect(self.move_current_down)
        self.pre_move_row = -1
        self.first_front_page = None

        self.comic_archive: Optional[ComicArchive] = None
        self.pages_list = []

    def reset_page(self):
        self.pageWidget.clear()
        self.comboBox.setDisabled(True)
        self.chkDoublePage.setDisabled(True)
        self.leBookmark.setDisabled(True)
        self.comic_archive = None
        self.pages_list = []

    def get_new_indexes(self, movement):
        selection = self.listWidget.selectionModel().selectedRows()
        selection.sort(reverse=movement > 0)
        newindexes = []
        oldindexes = []
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

    def set_selection(self, indexes):
        selection_ranges = []
        first = 0
        for i, selection in enumerate(indexes):
            if i == 0:
                first = selection[0]
                continue

            if selection != indexes[i - 1][0] + 1:
                selection_ranges.append((first, indexes[i - 1][0]))
                first = selection[0]

        selection_ranges.append((first, indexes[-1][0]))
        selection = QtCore.QItemSelection()
        for x in selection_ranges:
            selection.merge(
                QtCore.QItemSelection(self.listWidget.model().index(x[0], 0), self.listWidget.model().index(x[1], 0)),
                QtCore.QItemSelectionModel.SelectionFlag.Select,
            )

        self.listWidget.selectionModel().select(selection, QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect)
        return selection_ranges

    def move_current_up(self):
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

    def move_current_down(self):
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

    def item_move_event(self, s):
        if s == "start":
            self.pre_move_row = self.listWidget.currentRow()
        if s == "finish":
            if self.pre_move_row != self.listWidget.currentRow():
                self.listOrderChanged.emit()
                self.emit_front_cover_change()
                self.modified.emit()

    def change_page_type(self, i):
        new_type = self.comboBox.itemData(i)
        if self.get_current_page_type() != new_type:
            self.set_current_page_type(new_type)
            self.emit_front_cover_change()
            self.modified.emit()

    def change_page(self):
        row = self.listWidget.currentRow()
        pagetype = self.get_current_page_type()

        i = self.comboBox.findData(pagetype)
        self.comboBox.setCurrentIndex(i)

        self.chkDoublePage.setChecked("DoublePage" in self.listWidget.item(row).data(QtCore.Qt.UserRole)[0])

        if "Bookmark" in self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]:
            self.leBookmark.setText(self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]["Bookmark"])
        else:
            self.leBookmark.setText("")

        idx = int(self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)[0]["Image"])

        if self.comic_archive is not None:
            self.pageWidget.set_archive(self.comic_archive, idx)

    def get_first_front_cover(self):
        front_cover = 0
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_dict = item.data(QtCore.Qt.ItemDataRole.UserRole)[0]  # .toPyObject()[0]
            if "Type" in page_dict and page_dict["Type"] == PageType.FrontCover:
                front_cover = int(page_dict["Image"])
                break
        return front_cover

    def get_current_page_type(self):
        row = self.listWidget.currentRow()
        page_dict = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)[0]  # .toPyObject()[0]
        if "Type" in page_dict:
            return page_dict["Type"]

        return ""

    def set_current_page_type(self, t):
        row = self.listWidget.currentRow()
        page_dict = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)[0]  # .toPyObject()[0]

        if t == "":
            if "Type" in page_dict:
                del page_dict["Type"]
        else:
            page_dict["Type"] = str(t)

        item = self.listWidget.item(row)
        # wrap the dict in a tuple to keep from being converted to QtWidgets.QStrings
        item.setData(QtCore.Qt.ItemDataRole.UserRole, (page_dict,))
        item.setText(self.list_entry_text(page_dict))

    def toggle_double_page(self):
        row = self.listWidget.currentRow()
        page_dict = self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]

        if self.sender().isChecked():
            page_dict["DoublePage"] = str("true")
        elif "DoublePage" in page_dict:
            del page_dict["DoublePage"]
        self.modified.emit()

        item = self.listWidget.item(row)
        # wrap the dict in a tuple to keep from being converted to QStrings
        item.setData(QtCore.Qt.UserRole, (page_dict,))
        item.setText(self.list_entry_text(page_dict))

        self.listWidget.setFocus()

    def save_bookmark(self):
        row = self.listWidget.currentRow()
        page_dict = self.listWidget.item(row).data(QtCore.Qt.UserRole)[0]

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

    def set_data(self, comic_archive: ComicArchive, pages_list: list):
        self.comic_archive = comic_archive
        self.pages_list = pages_list
        if pages_list is not None and len(pages_list) > 0:
            self.comboBox.setDisabled(False)
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

    def list_entry_text(self, page_dict):
        text = str(int(page_dict["Image"]) + 1)
        if "Type" in page_dict:
            if page_dict["Type"] in self.pageTypeNames.keys():
                text += " (" + self.pageTypeNames[page_dict["Type"]] + ")"
            else:
                text += " (Error: " + page_dict["Type"] + ")"
        if "DoublePage" in page_dict:
            text += " " + "\U00002461"
        if "Bookmark" in page_dict:
            text += " " + "\U0001F516"
        return text

    def get_page_list(self):
        page_list = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_list.append(item.data(QtCore.Qt.ItemDataRole.UserRole)[0])  # .toPyObject()[0]
        return page_list

    def emit_front_cover_change(self):
        if self.first_front_page != self.get_first_front_cover():
            self.first_front_page = self.get_first_front_cover()
            self.firstFrontCoverChanged.emit(self.first_front_page)

    def set_metadata_style(self, data_style):
        # depending on the current data style, certain fields are disabled

        inactive_color = QtGui.QColor(255, 170, 150)
        active_palette = self.comboBox.palette()

        inactive_palette3 = self.comboBox.palette()
        inactive_palette3.setColor(QtGui.QPalette.ColorRole.Base, inactive_color)

        if data_style == MetaDataStyle.CIX:
            self.btnUp.setEnabled(True)
            self.btnDown.setEnabled(True)
            self.comboBox.setEnabled(True)
            self.chkDoublePage.setEnabled(True)
            self.leBookmark.setEnabled(True)
            self.listWidget.setEnabled(True)

            self.leBookmark.setPalette(active_palette)
            self.listWidget.setPalette(active_palette)

        elif data_style == MetaDataStyle.CBI:
            self.btnUp.setEnabled(False)
            self.btnDown.setEnabled(False)
            self.comboBox.setEnabled(False)
            self.chkDoublePage.setEnabled(False)
            self.leBookmark.setEnabled(False)
            self.listWidget.setEnabled(False)

            self.leBookmark.setPalette(inactive_palette3)
            self.listWidget.setPalette(inactive_palette3)

        elif data_style == MetaDataStyle.COMET:
            pass

        # make sure combo is disabled when no list
        if self.comic_archive is None:
            self.comboBox.setEnabled(False)
            self.chkDoublePage.setEnabled(False)
            self.leBookmark.setEnabled(False)
