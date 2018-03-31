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

import platform
import os
import sys

from PyQt5 import QtCore, QtGui, QtWidgets, uic

from .settings import ComicTaggerSettings
from .comicvinecacher import ComicVineCacher
from .comicvinetalker import ComicVineTalker
from .imagefetcher import ImageFetcher
from . import utils


windowsRarHelp = """
                 <html><head/><body><p>To write to CBR/RAR archives,
                 you will need to have the tools from
                 <a href="http://www.win-rar.com/download.html">
                 <span style=" text-decoration: underline; color:#0000ff;">WINRar</span>
                 </a> installed. (ComicTagger only uses the command-line rar tool,
                 which is free to use.)</p></body></html>
                """

linuxRarHelp = """
               <html><head/><body><p>To write to CBR/RAR archives,
               you will need to have the shareware rar tool from RARLab installed.
               Your package manager should have rar (e.g. "apt-get install rar"). If not, download it <a href="https://www.rarlab.com/download.htm">
               <span style=" text-decoration: underline; color:#0000ff;">here</span>
               </a>, and install in your path. </p></body></html>
               """
               
macRarHelp = """
                 <html><head/><body><p>To write to CBR/RAR archives,
                 you will need the rar tool.  The easiest way to get this is
                 to install <a href="https://brew.sh/">
                 <span style=" text-decoration: underline; color:#0000ff;">homebrew</span>
                 </a>. </p>Once homebrew is installed, run: <b>brew install caskroom/cask/rar</b></body></html>  
                """

windowsUnrarHelp = """
                 <html><head/><body><p>To read CBR/RAR archives,
                 you will need to have the unrar DLL from
                 <a href="https://www.rarlab.com/rar_add.htm">
                 <span style=" text-decoration: underline; color:#0000ff;">RARLab</span>
                 </a> installed. </p></body></html>
                """

linuxUnrarHelp = """
               <html><head/><body><p>To read CBR/RAR archives,
               you will need to have the unrar library from RARLab installed.
               Look <a href="https://github.com/beville/libunrar-binaries/releases">
               <span style=" text-decoration: underline; color:#0000ff;">here</span></a> for
               pre-compiled binaries, or <a href="https://www.rarlab.com/rar_add.htm">
               <span style=" text-decoration: underline; color:#0000ff;">here</span>
               </a>for the UnRAR source (which is easy to compile on Linux). </p></body></html>
               """
               
macUnrarHelp = """
                 <html><head/><body><p>To read CBR/RAR archives,
                 you will need the unrar library.  The easiest way to get this is
                 to install <a href="https://brew.sh/">
                 <span style=" text-decoration: underline; color:#0000ff;">homebrew</span>
                 </a>. </p>Once homebrew is installed, run: <b>brew install unrar</b></body></html>
                """


class SettingsWindow(QtWidgets.QDialog):

    def __init__(self, parent, settings):
        super(SettingsWindow, self).__init__(parent)

        uic.loadUi(ComicTaggerSettings.getUIFile('settingswindow.ui'), self)

        self.setWindowFlags(self.windowFlags() &
                            ~QtCore.Qt.WindowContextHelpButtonHint)

        self.settings = settings
        self.name = "Settings"
        
        self.priorUnrarLibPath = self.settings.unrar_lib_path

        if self.settings.haveOwnUnrarLib():
            # We have our own unrarlib, so no need for this GUI
            self.grpBoxUnrar.hide()
            
        if platform.system() == "Windows":
            self.lblRarHelp.setText(windowsRarHelp)
            self.lblUnrarHelp.setText(windowsUnrarHelp)

        elif platform.system() == "Linux":
            self.lblRarHelp.setText(linuxRarHelp)
            self.lblUnrarHelp.setText(linuxUnrarHelp)

        elif platform.system() == "Darwin":
            # Mac file dialog hides "/usr" and others, so allow user to type
            self.leUnrarLibPath.setReadOnly(False)
            self.leRarExePath.setReadOnly(False)
                     
            self.lblRarHelp.setText(macRarHelp)
            self.lblUnrarHelp.setText(macUnrarHelp)
            self.name = "Preferences"

        self.setWindowTitle("ComicTagger " + self.name)
        self.lblDefaultSettings.setText(
            "Revert to default " + self.name.lower())
        self.btnResetSettings.setText("Default " + self.name)

        nldtTip = (
            """<html>The <b>Default Name Length Match Tolerance</b> is for eliminating automatic
                search matches that are too long compared to your series name search. The higher
                it is, the more likely to have a good match, but each search will take longer and
                use more bandwidth. Too low, and only the very closest lexical matches will be
                explored.</html>""")

        self.leNameLengthDeltaThresh.setToolTip(nldtTip)

        pblTip = (
            """<html>
            The <b>Publisher Blacklist</b> is for eliminating automatic matches to certain publishers
            that you know are incorrect. Useful for avoiding international re-prints with same
            covers or series names. Enter publisher names separated by commas.
            </html>"""
        )
        self.tePublisherBlacklist.setToolTip(pblTip)

        validator = QtGui.QIntValidator(1, 4, self)
        self.leIssueNumPadding.setValidator(validator)

        validator = QtGui.QIntValidator(0, 99, self)
        self.leNameLengthDeltaThresh.setValidator(validator)

        self.settingsToForm()

        self.btnBrowseRar.clicked.connect(self.selectRar)
        self.btnBrowseUnrar.clicked.connect(self.selectUnrar)
        self.btnClearCache.clicked.connect(self.clearCache)
        self.btnResetSettings.clicked.connect(self.resetSettings)
        self.btnTestKey.clicked.connect(self.testAPIKey)

    def settingsToForm(self):

        # Copy values from settings to form
        self.leRarExePath.setText(self.settings.rar_exe_path)
        self.leUnrarLibPath.setText(self.settings.unrar_lib_path)
        self.leNameLengthDeltaThresh.setText(
            str(self.settings.id_length_delta_thresh))
        self.tePublisherBlacklist.setPlainText(
            self.settings.id_publisher_blacklist)

        if self.settings.check_for_new_version:
            self.cbxCheckForNewVersion.setCheckState(QtCore.Qt.Checked)

        if self.settings.parse_scan_info:
            self.cbxParseScanInfo.setCheckState(QtCore.Qt.Checked)

        if self.settings.use_series_start_as_volume:
            self.cbxUseSeriesStartAsVolume.setCheckState(QtCore.Qt.Checked)
        if self.settings.clear_form_before_populating_from_cv:
            self.cbxClearFormBeforePopulating.setCheckState(QtCore.Qt.Checked)
        if self.settings.remove_html_tables:
            self.cbxRemoveHtmlTables.setCheckState(QtCore.Qt.Checked)
        self.leKey.setText(str(self.settings.cv_api_key))

        if self.settings.assume_lone_credit_is_primary:
            self.cbxAssumeLoneCreditIsPrimary.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_characters_to_tags:
            self.cbxCopyCharactersToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_teams_to_tags:
            self.cbxCopyTeamsToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_locations_to_tags:
            self.cbxCopyLocationsToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_storyarcs_to_tags:
            self.cbxCopyStoryArcsToTags.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_notes_to_comments:
            self.cbxCopyNotesToComments.setCheckState(QtCore.Qt.Checked)
        if self.settings.copy_weblink_to_comments:
            self.cbxCopyWebLinkToComments.setCheckState(QtCore.Qt.Checked)
        if self.settings.apply_cbl_transform_on_cv_import:
            self.cbxApplyCBLTransformOnCVIMport.setCheckState(
                QtCore.Qt.Checked)
        if self.settings.apply_cbl_transform_on_bulk_operation:
            self.cbxApplyCBLTransformOnBatchOperation.setCheckState(
                QtCore.Qt.Checked)

        self.leRenameTemplate.setText(self.settings.rename_template)
        self.leIssueNumPadding.setText(
            str(self.settings.rename_issue_number_padding))
        if self.settings.rename_use_smart_string_cleanup:
            self.cbxSmartCleanup.setCheckState(QtCore.Qt.Checked)
        if self.settings.rename_extension_based_on_archive:
            self.cbxChangeExtension.setCheckState(QtCore.Qt.Checked)

    def accept(self):

        # Copy values from form to settings and save
        self.settings.rar_exe_path = str(self.leRarExePath.text())
        
        # Don't accept the form info if we have our own unrar lib
        if not self.settings.haveOwnUnrarLib():
            self.settings.unrar_lib_path = str(self.leUnrarLibPath.text())

        # make sure rar program is now in the path for the rar class
        if self.settings.rar_exe_path:
            utils.addtopath(os.path.dirname(self.settings.rar_exe_path))

        if self.settings.unrar_lib_path:
            os.environ["UNRAR_LIB_PATH"] = self.settings.unrar_lib_path
            # This doesn't do anything... we need to restart!
            
        if not str(self.leNameLengthDeltaThresh.text()).isdigit():
            self.leNameLengthDeltaThresh.setText("0")

        if not str(self.leIssueNumPadding.text()).isdigit():
            self.leIssueNumPadding.setText("0")

        self.settings.check_for_new_version = self.cbxCheckForNewVersion.isChecked()

        self.settings.id_length_delta_thresh = int(
            self.leNameLengthDeltaThresh.text())
        self.settings.id_publisher_blacklist = str(
            self.tePublisherBlacklist.toPlainText())

        self.settings.parse_scan_info = self.cbxParseScanInfo.isChecked()

        self.settings.use_series_start_as_volume = self.cbxUseSeriesStartAsVolume.isChecked()
        self.settings.clear_form_before_populating_from_cv = self.cbxClearFormBeforePopulating.isChecked()
        self.settings.remove_html_tables = self.cbxRemoveHtmlTables.isChecked()
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
        self.settings.rename_issue_number_padding = int(
            self.leIssueNumPadding.text())
        self.settings.rename_use_smart_string_cleanup = self.cbxSmartCleanup.isChecked()
        self.settings.rename_extension_based_on_archive = self.cbxChangeExtension.isChecked()

        self.settings.save()
        QtWidgets.QDialog.accept(self)

        if self.priorUnrarLibPath != self.settings.unrar_lib_path:
            QtWidgets.QMessageBox.information(
                self, "UnRar Library Change",
                "ComicTagger will need to be restarted for changes to take effect.")
            
    def selectRar(self):
        self.selectFile(self.leRarExePath, "RAR")

    def selectUnrar(self):
        self.selectFile(self.leUnrarLibPath, "UnRAR")

    def clearCache(self):
        ImageFetcher().clearCache()
        ComicVineCacher().clearCache()
        QtWidgets.QMessageBox.information(
            self, self.name, "Cache has been cleared.")

    def testAPIKey(self):
        if ComicVineTalker().testKey(str(self.leKey.text()).strip()):
            QtWidgets.QMessageBox.information(
                self, "API Key Test", "Key is valid!")
        else:
            QtWidgets.QMessageBox.warning(
                self, "API Key Test", "Key is NOT valid.")

    def resetSettings(self):
        self.settings.reset()
        self.settingsToForm()
        QtWidgets.QMessageBox.information(
            self,
            self.name,
            self.name +
            " have been returned to default values.")

    def selectFile(self, control, name):

        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)

        if platform.system() == "Windows":
            if name == "RAR":
                filter = self.tr("Rar Program (Rar.exe)")
            else:
                filter = self.tr("Libraries (*.dll)")
            dialog.setNameFilter(filter)
        else:
            # QtCore.QDir.Executable | QtCore.QDir.Files)
            dialog.setFilter(QtCore.QDir.Files)
            pass

        dialog.setDirectory(os.path.dirname(str(control.text())))
        if name == "RAR":
            dialog.setWindowTitle("Find " + name + " program")
        else:
             dialog.setWindowTitle("Find " + name + " library")
             
        if (dialog.exec_()):
            fileList = dialog.selectedFiles()
            control.setText(str(fileList[0]))

    def showRenameTab(self):
        self.tabWidget.setCurrentIndex(5)
