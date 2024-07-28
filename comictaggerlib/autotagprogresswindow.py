"""A PyQT4 dialog to show ID log and progress"""

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

from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.ui import ui_path
from comictalker.comictalker import ComicTalker

logger = logging.getLogger(__name__)


class AutoTagProgressWindow(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, talker: ComicTalker) -> None:
        super().__init__(parent)

        with (ui_path / "autotagprogresswindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.lblSourceName.setText(talker.attribution)

        self.archiveCoverWidget = CoverImageWidget(self.archiveCoverContainer, CoverImageWidget.DataMode, None, False)
        gridlayout = QtWidgets.QGridLayout(self.archiveCoverContainer)
        gridlayout.addWidget(self.archiveCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.testCoverWidget = CoverImageWidget(self.testCoverContainer, CoverImageWidget.DataMode, None, False)
        gridlayout = QtWidgets.QGridLayout(self.testCoverContainer)
        gridlayout.addWidget(self.testCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.isdone = False

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

    def set_archive_image(self, img_data: bytes) -> None:
        self.set_cover_image(img_data, self.archiveCoverWidget)

    def set_test_image(self, img_data: bytes) -> None:
        self.set_cover_image(img_data, self.testCoverWidget)

    def set_cover_image(self, img_data: bytes, widget: CoverImageWidget) -> None:
        widget.set_image_data(img_data)
        QtCore.QCoreApplication.processEvents()
        QtCore.QCoreApplication.processEvents()

    def reject(self) -> None:
        QtWidgets.QDialog.reject(self)
        self.isdone = True
