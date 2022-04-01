"""A PyQT4 dialog to show ID log and progress"""

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


from PyQt5 import QtCore, QtWidgets, uic

from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.settings import ComicTaggerSettings
from comictaggerlib.ui.qtutils import reduce_widget_font_size


class AutoTagProgressWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        uic.loadUi(ComicTaggerSettings.get_ui_file("autotagprogresswindow.ui"), self)

        self.archiveCoverWidget = CoverImageWidget(self.archiveCoverContainer, CoverImageWidget.DataMode, False)
        gridlayout = QtWidgets.QGridLayout(self.archiveCoverContainer)
        gridlayout.addWidget(self.archiveCoverWidget)
        gridlayout.setContentsMargins(0, 0, 0, 0)

        self.testCoverWidget = CoverImageWidget(self.testCoverContainer, CoverImageWidget.DataMode, False)
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

        reduce_widget_font_size(self.textEdit)

    def set_archive_image(self, img_data):
        self.set_cover_image(img_data, self.archiveCoverWidget)

    def set_test_image(self, img_data):
        self.set_cover_image(img_data, self.testCoverWidget)

    def set_cover_image(self, img_data, widget):
        widget.set_image_data(img_data)
        QtCore.QCoreApplication.processEvents()
        QtCore.QCoreApplication.processEvents()

    def reject(self):
        QtWidgets.QDialog.reject(self)
        self.isdone = True
