"""A PyQT4 dialog to confirm and set options for auto-tag"""

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


from PyQt5 import QtCore, QtGui, QtWidgets, uic

from comictaggerlib.settings import ComicTaggerSettings


class AutoTagStartWindow(QtWidgets.QDialog):
    def __init__(self, parent, settings, msg):
        super().__init__(parent)

        uic.loadUi(ComicTaggerSettings.get_ui_file("autotagstartwindow.ui"), self)
        self.label.setText(msg)

        self.setWindowFlags(
            QtCore.Qt.WindowType(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)
        )

        self.settings = settings

        self.cbxSaveOnLowConfidence.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.cbxDontUseYear.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.cbxAssumeIssueOne.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.cbxIgnoreLeadingDigitsInFilename.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.cbxRemoveAfterSuccess.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.cbxSpecifySearchString.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.leNameLengthMatchTolerance.setText(str(self.settings.id_length_delta_thresh))
        self.leSearchString.setEnabled(False)

        if self.settings.save_on_low_confidence:
            self.cbxSaveOnLowConfidence.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.dont_use_year_when_identifying:
            self.cbxDontUseYear.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.assume_1_if_no_issue_num:
            self.cbxAssumeIssueOne.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.ignore_leading_numbers_in_filename:
            self.cbxIgnoreLeadingDigitsInFilename.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.remove_archive_after_successful_match:
            self.cbxRemoveAfterSuccess.setCheckState(QtCore.Qt.CheckState.Checked)
        if self.settings.wait_and_retry_on_rate_limit:
            self.cbxWaitForRateLimit.setCheckState(QtCore.Qt.CheckState.Checked)

        nlmt_tip = """ <html>The <b>Name Length Match Tolerance</b> is for eliminating automatic
                search matches that are too long compared to your series name search. The higher
                it is, the more likely to have a good match, but each search will take longer and
                use more bandwidth. Too low, and only the very closest lexical matches will be
                explored.</html>"""

        self.leNameLengthMatchTolerance.setToolTip(nlmt_tip)

        ss_tip = """<html>
            The <b>series search string</b> specifies the search string to be used for all selected archives.
            Use this when trying to match archives with hard-to-parse or incorrect filenames.  All archives selected
            should be from the same series.
            </html>"""
        self.leSearchString.setToolTip(ss_tip)
        self.cbxSpecifySearchString.setToolTip(ss_tip)

        validator = QtGui.QIntValidator(0, 99, self)
        self.leNameLengthMatchTolerance.setValidator(validator)

        self.cbxSpecifySearchString.stateChanged.connect(self.search_string_toggle)

        self.auto_save_on_low = False
        self.dont_use_year = False
        self.assume_issue_one = False
        self.ignore_leading_digits_in_filename = False
        self.remove_after_success = False
        self.wait_and_retry_on_rate_limit = False
        self.search_string = None
        self.name_length_match_tolerance = self.settings.id_length_delta_thresh

    def search_string_toggle(self):
        enable = self.cbxSpecifySearchString.isChecked()
        self.leSearchString.setEnabled(enable)

    def accept(self):
        QtWidgets.QDialog.accept(self)

        self.auto_save_on_low = self.cbxSaveOnLowConfidence.isChecked()
        self.dont_use_year = self.cbxDontUseYear.isChecked()
        self.assume_issue_one = self.cbxAssumeIssueOne.isChecked()
        self.ignore_leading_digits_in_filename = self.cbxIgnoreLeadingDigitsInFilename.isChecked()
        self.remove_after_success = self.cbxRemoveAfterSuccess.isChecked()
        self.name_length_match_tolerance = int(self.leNameLengthMatchTolerance.text())
        self.wait_and_retry_on_rate_limit = self.cbxWaitForRateLimit.isChecked()

        # persist some settings
        self.settings.save_on_low_confidence = self.auto_save_on_low
        self.settings.dont_use_year_when_identifying = self.dont_use_year
        self.settings.assume_1_if_no_issue_num = self.assume_issue_one
        self.settings.ignore_leading_numbers_in_filename = self.ignore_leading_digits_in_filename
        self.settings.remove_archive_after_successful_match = self.remove_after_success
        self.settings.wait_and_retry_on_rate_limit = self.wait_and_retry_on_rate_limit

        if self.cbxSpecifySearchString.isChecked():
            self.search_string = str(self.leSearchString.text())
            if len(self.search_string) == 0:
                self.search_string = None
