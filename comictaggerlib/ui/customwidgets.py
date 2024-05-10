"""Custom widgets"""

from __future__ import annotations

from enum import auto
from sys import platform
from typing import Any

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt, pyqtSignal

from comicapi.utils import StrEnum
from comictaggerlib.graphics import graphics_path


class ClickedButtonEnum(StrEnum):
    up = auto()
    down = auto()
    main = auto()


# Multiselect combobox from: https://gis.stackexchange.com/a/351152 (with custom changes)
class CheckableComboBox(QtWidgets.QComboBox):
    itemChecked = pyqtSignal(str, bool)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

        # Keeps track of when the combobox list is shown
        self.justShown = False

    def resizeEvent(self, event: Any) -> None:
        # Recompute text to elide as needed
        super().resizeEvent(event)
        self._updateText()

    def eventFilter(self, obj: Any, event: Any) -> bool:
        # Allow events before the combobox list is shown
        if obj == self.view().viewport():
            # We record that the combobox list has been shown
            if event.type() == QEvent.Show:
                self.justShown = True
            # We record that the combobox list has hidden,
            # this will happen if the user does not make a selection
            # but clicks outside of the combobox list or presses escape
            if event.type() == QEvent.Hide:
                self._updateText()
                self.justShown = False
            # QEvent.MouseButtonPress is inconsistent on activation because double clicks are a thing
            if event.type() == QEvent.MouseButtonRelease:
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
            if item.checkState() == Qt.Checked:
                res.append(self.itemData(i))
        return res

    def addItem(self, text: str, data: Any = None) -> None:
        super().addItem(text, data)
        # Need to enable the checkboxes and require one checked item
        # Expected that state of *all* checkboxes will be set ('adjust_save_style_combo' in taggerwindow.py)
        if self.count() == 1:
            self.model().item(0).setCheckState(Qt.CheckState.Checked)

    def _updateText(self) -> None:
        texts = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                texts.append(item.text())
        text = ", ".join(texts)

        # Compute elided text (with "...")

        # The QStyleOptionComboBox is needed for the call to subControlRect
        so = QtWidgets.QStyleOptionComboBox()
        # init with the current widget
        so.initFrom(self)

        # Ask the style for the size of the text field
        rect = self.style().subControlRect(QtWidgets.QStyle.CC_ComboBox, so, QtWidgets.QStyle.SC_ComboBoxEditField)

        # Compute the elided text
        elidedText = self.fontMetrics().elidedText(text, Qt.ElideRight, rect.width())

        # This CheckableComboBox does not use the index, so we clear it and set the placeholder text
        self.setCurrentIndex(-1)
        self.setPlaceholderText(elidedText)

    def setItemChecked(self, index: Any, state: bool) -> None:
        qt_state = Qt.Checked if state else Qt.Unchecked
        item = self.model().item(index)
        current = self.currentData()
        # If we have at least one item checked emit itemChecked with the current check state and update text
        # Require at least one item to be checked and provide a tooltip
        if len(current) == 1 and not state and item.checkState() == Qt.Checked:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self, QRect(), 3000)
            return

        if len(current) > 0:
            item.setCheckState(qt_state)
            self.itemChecked.emit(self.itemData(index), state)
            self._updateText()

    def toggleItem(self, index: int) -> None:
        if self.model().item(index).checkState() == Qt.Checked:
            self.setItemChecked(index, False)
        else:
            self.setItemChecked(index, True)


# Inspiration from https://github.com/marcel-goldschen-ohm/ModelViewPyQt and https://github.com/zxt50330/qitemdelegate-example
class ReadStyleItemDelegate(QtWidgets.QStyledItemDelegate):
    buttonClicked = pyqtSignal(QModelIndex, ClickedButtonEnum)

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__()
        self.combobox = parent

        self.down_icon = QtGui.QImage(str(graphics_path / "down.png"))
        self.up_icon = QtGui.QImage(str(graphics_path / "up.png"))

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
        background_color = palette.color(QtGui.QPalette.Window)
        painter.fillRect(options.rect, background_color)

        style.drawPrimitive(QtWidgets.QStyle.PE_PanelItemViewItem, options, painter, self.combobox)

        painter.save()

        # Checkbox drawing logic
        checked = index.data(Qt.CheckStateRole)
        opts = QtWidgets.QStyleOptionButton()
        opts.state |= QtWidgets.QStyle.State_Active
        opts.rect = self.getCheckBoxRect(options)
        opts.state |= QtWidgets.QStyle.State_ReadOnly
        if checked:
            opts.state |= QtWidgets.QStyle.State_On
            style.drawPrimitive(
                QtWidgets.QStyle.PrimitiveElement.PE_IndicatorMenuCheckMark, opts, painter, self.combobox
            )
        else:
            opts.state |= QtWidgets.QStyle.State_Off
        if platform != "darwin":
            style.drawControl(QtWidgets.QStyle.CE_CheckBox, opts, painter, self.combobox)

        label = index.data(Qt.DisplayRole)
        rectangle = options.rect
        rectangle.setX(opts.rect.width() + 10)
        painter.drawText(rectangle, Qt.AlignVCenter, label)

        # Draw buttons
        if checked and (options.state & QtWidgets.QStyle.State_Selected):
            up_rect = self._button_up_rect(options.rect)
            down_rect = self._button_down_rect(options.rect)

            painter.drawImage(up_rect, self.up_icon)
            painter.drawImage(down_rect, self.down_icon)

        painter.restore()

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
        checkBoxRect = style.subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, opts, None)
        y = option.rect.y()
        h = option.rect.height()
        checkBoxTopLeftCorner = QPoint(5, int(y + h / 2 - checkBoxRect.height() / 2))

        return QRect(checkBoxTopLeftCorner, checkBoxRect.size())

    def itemClicked(self, index: QModelIndex, pos: QPoint) -> None:
        item_rect = self.combobox.view().visualRect(index)
        checked = index.data(Qt.CheckStateRole)
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
        checked = index.data(Qt.CheckStateRole)

        if checked == Qt.Checked and button_up_rect.contains(event.pos()):
            QtWidgets.QToolTip.showText(event.globalPos(), self.up_help, self.combobox, QRect(), 3000)
        elif checked == Qt.Checked and button_down_rect.contains(event.pos()):
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
            "Select which read style(s) to use", "Move item up in priority", "Move item down in priority"
        )
        self.setItemDelegate(itemDelegate)

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

        # Go on a bit of a merry-go-round with the signals to avoid custom model/view
        self.itemDelegate().buttonClicked.connect(self.buttonClicked)

        # Keeps track of when the combobox list is shown
        self.justShown = False

    def buttonClicked(self, index: QModelIndex, button: ClickedButtonEnum) -> None:
        if button == ClickedButtonEnum.up:
            self.moveItem(index.row(), up=True)
        elif button == ClickedButtonEnum.down:
            self.moveItem(index.row(), up=False)
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
            if event.type() == QEvent.Show:
                self.justShown = True
            # We record that the combobox list has hidden,
            # this will happen if the user does not make a selection
            # but clicks outside of the combobox list or presses escape
            if event.type() == QEvent.Hide:
                self._updateText()
                self.justShown = False
                self.dropdownClosed.emit(self.currentData())
            # QEvent.MouseButtonPress is inconsistent on activation because double clicks are a thing
            if event.type() == QEvent.MouseButtonRelease:
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
            if item.checkState() == Qt.Checked:
                res.append(self.itemData(i))
        return res

    def addItem(self, text: str, data: Any = None) -> None:
        super().addItem(text, data)
        # Need to enable the checkboxes and require one checked item
        # Expected that state of *all* checkboxes will be set ('adjust_save_style_combo' in taggerwindow.py)
        if self.count() == 1:
            self.model().item(0).setCheckState(Qt.CheckState.Checked)

        # Add room for "move" arrows
        text_width = self.fontMetrics().width(text)
        checkbox_width = 40
        total_width = text_width + checkbox_width + (self.itemDelegate().button_width * 2)
        if total_width > self.view().minimumWidth():
            self.view().setMinimumWidth(total_width)

    def moveItem(self, index: int, up: bool = False, row: int | None = None) -> None:
        """'Move' an item. Really swap the data and titles around on the two items"""
        if row is None:
            adjust = -1 if up else 1
            row = index + adjust

        # TODO Disable buttons at top and bottom. Do a check here for now
        if up and index == 0:
            return
        if up is False and row == self.count():
            return

        # Grab values for the rows to swap
        cur_data = self.model().item(index).data(Qt.UserRole)
        cur_title = self.model().item(index).data(Qt.DisplayRole)
        cur_state = self.model().item(index).data(Qt.CheckStateRole)

        swap_data = self.model().item(row).data(Qt.UserRole)
        swap_title = self.model().item(row).data(Qt.DisplayRole)
        swap_state = self.model().item(row).checkState()

        self.model().item(row).setData(cur_data, Qt.UserRole)
        self.model().item(row).setCheckState(cur_state)
        self.model().item(row).setText(cur_title)

        self.model().item(index).setData(swap_data, Qt.UserRole)
        self.model().item(index).setCheckState(swap_state)
        self.model().item(index).setText(swap_title)

    def _updateText(self) -> None:
        texts = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                texts.append(item.text())
        text = ", ".join(texts)

        # Compute elided text (with "...")

        # The QStyleOptionComboBox is needed for the call to subControlRect
        so = QtWidgets.QStyleOptionComboBox()
        # init with the current widget
        so.initFrom(self)

        # Ask the style for the size of the text field
        rect = self.style().subControlRect(QtWidgets.QStyle.CC_ComboBox, so, QtWidgets.QStyle.SC_ComboBoxEditField)

        # Compute the elided text
        elidedText = self.fontMetrics().elidedText(text, Qt.ElideRight, rect.width())

        # This CheckableComboBox does not use the index, so we clear it and set the placeholder text
        self.setCurrentIndex(-1)
        self.setPlaceholderText(elidedText)

    def setItemChecked(self, index: Any, state: bool) -> None:
        qt_state = Qt.Checked if state else Qt.Unchecked
        item = self.model().item(index)
        current = self.currentData()
        # If we have at least one item checked emit itemChecked with the current check state and update text
        # Require at least one item to be checked and provide a tooltip
        if len(current) == 1 and not state and item.checkState() == Qt.Checked:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self, QRect(), 3000)
            return

        if len(current) > 0:
            item.setCheckState(qt_state)
            self._updateText()

    def toggleItem(self, index: int) -> None:
        if self.model().item(index).checkState() == Qt.Checked:
            self.setItemChecked(index, False)
        else:
            self.setItemChecked(index, True)
