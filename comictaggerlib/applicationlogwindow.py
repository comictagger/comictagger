from __future__ import annotations

import logging

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comictaggerlib.ui import ui_path

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
    def __init__(self, log_handler: QTextEditLogger, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        uic.loadUi(ui_path / "applicationlogwindow.ui", self)

        self.log_handler = log_handler
        self.log_handler.qlog.connect(self.textEdit.append)

        f = QtGui.QFont("menlo")
        f.setStyleHint(QtGui.QFont.Monospace)
        self.setFont(f)
        self._button = QtWidgets.QPushButton(self)
        self._button.setText(self.tr("Test Me"))

        layout = self.layout()
        layout.addWidget(self._button)

        # Connect signal to slot
        self._button.clicked.connect(self.test)
        self.textEdit.setTabStopDistance(self.textEdit.tabStopDistance() * 2)

    def test(self) -> None:
        logger.debug(self.tr("damn, a bug"))
        logger.info(self.tr("something to remember"))
        logger.warning(self.tr("that's not right"))
        logger.error(self.tr("foobar"))
