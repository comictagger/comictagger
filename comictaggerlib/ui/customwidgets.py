"""Custom widgets"""

from __future__ import annotations

from typing import Any

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import QEvent, QModelIndex, QRect, Qt, pyqtSignal

from comictaggerlib.graphics import graphics_path


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


class CheckBoxStyle(QtWidgets.QProxyStyle):
    def subElementRect(
        self, element: QtWidgets.QStyle.SubElement, option: QtWidgets.QStyleOption, widget: QtWidgets.QWidget = None
    ) -> QRect:
        r = super().subElementRect(element, option, widget)
        if element == QtWidgets.QStyle.SE_ItemViewItemCheckIndicator:
            r.moveCenter(option.rect.center())
        return r


class SortLabelTableWidgetItem(QtWidgets.QTableWidgetItem):
    """Custom QTableWidgetItem to sort with '-' below numbers"""

    def __lt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        if self.text() == "-":
            return False
        if other.text() == "-":
            return True
        return super().__lt__(other)


class HoverQLabel(QtWidgets.QLabel):
    """A QLabel with two QButtons that appear on hover"""

    def __init__(self, text: str, parent: TableComboBox):
        super().__init__(text, parent=parent)
        self.combobox = parent

        self.button_up = QtWidgets.QPushButton(QtGui.QIcon(str(graphics_path / "up.png")), "", self)
        self.button_up.clicked.connect(self.button_up_clicked)
        self.button_up.setToolTip("Move style up in order")
        self.button_up.hide()

        self.button_down = QtWidgets.QPushButton(QtGui.QIcon(str(graphics_path / "down.png")), "", self)
        self.button_down.clicked.connect(self.button_down_clicked)
        self.button_down.setToolTip("Move style down in order")
        self.button_down.hide()

        # Place 'down' button on left side
        self.button_down.resize(self.button_down.sizeHint())

        # Place 'up' button on right side
        self.button_up.resize(self.button_up.sizeHint())

    def hideButtons(self) -> None:
        self.button_up.hide()
        self.button_down.hide()

    def showHideButtons(self, index: QModelIndex) -> None:
        # TODO Better to iterate over all? Send in check state too?
        item = self.combobox.tableWidget.item(index.row(), 1)
        item_checked = item.checkState()
        if index.row() != self.combobox.tableWidget.currentRow():
            # Hide the previous row buttons
            self.button_up.hide()
            self.button_down.hide()
        elif item_checked == Qt.Checked:
            self.button_up.show()
            self.button_down.show()
        else:
            self.button_up.hide()
            self.button_down.hide()

    def enterEvent(self, event: QEvent | None) -> None:
        # Need to manually set the rest of the row highlighted
        index: QModelIndex = self.combobox.tableWidget.indexAt(self.pos())
        self.combobox.tableWidget.selectRow(index.row())

        super().enterEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        index: QModelIndex = self.combobox.tableWidget.indexAt(self.pos())
        if self.combobox.justShown:
            self.combobox.justShown = False
        else:
            self.combobox.toggleItem(index)

    def resizeEvent(self, event: Any | None = None) -> None:
        self.button_down.move(self.width() - self.button_up.width(), (self.height() - self.button_up.height()) // 2)
        self.button_up.move(
            self.width() - self.button_up.width() - self.button_down.width(),
            (self.height() - self.button_up.height()) // 2,
        )

    def button_up_clicked(self) -> None:
        index: QModelIndex = self.combobox.tableWidget.indexAt(self.pos())
        self.combobox.moveItem(index, True)

    def button_down_clicked(self) -> None:
        index: QModelIndex = self.combobox.tableWidget.indexAt(self.pos())
        self.combobox.moveItem(index, False)


class TableComboBox(QtWidgets.QComboBox):
    itemChanged = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        # Longest width of read style label
        self.longest = 0

        self.tableWidget = QtWidgets.QTableWidget()
        self.setModel(self.tableWidget.model())
        self.setView(self.tableWidget)

        centered_checkbox_style = CheckBoxStyle()
        self.tableWidget.setStyle(centered_checkbox_style)

        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels([" # ", " Enabled ", "Read Style"])
        self.tableWidget.horizontalHeaderItem(0).setToolTip("Order of overlay operations")
        self.tableWidget.horizontalHeaderItem(1).setToolTip("Whether the style is enabled or not")
        self.tableWidget.horizontalHeaderItem(2).setToolTip("Name of the read style")

        self.tableWidget.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.tableWidget.resizeColumnsToContents()

        self.tableWidget.verticalHeader().setVisible(False)

        self.tableWidget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tableWidget.setShowGrid(False)

        # Prevent popup from closing when clicking on an item
        self.tableWidget.viewport().installEventFilter(self)

        # Keeps track of when the combobox list is shown
        self.justShown = False

        self.tableWidget.currentCellChanged.connect(self.current_cell_changed)

    def current_cell_changed(self, cur_row: int, cur_col: int, prev_row: int, prev_col: int) -> None:
        # When rebuilding, cur_row -1 will occur and cause a crash
        if cur_row == -1:
            return
        if prev_row == -1:
            # First time open
            cur_index = self.tableWidget.indexFromItem(self.tableWidget.item(cur_row, 0))
            self.tableWidget.cellWidget(cur_row, 2).showHideButtons(cur_index)
        elif cur_row != prev_row:
            # Hide previous
            prev_index = self.tableWidget.indexFromItem(self.tableWidget.item(prev_row, 0))
            self.tableWidget.cellWidget(prev_row, 2).showHideButtons(prev_index)
            # Show current
            cur_index = self.tableWidget.indexFromItem(self.tableWidget.item(cur_row, 0))
            self.tableWidget.cellWidget(cur_row, 2).showHideButtons(cur_index)

    def _longest_label(self) -> None:
        # Depending on "short" names for metadata, "Read Style" header or metadata name may be longer
        style_header_width = 0
        header_item = self.tableWidget.horizontalHeaderItem(2)
        if header_item is not None:
            font_metrics = QtGui.QFontMetrics(header_item.font())
            style_header_width = font_metrics.width(header_item.text())

        header_width = 0
        for col in range(self.tableWidget.columnCount() - 1):  # Skip "read style" as already done above
            header_item = self.tableWidget.horizontalHeaderItem(col)
            if header_item is not None:
                font_metrics = QtGui.QFontMetrics(header_item.font())
                text_width = font_metrics.width(header_item.text())
                header_width += text_width

        # Now check items
        for i in range(self.count()):
            hlabel = self.tableWidget.cellWidget(i, 2)
            hlabel_width = (
                style_header_width if style_header_width > hlabel.sizeHint().width() else hlabel.sizeHint().width()
            )
            # Get sizeHint of one button and double it
            total_width = hlabel_width + header_width + (hlabel.button_up.sizeHint().width() * 2)

            if total_width > self.longest:
                self.longest = total_width

    def _resizeTable(self) -> None:
        self._longest_label()
        self.tableWidget.setMinimumWidth(self.longest)

    def resizeEvent(self, event: Any | None = None) -> None:
        super().resizeEvent(event)
        self._updateText()

    def eventFilter(self, obj: Any, event: Any) -> bool:
        # Allow events before the combobox list is shown
        if obj == self.tableWidget.viewport():
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
                # TODO The first click in the table is currently consumed
                if self.justShown:
                    self.justShown = False
                    return True

                # Find the current index and item
                index = self.tableWidget.indexAt(event.pos())
                self.toggleItem(index)
                return True
        return False

    def emptyTable(self) -> None:
        self.tableWidget.setRowCount(0)
        self.longest = 0

    def moveItem(self, index: QModelIndex, up: bool = False, row: int | None = None) -> None:
        """'Move' an item. Really swap the data and titles around on the two rows"""
        if row is None:
            adjust = -1 if up else 1
            row = index.row() + adjust

        # Grab values for the rows to swap
        cur_data = self.tableWidget.item(index.row(), 0).data(Qt.UserRole)
        cur_title = self.tableWidget.cellWidget(index.row(), 2).text()
        swap_data = self.tableWidget.item(row, 0).data(Qt.UserRole)
        swap_title = self.tableWidget.cellWidget(row, 2).text()

        self.tableWidget.item(row, 0).setData(Qt.UserRole, cur_data)
        self.tableWidget.cellWidget(row, 2).setText(cur_title)
        self.tableWidget.item(index.row(), 0).setData(Qt.UserRole, swap_data)
        self.tableWidget.cellWidget(index.row(), 2).setText(swap_title)

        # Hide buttons and clear selection to indicate to user an action has taken place
        self.tableWidget.cellWidget(index.row(), 2).hideButtons()
        self.tableWidget.clearSelection()

        self.itemChanged.emit()

    def addItem(self, text: str = "", data: Any | None = None, rowPosition: int | None = None) -> None:
        rowPosition = (
            self.tableWidget.rowCount()
            if rowPosition is None or rowPosition > self.tableWidget.rowCount()
            else rowPosition
        )
        self.tableWidget.insertRow(rowPosition)

        sortTblItem = SortLabelTableWidgetItem()
        sortTblItem.setTextAlignment(Qt.AlignCenter)
        self.tableWidget.setItem(rowPosition, 0, sortTblItem)

        chkBoxItem = QtWidgets.QTableWidgetItem()
        # Set to true to get around the "one item must be checked" check for setItemChecked
        chkBoxItem.setCheckState(Qt.Checked)

        self.tableWidget.setItem(rowPosition, 1, chkBoxItem)
        self.tableWidget.setCellWidget(rowPosition, 2, HoverQLabel(text, parent=self))
        self.tableWidget.item(rowPosition, 0).setData(Qt.UserRole, data)

        self._updateLabels()
        self._updateText()
        # Manual as resizeEvent doesn't trigger
        self._resizeTable()

    def findData(self, data: str, role: int = Qt.UserRole) -> QModelIndex | None:
        for i in range(self.count()):
            item = self.itemData(i)
            if item == data:
                return self.tableWidget.indexFromItem(self.tableWidget.item(i, 0))
        return None

    def currentData(self) -> list[str]:
        res = []
        for i in range(self.count()):
            item = self.tableWidget.item(i, 1)
            if item.checkState() == Qt.Checked:
                res.append(self.itemData(i))
        return res

    def _setOrderNumbers(self) -> None:
        """Recalculate the order numbers"""
        current_data = self.currentData()
        text = "-"

        for j in range(self.count()):
            item = self.itemData(j)
            for i, cur in enumerate(current_data):
                if item == cur:
                    text = str(i + 1)

            self.tableWidget.item(j, 0).setText(text)

    def _updateLabels(self) -> None:
        """Update order label text and set button enablement"""
        cur_data_len = len(self.currentData())
        for i in range(self.count()):
            label = self.tableWidget.item(i, 0)
            checked = self.tableWidget.item(i, 1).checkState()
            data = self.itemData(i)
            label_num = "-"
            enable_up = True
            enable_down = True

            # Go through currentData
            for j, cur_data in enumerate(self.currentData()):
                if cur_data == data:
                    label_num = str(j + 1)
                    if cur_data_len == 1:
                        enable_up = False
                        enable_down = False
                    elif j == 0:
                        enable_up = False
                    elif j + 1 == cur_data_len:
                        enable_down = False

            label.setText(label_num)

            # Enable/disable hover buttons
            self.tableWidget.cellWidget(i, 2).button_up.setEnabled(enable_up)
            self.tableWidget.cellWidget(i, 2).button_down.setEnabled(enable_down)

        self.tableWidget.sortItems(0)
        self.tableWidget.clearSelection()

    def _nextOrderNumber(self) -> int:
        return len(self.currentData()) - 1

    def _updateText(self) -> None:
        texts = []
        for i in range(self.count()):
            item = self.tableWidget.item(i, 1)
            item_texts = self.tableWidget.cellWidget(i, 2)
            if item.checkState() == Qt.Checked:
                texts.append(item_texts.text())
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

    def setItemChecked(self, index: QModelIndex, state: bool) -> None:
        if index is None:
            return
        qt_state = Qt.Checked if state else Qt.Unchecked
        item = self.tableWidget.item(index.row(), 1)
        current_len = len(self.currentData())

        # Require at least one item to be checked and provide a tooltip
        if current_len == 1 and not state and item.checkState() == Qt.Checked:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self, QRect(), 3000)
            return

        if current_len > 0:
            item.setCheckState(qt_state)
            if not state:
                # Hide hover buttons of shown row (before it changes row)
                self.tableWidget.cellWidget(index.row(), 2).showHideButtons(index)
            self._setOrderNumbers()
            self._updateLabels()
            self._updateText()
            self.itemChanged.emit()

    def toggleItem(self, index: QModelIndex) -> None:
        cxb_index = self.model().index(index.row(), 1)
        if self.model().data(cxb_index, Qt.CheckStateRole) == Qt.Checked:
            self.setItemChecked(cxb_index, False)
        else:
            self.setItemChecked(cxb_index, True)
