"""A PyQt6 dialog to show a message and let the user check a box"""

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
from enum import Enum

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from comictaggerlib.ui import ui_path

logger = logging.getLogger(__name__)

StyleMessage = 0
StyleQuestion = 1


class OptionalMessageDialog(QtWidgets.QDialog):
    check_status = QtCore.pyqtSignal(bool)
    _dialog_queue: list[QtWidgets.QWidget] = []

    class Icon(Enum):
        Information = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation
        Warning = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning
        Critical = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxCritical
        Question = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxQuestion

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        style: int,
        title: str,
        msg: str,
        *,
        icon: Icon | None = None,
        checked: bool = False,
        check_text: str | None = "",
        details: str | None = None,
    ) -> None:
        super().__init__(parent)
        with (ui_path / "optionalmsgdialog.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)
        self.detailsTextEdit: QtWidgets.QTextEdit
        self.iconLabel: QtWidgets.QLabel
        self.firstLabel: QtWidgets.QLabel
        self.secondLabel: QtWidgets.QLabel
        self.checkBox: QtWidgets.QCheckBox
        self.buttonBox: QtWidgets.QDialogButtonBox
        self._1labelWidget: QtWidgets.QWidget
        self._2buttonWidget: QtWidgets.QWidget
        self.detailsWidget: QtWidgets.QWidget

        self.setWindowTitle(title or "Something happened?")
        self.was_accepted = False

        self.iconLabel.hide()
        if icon is not None:
            self.iconLabel.setPixmap(self.get_icon(icon))
            self.iconLabel.show()

        if title:
            self.firstLabel.setText(title)
        if msg:
            self.secondLabel.setText(msg)

        if check_text is not None:
            if style == StyleQuestion:
                check_text = "Remember this answer"
            else:
                check_text = "Don't show this message again"

        self.checkBox.setText(check_text)

        self.checkBox.setChecked(checked)
        self.checkBox.setVisible(bool(check_text))
        self.checkBox.adjustSize()
        self.checkBox.setMinimumWidth(self.checkBox.width())

        btnbox_style: QtWidgets.QDialogButtonBox.StandardButtons | QtWidgets.QDialogButtonBox.StandardButton
        btnbox_style = QtWidgets.QDialogButtonBox.StandardButton.Ok
        self.defaultButton = QtWidgets.QDialogButtonBox.StandardButton.Ok
        if style == StyleQuestion:
            btnbox_style = QtWidgets.QDialogButtonBox.StandardButton.Yes | QtWidgets.QDialogButtonBox.StandardButton.No
            self.defaultButton = QtWidgets.QDialogButtonBox.StandardButton.No

        self.buttonBox.setStandardButtons(btnbox_style)
        if b := self.buttonBox.button(self.defaultButton):
            b.setDefault(True)
            b.setFocus()
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.detailsWidget.hide()
        self.details_button = None
        if details is not None:  # Specifically allow the empty string
            self.detailsTextEdit.setText(details)
            self.details_button = self.buttonBox.addButton("details", self.buttonBox.ButtonRole.ActionRole)
            assert self.details_button
            self.details_button.clicked.connect(self.details_button_clicked)
        self.buttonBox.adjustSize()
        self.buttonBox.setMinimumWidth(self.buttonBox.width())

        self.detailsTextEdit.adjustSize()
        self._1labelWidget.adjustSize()
        self._2buttonWidget.adjustSize()
        self.detailsWidget.adjustSize()
        self.firstLabel.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.secondLabel.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        # self.installEventFilter(self)
        self.label_height = None
        self.button_height = None
        self.details_height = None
        self.button_y_end = 0

        self.update_size()
        self.set_limits()
        self._layout()

        self.label_height = self._1labelWidget.size().height()
        self.button_height = self._2buttonWidget.size().height()
        self.details_height = self.detailsWidget.size().height()
        self.buttonBox.rejected.connect(self.reject)
        self.finished.connect(self._check_status)
        copy = QtGui.QAction(self)
        copy.triggered.connect(self.copy)
        copy.setShortcut(QtGui.QKeySequence.StandardKey.Copy)
        self.addAction(copy)
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    def copy(self) -> None:
        text = ""
        if self.detailsWidget.isVisible():
            text = self.detailsTextEdit.toPlainText()
        else:
            if not self.secondLabel.hasSelectedText():
                self.secondLabel.keyPressEvent(
                    QtGui.QKeyEvent(
                        QtGui.QKeyEvent.Type.KeyPress, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier
                    )
                )
                self.secondLabel.keyPressEvent(
                    QtGui.QKeyEvent(
                        QtGui.QKeyEvent.Type.KeyRelease, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier
                    )
                )
                text = self.secondLabel.selectedText().replace("\u2029", "\n")
                self.secondLabel.setSelection(0, 0)
            else:
                text = self.secondLabel.selectedText().replace("\u2029", "\n")
        if text:
            QtGui.QGuiApplication.clipboard().setText(text)

    def set_limits(self) -> None:
        limit_w = max(self.screen().availableGeometry().size().width() // 2, 420)
        # Set minimum heigth
        label_size = max(self._1labelWidget.width(), self._2buttonWidget.width()) + 12
        min_w = min(limit_w, label_size)  # Limit the window width to half the window
        self.firstLabel.adjustSize()
        if self._1labelWidget.size().width() > min_w:
            min_w = self._1labelWidget.size().width() + 12
        self.setMinimumWidth(min_w)

    def _check_status(self) -> None:
        self.check_status.emit(self.checkBox.isChecked())

    def _layout(self) -> None:
        margin = 6

        rect = self.rect()
        label_height = self.label_height
        button_height = self.button_height
        button_y_end = self.button_y_end
        if not label_height or not button_height:
            label_height = self._1labelWidget.rect().height()
            button_height = self._2buttonWidget.rect().height()
            self._1labelWidget.setGeometry(0 + margin, 0 + margin, rect.width() - (margin * 2), label_height)

            button_y = margin + label_height + margin
            button_y_end = button_y + button_height + margin

            if button_y_end < 150:  # Min window size is 150 because fuck Qt
                button_y_end = 150
                button_y = button_y_end - button_height - margin

            self.button_y_end = button_y_end
            self._2buttonWidget.setGeometry(0 + margin, button_y, rect.width() - (margin * 2), button_height)

        details_y = button_y_end
        self.details_height = rect.height() - details_y - margin
        self.detailsWidget.setGeometry(0 + margin, details_y, rect.width() - (margin * 2), self.details_height)

    def resizeEvent(self, a0: QtGui.QResizeEvent | None) -> None:
        self._layout()
        return super().resizeEvent(a0)

    def details_button_clicked(self, e: QtCore.QEvent) -> None:
        self.detailsWidget.setHidden(not self.detailsWidget.isHidden())
        self.update_size()

    def update_size(self) -> None:
        minHeight = self._1labelWidget.size().height()
        minHeight += self._2buttonWidget.size().height()
        if not self.detailsWidget.isHidden():
            self.detailsWidget.layout().activate()
            minHeight += self.detailsWidget.layout().totalMinimumSize().height()

        self.setMinimumHeight(max(150, minHeight + 12 + 6))  # Min size is 150 because fuck Qt
        if self.height() < minHeight or self.detailsWidget.isHidden():
            self.resize(self.size().width(), minHeight)
        if not self.isVisible():
            return

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(0, 0)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(0, 0)

    def get_icon(self, icon: Icon) -> QtGui.QPixmap:
        iconSize = self.style().pixelMetric(QtWidgets.QStyle.PixelMetric.PM_MessageBoxIconSize)

        return (
            self.style()
            .standardIcon(icon.value, None, self)
            .pixmap(QtCore.QSize(iconSize, iconSize), self.devicePixelRatio())
        )

    @classmethod
    def show_dialog(cls) -> None:
        if cls._dialog_queue:
            dialog = cls._dialog_queue.pop(0)
            dialog.finished.connect(cls.show_dialog)
            dialog.show()
            return
        QtCore.QTimer.singleShot(1000, cls.show_dialog)

    @staticmethod
    def msg(
        parent: QtWidgets.QWidget,
        title: str,
        msg: str,
        *,
        checked: bool = False,
        check_text: str | None = "",
        icon: Icon | None = None,
        show: bool = True,
    ) -> OptionalMessageDialog:
        d = OptionalMessageDialog(parent, StyleMessage, title, msg, checked=checked, check_text=check_text, icon=icon)
        d.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        WT = QtCore.Qt.WindowType
        d.setWindowFlags(WT.Window)

        if show:
            OptionalMessageDialog._dialog_queue.append(d)
        return d

    @staticmethod
    def question(
        parent: QtWidgets.QWidget,
        title: str,
        msg: str,
        *,
        checked: bool = False,
        check_text: str | None = "",
        icon: Icon | None = Icon.Question,
        show: bool = True,
    ) -> OptionalMessageDialog:
        d = OptionalMessageDialog(parent, StyleQuestion, title, msg, checked=checked, check_text=check_text, icon=icon)
        d.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        WT = QtCore.Qt.WindowType
        d.setWindowFlags(WT.Window)

        if show:
            OptionalMessageDialog._dialog_queue.append(d)
        return d

    @staticmethod
    def msg_no_checkbox(
        parent: QtWidgets.QWidget,
        title: str,
        msg: str,
        *,
        checked: bool = False,
        icon: Icon | None = None,
        show: bool = True,
    ) -> OptionalMessageDialog:
        d = OptionalMessageDialog(parent, StyleMessage, title, msg, checked=checked, check_text=None, icon=icon)
        d.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        WT = QtCore.Qt.WindowType
        d.setWindowFlags(WT.Window)

        if show:
            OptionalMessageDialog._dialog_queue.append(d)
        return d

    @staticmethod
    def critical(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        details: str | None = None,
        modal: bool = True,
        *,
        show: bool = True,
    ) -> OptionalMessageDialog:
        d = OptionalMessageDialog(
            parent,
            StyleMessage,
            title,
            text,
            details=details,
            icon=OptionalMessageDialog.Icon.Critical,
            check_text=None,
        )
        WT = QtCore.Qt.WindowType
        if modal:
            d.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            d.setWindowFlags(WT.Window | WT.Dialog | WT.X11BypassWindowManagerHint | WT.WindowStaysOnTopHint)
        else:
            d.setWindowFlags(WT.Window)

        if show:
            OptionalMessageDialog._dialog_queue.append(d)
        return d

    @staticmethod
    def warning(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        details: str | None = None,
        modal: bool = True,
        *,
        show: bool = True,
    ) -> OptionalMessageDialog:
        d = OptionalMessageDialog(
            parent, StyleMessage, title, text, details=details, icon=OptionalMessageDialog.Icon.Warning, check_text=None
        )
        WT = QtCore.Qt.WindowType
        if modal:
            d.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            d.setWindowFlags(WT.Window | WT.Dialog | WT.X11BypassWindowManagerHint | WT.WindowStaysOnTopHint)
        else:
            d.setWindowFlags(WT.Window)

        if show:
            OptionalMessageDialog._dialog_queue.append(d)
        return d

    @staticmethod
    def information(
        parent: QtWidgets.QWidget | None,
        title: str,
        text: str,
        details: str | None = None,
        modal: bool = False,
        *,
        show: bool = True,
    ) -> OptionalMessageDialog:
        d = OptionalMessageDialog(
            parent,
            StyleMessage,
            title,
            text,
            details=details,
            icon=OptionalMessageDialog.Icon.Information,
            check_text=None,
        )
        WT = QtCore.Qt.WindowType
        if modal:
            d.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            d.setWindowFlags(WT.Window | WT.Dialog | WT.X11BypassWindowManagerHint | WT.WindowStaysOnTopHint)
        else:
            d.setWindowFlags(WT.Window)

        if show:
            OptionalMessageDialog._dialog_queue.append(d)
        return d
