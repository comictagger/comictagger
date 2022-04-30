"""A PyQT4 dialog to enter app settings"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import platform

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comicapi import utils
from comicapi.genericmetadata import md_test
from comictaggerlib.comicvinecacher import ComicVineCacher
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
                 installed. (ComicTagger only uses the command-line rar tool,
                 which is free to use.)</p></body></html>
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
<pre>The template for the new filename. Uses python format strings https://docs.python.org/3/library/string.html#format-string-syntax
Accepts the following variables:
{is_empty}       (boolean)
{tag_origin}     (string)
{series}        (string)
{issue}     (string)
{title}     (string)
{publisher}     (string)
{month}     (integer)
{year}      (integer)
{day}       (integer)
{issue_count}    (integer)
{volume}        (integer)
{genre}     (string)
{language}      (string)
{comments}      (string)
{volume_count}   (integer)
{critical_rating}    (string)
{country}       (string)
{alternate_series}   (string)
{alternate_number}   (string)
{alternate_count}    (integer)
{imprint}       (string)
{notes}     (string)
{web_link}       (string)
{format}        (string)
{manga}     (string)
{black_and_white} (boolean)
{page_count}     (integer)
{maturity_rating}    (string)
{community_rating}     (string)
{story_arc}      (string)
{series_group}   (string)
{scan_info}      (string)
{characters}    (string)
{teams}     (string)
{locations}     (string)
{credits}       (list of dict({&apos;role&apos;: string, &apos;person&apos;: string, &apos;primary&apos;: boolean}))
{tags}      (list of str)
{pages}     (list of dict({&apos;Image&apos;: string(int), &apos;Type&apos;: string}))

CoMet-only items:
{price}     (float)
{is_version_of}   (string)
{rights}        (string)
{identifier}    (string)
{last_mark}  (string)
{cover_image}    (string)

Examples:

{series} {issue} ({year})
Spider-Geddon 1 (2018)

{series} #{issue} - {title}
Spider-Geddon #1 - New Players; Check In
</pre>
"""


class SettingsWindow(QtWidgets.QDialog):
    def __init__(self, parent, settings):
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
        self.lblDefaultSettings.setText("Revert to default " + self.name.lower())
        self.btnResetSettings.setText("Default " + self.name)

        nldt_tip = """<html>The <b>Default Name Length Match Tolerance</b> is for eliminating automatic
                search matches that are too long compared to your series name search. The higher
                it is, the more likely to have a good match, but each search will take longer and
                use more bandwidth. Too low, and only the very closest lexical matches will be
                explored.</html>"""

        self.leNameLengthDeltaThresh.setToolTip(nldt_tip)

        pbl_tip = """<html>
            The <b>Publisher Filter</b> is for eliminating automatic matches to certain publishers
            that you know are incorrect. Useful for avoiding international re-prints with same
            covers or series names. Enter publisher names separated by commas.
            </html>"""
        self.tePublisherFilter.setToolTip(pbl_tip)

        validator = QtGui.QIntValidator(1, 4, self)
        self.leIssueNumPadding.setValidator(validator)

        validator = QtGui.QIntValidator(0, 99, self)
        self.leNameLengthDeltaThresh.setValidator(validator)

        self.leRenameTemplate.setToolTip(template_tooltip)
        self.settings_to_form()
        self.rename_error = None
        self.rename_test()

        self.btnBrowseRar.clicked.connect(self.select_rar)
        self.btnClearCache.clicked.connect(self.clear_cache)
        self.btnResetSettings.clicked.connect(self.reset_settings)
        self.btnTestKey.clicked.connect(self.test_api_key)
        self.btnTemplateHelp.clicked.connect(self.show_template_help)
        self.leRenameTemplate.textEdited.connect(self.rename__test)
        self.cbxMoveFiles.clicked.connect(self.rename_test)
        self.cbxRenameStrict.clicked.connect(self.rename_test)
        self.leDirectory.textEdited.connect(self.rename_test)

    def rename_test(self):
        self.rename__test(self.leRenameTemplate.text())

    def rename__test(self, template):
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

    def settings_to_form(self):
        # Copy values from settings to form
        self.leRarExePath.setText(self.settings.rar_exe_path)
        self.leNameLengthDeltaThresh.setText(str(self.settings.id_length_delta_thresh))
        self.tePublisherFilter.setPlainText(self.settings.id_publisher_filter)

        if self.settings.check_for_new_version:
            self.cbxCheckForNewVersion.setCheckState(QtCore.Qt.CheckState.Checked)

        if self.settings.parse_scan_info:
            self.cbxParseScanInfo.setCheckState(QtCore.Qt.CheckState.Checked)

        if self.settings.use_series_start_as_volume:
            self.cbxUseSeriesStartAsVolume.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.clear_form_before_populating_from_cv:
            self.cbxClearFormBeforePopulating.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.remove_html_tables:
            self.cbxRemoveHtmlTables.setCheckState(QtCore.Qt.CheckState.Checked)

        if self.settings.always_use_publisher_filter:
            self.cbxUseFilter.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.sort_series_by_year:
            self.cbxSortByYear.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.exact_series_matches_first:
            self.cbxExactMatches.setCheckState(QtCore.Qt.CheckState.Checked)

        self.leKey.setText(str(self.settings.cv_api_key))

        if self.settings.assume_lone_credit_is_primary:
            self.cbxAssumeLoneCreditIsPrimary.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.copy_characters_to_tags:
            self.cbxCopyCharactersToTags.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.copy_teams_to_tags:
            self.cbxCopyTeamsToTags.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.copy_locations_to_tags:
            self.cbxCopyLocationsToTags.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.copy_storyarcs_to_tags:
            self.cbxCopyStoryArcsToTags.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.copy_notes_to_comments:
            self.cbxCopyNotesToComments.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.copy_weblink_to_comments:
            self.cbxCopyWebLinkToComments.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.apply_cbl_transform_on_cv_import:
            self.cbxApplyCBLTransformOnCVIMport.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.apply_cbl_transform_on_bulk_operation:
            self.cbxApplyCBLTransformOnBatchOperation.setCheckState(QtCore.Qt.CheckState.Checked)

        self.leRenameTemplate.setText(self.settings.rename_template)
        self.leIssueNumPadding.setText(str(self.settings.rename_issue_number_padding))
        if self.settings.rename_use_smart_string_cleanup:
            self.cbxSmartCleanup.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.rename_extension_based_on_archive:
            self.cbxChangeExtension.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.rename_move_dir:
            self.cbxMoveFiles.setCheckState(QtCore.Qt.CheckState.Checked)
        self.leDirectory.setText(self.settings.rename_dir)
        if self.settings.rename_strict:
            self.cbxRenameStrict.setCheckState(QtCore.Qt.CheckState.Checked)

    def accept(self):
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

        if not str(self.leNameLengthDeltaThresh.text()).isdigit():
            self.leNameLengthDeltaThresh.setText("0")

        if not str(self.leIssueNumPadding.text()).isdigit():
            self.leIssueNumPadding.setText("0")

        self.settings.check_for_new_version = self.cbxCheckForNewVersion.isChecked()

        self.settings.id_length_delta_thresh = int(self.leNameLengthDeltaThresh.text())
        self.settings.id_publisher_filter = str(self.tePublisherFilter.toPlainText())

        self.settings.parse_scan_info = self.cbxParseScanInfo.isChecked()

        self.settings.use_series_start_as_volume = self.cbxUseSeriesStartAsVolume.isChecked()
        self.settings.clear_form_before_populating_from_cv = self.cbxClearFormBeforePopulating.isChecked()
        self.settings.remove_html_tables = self.cbxRemoveHtmlTables.isChecked()

        self.settings.always_use_publisher_filter = self.cbxUseFilter.isChecked()
        self.settings.sort_series_by_year = self.cbxSortByYear.isChecked()
        self.settings.exact_series_matches_first = self.cbxExactMatches.isChecked()

        self.settings.cv_api_key = str(self.leKey.text())
        ComicVineTalker.api_key = self.settings.cv_api_key.strip()
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

    def select_rar(self):
        self.select_file(self.leRarExePath, "RAR")

    def clear_cache(self):
        ImageFetcher().clear_cache()
        ComicVineCacher().clear_cache()
        QtWidgets.QMessageBox.information(self, self.name, "Cache has been cleared.")

    def test_api_key(self):
        if ComicVineTalker().test_key(str(self.leKey.text()).strip()):
            QtWidgets.QMessageBox.information(self, "API Key Test", "Key is valid!")
        else:
            QtWidgets.QMessageBox.warning(self, "API Key Test", "Key is NOT valid.")

    def reset_settings(self):
        self.settings.reset()
        self.settings_to_form()
        QtWidgets.QMessageBox.information(self, self.name, self.name + " have been returned to default values.")

    def select_file(self, control: QtWidgets.QLineEdit, name):

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

    def show_rename_tab(self):
        self.tabWidget.setCurrentIndex(5)

    def show_template_help(self):
        template_help_win = TemplateHelpWindow(self)
        template_help_win.setModal(False)
        template_help_win.show()


class TemplateHelpWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super(TemplateHelpWindow, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.get_ui_file("TemplateHelp.ui"), self)
