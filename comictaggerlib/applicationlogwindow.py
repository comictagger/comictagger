from __future__ import annotations

import logging

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comictaggerlib.settings import ComicTaggerSettings

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
    def __init__(self, log_handler: QTextEditLogger, parent: QtCore.QObject = None) -> None:
        super().__init__(parent)
        uic.loadUi(ComicTaggerSettings.get_ui_file("logwindow.ui"), self)

        self.log_handler = log_handler
        self.log_handler.qlog.connect(self.textEdit.append)

        f = QtGui.QFont("menlo")
        f.setStyleHint(QtGui.QFont.Monospace)
        self.setFont(f)
        self._button = QtWidgets.QPushButton(self)
        self._button.setText("Test Me")

        layout = self.layout()
        layout.addWidget(self._button)

        # Connect signal to slot
        self._button.clicked.connect(self.test)
        self.textEdit.setTabStopDistance(self.textEdit.tabStopDistance() * 2)

    def test(self) -> None:
        logger.debug("damn, a bug")
        logger.info("something to remember")
        logger.warning("that's not right")
        logger.error("foobar")
