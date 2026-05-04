"""Custom widgets"""

from __future__ import annotations

import io
from enum import auto
from sys import platform
from typing import Any, cast

from PIL import Image
from PyQt6 import QtGui, QtWidgets
from PyQt6.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt, pyqtSignal

from comicapi.utils import StrEnum
from comictaggerlib.graphics import graphics_path


class ClickedButtonEnum(StrEnum):
    up = auto()
    down = auto()
    main = auto()


class ModifyStyleItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__()
        self.combobox = parent

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> None:
        options = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        style = self.combobox.style()

        # Draw background with the same color as other widgets
        palette = self.combobox.palette()
        background_color = palette.color(QtGui.QPalette.ColorRole.Window)
        painter.fillRect(options.rect, background_color)

        style.drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_PanelItemViewItem, options, painter, self.combobox)

        painter.save()

        # Checkbox drawing logic
        checked = index.data(Qt.ItemDataRole.CheckStateRole)
        opts = QtWidgets.QStyleOptionButton()
        opts.state |= QtWidgets.QStyle.StateFlag.State_Active
        opts.rect = self.getCheckBoxRect(options)
        opts.state |= QtWidgets.QStyle.StateFlag.State_ReadOnly
        if checked:
            opts.state |= QtWidgets.QStyle.StateFlag.State_On
            style.drawPrimitive(
                QtWidgets.QStyle.PrimitiveElement.PE_IndicatorMenuCheckMark, opts, painter, self.combobox
            )
        else:
            opts.state |= QtWidgets.QStyle.StateFlag.State_Off
        if platform != "darwin":
            style.drawControl(QtWidgets.QStyle.ControlElement.CE_CheckBox, opts, painter, self.combobox)

        label = index.data(Qt.ItemDataRole.DisplayRole)
        rectangle = options.rect
        rectangle.setX(opts.rect.width() + 10)
        # We need the restore here so that text is colored properly
        painter.restore()
        painter.drawText(rectangle, Qt.AlignmentFlag.AlignVCenter, label)

    def getCheckBoxRect(self, option: QtWidgets.QStyleOptionViewItem) -> QRect:
        # Get size of a standard checkbox.
        opts = QtWidgets.QStyleOptionButton()
        style = option.widget.style()
        checkBoxRect = style.subElementRect(QtWidgets.QStyle.SubElement.SE_CheckBoxIndicator, opts, None)
        y = option.rect.y()
        h = option.rect.height()
        checkBoxTopLeftCorner = QPoint(5, int(y + h / 2 - checkBoxRect.height() / 2))

        return QRect(checkBoxTopLeftCorner, checkBoxRect.size())

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> QSize:
        # Reimpliment stock. Only height is used, width is ignored
        menu_option = QtWidgets.QStyleOptionMenuItem()
        size = self.combobox.style().sizeFromContents(
            QtWidgets.QStyle.ContentsType.CT_MenuItem, menu_option, option.rect.size(), self.combobox
        )
        return size


# Multiselect combobox from: https://gis.stackexchange.com/a/351152 (with custom changes)
class CheckableComboBox(QtWidgets.QComboBox):
    itemChecked = pyqtSignal(object, bool)
    # This would be (Tag, bool) but pyqt enforces types so we use object to allow duck-typing

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

        # Use a custom delegate to keep combo box styles consistent
        self.setItemDelegate(ModifyStyleItemDelegate(self))

        # Keeps track of when the combobox list is shown
        self.justShown = False

    # Longstanding bug that is fixed almost everywhere but in Linux/Windows pip wheels
    # https://stackoverflow.com/questions/65826378/how-do-i-use-qcombobox-setplaceholdertext/65830989#65830989
    def paintEvent(self, event: QEvent) -> None:
        painter = QtWidgets.QStylePainter(self)
        painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.Text))

        # draw the combobox frame, focusrect and selected etc.
        opt = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(opt)
        painter.drawComplexControl(QtWidgets.QStyle.ComplexControl.CC_ComboBox, opt)

        if self.currentIndex() < 0:
            opt.palette.setBrush(
                QtGui.QPalette.ColorRole.ButtonText,
                opt.palette.brush(QtGui.QPalette.ColorRole.ButtonText).color(),
            )
            if self.placeholderText():
                opt.currentText = self.placeholderText()

        # draw the icon and text
        painter.drawControl(QtWidgets.QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def resizeEvent(self, event: Any) -> None:
        # Recompute text to elide as needed
        super().resizeEvent(event)
        self._updateText()

    def eventFilter(self, obj: Any, event: Any) -> bool:
        # Allow events before the combobox list is shown
        if obj == self.view().viewport():
            # We record that the combobox list has been shown
            if event.type() == QEvent.Type.Show:
                self.justShown = True
            # We record that the combobox list has hidden,
            # this will happen if the user does not make a selection
            # but clicks outside of the combobox list or presses escape
            if event.type() == QEvent.Type.Hide:
                self._updateText()
                self.justShown = False
            # QEvent.Type.MouseButtonPress is inconsistent on activation because double clicks are a thing
            if event.type() == QEvent.Type.MouseButtonRelease:
                # If self.justShown is true it means that they clicked on the combobox to change the checked items
                # This is standard behavior (on macos) but I think it is surprising when it has a multiple select
                if self.justShown:
                    self.justShown = False
                    return True

                # Find the current index and item
                index = self.view().indexAt(event.pos())
                self.toggleItem(index.row())
                return True
        return False

    def currentData(self) -> list[Any]:
        # Return the list of all checked items data
        res = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.CheckState.Checked:
                res.append(self.itemData(i))
        return res

    def addItem(self, text: str, data: Any = None) -> None:
        super().addItem(text, data)
        # Need to enable the checkboxes and require one checked item
        # Expected that state of *all* checkboxes will be set ('adjust_tags_combo' in taggerwindow.py)
        if self.count() == 1:
            self.model().item(0).setCheckState(Qt.CheckState.Checked)

    def _updateText(self) -> None:
        texts = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.CheckState.Checked:
                texts.append(item.text())
        text = ", ".join(texts)

        # Compute elided text (with "...")

        # The QStyleOptionComboBox is needed for the call to subControlRect
        so = QtWidgets.QStyleOptionComboBox()
        # init with the current widget
        so.initFrom(self)

        # Ask the style for the size of the text field
        rect = self.style().subControlRect(
            QtWidgets.QStyle.ComplexControl.CC_ComboBox, so, QtWidgets.QStyle.SubControl.SC_ComboBoxEditField
        )

        # Compute the elided text
        elidedText = self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, rect.width())

        # This CheckableComboBox does not use the index, so we clear it and set the placeholder text
        self.setCurrentIndex(-1)
        self.setPlaceholderText(elidedText)

    def setItemChecked(self, index: Any, state: bool) -> None:
        qt_state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        item = self.model().item(index)
        current = self.currentData()
        # If we have at least one item checked emit itemChecked with the current check state and update text
        # Require at least one item to be checked and provide a tooltip
        if len(current) == 1 and not state and item.checkState() == Qt.CheckState.Checked:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self, QRect(), 3000)
            return

        if current:
            item.setCheckState(qt_state)
            self.itemChecked.emit(self.itemData(index), state)
            self._updateText()

    def toggleItem(self, index: int) -> None:
        if self.model().item(index).checkState() == Qt.CheckState.Checked:
            self.setItemChecked(index, False)
        else:
            self.setItemChecked(index, True)


# Inspiration from https://github.com/marcel-goldschen-ohm/ModelViewPyQt and https://github.com/zxt50330/qitemdelegate-example
class ReadStyleItemDelegate(QtWidgets.QStyledItemDelegate):
    buttonClicked = pyqtSignal(QModelIndex, ClickedButtonEnum)

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__()
        self.combobox = parent

        self.down_icon = QtGui.QImage(":/graphics/down.png")
        self.up_icon = QtGui.QImage(":/graphics/up.png")
        self.gray_down_icon = QtGui.QImage()
        self.gray_up_icon = QtGui.QImage()

        buffer = io.BytesIO()
        Image.open(io.BytesIO((graphics_path / "up.png").read_bytes())).convert("LA").save(buffer, format="png")
        self.gray_up_icon.loadFromData(buffer.getvalue())
        buffer = io.BytesIO()
        Image.open(io.BytesIO((graphics_path / "down.png").read_bytes())).convert("LA").save(buffer, format="png")
        self.gray_down_icon.loadFromData(buffer.getvalue())

        self.button_width = self.down_icon.width()
        self.button_padding = 5

        # Tooltip messages
        self.item_help: str = ""
        self.up_help: str = ""
        self.down_help: str = ""

        # Connect the signal to a slot in the delegate
        self.combobox.itemClicked.connect(self.itemClicked)

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> None:
        options = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        style = self.combobox.style()

        # Draw background with the same color as other widgets
        palette = self.combobox.palette()
        background_color = palette.color(QtGui.QPalette.ColorRole.Window)
        painter.fillRect(options.rect, background_color)

        style.drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_PanelItemViewItem, options, painter, self.combobox)

        painter.save()

        # Checkbox drawing logic
        checked = index.data(Qt.ItemDataRole.CheckStateRole)
        opts = QtWidgets.QStyleOptionButton()
        opts.state |= QtWidgets.QStyle.StateFlag.State_Active
        opts.rect = self.getCheckBoxRect(options)
        opts.state |= QtWidgets.QStyle.StateFlag.State_ReadOnly
        if checked:
            opts.state |= QtWidgets.QStyle.StateFlag.State_On
            style.drawPrimitive(
                QtWidgets.QStyle.PrimitiveElement.PE_IndicatorMenuCheckMark, opts, painter, self.combobox
            )
        else:
            opts.state |= QtWidgets.QStyle.StateFlag.State_Off
        if platform != "darwin":
            style.drawControl(QtWidgets.QStyle.ControlElement.CE_CheckBox, opts, painter, self.combobox)

        label = index.data(Qt.ItemDataRole.DisplayRole)
        rectangle = options.rect
        rectangle.setX(opts.rect.width() + 10)
        # We need the restore here so that text is colored properly
        painter.restore()
        painter.drawText(rectangle, Qt.AlignmentFlag.AlignVCenter, label)

        # Draw buttons
        if checked and (options.state & QtWidgets.QStyle.StateFlag.State_Selected):
            up_icon = self.up_icon
            down_icon = self.down_icon
            if index.row() == 0:
                up_icon = self.gray_up_icon
            if index.row() >= index.model().rowCount() - 1:
                down_icon = self.gray_down_icon

            up_rect = self._button_up_rect(options.rect)
            down_rect = self._button_down_rect(options.rect)
            painter.drawImage(up_rect, up_icon)
            painter.drawImage(down_rect, down_icon)

    def _button_up_rect(self, rect: QRect) -> QRect:
        return QRect(
            self.combobox.view().width() - (self.button_width * 2) - (self.button_padding * 2),
            rect.top() + (rect.height() - self.button_width) // 2,
            self.button_width,
            self.button_width,
        )

    def _button_down_rect(self, rect: QRect = QRect(10, 1, 12, 12)) -> QRect:
        return QRect(
            self.combobox.view().width() - self.button_padding - self.button_width,
            rect.top() + (rect.height() - self.button_width) // 2,
            self.button_width,
            self.button_width,
        )

    def getCheckBoxRect(self, option: QtWidgets.QStyleOptionViewItem) -> QRect:
        # Get size of a standard checkbox.
        opts = QtWidgets.QStyleOptionButton()
        style = option.widget.style()
        checkBoxRect = style.subElementRect(QtWidgets.QStyle.SubElement.SE_CheckBoxIndicator, opts, None)
        y = option.rect.y()
        h = option.rect.height()
        checkBoxTopLeftCorner = QPoint(5, int(y + h / 2 - checkBoxRect.height() / 2))

        return QRect(checkBoxTopLeftCorner, checkBoxRect.size())

    def itemClicked(self, index: QModelIndex, pos: QPoint) -> None:
        item_rect = self.combobox.view().visualRect(index)
        checked = index.data(Qt.ItemDataRole.CheckStateRole)
        button_up_rect = self._button_up_rect(item_rect)
        button_down_rect = self._button_down_rect(item_rect)

        if checked and button_up_rect.contains(pos):
            self.buttonClicked.emit(index, ClickedButtonEnum.up)
        elif checked and button_down_rect.contains(pos):
            self.buttonClicked.emit(index, ClickedButtonEnum.down)
        else:
            self.buttonClicked.emit(index, ClickedButtonEnum.main)

    def setToolTip(self, item: str = "", up: str = "", down: str = "") -> None:
        if item:
            self.item_help = item
        if up:
            self.up_help = up
        if down:
            self.down_help = down

    def helpEvent(
        self,
        event: QtGui.QHelpEvent,
        view: QtWidgets.QAbstractItemView,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        item_rect = view.visualRect(index)
        button_up_rect = self._button_up_rect(item_rect)
        button_down_rect = self._button_down_rect(item_rect)
        checked = index.data(Qt.ItemDataRole.CheckStateRole)

        if checked == Qt.CheckState.Checked and button_up_rect.contains(event.pos()):
            QtWidgets.QToolTip.showText(event.globalPos(), self.up_help, self.combobox, QRect(), 3000)
        elif checked == Qt.CheckState.Checked and button_down_rect.contains(event.pos()):
            QtWidgets.QToolTip.showText(event.globalPos(), self.down_help, self.combobox, QRect(), 3000)
        else:
            QtWidgets.QToolTip.showText(event.globalPos(), self.item_help, self.combobox, QRect(), 3000)
        return True

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> QSize:
        # Reimpliment standard combobox sizeHint. Only height is used by view, width is ignored
        menu_option = QtWidgets.QStyleOptionMenuItem()
        return self.combobox.style().sizeFromContents(
            QtWidgets.QStyle.ContentsType.CT_MenuItem, menu_option, option.rect.size(), self.combobox
        )


# Multiselect combobox from: https://gis.stackexchange.com/a/351152 (with custom changes)
class CheckableOrderComboBox(QtWidgets.QComboBox):
    itemClicked = pyqtSignal(QModelIndex, QPoint)
    dropdownClosed = pyqtSignal(list)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        itemDelegate = ReadStyleItemDelegate(self)
        itemDelegate.setToolTip(
            "Select which read tag(s) to use", "Move item up in priority", "Move item down in priority"
        )
        self.setItemDelegate(itemDelegate)

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

        # Go on a bit of a merry-go-round with the signals to avoid custom model/view
        self.itemDelegate().buttonClicked.connect(self.buttonClicked)

        # Keeps track of when the combobox list is shown
        self.justShown = False

    # Longstanding bug that is fixed almost everywhere but in Linux/Windows pip wheels
    # https://stackoverflow.com/questions/65826378/how-do-i-use-qcombobox-setplaceholdertext/65830989#65830989
    def paintEvent(self, event: QEvent) -> None:
        painter = QtWidgets.QStylePainter(self)
        painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.Text))

        # draw the combobox frame, focusrect and selected etc.
        opt = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(opt)
        painter.drawComplexControl(QtWidgets.QStyle.ComplexControl.CC_ComboBox, opt)

        if self.currentIndex() < 0:
            opt.palette.setBrush(
                QtGui.QPalette.ColorRole.ButtonText,
                opt.palette.brush(QtGui.QPalette.ColorRole.ButtonText).color(),
            )
            if self.placeholderText():
                opt.currentText = self.placeholderText()

        # draw the icon and text
        painter.drawControl(QtWidgets.QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def buttonClicked(self, index: QModelIndex, button: ClickedButtonEnum) -> None:
        if button == ClickedButtonEnum.up:
            self.moveItem(index.row(), index.row() - 1)
        elif button == ClickedButtonEnum.down:
            self.moveItem(index.row(), index.row() + 1)
        else:
            self.toggleItem(index.row())

    def resizeEvent(self, event: Any) -> None:
        # Recompute text to elide as needed
        super().resizeEvent(event)
        self._updateText()

    def eventFilter(self, obj: Any, event: Any) -> bool:
        # Allow events before the combobox list is shown
        if obj == self.view().viewport():
            # We record that the combobox list has been shown
            if event.type() == QEvent.Type.Show:
                self.justShown = True
            # We record that the combobox list has hidden,
            # this will happen if the user does not make a selection
            # but clicks outside of the combobox list or presses escape
            if event.type() == QEvent.Type.Hide:
                self._updateText()
                self.justShown = False
                # Reverse as the display order is in "priority" order for the user whereas overlay requires reversed
                self.dropdownClosed.emit(self.currentData())
            # QEvent.Type.MouseButtonPress is inconsistent on activation because double clicks are a thing
            if event.type() == QEvent.Type.MouseButtonRelease:
                # If self.justShown is true it means that they clicked on the combobox to change the checked items
                # This is standard behavior (on macos) but I think it is surprising when it has a multiple select
                if self.justShown:
                    self.justShown = False
                    return True

                # Find the current index and item
                index = self.view().indexAt(event.pos())
                if index.isValid():
                    self.itemClicked.emit(index, event.pos())
                    return True

        return False

    def currentData(self) -> list[Any]:
        # Return the list of all checked items data
        res = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.CheckState.Checked:
                res.append(self.itemData(i))
        return res

    def addItem(self, text: str, data: Any = None) -> None:
        super().addItem(text, data)
        # Need to enable the checkboxes and require one checked item
        # Expected that state of *all* checkboxes will be set ('adjust_tags_combo' in taggerwindow.py)
        if self.count() == 1:
            self.model().item(0).setCheckState(Qt.CheckState.Checked)

        # Add room for "move" arrows
        text_width = self.fontMetrics().boundingRect(text).width()
        checkbox_width = 40
        total_width = text_width + checkbox_width + (self.itemDelegate().button_width * 2)
        if total_width > self.view().minimumWidth():
            self.view().setMinimumWidth(total_width)

    def moveItem(self, index: int, row: int) -> None:
        """'Move' an item. Really swap the data and titles around on the two items"""

        model = cast(QtGui.QStandardItemModel, self.model())
        if row == index or row < 0 or row >= model.rowCount():
            return
        cur = model.item(index)
        new = model.item(row)
        cur_clone = cur.clone()
        new_clone = new.clone()

        model.setItem(cur.row(), cur.column(), new_clone)
        model.setItem(new.row(), new.column(), cur_clone)

    def _updateText(self) -> None:
        texts = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.CheckState.Checked:
                texts.append(item.text())
        text = ", ".join(texts)

        # Compute elided text (with "...")

        # The QStyleOptionComboBox is needed for the call to subControlRect
        so = QtWidgets.QStyleOptionComboBox()
        # init with the current widget
        so.initFrom(self)

        # Ask the style for the size of the text field
        rect = self.style().subControlRect(
            QtWidgets.QStyle.ComplexControl.CC_ComboBox, so, QtWidgets.QStyle.SubControl.SC_ComboBoxEditField
        )

        # Compute the elided text
        elidedText = self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, rect.width())

        # This CheckableComboBox does not use the index, so we clear it and set the placeholder text
        self.setCurrentIndex(-1)
        self.setPlaceholderText(elidedText)

    def setItemChecked(self, index: Any, state: bool) -> None:
        qt_state = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        item = self.model().item(index)
        current = self.currentData()
        # If we have at least one item checked emit itemChecked with the current check state and update text
        # Require at least one item to be checked and provide a tooltip
        if len(current) == 1 and not state and item.checkState() == Qt.CheckState.Checked:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self, QRect(), 3000)
            return

        if current:
            item.setCheckState(qt_state)
            self._updateText()

    def toggleItem(self, index: int) -> None:
        if self.model().item(index).checkState() == Qt.CheckState.Checked:
            self.setItemChecked(index, False)
        else:
            self.setItemChecked(index, True)
