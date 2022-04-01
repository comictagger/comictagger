"""A python app to (automatically) tag comic archives"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import platform
import signal
import sys
import traceback

from comictaggerlib import cli
from comictaggerlib.comicvinetalker import ComicVineTalker
from comictaggerlib.options import Options
from comictaggerlib.settings import ComicTaggerSettings

try:
    qt_available = True
    from PyQt5 import QtGui, QtWidgets

    from comictaggerlib.taggerwindow import TaggerWindow
except ImportError as e:
    print(e)
    qt_available = False


def ctmain():
    opts = Options()
    opts.parse_cmd_line_args()

    # Need to load setting before anything else
    SETTINGS = ComicTaggerSettings()

    # manage the CV API key
    if opts.cv_api_key:
        if opts.cv_api_key != SETTINGS.cv_api_key:
            SETTINGS.cv_api_key = opts.cv_api_key
            SETTINGS.save()
    if opts.only_set_key:
        print("Key set")
        return

    ComicVineTalker.api_key = SETTINGS.cv_api_key

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    if not qt_available and not opts.no_gui:
        opts.no_gui = True
        print("PyQt5 is not available.  ComicTagger is limited to command-line mode.", file=sys.stderr)

    if opts.no_gui:
        cli.cli_mode(opts, SETTINGS)
    else:
        os.environ["QtWidgets.QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        args = []
        if opts.darkmode:
            args.extend(["-platform", "windows:darkmode=2"])
        args.extend(sys.argv)
        app = QtWidgets.QApplication(args)
        if platform.system() == "Darwin":
            # Set the MacOS dock icon
            app.setWindowIcon(QtGui.QIcon(ComicTaggerSettings.get_graphic("app.png")))

        if platform.system() == "Windows":
            # For pure python, tell windows that we're not python,
            # so we can have our own taskbar icon
            import ctypes

            myappid = "comictagger"  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            # force close of console window
            swp_hidewindow = 0x0080
            console_wnd = ctypes.windll.kernel32.GetConsoleWindow()
            if console_wnd != 0:
                ctypes.windll.user32.SetWindowPos(console_wnd, None, 0, 0, 0, 0, swp_hidewindow)

        if platform.system() != "Linux":
            img = QtGui.QPixmap(ComicTaggerSettings.get_graphic("tags.png"))

            splash = QtWidgets.QSplashScreen(img)
            splash.show()
            splash.raise_()
            app.processEvents()

        try:
            tagger_window = TaggerWindow(opts.file_list, SETTINGS, opts=opts)
            tagger_window.setWindowIcon(QtGui.QIcon(ComicTaggerSettings.get_graphic("app.png")))
            tagger_window.show()

            if platform.system() != "Linux":
                splash.finish(tagger_window)

            sys.exit(app.exec())
        except Exception:
            print(traceback.format_exc())
            QtWidgets.QMessageBox.critical(
                QtWidgets.QMainWindow(), "Error", "Unhandled exception in app:\n" + traceback.format_exc()
            )
