from __future__ import annotations

import functools
import json
import logging
import os
import pathlib
import platform
import sys
import traceback
import types
from typing import TYPE_CHECKING

import settngs

from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.ctversion import version
from comictaggerlib.graphics import graphics_path
from comictalker.comictalker import ComicTalker

logger = logging.getLogger("comictagger")
try:
    qt_available = True
    from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets

    if TYPE_CHECKING:
        from comictaggerlib.taggerwindow import TaggerWindow
    tagger_window: TaggerWindow | None = None

    def show_exception_box(log_msg: str, details: str) -> None:
        """Checks if a QApplication instance is available and shows a messagebox with the exception message.
        If unavailable (non-console application), log an additional notice.
        """

        def find_window(widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
            for w in widget.children():
                if not w.isWidgetType():
                    continue
                if isinstance(w, QtWidgets.QWidget) and w.isWindow() and w.isVisible():
                    return find_window(w)
            return widget

        logger.error(log_msg)
        logger.error(details)
        if QtWidgets.QApplication.instance() is not None:
            primary_window = None
            if tagger_window:
                primary_window = find_window(tagger_window)
            modal_widget = QtWidgets.QApplication.activeModalWidget()
            active_window = QtWidgets.QApplication.activeWindow()
            tlist = QtWidgets.QApplication.topLevelWidgets() or None
            tl = None
            if tlist:
                tl = tlist[0]
            errorbox = QtWidgets.QMessageBox(primary_window or modal_widget or active_window or tagger_window or tl)
            errorbox.setStandardButtons(
                QtWidgets.QMessageBox.StandardButton.Abort | QtWidgets.QMessageBox.StandardButton.Ignore
            )
            if tagger_window:
                errorbox.addAction(tagger_window.actionExit)
            errorbox.setWindowTitle("Unexpected Exception")
            errorbox.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
            errorbox.setText(log_msg)
            errorbox.setDetailedText(details + " ")  # Forces text formatting on macOS
            errorbox.rejected.connect(lambda: QtWidgets.QApplication.exit(1))
            errorbox.accepted.connect(lambda: logger.warning("Exception ignored"))
            errorbox.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            errorbox.exec()  # Must stay exec so that this still works if it fails to load the main window
        else:
            logger.debug("No QApplication instance available.")

    class UncaughtHook(QtCore.QObject):
        _exception_caught = QtCore.pyqtSignal(object, object)

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
                logger.critical("Uncaught exception: %s: %s", exc_type.__name__, exc_value, exc_info=exc_info)
                log_msg = f"{exc_type.__name__}: {exc_value}"

                # trigger message box show
                self._exception_caught.emit(f"Oops. An unexpected error occurred:\n{log_msg}", trace_back)

    qt_exception_hook = UncaughtHook()

    try:
        # needed here to initialize QWebEngine
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

        qt_webengine_available = True
    except ImportError:
        qt_webengine_available = False

    class Application(QtWidgets.QApplication):
        openFileRequest = QtCore.pyqtSignal(QtCore.QUrl, name="openfileRequest")

        # Handles "Open With" from Finder on macOS
        def event(self, event: QtCore.QEvent) -> bool:
            if event.type() == QtCore.QEvent.Type.FileOpen:
                logger.debug("file open recieved: %s", event.url().toLocalFile())
                self.openFileRequest.emit(event.url())
                return True
            return super().event(event)

except ImportError as e:

    def show_exception_box(log_msg: str, details: str) -> None: ...

    logger.exception("Qt unavailable")
    qt_available = False
    import_error = e
if TYPE_CHECKING:
    assert QtCore and QtGui and QtWidgets and QtNetwork


def pre_gui_file_request(config: ct_ns, url: QtCore.QUrl) -> None:
    if url.toLocalFile() not in sys.argv:
        config.Runtime_Options__files.append(pathlib.Path(url.toLocalFile()))


def setupSocket(app: QtCore.QObject, config: settngs.Config[ct_ns]) -> QtNetwork.QLocalServer:
    # prevent multiple instances
    socket = QtNetwork.QLocalSocket(app)
    socket.connectToServer(config[0].internal__install_id)
    alive = socket.waitForConnected(3000)
    if alive:
        logger.setLevel(logging.INFO)
        logger.info("Another application with key [%s] is already running", config[0].internal__install_id)
        # send file list to other instance
        if config[0].Runtime_Options__files:
            socket.write(json.dumps(config[0].Runtime_Options__files).encode("utf-8"))
            if not socket.waitForBytesWritten(3000):
                logger.error(socket.errorString())
        socket.disconnectFromServer()
        raise SystemExit(0)
    # listen on a socket to prevent multiple instances
    socketServer = QtNetwork.QLocalServer(app)
    ok = socketServer.listen(config[0].internal__install_id)
    if not ok:
        if socketServer.serverError() == QtNetwork.QAbstractSocket.SocketError.AddressInUseError:
            socketServer.removeServer(config[0].internal__install_id)
            ok = socketServer.listen(config[0].internal__install_id)
        if not ok:
            logger.error(
                "Cannot start local socket with key [%s]. Reason: %s",
                config[0].internal__install_id,
                socketServer.errorString(),
            )
            raise SystemExit(0)
    return socketServer


def open_tagger_window(
    talkers: dict[str, ComicTalker], config: settngs.Config[ct_ns], error: tuple[str, bool] | None
) -> None:
    # Critical execeptions don't need to be caught UncaughtHook will display them to the user
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    args = [sys.argv[0]]
    app = Application(args)

    if error is not None:
        show_exception_box(error[0], " ")
        if error[1]:
            raise SystemExit(1)
    # needed to catch initial open file events (macOS)
    app.openFileRequest.connect(functools.partial(pre_gui_file_request, config[0]))

    # The window Icon needs to be set here. It's also set in taggerwindow.ui but it doesn't seem to matter
    app.setWindowIcon(QtGui.QIcon(":/graphics/app.png"))
    app.setApplicationName("ComicTagger")
    app.setApplicationDisplayName("ComicTagger")
    app.setApplicationVersion(version)

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

    splash = None
    if platform.system() != "Linux":
        img = QtGui.QPixmap()
        img.loadFromData((graphics_path / "tags.png").read_bytes())

        splash = QtWidgets.QSplashScreen(img)
        splash.show()
        splash.raise_()
        QtWidgets.QApplication.processEvents()

    try:
        from comictaggerlib.taggerwindow import TaggerWindow

        def activateModalWidget() -> None:
            assert QtGui and QtCore and QtWidgets
            modal_widget = QtWidgets.QApplication.activeModalWidget()
            active_window = QtWidgets.QApplication.activeWindow()
            if not active_window:
                return
            if not modal_widget:
                return
            if active_window != modal_widget:
                if modal_widget.isAncestorOf(active_window) or active_window.parent() == modal_widget:
                    logger.debug(
                        "skipping activation loop current active window (%r) is a child of the active modal widget (%r)",
                        active_window.windowTitle(),
                        modal_widget.windowTitle(),
                    )
                    return
                if active_window.windowTitle() == "Unexpected Exception":
                    logger.debug("skipping activation loop current active window is for an unexpected Exception")
                    return
                logger.debug(
                    "Qt/Wayland sucks: activating current modal widget %s -> %s",
                    active_window.windowTitle(),
                    modal_widget.windowTitle(),
                )
                modal_widget.activateWindow()
                QtCore.QTimer.singleShot(200, activateModalWidget)

        class Filter(QtCore.QObject):
            def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent[QtCore.QEvent.Type.WindowActivate]) -> bool:
                if (
                    event.type() in (event.Type.WindowActivate, event.Type.KeyPress, event.Type.KeyRelease)
                    and hasattr(obj, "isWindow")
                    and obj.isWindow()
                    and QtWidgets.QApplication.activeModalWidget()
                ):
                    if obj != QtWidgets.QApplication.activeModalWidget():
                        activateModalWidget()
                    return True
                return False

        flt = Filter(app)
        QtWidgets.QApplication.instance().installEventFilter(flt)
        socketServer = setupSocket(app, config)
        global tagger_window
        tagger_window = TaggerWindow(config, talkers, socketServer)
        app.openFileRequest.connect(tagger_window.open_file_event)
        tagger_window.show()
        tagger_window._post_show(config[0].Runtime_Options__files)
        # Catch open file events (macOS)

        if platform.system() != "Linux":
            assert splash
            splash.finish(tagger_window)

        sys.exit(app.exec())
    except Exception:
        logger.exception("GUI mode failed")
        QtWidgets.QMessageBox.critical(
            QtWidgets.QMainWindow(), "Error", "Unhandled exception in app:\n" + traceback.format_exc()
        )
