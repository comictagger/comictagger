"""A PyQT4 dialog to enter app settings"""
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

import html
import logging
import os
import pathlib
import platform
from typing import Any, cast

import settngs
from PyQt5 import QtCore, QtGui, QtWidgets, uic

import comictaggerlib.ui.talkeruigenerator
from comicapi import utils
from comicapi.genericmetadata import md_test
from comictaggerlib import ctsettings
from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.ctversion import version
from comictaggerlib.filerenamer import FileRenamer, Replacement, Replacements
from comictaggerlib.imagefetcher import ImageFetcher
from comictaggerlib.ui import ui_path
from comictalker.comiccacher import ComicCacher
from comictalker.comictalker import ComicTalker

logger = logging.getLogger(__name__)

windowsRarHelp = """
                <html><head/><body><p>To write to CBR/RAR archives,
                you will need to have the tools from
                <span style=" text-decoration: underline; color:#0000ff;">
                <a href="http://www.win-rar.com/download.html">WINRar</a></span>
                installed. (ComicTagger only uses the command-line rar tool.)
                </p></body></html>
                """

linuxRarHelp = """
                <html><head/><body><p>To write to CBR/RAR archives,
                you will need to have the shareware rar tool from RARLab installed.
                Your package manager should have rar (e.g. "apt-get install rar"). If not, download it
                <span style=" text-decoration: underline; color:#0000ff;">
                <a href="https://www.rarlab.com/download.htm">here</a></span>,
                and install in your path. </p></body></html>
                """

macRarHelp = """
                <html><head/><body><p>To write to CBR/RAR archives,
                you will need the rar tool.  The easiest way to get this is
                to install <span style=" text-decoration: underline; color:#0000ff;">
                <a href="https://brew.sh/">homebrew</a></span>.
                </p>Once homebrew is installed, run: <b>brew install caskroom/cask/rar</b></body></html>
                """


template_tooltip = """
The template for the new filename. Uses python format strings https://docs.python.org/3/library/string.html#format-string-syntax
Accepts the following variables:
{is_empty}         (boolean)
{tag_origin}       (string)
{series}           (string)
{issue}            (string)
{title}            (string)
{publisher}        (string)
{month}            (integer)
{year}             (integer)
{day}              (integer)
{issue_count}      (integer)
{volume}           (integer)
{genre}            (string)
{language}         (string)
{comments}         (string)
{volume_count}     (integer)
{critical_rating}  (float)
{country}          (string)
{alternate_series} (string)
{alternate_number} (string)
{alternate_count}  (integer)
{imprint}          (string)
{notes}            (string)
{web_link}         (string)
{format}           (string)
{manga}            (string)
{black_and_white}  (boolean)
{page_count}       (integer)
{maturity_rating}  (string)
{story_arc}        (string)
{series_group}     (string)
{scan_info}        (string)
{characters}       (string)
{teams}            (string)
{locations}        (string)
{credits}          (list of dict({'role': string, 'person': string, 'primary': boolean}))
{writer}           (string)
{penciller}        (string)
{inker}            (string)
{colorist}         (string)
{letterer}         (string)
{cover artist}     (string)
{editor}           (string)
{tags}             (list of str)
{pages}            (list of dict({'Image': string(int), 'Type': string, 'Bookmark': string, 'DoublePage': boolean}))

CoMet-only items:
{price}            (float)
{is_version_of}    (string)
{rights}           (string)
{identifier}       (string)
{last_mark}        (string)
{cover_image}      (string)

Examples:

{series} {issue} ({year})
Spider-Geddon 1 (2018)

{series} #{issue} - {title}
Spider-Geddon #1 - New Players; Check In
"""


class SettingsWindow(QtWidgets.QDialog):
    def __init__(
        self, parent: QtWidgets.QWidget, config: settngs.Config[ct_ns], talkers: dict[str, ComicTalker]
    ) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "settingswindow.ui", self)

        self.setWindowFlags(
            QtCore.Qt.WindowType(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)
        )

        self.config = config
        self.talkers = talkers
        self.name = "Settings"

        if platform.system() == "Windows":
            self.lblRarHelp.setText(windowsRarHelp)

        elif platform.system() == "Linux":
            self.lblRarHelp.setText(linuxRarHelp)

        elif platform.system() == "Darwin":
            self.leRarExePath.setReadOnly(False)

            self.lblRarHelp.setText(macRarHelp)
            self.name = "Preferences"

        self.setWindowTitle("ComicTagger " + self.name)
        self.lblDefaultSettings.setText("Revert to default " + self.name.casefold())
        self.btnResetSettings.setText("Default " + self.name)

        nmit_tip = """<html>The <b>Name Match Ratio Threshold: Auto-Identify</b> is for eliminating automatic
                search matches that are too long compared to your series name search. The lower
                it is, the more likely to have a good match, but each search will take longer and
                use more bandwidth. Too high, and only the very closest matches will be explored.</html>"""
        nmst_tip = """<html>The <b>Name Match Ratio Threshold: Search</b> is for reducing the total
                number of results that are returned from a search. The lower it is, the more pages will
                be returned (max 5 pages or 500 results)</html>"""

        self.sbNameMatchIdentifyThresh.setToolTip(nmit_tip)
        self.sbNameMatchSearchThresh.setToolTip(nmst_tip)

        pbl_tip = """<html>
            The <b>Publisher Filter</b> is for eliminating automatic matches to certain publishers
            that you know are incorrect. Useful for avoiding international re-prints with same
            covers or series names. Enter publisher names separated by commas.
            </html>"""
        self.tePublisherFilter.setToolTip(pbl_tip)

        validator = QtGui.QIntValidator(1, 4, self)
        self.leIssueNumPadding.setValidator(validator)

        self.leRenameTemplate.setToolTip(f"<pre>{html.escape(template_tooltip)}</pre>")
        self.rename_error: Exception | None = None

        self.sources = comictaggerlib.ui.talkeruigenerator.generate_source_option_tabs(
            self.tComicTalkers, self.config, self.talkers
        )
        self.connect_signals()
        self.settings_to_form()
        self.rename_test()
        self.dir_test()
        self.leFilenameParserTest.setText(self.lblRenameTest.text())
        self.filename_parser_test()

        # Set General as start tab
        self.tabWidget.setCurrentIndex(0)

    def connect_signals(self) -> None:
        self.btnBrowseRar.clicked.connect(self.select_rar)
        self.btnClearCache.clicked.connect(self.clear_cache)
        self.btnResetSettings.clicked.connect(self.reset_settings)
        self.btnTemplateHelp.clicked.connect(self.show_template_help)
        self.cbxMoveFiles.clicked.connect(self.dir_test)
        self.leDirectory.textEdited.connect(self.dir_test)
        self.cbxComplicatedParser.clicked.connect(self.switch_parser)

        self.btnAddLiteralReplacement.clicked.connect(self.addLiteralReplacement)
        self.btnAddValueReplacement.clicked.connect(self.addValueReplacement)
        self.btnRemoveLiteralReplacement.clicked.connect(self.removeLiteralReplacement)
        self.btnRemoveValueReplacement.clicked.connect(self.removeValueReplacement)

        self.leRenameTemplate.textEdited.connect(self.rename_test)
        self.cbxMoveFiles.clicked.connect(self.rename_test)
        self.cbxRenameStrict.clicked.connect(self.rename_test)
        self.cbxSmartCleanup.clicked.connect(self.rename_test)
        self.cbxChangeExtension.clicked.connect(self.rename_test)
        self.leIssueNumPadding.textEdited.connect(self.rename_test)
        self.twLiteralReplacements.cellChanged.connect(self.rename_test)
        self.twValueReplacements.cellChanged.connect(self.rename_test)

        self.leFilenameParserTest.textEdited.connect(self.filename_parser_test)
        self.cbxRemoveC2C.clicked.connect(self.filename_parser_test)
        self.cbxRemoveFCBD.clicked.connect(self.filename_parser_test)
        self.cbxRemovePublisher.clicked.connect(self.filename_parser_test)
        self.cbxProtofoliusIssueNumberScheme.clicked.connect(self.filename_parser_test)
        self.cbxProtofoliusIssueNumberScheme.clicked.connect(self.protofolius_clicked)
        self.cbxAllowIssueStartWithLetter.clicked.connect(self.filename_parser_test)
        self.cbxSplitWords.clicked.connect(self.filename_parser_test)

    def disconnect_signals(self) -> None:
        self.btnAddLiteralReplacement.clicked.disconnect()
        self.btnAddValueReplacement.clicked.disconnect()
        self.btnBrowseRar.clicked.disconnect()
        self.btnClearCache.clicked.disconnect()
        self.btnRemoveLiteralReplacement.clicked.disconnect()
        self.btnRemoveValueReplacement.clicked.disconnect()
        self.btnResetSettings.clicked.disconnect()
        self.btnTemplateHelp.clicked.disconnect()
        self.cbxChangeExtension.clicked.disconnect()
        self.cbxComplicatedParser.clicked.disconnect()
        self.cbxMoveFiles.clicked.disconnect()
        self.cbxRenameStrict.clicked.disconnect()
        self.cbxSmartCleanup.clicked.disconnect()
        self.leDirectory.textEdited.disconnect()
        self.leIssueNumPadding.textEdited.disconnect()
        self.leRenameTemplate.textEdited.disconnect()
        self.twLiteralReplacements.cellChanged.disconnect()
        self.twValueReplacements.cellChanged.disconnect()
        self.leFilenameParserTest.textEdited.disconnect()
        self.cbxRemoveC2C.clicked.disconnect()
        self.cbxRemoveFCBD.clicked.disconnect()
        self.cbxRemovePublisher.clicked.disconnect()
        self.cbxProtofoliusIssueNumberScheme.clicked.disconnect()
        self.cbxAllowIssueStartWithLetter.clicked.disconnect()
        self.cbxSplitWords.clicked.disconnect()

    def protofolius_clicked(self, *args: Any, **kwargs: Any) -> None:
        if self.cbxProtofoliusIssueNumberScheme.isChecked():
            self.cbxAllowIssueStartWithLetter.setEnabled(False)
            self.cbxAllowIssueStartWithLetter.setChecked(True)
        else:
            self.cbxAllowIssueStartWithLetter.setEnabled(True)
        self.filename_parser_test()

    def filename_parser_test(self, *args: Any, **kwargs: Any) -> None:
        self._filename_parser_test(self.leFilenameParserTest.text())

    def _filename_parser_test(self, filename: str) -> None:
        filename_info = utils.parse_filename(
            filename=filename,
            complicated_parser=self.cbxComplicatedParser.isChecked(),
            remove_c2c=self.cbxRemoveC2C.isChecked(),
            remove_fcbd=self.cbxRemoveFCBD.isChecked(),
            remove_publisher=self.cbxRemovePublisher.isChecked(),
            split_words=self.cbxSplitWords.isChecked(),
            allow_issue_start_with_letter=self.cbxAllowIssueStartWithLetter.isChecked(),
            protofolius_issue_number_scheme=self.cbxProtofoliusIssueNumberScheme.isChecked(),
        )
        report = ""
        for item in (
            "series",
            "issue",
            "issue_count",
            "title",
            "volume",
            "volume_count",
            "year",
            "alternate",
            "publisher",
            "format",
            "archive",
            "remainder",
            "annual",
            "c2c",
            "fcbd",
        ):
            report += f"{item.title().replace('_', ' ')}: {dict(filename_info)[item]}\n"
        self.lblFilenameParserTest.setText(report)

    def addLiteralReplacement(self) -> None:
        self.insertRow(self.twLiteralReplacements, self.twLiteralReplacements.rowCount(), Replacement("", "", False))

    def addValueReplacement(self) -> None:
        self.insertRow(self.twValueReplacements, self.twValueReplacements.rowCount(), Replacement("", "", False))

    def removeLiteralReplacement(self) -> None:
        if self.twLiteralReplacements.currentRow() >= 0:
            self.twLiteralReplacements.removeRow(self.twLiteralReplacements.currentRow())

    def removeValueReplacement(self) -> None:
        if self.twValueReplacements.currentRow() >= 0:
            self.twValueReplacements.removeRow(self.twValueReplacements.currentRow())

    def insertRow(self, table: QtWidgets.QTableWidget, row: int, replacement: Replacement) -> None:
        find, replace, strict_only = replacement
        table.insertRow(row)
        table.setItem(row, 0, QtWidgets.QTableWidgetItem(find))
        table.setItem(row, 1, QtWidgets.QTableWidgetItem(replace))
        tmp = QtWidgets.QTableWidgetItem()
        if strict_only:
            tmp.setCheckState(QtCore.Qt.Checked)
        else:
            tmp.setCheckState(QtCore.Qt.Unchecked)
        table.setItem(row, 2, tmp)

    def rename_test(self, *args: Any, **kwargs: Any) -> None:
        self._rename_test(self.leRenameTemplate.text())

    def dir_test(self) -> None:
        self.lblDir.setText(
            str(pathlib.Path(self.leDirectory.text().strip()).resolve()) if self.cbxMoveFiles.isChecked() else ""
        )

    def _rename_test(self, template: str) -> None:
        if not str(self.leIssueNumPadding.text()).isdigit():
            self.leIssueNumPadding.setText("0")
        fr = FileRenamer(
            md_test,
            platform="universal" if self.cbxRenameStrict.isChecked() else "auto",
            replacements=self.get_replacements(),
        )
        fr.move = self.cbxMoveFiles.isChecked()
        fr.set_template(template)
        fr.set_issue_zero_padding(int(self.leIssueNumPadding.text()))
        fr.set_smart_cleanup(self.cbxSmartCleanup.isChecked())
        try:
            self.lblRenameTest.setText(fr.determine_name(".cbz"))
            self.rename_error = None
        except Exception as e:
            self.rename_error = e
            self.lblRenameTest.setText(str(e))

    def switch_parser(self) -> None:
        complicated = self.cbxComplicatedParser.isChecked()

        self.cbxRemoveC2C.setEnabled(complicated)
        self.cbxRemoveFCBD.setEnabled(complicated)
        self.cbxRemovePublisher.setEnabled(complicated)
        self.filename_parser_test()

    def settings_to_form(self) -> None:
        self.disconnect_signals()
        # Copy values from settings to form
        if "archiver" in self.config[1] and "rar" in self.config[1]["archiver"].v:
            self.leRarExePath.setText(getattr(self.config[0], self.config[1]["archiver"].v["rar"].internal_name))
        else:
            self.leRarExePath.setEnabled(False)
        self.sbNameMatchIdentifyThresh.setValue(self.config[0].Issue_Identifier__series_match_identify_thresh)
        self.sbNameMatchSearchThresh.setValue(self.config[0].Issue_Identifier__series_match_search_thresh)
        self.tePublisherFilter.setPlainText("\n".join(self.config[0].Issue_Identifier__publisher_filter))

        self.cbxCheckForNewVersion.setChecked(self.config[0].General__check_for_new_version)

        self.cbxComplicatedParser.setChecked(self.config[0].Filename_Parsing__complicated_parser)
        self.cbxRemoveC2C.setChecked(self.config[0].Filename_Parsing__remove_c2c)
        self.cbxRemoveFCBD.setChecked(self.config[0].Filename_Parsing__remove_fcbd)
        self.cbxRemovePublisher.setChecked(self.config[0].Filename_Parsing__remove_publisher)
        self.cbxProtofoliusIssueNumberScheme.setChecked(
            self.config[0].Filename_Parsing__protofolius_issue_number_scheme
        )
        self.cbxAllowIssueStartWithLetter.setChecked(self.config[0].Filename_Parsing__allow_issue_start_with_letter)

        self.switch_parser()

        self.cbxClearFormBeforePopulating.setChecked(self.config[0].Issue_Identifier__clear_form_before_populating)
        self.cbxUseFilter.setChecked(self.config[0].Issue_Identifier__always_use_publisher_filter)
        self.cbxSortByYear.setChecked(self.config[0].Issue_Identifier__sort_series_by_year)
        self.cbxExactMatches.setChecked(self.config[0].Issue_Identifier__exact_series_matches_first)

        self.cbxAssumeLoneCreditIsPrimary.setChecked(self.config[0].Comic_Book_Lover__assume_lone_credit_is_primary)
        self.cbxCopyCharactersToTags.setChecked(self.config[0].Comic_Book_Lover__copy_characters_to_tags)
        self.cbxCopyTeamsToTags.setChecked(self.config[0].Comic_Book_Lover__copy_teams_to_tags)
        self.cbxCopyLocationsToTags.setChecked(self.config[0].Comic_Book_Lover__copy_locations_to_tags)
        self.cbxCopyStoryArcsToTags.setChecked(self.config[0].Comic_Book_Lover__copy_storyarcs_to_tags)
        self.cbxCopyNotesToComments.setChecked(self.config[0].Comic_Book_Lover__copy_notes_to_comments)
        self.cbxCopyWebLinkToComments.setChecked(self.config[0].Comic_Book_Lover__copy_weblink_to_comments)
        self.cbxApplyCBLTransformOnCVIMport.setChecked(self.config[0].Comic_Book_Lover__apply_transform_on_import)
        self.cbxApplyCBLTransformOnBatchOperation.setChecked(
            self.config[0].Comic_Book_Lover__apply_transform_on_bulk_operation
        )

        self.leRenameTemplate.setText(self.config[0].File_Rename__template)
        self.leIssueNumPadding.setText(str(self.config[0].File_Rename__issue_number_padding))
        self.cbxSmartCleanup.setChecked(self.config[0].File_Rename__use_smart_string_cleanup)
        self.cbxChangeExtension.setChecked(self.config[0].File_Rename__set_extension_based_on_archive)
        self.cbxMoveFiles.setChecked(self.config[0].File_Rename__move_to_dir)
        self.leDirectory.setText(self.config[0].File_Rename__dir)
        self.cbxRenameStrict.setChecked(self.config[0].File_Rename__strict)

        for table, replacments in zip(
            (self.twLiteralReplacements, self.twValueReplacements), self.config[0].File_Rename__replacements
        ):
            table.clearContents()
            for i in reversed(range(table.rowCount())):
                table.removeRow(i)
            for row, replacement in enumerate(replacments):
                self.insertRow(table, row, replacement)

        # Set talker values
        comictaggerlib.ui.talkeruigenerator.settings_to_talker_form(self.sources, self.config)

        self.connect_signals()

    def get_replacements(self) -> Replacements:
        literal_replacements = []
        value_replacements = []
        for row in range(self.twLiteralReplacements.rowCount()):
            if self.twLiteralReplacements.item(row, 0).text():
                literal_replacements.append(
                    Replacement(
                        self.twLiteralReplacements.item(row, 0).text(),
                        self.twLiteralReplacements.item(row, 1).text(),
                        self.twLiteralReplacements.item(row, 2).checkState() == QtCore.Qt.Checked,
                    )
                )
        for row in range(self.twValueReplacements.rowCount()):
            if self.twValueReplacements.item(row, 0).text():
                value_replacements.append(
                    Replacement(
                        self.twValueReplacements.item(row, 0).text(),
                        self.twValueReplacements.item(row, 1).text(),
                        self.twValueReplacements.item(row, 2).checkState() == QtCore.Qt.Checked,
                    )
                )
        return Replacements(literal_replacements, value_replacements)

    def accept(self) -> None:
        self.rename_test()
        if self.rename_error is not None:
            if isinstance(self.rename_error, ValueError):
                logger.exception("Invalid format string: %s", self.config[0].File_Rename__template)
                QtWidgets.QMessageBox.critical(
                    self,
                    "Invalid format string!",
                    "Your rename template is invalid!"
                    + f"<br/><br/>{self.rename_error}<br/><br/>"
                    + "Please consult the template help in the "
                    + "settings and the documentation on the format at "
                    + "<a href='https://docs.python.org/3/library/string.html#format-string-syntax'>"
                    + "https://docs.python.org/3/library/string.html#format-string-syntax</a>",
                )
                return
            else:
                logger.exception(
                    "Formatter failure: %s metadata: %s", self.config[0].File_Rename__template, self.renamer.metadata
                )
                QtWidgets.QMessageBox.critical(
                    self,
                    "The formatter had an issue!",
                    "The formatter has experienced an unexpected error!"
                    + f"<br/><br/>{type(self.rename_error).__name__}: {self.rename_error}<br/><br/>"
                    + "Please open an issue at "
                    + "<a href='https://github.com/comictagger/comictagger'>"
                    + "https://github.com/comictagger/comictagger</a>",
                )

        # Copy values from form to settings and save
        if "archiver" in self.config[1] and "rar" in self.config[1]["archiver"].v:
            setattr(self.config[0], self.config[1]["archiver"].v["rar"].internal_name, str(self.leRarExePath.text()))

            # make sure rar program is now in the path for the rar class
            if self.config[0].archiver_rar:  # type: ignore[attr-defined]
                utils.add_to_path(os.path.dirname(str(self.leRarExePath.text())))

        if not str(self.leIssueNumPadding.text()).isdigit():
            self.leIssueNumPadding.setText("0")

        self.config[0].General__check_for_new_version = self.cbxCheckForNewVersion.isChecked()

        self.config[0].Issue_Identifier__series_match_identify_thresh = self.sbNameMatchIdentifyThresh.value()
        self.config[0].Issue_Identifier__series_match_search_thresh = self.sbNameMatchSearchThresh.value()
        self.config[0].Issue_Identifier__publisher_filter = utils.split(self.tePublisherFilter.toPlainText(), "\n")

        self.config[0].Filename_Parsing__complicated_parser = self.cbxComplicatedParser.isChecked()
        self.config[0].Filename_Parsing__remove_c2c = self.cbxRemoveC2C.isChecked()
        self.config[0].Filename_Parsing__remove_fcbd = self.cbxRemoveFCBD.isChecked()
        self.config[0].Filename_Parsing__remove_publisher = self.cbxRemovePublisher.isChecked()
        self.config[0].Filename_Parsing__allow_issue_start_with_letter = self.cbxAllowIssueStartWithLetter.isChecked()
        self.config.values.Filename_Parsing__protofolius_issue_number_scheme = (
            self.cbxProtofoliusIssueNumberScheme.isChecked()
        )

        self.config[0].Issue_Identifier__clear_form_before_populating = self.cbxClearFormBeforePopulating.isChecked()
        self.config[0].Issue_Identifier__always_use_publisher_filter = self.cbxUseFilter.isChecked()
        self.config[0].Issue_Identifier__sort_series_by_year = self.cbxSortByYear.isChecked()
        self.config[0].Issue_Identifier__exact_series_matches_first = self.cbxExactMatches.isChecked()

        self.config[0].Comic_Book_Lover__assume_lone_credit_is_primary = self.cbxAssumeLoneCreditIsPrimary.isChecked()
        self.config[0].Comic_Book_Lover__copy_characters_to_tags = self.cbxCopyCharactersToTags.isChecked()
        self.config[0].Comic_Book_Lover__copy_teams_to_tags = self.cbxCopyTeamsToTags.isChecked()
        self.config[0].Comic_Book_Lover__copy_locations_to_tags = self.cbxCopyLocationsToTags.isChecked()
        self.config[0].Comic_Book_Lover__copy_storyarcs_to_tags = self.cbxCopyStoryArcsToTags.isChecked()
        self.config[0].Comic_Book_Lover__copy_notes_to_comments = self.cbxCopyNotesToComments.isChecked()
        self.config[0].Comic_Book_Lover__copy_weblink_to_comments = self.cbxCopyWebLinkToComments.isChecked()
        self.config[0].Comic_Book_Lover__apply_transform_on_import = self.cbxApplyCBLTransformOnCVIMport.isChecked()
        self.config.values.Comic_Book_Lover__apply_transform_on_bulk_operation = (
            self.cbxApplyCBLTransformOnBatchOperation.isChecked()
        )

        self.config[0].File_Rename__template = str(self.leRenameTemplate.text())
        self.config[0].File_Rename__issue_number_padding = int(self.leIssueNumPadding.text())
        self.config[0].File_Rename__use_smart_string_cleanup = self.cbxSmartCleanup.isChecked()
        self.config[0].File_Rename__set_extension_based_on_archive = self.cbxChangeExtension.isChecked()
        self.config[0].File_Rename__move_to_dir = self.cbxMoveFiles.isChecked()
        self.config[0].File_Rename__dir = self.leDirectory.text()

        self.config[0].File_Rename__strict = self.cbxRenameStrict.isChecked()
        self.config[0].File_Rename__replacements = self.get_replacements()

        # Read settings from talker tabs
        self.config = comictaggerlib.ui.talkeruigenerator.form_settings_to_config(self.sources, self.config)

        self.update_talkers_config()

        ctsettings.save_file(self.config, self.config[0].Runtime_Options__config.user_config_dir / "settings.json")
        self.parent().config = self.config
        QtWidgets.QDialog.accept(self)

    def update_talkers_config(self) -> None:
        ctsettings.talkers = self.talkers
        self.config = ctsettings.plugin.validate_talker_settings(self.config)
        del ctsettings.talkers

    def select_rar(self) -> None:
        self.select_file(self.leRarExePath, "RAR")

    def clear_cache(self) -> None:
        ImageFetcher(self.config[0].Runtime_Options__config.user_cache_dir).clear_cache()
        ComicCacher(self.config[0].Runtime_Options__config.user_cache_dir, version).clear_cache()
        QtWidgets.QMessageBox.information(self, self.name, "Cache has been cleared.")

    def reset_settings(self) -> None:
        self.config = cast(settngs.Config[ct_ns], settngs.get_namespace(settngs.defaults(self.config[1])))
        self.settings_to_form()
        QtWidgets.QMessageBox.information(self, self.name, self.name + " have been returned to default values.")

    def select_file(self, control: QtWidgets.QLineEdit, name: str) -> None:
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)

        if platform.system() == "Windows":
            if name == "RAR":
                flt = "Rar Program (Rar.exe)"
            else:
                flt = "Libraries (*.dll)"
            dialog.setNameFilter(flt)
        else:
            dialog.setFilter(QtCore.QDir.Filter.Files)

        dialog.setDirectory(os.path.dirname(str(control.text())))
        if name == "RAR":
            dialog.setWindowTitle(f"Find {name} program")
        else:
            dialog.setWindowTitle(f"Find {name} library")

        if dialog.exec():
            file_list = dialog.selectedFiles()
            control.setText(str(file_list[0]))

    def show_rename_tab(self) -> None:
        self.tabWidget.setCurrentIndex(5)

    def show_template_help(self) -> None:
        template_help_win = TemplateHelpWindow(self)
        template_help_win.setModal(False)
        template_help_win.show()


class TemplateHelpWindow(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "TemplateHelp.ui", self)
