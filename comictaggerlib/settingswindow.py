"""A PyQT4 dialog to enter app settings"""
#
# Copyright 2012-2014 Anthony Beville
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

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comicapi import utils
from comicapi.genericmetadata import md_test
from comictaggerlib.comiccacher import ComicCacher
from comictaggerlib.comicvinetalker import ComicVineTalker
from comictaggerlib.filerenamer import FileRenamer
from comictaggerlib.imagefetcher import ImageFetcher
from comictaggerlib.settings import ComicTaggerSettings

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
{pages}            (list of dict({'Image': string(int), 'Type': string, 'Bookmark': string, 'DoublePage': string}))

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
    def __init__(self, parent: QtWidgets.QWidget, settings: ComicTaggerSettings) -> None:
        super().__init__(parent)

        uic.loadUi(ComicTaggerSettings.get_ui_file("settingswindow.ui"), self)

        self.setWindowFlags(
            QtCore.Qt.WindowType(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)
        )

        self.settings = settings
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
        self.settings_to_form()
        self.rename_error: Exception | None = None
        self.rename_test()
        self.dir_test()

        self.btnBrowseRar.clicked.connect(self.select_rar)
        self.btnClearCache.clicked.connect(self.clear_cache)
        self.btnResetSettings.clicked.connect(self.reset_settings)
        self.btnTestKey.clicked.connect(self.test_api_key)
        self.btnTemplateHelp.clicked.connect(self.show_template_help)
        self.leRenameTemplate.textEdited.connect(self._rename_test)
        self.cbxMoveFiles.clicked.connect(self.rename_test)
        self.cbxMoveFiles.clicked.connect(self.dir_test)
        self.cbxRenameStrict.clicked.connect(self.rename_test)
        self.leDirectory.textEdited.connect(self.dir_test)
        self.cbxComplicatedParser.clicked.connect(self.switch_parser)

    def rename_test(self) -> None:
        self._rename_test(self.leRenameTemplate.text())

    def dir_test(self) -> None:
        self.lblDir.setText(
            str(pathlib.Path(self.leDirectory.text().strip()).absolute()) if self.cbxMoveFiles.isChecked() else ""
        )

    def _rename_test(self, template: str) -> None:
        fr = FileRenamer(md_test, platform="universal" if self.cbxRenameStrict.isChecked() else "auto")
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

    def settings_to_form(self) -> None:
        # Copy values from settings to form
        self.leRarExePath.setText(self.settings.rar_exe_path)
        self.sbNameMatchIdentifyThresh.setValue(self.settings.id_series_match_identify_thresh)
        self.sbNameMatchSearchThresh.setValue(self.settings.id_series_match_search_thresh)
        self.tePublisherFilter.setPlainText(self.settings.id_publisher_filter)

        self.cbxCheckForNewVersion.setChecked(self.settings.check_for_new_version)

        self.cbxComplicatedParser.setChecked(self.settings.complicated_parser)
        self.cbxRemoveC2C.setChecked(self.settings.remove_c2c)
        self.cbxRemoveFCBD.setChecked(self.settings.remove_fcbd)
        self.cbxRemovePublisher.setChecked(self.settings.remove_publisher)
        self.switch_parser()

        self.cbxUseSeriesStartAsVolume.setChecked(self.settings.use_series_start_as_volume)
        self.cbxClearFormBeforePopulating.setChecked(self.settings.clear_form_before_populating_from_cv)
        self.cbxRemoveHtmlTables.setChecked(self.settings.remove_html_tables)

        self.cbxUseFilter.setChecked(self.settings.always_use_publisher_filter)
        self.cbxSortByYear.setChecked(self.settings.sort_series_by_year)
        self.cbxExactMatches.setChecked(self.settings.exact_series_matches_first)

        self.leKey.setText(self.settings.cv_api_key)
        self.leURL.setText(self.settings.cv_url)

        self.cbxAssumeLoneCreditIsPrimary.setChecked(self.settings.assume_lone_credit_is_primary)
        self.cbxCopyCharactersToTags.setChecked(self.settings.copy_characters_to_tags)
        self.cbxCopyTeamsToTags.setChecked(self.settings.copy_teams_to_tags)
        self.cbxCopyLocationsToTags.setChecked(self.settings.copy_locations_to_tags)
        self.cbxCopyStoryArcsToTags.setChecked(self.settings.copy_storyarcs_to_tags)
        self.cbxCopyNotesToComments.setChecked(self.settings.copy_notes_to_comments)
        self.cbxCopyWebLinkToComments.setChecked(self.settings.copy_weblink_to_comments)
        self.cbxApplyCBLTransformOnCVIMport.setChecked(self.settings.apply_cbl_transform_on_cv_import)
        self.cbxApplyCBLTransformOnBatchOperation.setChecked(self.settings.apply_cbl_transform_on_bulk_operation)

        self.leRenameTemplate.setText(self.settings.rename_template)
        self.leIssueNumPadding.setText(str(self.settings.rename_issue_number_padding))
        self.cbxSmartCleanup.setChecked(self.settings.rename_use_smart_string_cleanup)
        self.cbxChangeExtension.setChecked(self.settings.rename_extension_based_on_archive)
        self.cbxMoveFiles.setChecked(self.settings.rename_move_dir)
        self.leDirectory.setText(self.settings.rename_dir)
        self.cbxRenameStrict.setChecked(self.settings.rename_strict)

    def accept(self) -> None:
        self.rename_test()
        if self.rename_error is not None:
            QtWidgets.QMessageBox.critical(
                self,
                "Invalid format string!",
                "Your rename template is invalid!"
                f"<br/><br/>{self.rename_error}<br/><br/>"
                "Please consult the template help in the "
                "settings and the documentation on the format at "
                "<a href='https://docs.python.org/3/library/string.html#format-string-syntax'>"
                "https://docs.python.org/3/library/string.html#format-string-syntax</a>",
            )
            return

        # Copy values from form to settings and save
        self.settings.rar_exe_path = str(self.leRarExePath.text())

        # make sure rar program is now in the path for the rar class
        if self.settings.rar_exe_path:
            utils.add_to_path(os.path.dirname(self.settings.rar_exe_path))

        if not str(self.leIssueNumPadding.text()).isdigit():
            self.leIssueNumPadding.setText("0")

        self.settings.check_for_new_version = self.cbxCheckForNewVersion.isChecked()

        self.settings.id_series_match_identify_thresh = self.sbNameMatchIdentifyThresh.value()
        self.settings.id_series_match_search_thresh = self.sbNameMatchSearchThresh.value()
        self.settings.id_publisher_filter = str(self.tePublisherFilter.toPlainText())

        self.settings.complicated_parser = self.cbxComplicatedParser.isChecked()
        self.settings.remove_c2c = self.cbxRemoveC2C.isChecked()
        self.settings.remove_fcbd = self.cbxRemoveFCBD.isChecked()
        self.settings.remove_publisher = self.cbxRemovePublisher.isChecked()

        self.settings.use_series_start_as_volume = self.cbxUseSeriesStartAsVolume.isChecked()
        self.settings.clear_form_before_populating_from_cv = self.cbxClearFormBeforePopulating.isChecked()
        self.settings.remove_html_tables = self.cbxRemoveHtmlTables.isChecked()

        self.settings.always_use_publisher_filter = self.cbxUseFilter.isChecked()
        self.settings.sort_series_by_year = self.cbxSortByYear.isChecked()
        self.settings.exact_series_matches_first = self.cbxExactMatches.isChecked()

        self.settings.cv_api_key = self.leKey.text().strip()
        ComicVineTalker.api_key = self.settings.cv_api_key
        self.settings.cv_url = self.leURL.text().strip()
        ComicVineTalker.api_base_url = self.settings.cv_url
        self.settings.assume_lone_credit_is_primary = self.cbxAssumeLoneCreditIsPrimary.isChecked()
        self.settings.copy_characters_to_tags = self.cbxCopyCharactersToTags.isChecked()
        self.settings.copy_teams_to_tags = self.cbxCopyTeamsToTags.isChecked()
        self.settings.copy_locations_to_tags = self.cbxCopyLocationsToTags.isChecked()
        self.settings.copy_storyarcs_to_tags = self.cbxCopyStoryArcsToTags.isChecked()
        self.settings.copy_notes_to_comments = self.cbxCopyNotesToComments.isChecked()
        self.settings.copy_weblink_to_comments = self.cbxCopyWebLinkToComments.isChecked()
        self.settings.apply_cbl_transform_on_cv_import = self.cbxApplyCBLTransformOnCVIMport.isChecked()
        self.settings.apply_cbl_transform_on_bulk_operation = self.cbxApplyCBLTransformOnBatchOperation.isChecked()

        self.settings.rename_template = str(self.leRenameTemplate.text())
        self.settings.rename_issue_number_padding = int(self.leIssueNumPadding.text())
        self.settings.rename_use_smart_string_cleanup = self.cbxSmartCleanup.isChecked()
        self.settings.rename_extension_based_on_archive = self.cbxChangeExtension.isChecked()
        self.settings.rename_move_dir = self.cbxMoveFiles.isChecked()
        self.settings.rename_dir = self.leDirectory.text()

        self.settings.rename_strict = self.cbxRenameStrict.isChecked()

        self.settings.save()
        QtWidgets.QDialog.accept(self)

    def select_rar(self) -> None:
        self.select_file(self.leRarExePath, "RAR")

    def clear_cache(self) -> None:
        ImageFetcher().clear_cache()
        ComicCacher().clear_cache()
        QtWidgets.QMessageBox.information(self, self.name, "Cache has been cleared.")

    def test_api_key(self) -> None:
        if ComicVineTalker().test_key(self.leKey.text().strip(), self.leURL.text().strip()):
            QtWidgets.QMessageBox.information(self, "API Key Test", "Key is valid!")
        else:
            QtWidgets.QMessageBox.warning(self, "API Key Test", "Key is NOT valid.")

    def reset_settings(self) -> None:
        self.settings.reset()
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
            dialog.setWindowTitle("Find " + name + " program")
        else:
            dialog.setWindowTitle("Find " + name + " library")

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

        uic.loadUi(ComicTaggerSettings.get_ui_file("TemplateHelp.ui"), self)
