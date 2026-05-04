"""A PyQT4 dialog to edit credits"""

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
import operator

import natsort
from PyQt6 import QtCore, QtGui, QtWidgets, uic

from comicapi import utils
from comicapi.genericmetadata import Credit
from comicapi.tags import Tag
from comictaggerlib.optionalmsgdialog import OptionalMessageDialog
from comictaggerlib.ui import ui_path
from comictaggerlib.ui.qtutils import enable_widget

logger = logging.getLogger(__name__)


class CreditEditorWindow(QtWidgets.QDialog):
    creditChanged = QtCore.pyqtSignal(Credit, int)

    def __init__(
        self, parent: QtWidgets.QWidget, write_tags: list[Tag], row: int, credit: Credit, title: str = "New Credit"
    ) -> None:
        super().__init__(parent)

        with (ui_path / "crediteditorwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.md_attributes = {
            "credits.person": self.leName,
            "credits.language": self.cbLanguage,
            "credits.role": self.cbRole,
            "credits.primary": self.cbPrimary,
        }

        self.credit = credit
        self.row = row
        self.write_tags = write_tags

        self.setWindowTitle(title)
        self.setModal(True)

        # Add the entries to the role combobox
        self.cbRole.addItem("")
        self.cbRole.addItem("Artist")
        self.cbRole.addItem("Colorist")
        self.cbRole.addItem("Cover Artist")
        self.cbRole.addItem("Editor")
        self.cbRole.addItem("Inker")
        self.cbRole.addItem("Letterer")
        self.cbRole.addItem("Penciller")
        self.cbRole.addItem("Plotter")
        self.cbRole.addItem("Scripter")
        self.cbRole.addItem("Translator")
        self.cbRole.addItem("Writer")
        self.cbRole.addItem("Other")

        self.cbLanguage.addItem("", "")
        for f in natsort.humansorted(utils.languages().items(), operator.itemgetter(1)):
            self.cbLanguage.addItem(f[1], f[0])

        self.leName.setText(credit.person)

        if credit.role is not None and credit.role != "":
            i = self.cbRole.findText(credit.role)
            if i == -1:
                self.cbRole.setEditText(credit.role)
            else:
                self.cbRole.setCurrentIndex(i)

        if credit.language != "":
            i = (
                self.cbLanguage.findData(credit.language, QtCore.Qt.ItemDataRole.UserRole)
                if self.cbLanguage.findData(credit.language, QtCore.Qt.ItemDataRole.UserRole) > -1
                else self.cbLanguage.findText(credit.language)
            )
            if i == -1:
                self.cbLanguage.setEditText(credit.language)
            else:
                self.cbLanguage.setCurrentIndex(i)

        self.cbPrimary.setChecked(credit.primary)
        self.update_tag_tweaks()
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    def get_credit(self) -> Credit:
        lang = self.cbLanguage.currentData() or self.cbLanguage.currentText()
        return Credit(self.leName.text(), self.cbRole.currentText(), self.cbPrimary.isChecked(), lang)

    def update_tag_tweaks(self) -> None:
        # depending on the current data tag, certain fields are disabled
        enabled_widgets = set()
        for tag in self.write_tags:
            enabled_widgets.update(tag.supported_attributes)

        for md_field, widget in self.md_attributes.items():
            if widget is not None and not isinstance(widget, (int)):
                enable_widget(widget, md_field in enabled_widgets)

    def accept(self) -> None:
        if self.leName.text() == "":
            OptionalMessageDialog.warning(self, "Whoops", "You need to enter a name for a credit.")
            return

        QtWidgets.QDialog.accept(self)
        new = self.get_credit()
        if self.credit != new:
            self.creditChanged.emit(new, self.row)
