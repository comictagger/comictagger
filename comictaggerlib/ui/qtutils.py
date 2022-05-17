"""Some utilities for the GUI"""

import io
import logging
import traceback
from typing import Optional

from comictaggerlib.settings import ComicTaggerSettings

logger = logging.getLogger(__name__)

try:
    from PyQt5 import QtGui, QtWidgets

    qt_available = True
except ImportError:
    qt_available = False

if qt_available:
    try:
        from PIL import Image, ImageQt

        pil_available = True
    except ImportError:
        pil_available = False

    def reduce_widget_font_size(widget: QtWidgets.QWidget, delta: int = 2) -> None:
        f = widget.font()
        if f.pointSize() > 10:
            f.setPointSize(f.pointSize() - delta)
        widget.setFont(f)

    def center_window_on_screen(window: QtWidgets.QWidget) -> None:
        """Center the window on screen.

        This implementation will handle the window
        being resized or the screen resolution changing.
        """
        # Get the current screens' dimensions...
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        # The horizontal position is calculated as (screen width - window width) / 2
        hpos = int((screen.width() - window.width()) / 2)
        # And vertical position the same, but with the height dimensions
        vpos = int((screen.height() - window.height()) / 2)
        # And the move call repositions the window
        window.move(hpos, vpos)

    def center_window_on_parent(window: QtWidgets.QWidget) -> None:

        top_level = window
        while top_level.parent() is not None:
            parent = top_level.parent()
            if isinstance(parent, QtWidgets.QWidget):
                top_level = parent

        # Get the current screens' dimensions...
        main_window_size = top_level.geometry()
        # ... and get this windows' dimensions
        # The horizontal position is calculated as (screen width - window width) / 2
        hpos = int((main_window_size.width() - window.width()) / 2)
        # And vertical position the same, but with the height dimensions
        vpos = int((main_window_size.height() - window.height()) / 2)
        # And the move call repositions the window
        window.move(hpos + main_window_size.left(), vpos + main_window_size.top())

    def get_qimage_from_data(image_data: bytes) -> QtGui.QImage:
        img = QtGui.QImage()
        success = img.loadFromData(image_data)
        if not success:
            try:
                if pil_available:
                    # Qt doesn't understand the format, but maybe PIL does
                    img = ImageQt.ImageQt(Image.open(io.BytesIO(image_data)))
                    success = True
            except Exception:
                pass
        # if still nothing, go with default image
        if not success:
            img.load(ComicTaggerSettings.get_graphic("nocover.png"))
        return img

    def qt_error(msg: str, e: Optional[Exception] = None) -> None:
        trace = ""
        if e:
            trace = "\n".join(traceback.format_exception(type(e), e, e.__traceback__))

        QtWidgets.QMessageBox.critical(QtWidgets.QMainWindow(), "Error", msg + trace)
