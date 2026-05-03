from __future__ import annotations

import logging
import pathlib

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from .ui import ui_path

logger = logging.getLogger(__name__)


class QTextEditLogger(QtCore.QObject, logging.Handler):
    qlog = QtCore.pyqtSignal(str)

    def __init__(self, formatter: logging.Formatter, level: int) -> None:
        super().__init__()
        self.setFormatter(formatter)
        self.setLevel(level)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.qlog.emit(msg.strip())


class ApplicationLogWindow(QtWidgets.QDialog):
    def __init__(
        self, log_folder: pathlib.Path, log_handler: QTextEditLogger, parent: QtCore.QObject | None = None
    ) -> None:
        super().__init__(parent)
        with (ui_path / "applicationlogwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.log_handler = log_handler
        self.log_handler.qlog.connect(self.textEdit.append)

        f = QtGui.QFont("menlo")
        f.setStyleHint(QtGui.QFont.StyleHint.Monospace)
        self.setFont(f)
        self._button = QtWidgets.QPushButton(self)
        self._button.setText("Test Me")

        self.log_folder = log_folder
        self.lblLogLocation.setText(f'Log Location: <a href="file://{log_folder}">{log_folder}</a>')

        layout = self.layout()
        layout.addWidget(self._button)

        # Connect signal to slot
        self._button.clicked.connect(self.test)
        self.textEdit.setTabStopDistance(self.textEdit.tabStopDistance() * 2)
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    def test(self) -> None:
        logger.debug("damn, a bug")
        logger.info("something to remember")
        logger.warning("that's not right")
        logger.error("foobar")
