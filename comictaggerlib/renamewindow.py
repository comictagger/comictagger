"""A PyQT4 dialog to confirm rename"""

#
# Copyright 2012-2014 ComicTagger Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import logging

import settngs
from PyQt6 import QtCore, QtGui, QtWidgets, uic
from PyQt6.QtGui import QColorConstants

from comicapi import utils
from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata
from comicapi.tags import Tag
from comictalker.comictalker import ComicTalker

from .ctsettings import ct_ns
from .filerenamer import FileRenamer, get_rename_dir
from .md import read_selected_tags
from .optionalmsgdialog import OptionalMessageDialog
from .settingswindow import SettingsWindow
from .ui import ui_path
from .ui.qtutils import center_window_on_parent

logger = logging.getLogger(__name__)


class RenameWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        comic_archive_list: list[ComicArchive],
        read_tags: list[Tag],
        config: settngs.Config[ct_ns],
        talkers: dict[str, ComicTalker],
    ) -> None:
        super().__init__(parent)

        with (ui_path / "renamewindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)

        self.label.setText(f"Preview (based on {', '.join(tag.name for tag in read_tags)} tags):")

        self.setWindowFlags(
            QtCore.Qt.WindowType(
                self.windowFlags()
                | QtCore.Qt.WindowType.WindowSystemMenuHint
                | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            )
        )

        self.config = config
        self.talkers = talkers
        self.comic_archive_list = comic_archive_list
        self.read_tags = read_tags
        self.rename_list: list[str] = []

        self.btnSettings.clicked.connect(self.modify_settings)
        platform = "universal" if self.config[0].File_Rename__strict_filenames else "auto"
        self.renamer = FileRenamer(None, platform=platform, replacements=self.config[0].File_Rename__replacements)

        self.do_preview()
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    def config_renamer(self, ca: ComicArchive, md: GenericMetadata = GenericMetadata()) -> tuple[str, Exception | None]:
        self.renamer.set_template(self.config[0].File_Rename__template)
        self.renamer.set_issue_zero_padding(self.config[0].File_Rename__issue_number_padding)
        self.renamer.set_smart_cleanup(self.config[0].File_Rename__use_smart_string_cleanup)
        self.renamer.replacements = self.config[0].File_Rename__replacements
        self.renamer.move_only = self.config[0].File_Rename__only_move
        error = None

        new_ext = ca.path.suffix  # default
        if self.config[0].File_Rename__auto_extension:
            new_ext = ca.extension()

        if md is None or md.is_empty:
            md, _, error = read_selected_tags(
                self.read_tag_ids,
                ca,
                self.config[0].Metadata_Options__tag_merge,
                self.config[0].Metadata_Options__tag_merge_lists,
            )
            if error is not None:
                logger.error("Failed to load tags from %s: %s", ca.path, error)

            if md.is_empty:
                md = ca.metadata_from_filename(
                    self.config[0].Filename_Parsing__filename_parser,
                    self.config[0].Filename_Parsing__remove_c2c,
                    self.config[0].Filename_Parsing__remove_fcbd,
                    self.config[0].Filename_Parsing__remove_publisher,
                )
        self.renamer.set_metadata(md, ca.path.name)
        self.renamer.move = self.config[0].File_Rename__move
        return new_ext, error

    def do_preview(self) -> None:
        self.twList.setRowCount(0)

        self.twList.setSortingEnabled(False)

        errors = False
        for ca in self.comic_archive_list:
            new_ext, error = self.config_renamer(ca)
            errors = errors or error is not None
            try:
                new_name = self.renamer.determine_name(new_ext)
            except ValueError as e:
                logger.exception("Invalid format string: %s", self.config[0].File_Rename__template)
                OptionalMessageDialog.critical(
                    self,
                    "Invalid format string!",
                    "Your rename template is invalid!"
                    f"\n\n{e}\n\n"
                    "Please consult the template help in the "
                    "settings and the documentation on the format at "
                    "https://docs.python.org/3/library/string.html#format-string-syntax",
                )
                return
            except Exception as e:
                logger.exception(
                    "Formatter failure: %s metadata: %s", self.config[0].File_Rename__template, self.renamer.metadata
                )
                OptionalMessageDialog.critical(
                    self,
                    "The formatter had an issue!",
                    "The formatter has experienced an unexpected error!"
                    f"\n\n{type(e).__name__}: {e}\n\n"
                    "Please open an issue at "
                    "https://github.com/comictagger/comictagger",
                )
                return

            folder = get_rename_dir(
                ca,
                self.config[0].File_Rename__dir if self.config[0].File_Rename__move else None,
            )

            row = self.twList.rowCount()
            self.twList.insertRow(row)
            folder_item = QtWidgets.QTableWidgetItem()
            old_name_item = QtWidgets.QTableWidgetItem()
            new_name_item = QtWidgets.QTableWidgetItem()

            item_text = str(folder)
            folder_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 0, folder_item)
            folder_item.setText(item_text)
            folder_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            item_text = str(ca.path.name)
            old_name_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 1, old_name_item)
            old_name_item.setText(item_text)
            old_name_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, item_text)

            new_name_item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.twList.setItem(row, 2, new_name_item)
            if error is not None:
                new_name_item.setText(f"Error reading tags: {error}")
                new_name_item.setBackground(QColorConstants.Red)
            else:
                new_name_item.setText(new_name)
            new_name_item.setData(QtCore.Qt.ItemDataRole.ToolTipRole, new_name)

            self.rename_list.append(new_name)

        # Adjust column sizes
        self.twList.setVisible(False)
        self.twList.resizeColumnsToContents()
        self.twList.setVisible(True)
        if self.twList.columnWidth(0) > 200:
            self.twList.setColumnWidth(0, 200)

        self.twList.setSortingEnabled(True)
        if errors:
            OptionalMessageDialog.warning(
                self, "Read Failed!", "One or more of the read tags failed to load, check log for details"
            )

    def modify_settings(self) -> None:
        self.settingswin = SettingsWindow(self, self.config, self.talkers)
        self.settingswin.setModal(True)
        self.settingswin.show_rename_tab()
        self.settingswin.accepted.connect(self.settings_closed)
        self.settingswin.show()

    def settings_closed(self) -> None:
        self.config = self.settingswin.config
        self.do_preview()

    def accept(self) -> None:
        prog_dialog = QtWidgets.QProgressDialog("", "Cancel", 0, len(self.rename_list), self)
        prog_dialog.setWindowTitle("Renaming Archives")
        prog_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        prog_dialog.setMinimumDuration(100)
        center_window_on_parent(prog_dialog)
        QtCore.QCoreApplication.processEvents()

        failed_renames: list[tuple[str, str, OSError]] = []
        try:
            for idx, comic in enumerate(zip(self.comic_archive_list, self.rename_list), 1):
                if prog_dialog.wasCanceled():
                    break

                prog_dialog.setValue(idx)
                prog_dialog.setLabelText(comic[1])
                if idx % 5 == 0:
                    QtCore.QCoreApplication.processEvents()

                folder = get_rename_dir(
                    comic[0],
                    self.config[0].File_Rename__dir if self.config[0].File_Rename__move else None,
                )

                full_path = folder / comic[1]

                if full_path == comic[0].path:
                    logger.info("%s: Filename is already good!", comic[1])
                    continue

                if not comic[0].is_writable(check_archive_status=False):
                    continue

                new_name = utils.unique_file(full_path)
                try:
                    comic[0].rename(new_name)
                except OSError as e:
                    logger.exception("Failed to rename comic archive: %s", comic[0].path)
                    failed_renames.append(
                        (
                            utils.path_to_short_str(comic[0].path),
                            utils.path_to_short_str(comic[0].path, new_name),
                            e,
                        )
                    )
        except Exception as e:
            assert comic
            logger.exception("Failed to rename comic archive: %s", comic[0].path)
            OptionalMessageDialog.critical(
                self,
                "There was an issue when renaming!",
                f"Renaming failed!\n\n{type(e).__name__}: {e}\n\n",
            )

        if failed_renames:
            OptionalMessageDialog.critical(
                self,
                f"Failed to rename {len(failed_renames)} files!",
                "Renaming failed for {} files!\n\n{}\n\n".format(
                    len(failed_renames),
                    "\n".join([f"- {x[0]!r} -> {x[1]!r}: {x[2]}" for x in failed_renames]),
                ),
            )

        prog_dialog.close()
        QtCore.QCoreApplication.processEvents()

        QtWidgets.QDialog.accept(self)
