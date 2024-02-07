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
from typing import Any

from PyQt5 import QtWidgets, uic

from comictaggerlib.ui import ui_path

logger = logging.getLogger(__name__)


class CreditEditorWindow(QtWidgets.QDialog):
    ModeEdit = 0
    ModeNew = 1

    def __init__(self, parent: QtWidgets.QWidget, mode: int, role: str, name: str, primary: bool) -> None:
        super().__init__(parent)

        with (ui_path / "crediteditorwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.mode = mode

        if self.mode == self.ModeEdit:
            self.setWindowTitle("Edit Credit")
        else:
            self.setWindowTitle("New Credit")

        # Add the entries to the role combobox
        self.cbRole.addItem("")
        self.cbRole.addItem("Writer")
        self.cbRole.addItem("Artist")
        self.cbRole.addItem("Penciller")
        self.cbRole.addItem("Inker")
        self.cbRole.addItem("Colorist")
        self.cbRole.addItem("Letterer")
        self.cbRole.addItem("Cover Artist")
        self.cbRole.addItem("Editor")
        self.cbRole.addItem("Other")
        self.cbRole.addItem("Plotter")
        self.cbRole.addItem("Scripter")

        self.leName.setText(name)

        if role is not None and role != "":
            i = self.cbRole.findText(role)
            if i == -1:
                self.cbRole.setEditText(role)
            else:
                self.cbRole.setCurrentIndex(i)

        self.cbPrimary.setChecked(primary)

        self.cbRole.currentIndexChanged.connect(self.role_changed)
        self.cbRole.editTextChanged.connect(self.role_changed)

        self.update_primary_button()

    def update_primary_button(self) -> None:
        enabled = self.current_role_can_be_primary()
        self.cbPrimary.setEnabled(enabled)

    def current_role_can_be_primary(self) -> bool:
        role = self.cbRole.currentText()
        if role.casefold() in ("artist", "writer"):
            return True

        return False

    def role_changed(self, s: Any) -> None:
        self.update_primary_button()

    def get_credits(self) -> tuple[str, str, bool]:
        primary = self.current_role_can_be_primary() and self.cbPrimary.isChecked()
        return self.cbRole.currentText(), self.leName.text(), primary

    def accept(self) -> None:
        if self.cbRole.currentText() == "" or self.leName.text() == "":
            QtWidgets.QMessageBox.warning(self, "Whoops", "You need to enter both role and name for a credit.")
        else:
            QtWidgets.QDialog.accept(self)
