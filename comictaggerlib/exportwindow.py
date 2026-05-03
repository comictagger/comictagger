"""A PyQT4 dialog to confirm and set options for export to zip"""

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
from enum import Enum, auto
from typing import NamedTuple

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from .ui import ui_path

logger = logging.getLogger(__name__)


class ExportConflictOpts(Enum):
    DONT_CREATE = auto()
    OVERWRITE = auto()
    CREATE_UNIQUE = auto()


class ExportConfig(NamedTuple):
    conflict: ExportConflictOpts
    add_to_list: bool
    delete_original: bool


class ExportWindow(QtWidgets.QDialog):
    export = QtCore.pyqtSignal(ExportConfig)

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        with (ui_path / "exportwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)
        self.label: QtWidgets.QLabel
        self.cbxDeleteOriginal: QtWidgets.QCheckBox
        self.cbxAddToList: QtWidgets.QCheckBox
        self.radioDontCreate: QtWidgets.QRadioButton
        self.radioCreateNew: QtWidgets.QRadioButton
        self.msg = """You have selected {count} archive(s) to export to Zip format.  New archives will be created in the same folder as the original.

                   Please choose config below, and select OK.
                   """

        self.setWindowFlags(
            QtCore.Qt.WindowType(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)
        )

        self.cbxDeleteOriginal.setChecked(False)
        self.cbxAddToList.setChecked(True)
        self.radioDontCreate.setChecked(True)
        self.setModal(True)
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    def show(self, count: int) -> None:
        self.label.setText(self.msg.format(count=count))
        self.adjustSize()
        QtWidgets.QDialog.show(self)

    def accept(self) -> None:

        conflict = ExportConflictOpts.DONT_CREATE
        if self.radioDontCreate.isChecked():
            conflict = ExportConflictOpts.DONT_CREATE
        elif self.radioCreateNew.isChecked():
            conflict = ExportConflictOpts.CREATE_UNIQUE

        QtWidgets.QDialog.accept(self)
        self.export.emit(ExportConfig(conflict, self.cbxAddToList.isChecked(), self.cbxDeleteOriginal.isChecked()))
