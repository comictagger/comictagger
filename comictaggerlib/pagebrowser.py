"""A PyQT4 dialog to show pages of a comic archive"""
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
import platform

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.graphics import graphics_path
from comictaggerlib.ui import ui_path
from comictalker.talkerbase import ComicTalker

logger = logging.getLogger(__name__)


class PageBrowserWindow(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, talker_api: ComicTalker, metadata: GenericMetadata) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "pagebrowser.ui", self)

        self.pageWidget = CoverImageWidget(self.pageContainer, talker_api, CoverImageWidget.ArchiveMode)
        gridlayout = QtWidgets.QGridLayout(self.pageContainer)
        gridlayout.addWidget(self.pageWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)
        self.pageWidget.showControls = False

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.comic_archive: ComicArchive | None = None
        self.page_count = 0
        self.current_page_num = 0
        self.metadata = metadata

        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Close).setDefault(True)
        if platform.system() == "Darwin":
            self.btnPrev.setText("<<")
            self.btnNext.setText(">>")
        else:
            self.btnPrev.setIcon(QtGui.QIcon(str(graphics_path / "left.png")))
            self.btnNext.setIcon(QtGui.QIcon(str(graphics_path / "right.png")))

        self.btnNext.clicked.connect(self.next_page)
        self.btnPrev.clicked.connect(self.prev_page)
        self.show()

        self.btnNext.setEnabled(False)
        self.btnPrev.setEnabled(False)

    def reset(self) -> None:
        self.comic_archive = None
        self.page_count = 0
        self.current_page_num = 0
        self.metadata = GenericMetadata()

        self.btnNext.setEnabled(False)
        self.btnPrev.setEnabled(False)
        self.pageWidget.clear()

    def set_comic_archive(self, ca: ComicArchive) -> None:

        self.comic_archive = ca
        self.page_count = ca.get_number_of_pages()
        self.current_page_num = 0
        self.pageWidget.set_archive(self.comic_archive)
        self.set_page()

        if self.page_count > 1:
            self.btnNext.setEnabled(True)
            self.btnPrev.setEnabled(True)

    def next_page(self) -> None:

        if self.current_page_num + 1 < self.page_count:
            self.current_page_num += 1
        else:
            self.current_page_num = 0
        self.set_page()

    def prev_page(self) -> None:

        if self.current_page_num - 1 >= 0:
            self.current_page_num -= 1
        else:
            self.current_page_num = self.page_count - 1
        self.set_page()

    def set_page(self) -> None:
        if not self.metadata.is_empty:
            archive_page_index = self.metadata.get_archive_page_index(self.current_page_num)
        else:
            archive_page_index = self.current_page_num

        self.pageWidget.set_page(archive_page_index)
        self.setWindowTitle(f"Page Browser - Page {self.current_page_num + 1} (of {self.page_count}) ")
