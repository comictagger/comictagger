from __future__ import annotations

import logging.handlers
import os
import platform
import sys
import traceback
import types

import settngs

from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.graphics import graphics_path
from comictalker.comictalker import ComicTalker

logger = logging.getLogger("comictagger")
try:
    qt_available = True
    from PyQt5 import QtCore, QtGui, QtWidgets

    def show_exception_box(log_msg: str) -> None:
        """Checks if a QApplication instance is available and shows a messagebox with the exception message.
        If unavailable (non-console application), log an additional notice.
        """
        if QtWidgets.QApplication.instance() is not None:
            errorbox = QtWidgets.QMessageBox()
            errorbox.setText(log_msg)
            errorbox.exec()
            QtWidgets.QApplication.exit(1)
        else:
            logger.debug("No QApplication instance available.")

    class UncaughtHook(QtCore.QObject):
        _exception_caught = QtCore.pyqtSignal(object)

        def __init__(self) -> None:
            super().__init__()

            # this registers the exception_hook() function as hook with the Python interpreter
            sys.excepthook = self.exception_hook

            # connect signal to execute the message box function always on main thread
            self._exception_caught.connect(show_exception_box)

        def exception_hook(
            self, exc_type: type[BaseException], exc_value: BaseException, exc_traceback: types.TracebackType | None
        ) -> None:
            """Function handling uncaught exceptions.
            It is triggered each time an uncaught exception occurs.
            """
            if issubclass(exc_type, KeyboardInterrupt):
                # ignore keyboard interrupt to support console applications
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
            else:
                exc_info = (exc_type, exc_value, exc_traceback)
                trace_back = "".join(traceback.format_tb(exc_traceback))
                log_msg = f"{exc_type.__name__}: {exc_value}\n\n{trace_back}"
                logger.critical("Uncaught exception: %s: %s", exc_type.__name__, exc_value, exc_info=exc_info)

                # trigger message box show
                self._exception_caught.emit(f"Oops. An unexpected error occurred:\n{log_msg}")

    qt_exception_hook = UncaughtHook()
    from comictaggerlib.taggerwindow import TaggerWindow

    class Application(QtWidgets.QApplication):
        openFileRequest = QtCore.pyqtSignal(QtCore.QUrl, name="openfileRequest")

        # Handles "Open With" from Finder on macOS
        def event(self, event: QtCore.QEvent) -> bool:
            if event.type() == QtCore.QEvent.FileOpen:
                logger.info(event.url().toLocalFile())
                self.openFileRequest.emit(event.url())
                return True
            return super().event(event)

except ImportError:

    def show_exception_box(log_msg: str) -> None:
        ...

    logger.exception("Qt unavailable")
    qt_available = False


def open_tagger_window(
    talkers: dict[str, ComicTalker], config: settngs.Config[ct_ns], error: tuple[str, bool] | None
) -> None:
    os.environ["QtWidgets.QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    args = []
    if config[0].runtime_darkmode:
        args.extend(["-platform", "windows:darkmode=2"])
    args.extend(sys.argv)
    app = Application(args)
    if error is not None:
        show_exception_box(error[0])
        if error[1]:
            raise SystemExit(1)

    # needed to catch initial open file events (macOS)
    app.openFileRequest.connect(lambda x: config[0].runtime_files.append(x.toLocalFile()))

    if platform.system() == "Darwin":
        # Set the MacOS dock icon
        app.setWindowIcon(QtGui.QIcon(str(graphics_path / "app.png")))

    if platform.system() == "Windows":
        # For pure python, tell windows that we're not python,
        # so we can have our own taskbar icon
        import ctypes

        myappid = "comictagger"  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)  # type: ignore[attr-defined]
        # force close of console window
        swp_hidewindow = 0x0080
        console_wnd = ctypes.windll.kernel32.GetConsoleWindow()  # type: ignore[attr-defined]
        if console_wnd != 0:
            ctypes.windll.user32.SetWindowPos(console_wnd, None, 0, 0, 0, 0, swp_hidewindow)  # type: ignore[attr-defined]

    if platform.system() != "Linux":
        img = QtGui.QPixmap(str(graphics_path / "tags.png"))

        splash = QtWidgets.QSplashScreen(img)
        splash.show()
        splash.raise_()
        QtWidgets.QApplication.processEvents()

    try:
        tagger_window = TaggerWindow(config[0].runtime_files, config, talkers)
        tagger_window.setWindowIcon(QtGui.QIcon(str(graphics_path / "app.png")))
        tagger_window.show()

        # Catch open file events (macOS)
        app.openFileRequest.connect(tagger_window.open_file_event)

        if platform.system() != "Linux":
            splash.finish(tagger_window)

        sys.exit(app.exec())
    except Exception:
        logger.exception("GUI mode failed")
        QtWidgets.QMessageBox.critical(
            QtWidgets.QMainWindow(), "Error", "Unhandled exception in app:\n" + traceback.format_exc()
        )
