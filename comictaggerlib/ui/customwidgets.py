"""Custom widgets"""

from __future__ import annotations

from typing import Any

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import QEvent, QModelIndex, QRect, Qt, pyqtSignal


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


class SortLabelTableWidgetItem(QtWidgets.QTableWidgetItem):
    """Custom QTableWidgetItem to sort with '-' below numbers"""

    def __lt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        if self.text() == "-":
            return False
        if other.text() == "-":
            return True
        return super().__lt__(other)


class HoverQLabel(QtWidgets.QLabel):
    def __init__(self, text: str, parent: TableComboBox):
        super().__init__(text, parent=parent)
        self.combobox = parent

        self.button_up = QtWidgets.QPushButton("Up", self)
        self.button_up.clicked.connect(self.button_up_clicked)
        self.button_up.hide()

        self.button_down = QtWidgets.QPushButton("Down", self)
        self.button_down.clicked.connect(self.button_down_clicked)
        self.button_down.hide()

        # Place 'down' button on left side
        self.button_down.move(self.width() - self.button_down.width(), 0)
        self.button_down.resize(self.button_down.sizeHint())

        # Place 'up' button on right side
        self.button_up.move(self.width() - self.button_up.width() - self.button_down.width(), 0)
        self.button_up.resize(self.button_up.sizeHint())

        # self.resizeEvent = self.adjustButton

    def _showHideButtons(self, index: QModelIndex) -> None:
        # TODO Better to iterate over all?
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
        self.combobox._move_item(index, True)

    def button_down_clicked(self) -> None:
        index: QModelIndex = self.combobox.tableWidget.indexAt(self.pos())
        self.combobox._move_item(index, False)


class TableComboBox(QtWidgets.QComboBox):
    itemChecked = pyqtSignal(str, bool)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.tableWidget = QtWidgets.QTableWidget()
        self.setModel(self.tableWidget.model())
        self.setView(self.tableWidget)

        self.tableWidget.setColumnCount(3)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setHorizontalHeaderLabels(["Order", "Enabled", "Read Style"])
        self.tableWidget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tableWidget.setShowGrid(False)
        self.tableWidget.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.tableWidget.resizeColumnsToContents()

        # Prevent popup from closing when clicking on an item
        self.tableWidget.viewport().installEventFilter(self)

        # Keeps track of when the combobox list is shown
        self.justShown = False

        self.tableWidget.currentCellChanged.connect(self.current_cell_changed)

    def current_cell_changed(self, cur_row: int, cur_col: int, prev_row: int, prev_col: int) -> None:
        if prev_row == -1:
            # First time open
            cur_index = self.tableWidget.indexFromItem(self.tableWidget.item(cur_row, 0))
            self.tableWidget.cellWidget(cur_row, 2)._showHideButtons(cur_index)
        elif cur_row != prev_row:
            # Hide previous
            prev_index = self.tableWidget.indexFromItem(self.tableWidget.item(prev_row, 0))
            self.tableWidget.cellWidget(prev_row, 2)._showHideButtons(prev_index)
            # Show current
            cur_index = self.tableWidget.indexFromItem(self.tableWidget.item(cur_row, 0))
            self.tableWidget.cellWidget(cur_row, 2)._showHideButtons(cur_index)

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

    def _move_item(self, index: QModelIndex, up: bool) -> None:
        adjust = -1 if up else 1
        cur_item = self.tableWidget.item(index.row(), 0)
        cur_item_data = cur_item.data(Qt.UserRole)
        cur_key, cur_value = next(iter(cur_item_data.items()))

        swap_item = self.tableWidget.item(index.row() + adjust, 0)
        swap_item_data = swap_item.data(Qt.UserRole)
        swap_key, swap_value = next(iter(swap_item_data.items()))

        # While the buttons should not be enabled, check for valid numbers to swap anyway
        if cur_value != -1 and swap_value != -1:
            cur_item.setData(Qt.UserRole, {cur_key: swap_value})
            swap_item.setData(Qt.UserRole, {swap_key: cur_value})

            self._updateLabels()
            # Selected (highlighted) row moves so is no longer under the mouse
            self.tableWidget.selectRow(index.row())

    def addItem(self, label: str = "-", checked: bool = False, text: str = "", data: Any | None = None) -> None:
        rowPosition = self.tableWidget.rowCount()
        self.tableWidget.insertRow(rowPosition)

        self.tableWidget.setItem(rowPosition, 0, SortLabelTableWidgetItem(label))

        chkBoxItem = QtWidgets.QTableWidgetItem()
        chkBoxItem.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.tableWidget.setItem(rowPosition, 1, chkBoxItem)
        self.tableWidget.setCellWidget(rowPosition, 2, HoverQLabel(text, parent=self))
        self.tableWidget.item(rowPosition, 0).setData(Qt.UserRole, data)

        self._updateLabels()
        self._updateText()

    def currentData(self) -> dict[str, int]:
        # Return the list of all checked items data
        res = {}
        for i in range(self.count()):
            item = self.tableWidget.item(i, 1)
            if item.checkState() == Qt.Checked:
                res.update(self.itemData(i))
        return res

    def _setOrderNumbers(self) -> None:
        """Recalculate the order numbers; 0,2 -> 0,1"""
        current_data = self.currentData()
        # Convert dict to list of tuples
        data = list(current_data.items())
        # Sort the list by value (second element in the tuple)
        sorted_data = sorted(data, key=lambda x: x[1])
        for i, value in enumerate(sorted_data):
            for j in range(self.count()):
                item = self.itemData(j)
                if list(item.keys())[0] == value[0]:
                    self.tableWidget.item(j, 0).setData(Qt.UserRole, {value[0]: i})

    def _updateLabels(self) -> None:
        """Update order label text and set button enablement"""
        cur_data_len = len(self.currentData())
        for i in range(self.count()):
            label = self.tableWidget.item(i, 0)
            data = self.itemData(i)
            k, val = next(iter(data.items()))
            val += 1
            text = "-" if val == 0 else str(val)
            label.setText(text)

            # Enable all buttons
            self.tableWidget.cellWidget(i, 2).button_up.setEnabled(True)
            self.tableWidget.cellWidget(i, 2).button_down.setEnabled(True)

            # Disable top up button and bottom down button
            if val == 1:
                self.tableWidget.cellWidget(i, 2).button_up.setEnabled(False)
                # Disable the down button if single item. Show buttons as a sign it is checked
                if val == cur_data_len:
                    self.tableWidget.cellWidget(i, 2).button_down.setEnabled(False)
            elif val == cur_data_len:
                self.tableWidget.cellWidget(i, 2).button_down.setEnabled(False)

        self.tableWidget.sortItems(0)

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
        qt_state = Qt.Checked if state else Qt.Unchecked
        item = self.tableWidget.item(index.row(), 1)
        current = self.currentData()
        # If we have at least one item checked emit itemChecked with the current check state and update text
        # Require at least one item to be checked and provide a tooltip
        if len(current) == 1 and not state and item.checkState() == Qt.Checked:
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.toolTip(), self, QRect(), 3000)
            return

        if len(current) > 0:
            item.setCheckState(qt_state)
            item_data: dict[str, int] = self.itemData(index.row())
            key_name = list(item_data.keys())[0]
            if state:
                next_num = self._nextOrderNumber()
                data = {key_name: next_num}
                self.tableWidget.item(index.row(), 0).setText(str(next_num + 1))
                self.tableWidget.item(index.row(), 0).setData(Qt.UserRole, data)
            else:
                data = {key_name: -1}
                self.tableWidget.item(index.row(), 0).setText("-")
                self.tableWidget.item(index.row(), 0).setData(Qt.UserRole, data)
                # We need to check the order numbers as any number could have been removed
                self._setOrderNumbers()

            self.itemChecked.emit(key_name, state)
            self._updateText()
            self._updateLabels()
            # Check if buttons need to be shown or hidden
            self.tableWidget.cellWidget(index.row(), 2)._showHideButtons(index)
            # As the sort may have moved the highlighted row, select what's under the mouse
            self.tableWidget.selectRow(index.row())

    def toggleItem(self, index: QModelIndex) -> None:
        cxb_index = self.model().index(index.row(), 1)
        if self.model().data(cxb_index, Qt.CheckStateRole) == Qt.Checked:
            self.setItemChecked(cxb_index, False)
        else:
            self.setItemChecked(cxb_index, True)
