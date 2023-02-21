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


def generate_checkbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QCheckBox:
    widget = QtWidgets.QCheckBox(option.display_name)
    widget.setToolTip(option.help)
    layout.addWidget(widget, layout.rowCount(), 0, 1, -1)

    return widget


def generate_spinbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QSpinBox:
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QSpinBox()
    widget.setRange(0, 9999)
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1, alignment=QtCore.Qt.AlignLeft)

    return widget


def generate_doublespinbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QDoubleSpinBox:
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QDoubleSpinBox()
    widget.setRange(0, 9999.99)
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1, alignment=QtCore.Qt.AlignLeft)

    return widget


def generate_textbox(
    option: settngs.Setting, layout: QtWidgets.QGridLayout
) -> tuple[QtWidgets.QLineEdit, QtWidgets.QPushButton]:
    btn = None
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QLineEdit()
    widget.setObjectName(option.internal_name)
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1)

    # Special case for api_key, make a test button
    if option.internal_name.endswith("api_key"):
        btn = QtWidgets.QPushButton("Test Key")
        layout.addWidget(btn, row, 2)

    if option.internal_name.endswith("url"):
        btn = QtWidgets.QPushButton("Test URL")
        layout.addWidget(btn, row, 2)

    return widget, btn


def settings_to_talker_form(sources: dict[str, QtWidgets.QWidget], config: settngs.Config[settngs.Namespace]) -> None:
    # Set the active talker in sources combo box
    sources["talker_source"].setCurrentIndex(sources["talker_source"].findData(config[0].talker_source))

    for talker in sources["tabs"].items():
        for name, widget in talker[1]["widgets"].items():
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
    config[0].talker_source = sources["talker_source"].itemData(sources["talker_source"].currentIndex())

    for tab in sources["tabs"].items():
        for name, widget in tab[1]["widgets"].items():
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
    lbl_info = QtWidgets.QLabel("Information Source:")
    cbx_info = QtWidgets.QComboBox()
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Sunken)
    talker_tabs = QtWidgets.QTabWidget()

    talker_layout.addWidget(lbl_info, 0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    talker_layout.addWidget(cbx_info, 0, 1, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    talker_layout.addWidget(line, 1, 0, 1, -1)
    talker_layout.addWidget(talker_tabs, 2, 0, 1, -1)

    comic_talker_tab_layout.addLayout(talker_layout)

    # Add cbx_info combobox to sources for getting and setting talker
    sources["talker_source"] = cbx_info

    # Add source sub tabs to Comic Sources tab
    for talker_id, talker_obj in talkers.items():
        # Add source to general tab dropdown list
        cbx_info.addItem(talker_obj.name, talker_id)

        tab_name = talker_id
        sources["tabs"][tab_name] = {"tab": QtWidgets.QWidget(), "widgets": {}}
        layout_grid = QtWidgets.QGridLayout()

        for option in config[1][f"talker_{talker_id}"][1].values():
            current_widget = None
            if option.action is not None and (
                option.action is argparse.BooleanOptionalAction
                or option.type is bool
                or option.action == "store_true"
                or option.action == "store_false"
            ):
                current_widget = generate_checkbox(option, layout_grid)
                sources["tabs"][tab_name]["widgets"][option.internal_name] = current_widget
            elif option.type is int:
                current_widget = generate_spinbox(option, layout_grid)
                sources["tabs"][tab_name]["widgets"][option.internal_name] = current_widget
            elif option.type is float:
                current_widget = generate_doublespinbox(option, layout_grid)
                sources["tabs"][tab_name]["widgets"][option.internal_name] = current_widget
            # option.type of None should be string
            elif (option.type is None and option.action is None) or option.type is str:
                current_widget, btn = generate_textbox(option, layout_grid)
                sources["tabs"][tab_name]["widgets"][option.internal_name] = current_widget

                if option.internal_name.endswith("key"):
                    # Attach test api function to button. A better way?
                    api_key_btn_connect(btn, talker_id, sources, talkers)
                if option.internal_name.endswith("url"):
                    # Attach test api function to button. A better way?
                    api_url_btn_connect(btn, talker_id, sources, talkers)
            else:
                logger.debug(f"Unsupported talker option found. Name: {option.internal_name} Type: {option.type}")

        # Add vertical spacer
        vspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout_grid.addItem(vspacer, layout_grid.rowCount() + 1, 0)
        # Display the new widgets
        sources["tabs"][tab_name]["tab"].setLayout(layout_grid)

        # Add new sub tab to Comic Source tab
        talker_tabs.addTab(sources["tabs"][tab_name]["tab"], talker_obj.name)

    return sources
