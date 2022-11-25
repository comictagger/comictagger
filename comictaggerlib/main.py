"""A python app to (automatically) tag comic archives"""
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

import json
import logging.handlers
import os
import pathlib
import platform
import signal
import sys
import traceback
import types

import comictalker.comictalkerapi as ct_api
from comicapi import utils
from comictaggerlib import cli
from comictaggerlib.ctversion import version
from comictaggerlib.graphics import graphics_path
from comictaggerlib.options import parse_cmd_line
from comictaggerlib.settings import ComicTaggerSettings
from comictalker.talkerbase import TalkerError

if sys.version_info < (3, 10):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata

logger = logging.getLogger("comictagger")
logging.getLogger("comicapi").setLevel(logging.DEBUG)
logging.getLogger("comictaggerlib").setLevel(logging.DEBUG)
logging.getLogger("comictalker").setLevel(logging.DEBUG)
logger.setLevel(logging.DEBUG)

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

        def event(self, event: QtCore.QEvent) -> bool:
            if event.type() == QtCore.QEvent.FileOpen:
                logger.info(event.url().toLocalFile())
                self.openFileRequest.emit(event.url())
                return True
            return super().event(event)

except ImportError as e:

    def show_exception_box(log_msg: str) -> None:
        ...

    logger.error(str(e))
    qt_available = False


def rotate(handler: logging.handlers.RotatingFileHandler, filename: pathlib.Path) -> None:
    if filename.is_file() and filename.stat().st_size > 0:
        handler.doRollover()


def update_publishers() -> None:
    json_file = ComicTaggerSettings.get_settings_folder() / "publishers.json"
    if json_file.exists():
        try:
            utils.update_publishers(json.loads(json_file.read_text("utf-8")))
        except Exception as e:
            logger.exception("Failed to load publishers from %s", json_file)
            show_exception_box(str(e))


def ctmain() -> None:
    opts = parse_cmd_line()
    settings = ComicTaggerSettings(opts.config_path)

    os.makedirs(ComicTaggerSettings.get_settings_folder() / "logs", exist_ok=True)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    file_handler = logging.handlers.RotatingFileHandler(
        ComicTaggerSettings.get_settings_folder() / "logs" / "ComicTagger.log", encoding="utf-8", backupCount=10
    )
    rotate(file_handler, ComicTaggerSettings.get_settings_folder() / "logs" / "ComicTagger.log")
    logging.basicConfig(
        handlers=[
            stream_handler,
            file_handler,
        ],
        level=logging.WARNING,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if settings.settings_warning < 4:
        print(  # noqa: T201
            """
!!!Warning!!!
The next release will save settings in a different format
NO SETTINGS WILL BE TRANSFERED to the new version.
See https://github.com/comictagger/comictagger/releases/1.5.5 for more information.
""",
            file=sys.stderr,
        )

    # manage the CV API key
    # None comparison is used so that the empty string can unset the value
    if opts.cv_api_key is not None or opts.cv_url is not None:
        settings.cv_api_key = opts.cv_api_key if opts.cv_api_key is not None else settings.cv_api_key
        settings.cv_url = opts.cv_url if opts.cv_url is not None else settings.cv_url
        settings.save()
    if opts.only_set_cv_key:
        print("Key set")  # noqa: T201
        return

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    logger.info(
        "ComicTagger Version: %s running on: %s PyInstaller: %s",
        version,
        platform.system(),
        "Yes" if getattr(sys, "frozen", None) else "No",
    )

    logger.debug("Installed Packages")
    for pkg in sorted(importlib_metadata.distributions(), key=lambda x: x.name):
        logger.debug("%s\t%s", pkg.metadata["Name"], pkg.metadata["Version"])

    if not qt_available and not opts.no_gui:
        opts.no_gui = True
        logger.warning("PyQt5 is not available. ComicTagger is limited to command-line mode.")

    talker_exception = None
    try:
        talker_api = ct_api.get_comic_talker("comicvine")(  # type: ignore[call-arg]
            version=version,
            cache_folder=ComicTaggerSettings.get_settings_folder(),
            series_match_thresh=settings.id_series_match_search_thresh,
            remove_html_tables=settings.remove_html_tables,
            use_series_start_as_volume=settings.use_series_start_as_volume,
            wait_on_ratelimit=settings.wait_and_retry_on_rate_limit,
            api_url=settings.cv_url,
            api_key=settings.cv_api_key,
        )
    except TalkerError as e:
        logger.exception("Unable to load talker")
        talker_exception = e
        if opts.no_gui:
            raise SystemExit(1)

    utils.load_publishers()
    update_publishers()

    if opts.no_gui:
        try:
            cli.cli_mode(opts, settings, talker_api)
        except Exception:
            logger.exception("CLI mode failed")
    else:
        os.environ["QtWidgets.QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        args = []
        if opts.darkmode:
            args.extend(["-platform", "windows:darkmode=2"])
        args.extend(sys.argv)
        app = Application(args)
        if talker_exception is not None:
            trace_back = "".join(traceback.format_tb(talker_exception.__traceback__))
            log_msg = f"{type(talker_exception).__name__}: {talker_exception}\n\n{trace_back}"
            show_exception_box(f"Unable to load talker: {log_msg}")
            raise SystemExit(1)

        # needed to catch initial open file events (macOS)
        app.openFileRequest.connect(lambda x: opts.files.append(x.toLocalFile()))

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
            tagger_window = TaggerWindow(opts.files, settings, talker_api, opts=opts)
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
