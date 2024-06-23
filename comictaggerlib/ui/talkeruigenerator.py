from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Any, NamedTuple, cast

import settngs
from PyQt5 import QtCore, QtGui, QtWidgets

from comictaggerlib.coverimagewidget import CoverImageWidget
from comictaggerlib.ctsettings import ct_ns, group_for_plugin
from comictalker.comictalker import ComicTalker

logger = logging.getLogger(__name__)


class TalkerTab(NamedTuple):
    tab: QtWidgets.QWidget
    # dict[option.setting_name] = QWidget
    widgets: dict[str, QtWidgets.QWidget]


class Sources(NamedTuple):
    cbx_sources: QtWidgets.QComboBox
    tabs: list[tuple[ComicTalker, TalkerTab]]


class PasswordEdit(QtWidgets.QLineEdit):
    """
    Password LineEdit with icons to show/hide password entries.
    Taken from https://github.com/pythonguis/python-qtwidgets/tree/master/qtwidgets
    Based on this example https://kushaldas.in/posts/creating-password-input-widget-in-pyqt.html by Kushal Das.
    """

    def __init__(self, show_visibility: bool = True, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.visibleIcon = QtGui.QIcon(":/graphics/eye.svg")
        self.hiddenIcon = QtGui.QIcon(":/graphics/hidden.svg")

        self.setEchoMode(QtWidgets.QLineEdit.Password)

        if show_visibility:
            # Add the password hide/shown toggle at the end of the edit box.
            self.togglepasswordAction = self.addAction(self.visibleIcon, QtWidgets.QLineEdit.TrailingPosition)
            self.togglepasswordAction.setToolTip("Show password")
            self.togglepasswordAction.triggered.connect(self.on_toggle_password_action)

        self.password_shown = False

    def on_toggle_password_action(self) -> None:
        if not self.password_shown:
            self.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.password_shown = True
            self.togglepasswordAction.setIcon(self.hiddenIcon)
            self.togglepasswordAction.setToolTip("Hide password")
        else:
            self.setEchoMode(QtWidgets.QLineEdit.Password)
            self.password_shown = False
            self.togglepasswordAction.setIcon(self.visibleIcon)
            self.togglepasswordAction.setToolTip("Show password")


def generate_api_widgets(
    talker: ComicTalker,
    widgets: TalkerTab,
    key_option: settngs.Setting,
    url_option: settngs.Setting,
    layout: QtWidgets.QGridLayout,
    definitions: settngs.Definitions,
) -> None:
    # *args enforces keyword arguments and allows position arguments to be ignored
    def call_check_api(*args: Any, tab: TalkerTab, talker: ComicTalker, definitions: settngs.Definitions) -> None:
        check_text, check_bool = talker.check_status(get_config_from_tab(tab, definitions[group_for_plugin(talker)]))
        if check_bool:
            QtWidgets.QMessageBox.information(None, "API Test Success", check_text)
        else:
            QtWidgets.QMessageBox.warning(None, "API Test Failed", check_text)

    # get the actual config objects in case they have overwritten the default
    btn_test_row = None

    # only file settings are saved
    if key_option.file:
        # record the current row, so we know where to add the button
        btn_test_row = layout.rowCount()
        le_key = generate_password_textbox(key_option, layout)

        # To enable setting and getting
        widgets.widgets[key_option.setting_name] = le_key

    # only file settings are saved
    if url_option.file:
        # record the current row, so we know where to add the button
        # We overwrite so that the default will be next to the url text box
        btn_test_row = layout.rowCount()
        le_url = generate_textbox(url_option, layout)
        # We insert the default url here so that people don't think it's unset
        le_url.setText(talker.default_api_url)
        # To enable setting and getting
        widgets.widgets[url_option.setting_name] = le_url

    # The button row was recorded so we add it
    if btn_test_row is not None:
        btn = QtWidgets.QPushButton("Test API")
        layout.addWidget(btn, btn_test_row, 2)
        # partial is used as connect will pass in event information
        btn.clicked.connect(partial(call_check_api, tab=widgets, talker=talker, definitions=definitions))


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


def generate_password_textbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QLineEdit:
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    lbl.setToolTip(option.help)
    layout.addWidget(lbl, row, 0)
    widget = PasswordEdit()
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1)

    return widget


def generate_path_textbox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QLineEdit:
    def open_file_picker() -> None:
        if widget.text():
            current_path = Path(widget.text())
        else:
            current_path = Path.home()
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Select File", str(current_path), "")
        if file_path:
            widget.setText(file_path)

    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    lbl.setToolTip(option.help)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QLineEdit()
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1)

    browse_button = QtWidgets.QPushButton("Browse")
    browse_button.clicked.connect(partial(open_file_picker))
    layout.addWidget(browse_button, row, 2)

    return widget


def generate_talker_info(talker: ComicTalker, config: settngs.Config[ct_ns], layout: QtWidgets.QGridLayout) -> None:
    row = layout.rowCount()

    # Add a horizontal layout to break link from options below
    talker_info_layout = QtWidgets.QHBoxLayout()

    logo = CoverImageWidget(
        talker_info_layout.parentWidget(),
        CoverImageWidget.URLMode,
        config.values.Runtime_Options__config.user_cache_dir,
        talker,
        False,
    )
    logo.showControls = False
    logo.setFixedSize(100, 100)
    logo.set_url(talker.logo_url)

    grid_logo = QtWidgets.QGridLayout(talker_info_layout.parentWidget())
    grid_logo.addWidget(logo)
    grid_logo.setContentsMargins(0, 0, 0, 0)
    talker_info_layout.addLayout(grid_logo, 2)

    about = QtWidgets.QTextBrowser()
    about.setOpenExternalLinks(True)
    about.setMaximumHeight(100)
    about.setText(talker.about)
    talker_info_layout.addWidget(about, 2)

    layout.addLayout(talker_info_layout, row, 0, 3, 0)

    # Add horizontal divider
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Sunken)
    layout.addWidget(line, row + 3, 0, 1, -1)


def generate_combobox(option: settngs.Setting, layout: QtWidgets.QGridLayout) -> QtWidgets.QComboBox:
    row = layout.rowCount()
    lbl = QtWidgets.QLabel(option.display_name)
    lbl.setToolTip(option.help)
    layout.addWidget(lbl, row, 0)
    widget = QtWidgets.QComboBox()
    for choice in option.choices:  # type: ignore
        widget.addItem(str(choice))
    widget.setToolTip(option.help)
    layout.addWidget(widget, row, 1)

    return widget


def settings_to_talker_form(sources: Sources, config: settngs.Config[ct_ns]) -> None:
    # Set the active talker via id in sources combo box
    sources[0].setCurrentIndex(sources[0].findData(config[0].Sources__source))

    # Iterate over the tabs, the talker is included in the tab so no extra lookup is needed
    for talker, tab in sources.tabs:
        # setting_name is guaranteed to be unique within a talker
        # and refer to the correct item in config.definitions.v['group name']
        for setting_name, widget in tab.widgets.items():
            setting = config.definitions[group_for_plugin(talker)].v[setting_name]
            value, default = settngs.get_option(config.values, setting)

            # The setting has already been associated to a widget,
            # we try to force a conversion to the expected type
            try:
                if isinstance(widget, QtWidgets.QLineEdit):
                    # Do not show the default value
                    if setting.default is not None:
                        widget.setPlaceholderText(str(setting.default))
                    if not default:
                        widget.setText(str(value))

                elif isinstance(widget, QtWidgets.QComboBox):
                    widget.setCurrentIndex(widget.findText(str(value)))

                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(value))

                elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(float(value))

                elif isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(value))
                else:
                    raise Exception("failed to set widget")
            except Exception:
                logger.debug("Failed to set value of %s for %s(%s)", setting_name, talker.name, talker.id)


def get_config_from_tab(tab: TalkerTab, definitions: settngs.Group) -> dict[str, Any]:
    talker_options = {}
    # setting_name is guaranteed to be unique within a talker
    # and refer to the correct item in config.values['group name']
    for setting_name, widget in tab.widgets.items():
        value = None
        setting = definitions.v[setting_name]

        # Retrieve the widget value
        if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            value = widget.value()
        elif isinstance(widget, QtWidgets.QLineEdit):
            value = widget.text().strip()
        elif isinstance(widget, QtWidgets.QComboBox):
            value = widget.currentText()
        elif isinstance(widget, QtWidgets.QCheckBox):
            value = widget.isChecked()

        # Reset to default if the widget_value is empty
        if (isinstance(value, str) and value == "") or value is None:
            value = setting.default

        # Parse string values into their real types
        typ = setting.type
        if isinstance(value, str) and typ:
            value = typ(value)

        # Warn if the resulting type isn't the guessed type
        guessed_type, _ = setting._guess_type()
        if (
            value is not None
            and guessed_type not in (None, "Any")
            and (isinstance(guessed_type, type) and not isinstance(value, guessed_type))
        ):
            logger.warn(
                "Guessed type is wrong on for '%s': expected: %s got: %s",
                setting_name,
                guessed_type,
                type(value),
            )
        talker_options[setting.dest] = value
    return talker_options


def form_settings_to_config(sources: Sources, config: settngs.Config[ct_ns]) -> settngs.Config[ct_ns]:
    # Update the currently selected talker
    config.values.Sources__source = sources.cbx_sources.currentData()
    cfg = settngs.normalize_config(config, True, True)

    # Iterate over the tabs, the talker is included in the tab so no extra lookup is needed
    for talker, tab in sources.tabs:
        talker_options = cfg.values[group_for_plugin(talker)]
        talker_options.update(get_config_from_tab(tab, cfg.definitions[group_for_plugin(talker)]))
    return cast(settngs.Config[ct_ns], settngs.get_namespace(cfg, True, True))


def generate_source_option_tabs(
    comic_talker_tab: QtWidgets.QWidget,
    config: settngs.Config[ct_ns],
    talkers: dict[str, ComicTalker],
) -> Sources:
    """
    Generate GUI tabs and settings for talkers
    """

    # Tab comes with a QVBoxLayout
    comic_talker_tab_layout = comic_talker_tab.layout()

    talker_layout = QtWidgets.QGridLayout()
    lbl_select_talker = QtWidgets.QLabel("Metadata Source:")
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Sunken)
    talker_tabs = QtWidgets.QTabWidget()

    # Store all widgets as to allow easier access to their values vs. using findChildren etc. on the tab widget
    sources: Sources = Sources(QtWidgets.QComboBox(), [])

    talker_layout.addWidget(lbl_select_talker, 0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    talker_layout.addWidget(sources[0], 0, 1, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
    talker_layout.addWidget(line, 1, 0, 1, -1)
    talker_layout.addWidget(talker_tabs, 2, 0, 1, -1)

    comic_talker_tab_layout.addLayout(talker_layout)

    # Add source sub tabs to Comic Sources tab
    for t_id, talker in list(talkers.items()):
        # Add source to general tab dropdown list
        sources.cbx_sources.addItem(talker.name, t_id)
        tab = TalkerTab(tab=QtWidgets.QWidget(), widgets={})

        layout_grid = QtWidgets.QGridLayout()
        url_option: settngs.Setting | None = None
        key_option: settngs.Setting | None = None

        # Add logo and about text
        generate_talker_info(talker, config, layout_grid)

        dest_created = set()
        for option in config.definitions[group_for_plugin(talker)].v.values():
            guessed_type, _ = option._guess_type()

            # Skip destinations that have already been created
            if option.dest in dest_created:
                logger.debug("Skipped creating gui option for %s", option.dest)
                continue

            # Pull out the key and url option, they get created last
            if option.setting_name == f"{t_id}_key":
                key_option = option
                continue
            elif option.setting_name == f"{t_id}_url":
                url_option = option
                continue
            elif not option.file:
                continue

            # Map types to widgets
            elif guessed_type is bool:
                current_widget = generate_checkbox(option, layout_grid)
                tab.widgets[option.setting_name] = current_widget
            elif guessed_type is int:
                current_widget = generate_spinbox(option, layout_grid)
                tab.widgets[option.setting_name] = current_widget
            elif guessed_type is float:
                current_widget = generate_doublespinbox(option, layout_grid)
                tab.widgets[option.setting_name] = current_widget
            elif guessed_type is Path:
                current_widget = generate_path_textbox(option, layout_grid)
                tab.widgets[option.setting_name] = current_widget

            elif guessed_type is str:
                # If we have a specific set of options
                if option.choices is not None:
                    current_widget = generate_combobox(option, layout_grid)
                # It ends with a password we hide it by default
                elif option.setting_name.casefold().endswith("password"):
                    current_widget = generate_password_textbox(option, layout_grid)
                else:
                    # Default to a text box
                    current_widget = generate_textbox(option, layout_grid)
                tab.widgets[option.setting_name] = current_widget
            else:
                # We didn't create anything for this dest
                logger.debug(f"Unsupported talker option found. Name: {option.internal_name} Type: {option.type}")
                continue
            # Mark this destination as being created
            dest_created.add(option.dest)

        # The key and url options are always defined.
        # If they aren't something has gone wrong with the talker, remove it
        if key_option is None or url_option is None:
            del talkers[t_id]
            continue

        # Add talker URL and API key fields
        generate_api_widgets(talker, tab, key_option, url_option, layout_grid, definitions=config.definitions)

        # Add vertical spacer
        vspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout_grid.addItem(vspacer, layout_grid.rowCount() + 1, 0)
        # Display the new widgets
        tab.tab.setLayout(layout_grid)

        # Add new sub tab to Comic Source tab
        talker_tabs.addTab(tab.tab, talker.name)
        sources.tabs.append((talker, tab))

    return sources
