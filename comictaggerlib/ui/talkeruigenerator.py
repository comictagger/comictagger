from __future__ import annotations

import argparse
import logging
from functools import partial
from typing import Any, NamedTuple

import settngs
from PyQt5 import QtCore, QtWidgets

from comictalker.comictalker import ComicTalker

logger = logging.getLogger(__name__)


class TalkerTab(NamedTuple):
    tab: QtWidgets.QWidget
    widgets: dict[str, QtWidgets.QWidget]


def generate_api_widgets(
    talker_id: str,
    sources: dict[str, QtWidgets.QWidget],
    config: settngs.Config[settngs.Namespace],
    layout: QtWidgets.QGridLayout,
    talkers: dict[str, ComicTalker],
) -> None:
    # *args enforces keyword arguments and allows position arguments to be ignored
    def call_check_api(*args: Any, le_url: QtWidgets.QLineEdit, le_key: QtWidgets.QLineEdit, talker_id: str) -> None:
        url = ""
        key = ""
        if le_key is not None:
            key = le_key.text().strip()
        if le_url is not None:
            url = le_url.text().strip()

        check_text, check_bool = talkers[talker_id].check_api_key(url, key)
        if check_bool:
            QtWidgets.QMessageBox.information(None, "API Test Success", check_text)
        else:
            QtWidgets.QMessageBox.warning(None, "API Test Failed", check_text)

    def show_key(le_key: QtWidgets.QLineEdit) -> None:
        current_state = le_key.echoMode()

        if current_state == 0:
            le_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.PasswordEchoOnEdit)
        else:
            le_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Normal)

    # get the actual config objects in case they have overwritten the default
    talker_key = config[1][f"talker_{talker_id}"][1][f"{talker_id}_key"]
    talker_url = config[1][f"talker_{talker_id}"][1][f"{talker_id}_url"]
    btn_test_row = None
    le_key = None
    le_url = None

    # only file settings are saved
    if talker_key.file:
        # record the current row so we know where to add the button
        btn_show_key = layout.rowCount()
        le_key = generate_textbox(talker_key, layout)
        le_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.PasswordEchoOnEdit)
        # To enable setting and getting
        sources["tabs"][talker_id].widgets[f"talker_{talker_id}_{talker_id}_key"] = le_key

    # only file settings are saved
    if talker_url.file:
        # record the current row so we know where to add the button
        # We overwrite so that the default will be next to the url text box
        btn_test_row = layout.rowCount()
        le_url = generate_textbox(talker_url, layout)
        # To enable setting and getting
        sources["tabs"][talker_id].widgets[f"talker_{talker_id}_{talker_id}_url"] = le_url

    # The key button row was recorded so we add the show/hide button
    if btn_show_key is not None:
        btn_show = QtWidgets.QPushButton("Show/Hide")
        layout.addWidget(btn_show, btn_show_key, 2)
        btn_show.clicked.connect(partial(show_key, le_key=le_key))

    # The button row was recorded so we add it
    if btn_test_row is not None:
        btn = QtWidgets.QPushButton("Test API")
        layout.addWidget(btn, btn_test_row, 2)
        # partial is used as connect will pass in event information
        btn.clicked.connect(partial(call_check_api, le_url=le_url, le_key=le_key, talker_id=talker_id))


def generate_checkbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QCheckBox:
    widget = QtWidgets.QCheckBox(option.display_name)
    widget.setToolTip(option.help)
    layout.addWidget(widget, layout.rowCount(), 0, 1, -1)

    return widget


def generate_spinbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QSpinBox:
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    lbl.setToolTip(option.help)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QSpinBox()
    widget.setRange(0, 9999)
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1, alignment=QtCore.Qt.AlignLeft)

    return widget


def generate_doublespinbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QDoubleSpinBox:
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    lbl.setToolTip(option.help)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QDoubleSpinBox()
    widget.setRange(0, 9999.99)
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1, alignment=QtCore.Qt.AlignLeft)

    return widget


def generate_textbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QLineEdit:
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    lbl.setToolTip(option.help)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QLineEdit()
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1)

    return widget


def settings_to_talker_form(sources: dict[str, QtWidgets.QWidget], config: settngs.Config[settngs.Namespace]) -> None:
    # Set the active talker via id in sources combo box
    sources["cbx_select_talker"].setCurrentIndex(sources["cbx_select_talker"].findData(config[0].talker_source))

    for talker in sources["tabs"].items():
        for name, widget in talker[1].widgets.items():
            value = getattr(config[0], name)
            value_type = type(value)
            try:
                if value_type is str:
                    widget.setText(value)
                if value_type is int or value_type is float:
                    widget.setValue(value)
                if value_type is bool:
                    widget.setChecked(value)
            except Exception:
                logger.debug("Failed to set value of %s", name)


def form_settings_to_config(sources: dict[str, QtWidgets.QWidget], config: settngs.Config[settngs.Namespace]) -> None:
    # Source combo box value
    config[0].talker_source = sources["cbx_select_talker"].currentData()

    for tab in sources["tabs"].items():
        for name, widget in tab[1].widgets.items():
            widget_value = None
            if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                widget_value = widget.value()
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget_value = widget.text().strip()
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget_value = widget.isChecked()

            setattr(config[0], name, widget_value)


def generate_source_option_tabs(
    comic_talker_tab: QtWidgets.QWidget,
    config: settngs.Config[settngs.Namespace],
    talkers: dict[str, ComicTalker],
) -> dict[str, QtWidgets.QWidget]:
    """
    Generate GUI tabs and settings for talkers
    """

    # Store all widgets as to allow easier access to their values vs. using findChildren etc. on the tab widget
    sources: dict = {"tabs": {}}

    # Tab comes with a QVBoxLayout
    comic_talker_tab_layout = comic_talker_tab.layout()

    talker_layout = QtWidgets.QGridLayout()
    lbl_select_talker = QtWidgets.QLabel("Metadata Source:")
    cbx_select_talker = QtWidgets.QComboBox()
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Sunken)
    talker_tabs = QtWidgets.QTabWidget()

    talker_layout.addWidget(lbl_select_talker, 0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    talker_layout.addWidget(cbx_select_talker, 0, 1, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    talker_layout.addWidget(line, 1, 0, 1, -1)
    talker_layout.addWidget(talker_tabs, 2, 0, 1, -1)

    comic_talker_tab_layout.addLayout(talker_layout)

    # Add combobox to sources for getting and setting talker
    sources["cbx_select_talker"] = cbx_select_talker

    # Add source sub tabs to Comic Sources tab
    for talker_id, talker_obj in talkers.items():
        # Add source to general tab dropdown list
        cbx_select_talker.addItem(talker_obj.name, talker_id)

        tab_name = talker_id
        sources["tabs"][tab_name] = TalkerTab(tab=QtWidgets.QWidget(), widgets={})
        layout_grid = QtWidgets.QGridLayout()

        for option in config[1][f"talker_{talker_id}"][1].values():
            if not option.file:
                continue
            if option.dest in (f"{talker_id}_url", f"{talker_id}_key"):
                continue
            current_widget = None
            if option.action is not None and (
                option.action is argparse.BooleanOptionalAction
                or option.type is bool
                or option.action == "store_true"
                or option.action == "store_false"
            ):
                current_widget = generate_checkbox(option, layout_grid)
                sources["tabs"][tab_name].widgets[option.internal_name] = current_widget
            elif option.type is int:
                current_widget = generate_spinbox(option, layout_grid)
                sources["tabs"][tab_name].widgets[option.internal_name] = current_widget
            elif option.type is float:
                current_widget = generate_doublespinbox(option, layout_grid)
                sources["tabs"][tab_name].widgets[option.internal_name] = current_widget
            # option.type of None should be string
            elif (option.type is None and option.action is None) or option.type is str:
                current_widget = generate_textbox(option, layout_grid)
                sources["tabs"][tab_name].widgets[option.internal_name] = current_widget
            else:
                logger.debug(f"Unsupported talker option found. Name: {option.internal_name} Type: {option.type}")

        # Add talker URL and API key fields
        generate_api_widgets(talker_id, sources, config, layout_grid, talkers)

        # Add vertical spacer
        vspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout_grid.addItem(vspacer, layout_grid.rowCount() + 1, 0)
        # Display the new widgets
        sources["tabs"][tab_name].tab.setLayout(layout_grid)

        # Add new sub tab to Comic Source tab
        talker_tabs.addTab(sources["tabs"][tab_name].tab, talker_obj.name)

    return sources
