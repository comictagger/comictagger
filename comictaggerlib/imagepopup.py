"""A PyQT4 widget to display a popup image"""
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

from PyQt5 import QtCore, QtGui, QtWidgets, sip, uic

from comictaggerlib.graphics import graphics_path
from comictaggerlib.ui import ui_path

logger = logging.getLogger(__name__)


class ImagePopup(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, image_pixmap: QtGui.QPixmap) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "imagepopup.ui", self)

        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))

        self.setWindowFlags(QtCore.Qt.WindowType.Popup)
        self.setWindowState(QtCore.Qt.WindowState.WindowFullScreen)

        self.imagePixmap = image_pixmap

        screen_size = QtGui.QGuiApplication.primaryScreen().geometry()
        QtWidgets.QApplication.primaryScreen()
        self.resize(screen_size.width(), screen_size.height())
        self.move(0, 0)

        # This is a total hack.  Uses a snapshot of the desktop, and overlays a
        # translucent screen over it.  Probably can do it better by setting opacity of a widget
        # TODO: macOS denies this
        screen = QtWidgets.QApplication.primaryScreen()
        self.desktopBg = screen.grabWindow(sip.voidptr(0), 0, 0, screen_size.width(), screen_size.height())
        bg = QtGui.QPixmap(str(graphics_path / "popup_bg.png"))
        self.clientBgPixmap = bg.scaled(
            screen_size.width(),
            screen_size.height(),
            QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.setMask(self.clientBgPixmap.mask())

        self.apply_image_pixmap()
        self.showFullScreen()
        self.raise_()
        QtWidgets.QApplication.restoreOverrideCursor()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, 0, self.desktopBg)
        painter.drawPixmap(0, 0, self.clientBgPixmap)
        painter.end()

    def apply_image_pixmap(self) -> None:
        win_h = self.height()
        win_w = self.width()

        if self.imagePixmap.width() > win_w or self.imagePixmap.height() > win_h:
            # scale the pixmap to fit in the frame
            display_pixmap = self.imagePixmap.scaled(
                win_w, win_h, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.SmoothTransformation
            )
            self.lblImage.setPixmap(display_pixmap)
        else:
            display_pixmap = self.imagePixmap
        self.lblImage.setPixmap(display_pixmap)

        # move and resize the label to be centered in the fame
        img_w = display_pixmap.width()
        img_h = display_pixmap.height()
        self.lblImage.resize(img_w, img_h)
        self.lblImage.move(int((win_w - img_w) / 2), int((win_h - img_h) / 2))

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        self.close()
