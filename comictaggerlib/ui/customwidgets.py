"""Custom widgets"""

from __future__ import annotations

from typing import Any

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import QEvent, QRect, Qt, pyqtSignal


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
