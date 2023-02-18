from __future__ import annotations

import argparse
import logging

import settngs
from PyQt5 import QtCore, QtWidgets

from comictalker.comictalker import ComicTalker

logger = logging.getLogger(__name__)


def call_check_api_key(
    talker_id: str,
    sources_info: dict[str, QtWidgets.QWidget],
    talkers: dict[str, ComicTalker],
):
    key = ""
    # Find the correct widget to get the API key
    for name, widget in sources_info[talker_id]["widgets"].items():
        if name.startswith("talker_" + talker_id) and name.endswith("api_key"):
            key = widget.text().strip()

    if talkers[talker_id].check_api_key(key):
        QtWidgets.QMessageBox.information(None, "API Key Test", "Key is valid!")
    else:
        QtWidgets.QMessageBox.warning(None, "API Key Test", "Key is NOT valid!")


def call_check_api_url(
    talker_id: str,
    sources_info: dict[str, QtWidgets.QWidget],
    talkers: dict[str, ComicTalker],
):
    url = ""
    # Find the correct widget to get the URL key
    for name, widget in sources_info[talker_id]["widgets"].items():
        if name.startswith("talker_" + talker_id) and name.endswith("url"):
            url = widget.text().strip()

    if talkers[talker_id].check_api_url(url):
        QtWidgets.QMessageBox.information(None, "API Key Test", "URL is valid!")
    else:
        QtWidgets.QMessageBox.warning(None, "API Key Test", "URL is NOT valid!")


def api_key_btn_connect(
    btn: QtWidgets.QPushButton,
    talker_id: str,
    sources_info: dict[str, QtWidgets.QWidget],
    talkers: dict[str, ComicTalker],
) -> None:
    btn.clicked.connect(lambda: call_check_api_key(talker_id, sources_info, talkers))


def api_url_btn_connect(
    btn: QtWidgets.QPushButton,
    talker_id: str,
    sources_info: dict[str, QtWidgets.QWidget],
    talkers: dict[str, ComicTalker],
) -> None:
    btn.clicked.connect(lambda: call_check_api_url(talker_id, sources_info, talkers))


def format_internal_name(int_name: str = "") -> str:
    # Presume talker_<name>_<nm>: talker_comicvine_cv_widget_name
    int_name_split = int_name.split("_")
    del int_name_split[0:3]
    int_name_split[0] = int_name_split[0].capitalize()
    new_name = " ".join(int_name_split)
    return new_name


def generate_checkbox(
    option: settngs.Setting, layout: QtWidgets.QGridLayout
) -> tuple[QtWidgets.QGridLayout, QtWidgets.QCheckBox]:
    # bool equals a checkbox (QCheckBox)
    widget = QtWidgets.QCheckBox(format_internal_name(option.internal_name))
    # Add tooltip text
    widget.setToolTip(option.help)
    # Add widget and span all columns
    layout.addWidget(widget, layout.rowCount() + 1, 0, 1, -1)

    return layout, widget


def generate_spinbox(
    option: settngs.Setting, value: int | float, layout: QtWidgets.QGridLayout
) -> tuple[QtWidgets.QGridLayout, QtWidgets.QSpinBox | QtWidgets.QDoubleSpinBox]:
    if isinstance(value, int):
        # int equals a spinbox (QSpinBox)
        lbl = QtWidgets.QLabel(option.internal_name)
        # Create a label
        layout.addWidget(lbl, layout.rowCount() + 1, 0)
        widget = QtWidgets.QSpinBox()
        widget.setRange(0, 9999)
        widget.setToolTip(option.help)
        layout.addWidget(widget, layout.rowCount() - 1, 1, alignment=QtCore.Qt.AlignLeft)

    if isinstance(value, float):
        # float equals a spinbox (QDoubleSpinBox)
        lbl = QtWidgets.QLabel(format_internal_name(option.internal_name))
        # Create a label
        layout.addWidget(lbl, layout.rowCount() + 1, 0)
        widget = QtWidgets.QDoubleSpinBox()
        widget.setRange(0, 9999.99)
        widget.setToolTip(option.help)
        layout.addWidget(widget, layout.rowCount() - 1, 1, alignment=QtCore.Qt.AlignLeft)

    return layout, widget


def generate_textbox(
    option: settngs.Setting, layout: QtWidgets.QGridLayout
) -> tuple[QtWidgets.QGridLayout, QtWidgets.QLineEdit, QtWidgets.QPushButton]:
    btn = None
    # str equals a text field (QLineEdit)
    lbl = QtWidgets.QLabel(format_internal_name(option.internal_name))
    # Create a label
    layout.addWidget(lbl, layout.rowCount() + 1, 0)
    widget = QtWidgets.QLineEdit()
    widget.setObjectName(option.internal_name)
    widget.setToolTip(option.help)
    layout.addWidget(widget, layout.rowCount() - 1, 1)
    # Special case for api_key, make a test button
    if option.internal_name.endswith("api_key"):
        btn = QtWidgets.QPushButton("Test Key")
        layout.addWidget(btn, layout.rowCount() - 1, 2)

    if option.internal_name.endswith("url"):
        btn = QtWidgets.QPushButton("Test URL")
        layout.addWidget(btn, layout.rowCount() - 1, 2)

    return layout, widget, btn


def settings_to_talker_form(sources: dict[str, QtWidgets.QWidget], config: settngs.Config[settngs.Namespace]):
    for talker in sources.items():
        for name, widget in talker[1]["widgets"].items():
            value = getattr(config[0], name)
            value_type = type(value)
            try:
                if value_type is str:
                    # Special case for general dropdown box
                    if name == "talker_source":
                        widget.setCurrentIndex(widget.findData(config[0].talker_source))
                    else:
                        widget.setText(value)
                if value_type is int or value_type is float:
                    widget.setValue(value)
                if value_type is bool:
                    widget.setChecked(value)
            except Exception:
                logger.debug("Failed to set value of %s", name)


def generate_source_option_tabs(
    tabs: QtWidgets.QTabWidget,
    config: settngs.Config[settngs.Namespace],
    talkers: dict[str, ComicTalker],
) -> dict[str, QtWidgets.QWidget]:
    """
    Generate GUI tabs and settings for talkers
    """

    sources: dict = {}
    # Use a dict to make a var name from var
    source_info = {}

    # Add General tab
    source_info["general"] = {"tab": QtWidgets.QWidget(), "widgets": {}}
    general_layout = QtWidgets.QGridLayout()
    lbl_info = QtWidgets.QLabel("Information Source:")
    cbx_info = QtWidgets.QComboBox()
    general_layout.addWidget(lbl_info, 0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    general_layout.addWidget(cbx_info, 0, 1, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    vspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
    general_layout.addItem(vspacer, 1, 0)
    source_info["general"]["widgets"]["talker_source"] = cbx_info

    source_info["general"]["tab"].setLayout(general_layout)
    tabs.addTab(source_info["general"]["tab"], "General")

    # Add source sub tabs to Comic Sources tab
    for talker_id, talker_obj in talkers.items():
        # Add source to general tab dropdown list
        source_info["general"]["widgets"]["talker_source"].addItem(talker_obj.name, talker_id)

        tab_name = talker_id
        source_info[tab_name] = {"tab": QtWidgets.QWidget(), "widgets": {}}
        layout_grid = QtWidgets.QGridLayout()

        for option in config[1][f"talker_{talker_id}"][1].values():
            current_widget = None
            if option.action is not None and (
                option.action is argparse.BooleanOptionalAction
                or option.action is bool
                or option.action == "store_true"
                or option.action == "store_false"
            ):
                layout_grid, current_widget = generate_checkbox(option, layout_grid)
                source_info[tab_name]["widgets"][option.internal_name] = current_widget
            elif option.type is int or option.type is float:
                layout_grid, current_widget = generate_spinbox(
                    option, getattr(config[0], option.internal_name), layout_grid
                )
                source_info[tab_name]["widgets"][option.internal_name] = current_widget
            # option.type of None should be string
            elif option.type is None or option.type is str:
                layout_grid, current_widget, btn = generate_textbox(option, layout_grid)
                source_info[tab_name]["widgets"][option.internal_name] = current_widget

                if option.internal_name.endswith("key"):
                    # Attach test api function to button. A better way?
                    api_key_btn_connect(btn, talker_id, source_info, talkers)
                if option.internal_name.endswith("url"):
                    # Attach test api function to button. A better way?
                    api_url_btn_connect(btn, talker_id, source_info, talkers)
            else:
                logger.debug(f"Unsupported talker option found. Name: {option.internal_name} Type: {option.type}")

        # Add vertical spacer
        vspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout_grid.addItem(vspacer, layout_grid.rowCount() + 1, 0)
        # Display the new widgets
        source_info[tab_name]["tab"].setLayout(layout_grid)

        # Add new sub tab to Comic Source tab
        tabs.addTab(source_info[tab_name]["tab"], talker_obj.name)
        sources.update(source_info)

    return sources
