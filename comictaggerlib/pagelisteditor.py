"""A PyQt5 widget for editing the page list info"""

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

from PyQt5 import QtCore, QtWidgets, uic

from comicapi.comicarchive import ComicArchive, metadata_styles
from comicapi.genericmetadata import ImageMetadata, PageType
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import enable_widget

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

        with (ui_path / "pagelisteditor.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.md_attributes = {
            "pages.image_index": [self.btnDown, self.btnUp],
            "pages.type": self.cbPageType,
            "pages.double_page": self.chkDoublePage,
            "pages.bookmark": self.leBookmark,
            "pages": self,
        }

        self.pageWidget = CoverImageWidget(self.pageContainer, CoverImageWidget.ArchiveMode, None, None)
        gridlayout = QtWidgets.QGridLayout(self.pageContainer)
        gridlayout.addWidget(self.pageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)
        self.pageWidget.showControls = False

        self.blur = False
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
        self.cbxBlur.clicked.connect(self._toggle_blur)
        self.leBookmark.editingFinished.connect(self.save_bookmark)
        self.btnUp.clicked.connect(self.move_current_up)
        self.btnDown.clicked.connect(self.move_current_down)
        self.btnIdentifyScannerPage.clicked.connect(self.identify_scanner_page)
        self.pre_move_row = -1
        self.first_front_page: int | None = None

        self.comic_archive: ComicArchive | None = None
        self.pages_list: list[ImageMetadata] = []
        self.data_styles: list[str] = []

    def set_blur(self, blur: bool) -> None:
        self.pageWidget.blur = self.blur = blur
        self.cbxBlur.setChecked(blur)
        self.pageWidget.update_content()

    def _toggle_blur(self) -> None:
        self.pageWidget.blur = self.blur = not self.blur
        self.cbxBlur.setChecked(self.blur)
        self.pageWidget.update_content()

    def reset_page(self) -> None:
        self.pageWidget.clear()
        self.cbPageType.setEnabled(False)
        self.chkDoublePage.setEnabled(False)
        self.leBookmark.setEnabled(False)
        self.listWidget.clear()
        self.comic_archive = None
        self.pages_list = []
        self.cbxBlur.setChecked(self.blur)

    def add_page_type_item(self, text: str, user_data: str, shortcut: str, show_shortcut: bool = True) -> None:
        if show_shortcut:
            text = text + " (" + shortcut + ")"
        self.cbPageType.addItem(text, user_data)
        action_item = QtWidgets.QAction(shortcut, self)
        action_item.triggered.connect(lambda: self.select_page_type_item(self.cbPageType.findData(user_data)))
        action_item.setShortcut(shortcut)
        self.addAction(action_item)

    def identify_scanner_page(self) -> None:
        if self.comic_archive is None:
            return
        row = self.comic_archive.get_scanner_page_index()
        if row is None:
            return
        page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)

        page_dict["type"] = PageType.Deleted

        item = self.listWidget.item(row)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, page_dict)
        item.setText(self.list_entry_text(page_dict))
        self.change_page()

    def select_page_type_item(self, idx: int) -> None:
        if self.cbPageType.isEnabled() and self.listWidget.count() > 0:
            self.cbPageType.setCurrentIndex(idx)
            self.change_page_type(idx)

    def get_new_indexes(self, movement: int) -> list[tuple[int, int]]:
        selection = self.listWidget.selectionModel().selectedRows()
        selection.sort(reverse=movement > 0)
        new_indexes: list[int] = []
        old_indexes: list[int] = []
        for x in selection:
            current = x.row()
            old_indexes.append(current)
            if 0 <= current + movement <= self.listWidget.count() - 1:
                if len(new_indexes) < 1 or current + movement != new_indexes[-1]:
                    current += movement

            new_indexes.append(current)
        old_indexes.sort()
        new_indexes.sort()
        return list(zip(new_indexes, old_indexes))

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
        if self.listWidget.count() > 0 and self.get_current_page_type() != new_type:
            self.set_current_page_type(new_type)
            self.emit_front_cover_change()
            self.modified.emit()

    def change_page(self) -> None:
        row = self.listWidget.currentRow()
        pagetype = self.get_current_page_type()

        i = self.cbPageType.findData(pagetype)
        self.cbPageType.setCurrentIndex(i)

        self.chkDoublePage.setChecked("double_page" in self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole))

        if "bookmark" in self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole):
            self.leBookmark.setText(self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)["bookmark"])
        else:
            self.leBookmark.setText("")

        idx = int(self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)["image_index"])

        if self.comic_archive is not None:
            self.pageWidget.set_archive(self.comic_archive, idx)

    def get_first_front_cover(self) -> int:
        front_cover = 0
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_dict: ImageMetadata = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if "type" in page_dict and page_dict["type"] == PageType.FrontCover:
                front_cover = int(page_dict["image_index"])
                break
        return front_cover

    def get_current_page_type(self) -> str:
        row = self.listWidget.currentRow()
        page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)
        if "type" in page_dict:
            return page_dict["type"]

        return ""

    def set_current_page_type(self, t: str) -> None:
        rows = self.listWidget.selectionModel().selectedRows()
        for index in rows:
            row = index.row()
            page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)

            if t == "":
                if "type" in page_dict:
                    del page_dict["type"]
            else:
                page_dict["type"] = t

            item = self.listWidget.item(row)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, page_dict)
            item.setText(self.list_entry_text(page_dict))

    def toggle_double_page(self) -> None:
        rows = self.listWidget.selectionModel().selectedRows()
        for index in rows:
            row = index.row()
            page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)

            cbx = self.sender()

            if isinstance(cbx, QtWidgets.QCheckBox) and cbx.isChecked():
                if "double_page" not in page_dict:
                    page_dict["double_page"] = True
                    self.modified.emit()
            elif "double_page" in page_dict:
                del page_dict["double_page"]
                self.modified.emit()

            item = self.listWidget.item(row)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, page_dict)
            item.setText(self.list_entry_text(page_dict))

        self.listWidget.setFocus()

    def save_bookmark(self) -> None:
        row = self.listWidget.currentRow()
        page_dict: ImageMetadata = self.listWidget.item(row).data(QtCore.Qt.ItemDataRole.UserRole)

        current_bookmark = ""
        if "bookmark" in page_dict:
            current_bookmark = page_dict["bookmark"]

        if self.leBookmark.text().strip():
            new_bookmark = str(self.leBookmark.text().strip())
            if current_bookmark != new_bookmark:
                page_dict["bookmark"] = new_bookmark
                self.modified.emit()
        elif current_bookmark != "":
            del page_dict["bookmark"]
            self.modified.emit()

        item = self.listWidget.item(row)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, page_dict)
        item.setText(self.list_entry_text(page_dict))

        self.listWidget.setFocus()

    def set_data(self, comic_archive: ComicArchive, pages_list: list[ImageMetadata]) -> None:
        self.cbxBlur.setChecked(self.blur)
        self.comic_archive = comic_archive
        self.pages_list = pages_list
        if pages_list:
            self.set_metadata_style(self.data_styles)
        else:
            self.cbPageType.setEnabled(False)
            self.chkDoublePage.setEnabled(False)
            self.leBookmark.setEnabled(False)

        self.listWidget.itemSelectionChanged.disconnect(self.change_page)

        self.listWidget.clear()
        for p in pages_list:
            item = QtWidgets.QListWidgetItem(self.list_entry_text(p))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, p)

            self.listWidget.addItem(item)
        self.first_front_page = self.get_first_front_cover()
        self.listWidget.itemSelectionChanged.connect(self.change_page)
        self.listWidget.setCurrentRow(0)

    def list_entry_text(self, page_dict: ImageMetadata) -> str:
        text = str(int(page_dict["image_index"]) + 1)
        if "type" in page_dict:
            if page_dict["type"] in self.pageTypeNames:
                text += " (" + self.pageTypeNames[page_dict["type"]] + ")"
            else:
                text += " (Error: " + page_dict["type"] + ")"
        if "double_page" in page_dict:
            text += " ②"
        if "bookmark" in page_dict:
            text += " 🔖"
        return text

    def get_page_list(self) -> list[ImageMetadata]:
        page_list = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            page_list.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
        return page_list

    def emit_front_cover_change(self) -> None:
        if self.first_front_page != self.get_first_front_cover():
            self.first_front_page = self.get_first_front_cover()
            self.firstFrontCoverChanged.emit(self.first_front_page)

    def set_metadata_style(self, data_styles: list[str]) -> None:
        # depending on the current data style, certain fields are disabled
        if data_styles:
            styles = [metadata_styles[style] for style in data_styles]
            enabled_widgets = set()
            for style in styles:
                enabled_widgets.update(style.supported_attributes)

            self.data_styles = data_styles

            for metadata, widget in self.md_attributes.items():
                enable_widget(widget, metadata in enabled_widgets)
