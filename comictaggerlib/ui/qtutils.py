"""Some utilities for the GUI"""

from __future__ import annotations

import io
import logging
import traceback
import webbrowser
from collections.abc import Sequence

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QWidget

from comictaggerlib.graphics import graphics_path

logger = logging.getLogger(__name__)

try:
    from PyQt5 import QtGui, QtWidgets
    from PyQt5.QtCore import Qt

    qt_available = True
except ImportError:
    qt_available = False

if qt_available:
    try:
        from PIL import Image, ImageQt

        pil_available = True
    except ImportError:
        pil_available = False

    try:
        from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView

        class WebPage(QWebEnginePage):
            def acceptNavigationRequest(
                self, url: QUrl, n_type: QWebEnginePage.NavigationType, isMainFrame: bool
            ) -> bool:
                if n_type in (
                    QWebEnginePage.NavigationType.NavigationTypeOther,
                    QWebEnginePage.NavigationType.NavigationTypeTyped,
                ):
                    return True
                if n_type in (QWebEnginePage.NavigationType.NavigationTypeLinkClicked,) and url.scheme() in (
                    "http",
                    "https",
                ):
                    webbrowser.open(url.toString())
                return False

        def new_web_view(parent: QWidget) -> QWebEngineView:
            webengine = QWebEngineView(parent)
            webengine.setPage(WebPage(parent))
            webengine.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            settings = webengine.settings()
            settings.setAttribute(settings.WebAttribute.AutoLoadImages, True)
            settings.setAttribute(settings.WebAttribute.JavascriptEnabled, False)
            settings.setAttribute(settings.WebAttribute.JavascriptCanOpenWindows, False)
            settings.setAttribute(settings.WebAttribute.JavascriptCanAccessClipboard, False)
            settings.setAttribute(settings.WebAttribute.LinksIncludedInFocusChain, False)
            settings.setAttribute(settings.WebAttribute.LocalStorageEnabled, False)
            settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
            settings.setAttribute(settings.WebAttribute.XSSAuditingEnabled, False)
            settings.setAttribute(settings.WebAttribute.SpatialNavigationEnabled, True)
            settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, False)
            settings.setAttribute(settings.WebAttribute.HyperlinkAuditingEnabled, False)
            settings.setAttribute(settings.WebAttribute.ScrollAnimatorEnabled, False)
            settings.setAttribute(settings.WebAttribute.ErrorPageEnabled, False)
            settings.setAttribute(settings.WebAttribute.PluginsEnabled, False)
            settings.setAttribute(settings.WebAttribute.FullScreenSupportEnabled, False)
            settings.setAttribute(settings.WebAttribute.ScreenCaptureEnabled, False)
            settings.setAttribute(settings.WebAttribute.WebGLEnabled, False)
            settings.setAttribute(settings.WebAttribute.Accelerated2dCanvasEnabled, False)
            settings.setAttribute(settings.WebAttribute.AutoLoadIconsForPage, False)
            settings.setAttribute(settings.WebAttribute.TouchIconsEnabled, False)
            settings.setAttribute(settings.WebAttribute.FocusOnNavigationEnabled, False)
            settings.setAttribute(settings.WebAttribute.PrintElementBackgrounds, False)
            settings.setAttribute(settings.WebAttribute.AllowRunningInsecureContent, False)
            settings.setAttribute(settings.WebAttribute.AllowGeolocationOnInsecureOrigins, False)
            settings.setAttribute(settings.WebAttribute.AllowWindowActivationFromJavaScript, False)
            settings.setAttribute(settings.WebAttribute.ShowScrollBars, True)
            settings.setAttribute(settings.WebAttribute.PlaybackRequiresUserGesture, True)
            settings.setAttribute(settings.WebAttribute.JavascriptCanPaste, False)
            settings.setAttribute(settings.WebAttribute.WebRTCPublicInterfacesOnly, False)
            settings.setAttribute(settings.WebAttribute.DnsPrefetchEnabled, False)
            settings.setAttribute(settings.WebAttribute.PdfViewerEnabled, False)
            return webengine

    except ImportError:

        def new_web_view(parent: QWidget) -> QWebEngineView: ...

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
            img.load(str(graphics_path / "nocover.png"))
        return img

    def qt_error(msg: str, e: Exception | None = None) -> None:
        trace = ""
        if e:
            trace = "\n".join(traceback.format_exception(type(e), e, e.__traceback__))

        QtWidgets.QMessageBox.critical(QtWidgets.QMainWindow(), "Error", msg + trace)

    active_palette = None

    def enable_widget(widget: QtWidgets.QWidget | list[QtWidgets.QWidget], enable: bool) -> None:
        if isinstance(widget, Sequence):
            for w in widget:
                _enable_widget(w, enable)
        else:
            _enable_widget(widget, enable)

    def _enable_widget(widget: QtWidgets.QWidget, enable: bool) -> None:
        global active_palette
        if not (widget is not None and active_palette is not None):
            return
        active_color = active_palette.color(QtGui.QPalette.ColorRole.Base)

        inactive_color = QtGui.QColor(255, 170, 150)
        inactive_brush = QtGui.QBrush(inactive_color)
        active_brush = QtGui.QBrush(active_color)

        def palettes() -> tuple[QtGui.QPalette, QtGui.QPalette, QtGui.QPalette]:
            inactive_palette1 = QtGui.QPalette(active_palette)
            inactive_palette1.setColor(QtGui.QPalette.ColorRole.Base, inactive_color)

            inactive_palette2 = QtGui.QPalette(active_palette)
            inactive_palette2.setColor(widget.backgroundRole(), inactive_color)

            inactive_palette3 = QtGui.QPalette(active_palette)
            inactive_palette3.setColor(QtGui.QPalette.ColorRole.Base, inactive_color)
            inactive_palette3.setColor(widget.foregroundRole(), inactive_color)
            return inactive_palette1, inactive_palette2, inactive_palette3

        if hasattr(widget, "setEnabled"):
            widget.setEnabled(enable)

        if enable:
            if isinstance(widget, QtWidgets.QTableWidgetItem):
                widget.setBackground(active_brush)
                return

            widget.setAutoFillBackground(False)
            widget.setPalette(active_palette)
            if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QComboBox, QtWidgets.QPushButton)):
                widget.setEnabled(True)
            elif isinstance(widget, (QtWidgets.QTextEdit, QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox)):
                widget.setReadOnly(False)
            elif isinstance(widget, QtWidgets.QListWidget):
                widget.setMovement(QtWidgets.QListWidget.Free)
        else:
            if isinstance(widget, QtWidgets.QTableWidgetItem):
                widget.setBackground(inactive_brush)
                return

            widget.setAutoFillBackground(True)
            if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QComboBox, QtWidgets.QPushButton)):
                inactive_palette = palettes()
                widget.setPalette(inactive_palette[1])
                widget.setEnabled(False)
            elif isinstance(widget, (QtWidgets.QTextEdit, QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox)):
                inactive_palette = palettes()
                widget.setReadOnly(True)
                widget.setPalette(inactive_palette[0])
            elif isinstance(widget, QtWidgets.QListWidget):
                inactive_palette = palettes()
                widget.setPalette(inactive_palette[0])
                widget.setMovement(QtWidgets.QListWidget.Static)

    def replaceWidget(
        layout: QtWidgets.QLayout | QtWidgets.QSplitter, old_widget: QtWidgets.QWidget, new_widget: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:

        if isinstance(layout, QtWidgets.QLayout):
            layout.replaceWidget(old_widget, new_widget)
        elif isinstance(layout, QtWidgets.QSplitter):
            layout.refresh()
            layout.replaceWidget(layout.indexOf(old_widget), new_widget)

        new_widget.setBaseSize(old_widget.baseSize())
        new_widget.setSizeIncrement(old_widget.sizeIncrement())
        new_widget.setMinimumSize(old_widget.minimumSize())
        new_widget.setMaximumSize(old_widget.maximumSize())
        new_widget.setGeometry(old_widget.geometry())
        new_widget.setSizePolicy(old_widget.sizePolicy())

        old_widget.hide()
        old_widget.deleteLater()
        # QSplitter has issues with replacing a widget before it's been first shown. Assume it should be visible
        new_widget.show()
        return new_widget
