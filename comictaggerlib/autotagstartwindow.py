"""A PyQT4 dialog to confirm and set options for auto-tag"""
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

import logging

import settngs
from PyQt5 import QtCore, QtWidgets, uic

from comictaggerlib.ui import ui_path

logger = logging.getLogger(__name__)


class AutoTagStartWindow(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, options: settngs.Namespace, msg: str) -> None:
        super().__init__(parent)

        uic.loadUi(ui_path / "autotagstartwindow.ui", self)
        self.label.setText(msg)

        self.setWindowFlags(
            QtCore.Qt.WindowType(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)
        )

        self.options = options

        self.cbxSpecifySearchString.setChecked(False)
        self.cbxSplitWords.setChecked(False)
        self.sbNameMatchSearchThresh.setValue(self.options.identifier_series_match_identify_thresh)
        self.leSearchString.setEnabled(False)

        self.cbxSaveOnLowConfidence.setChecked(self.options.autotag_save_on_low_confidence)
        self.cbxDontUseYear.setChecked(self.options.autotag_dont_use_year_when_identifying)
        self.cbxAssumeIssueOne.setChecked(self.options.autotag_assume_1_if_no_issue_num)
        self.cbxIgnoreLeadingDigitsInFilename.setChecked(self.options.autotag_ignore_leading_numbers_in_filename)
        self.cbxRemoveAfterSuccess.setChecked(self.options.autotag_remove_archive_after_successful_match)
        self.cbxWaitForRateLimit.setChecked(self.options.autotag_wait_and_retry_on_rate_limit)
        self.cbxAutoImprint.setChecked(self.options.talkers_auto_imprint)

        nlmt_tip = """<html>The <b>Name Match Ratio Threshold: Auto-Identify</b> is for eliminating automatic
                search matches that are too long compared to your series name search. The lower
                it is, the more likely to have a good match, but each search will take longer and
                use more bandwidth. Too high, and only the very closest matches will be explored.</html>"""

        self.sbNameMatchSearchThresh.setToolTip(nlmt_tip)

        ss_tip = """<html>
            The <b>series search string</b> specifies the search string to be used for all selected archives.
            Use this when trying to match archives with hard-to-parse or incorrect filenames.  All archives selected
            should be from the same series.
            </html>"""
        self.leSearchString.setToolTip(ss_tip)
        self.cbxSpecifySearchString.setToolTip(ss_tip)

        self.cbxSpecifySearchString.stateChanged.connect(self.search_string_toggle)

        self.auto_save_on_low = False
        self.dont_use_year = False
        self.assume_issue_one = False
        self.ignore_leading_digits_in_filename = False
        self.remove_after_success = False
        self.wait_and_retry_on_rate_limit = False
        self.search_string = ""
        self.name_length_match_tolerance = self.options.comicvine_series_match_search_thresh
        self.split_words = self.cbxSplitWords.isChecked()

    def search_string_toggle(self) -> None:
        enable = self.cbxSpecifySearchString.isChecked()
        self.leSearchString.setEnabled(enable)

    def accept(self) -> None:
        QtWidgets.QDialog.accept(self)

        self.auto_save_on_low = self.cbxSaveOnLowConfidence.isChecked()
        self.dont_use_year = self.cbxDontUseYear.isChecked()
        self.assume_issue_one = self.cbxAssumeIssueOne.isChecked()
        self.ignore_leading_digits_in_filename = self.cbxIgnoreLeadingDigitsInFilename.isChecked()
        self.remove_after_success = self.cbxRemoveAfterSuccess.isChecked()
        self.name_length_match_tolerance = self.sbNameMatchSearchThresh.value()
        self.wait_and_retry_on_rate_limit = self.cbxWaitForRateLimit.isChecked()
        self.split_words = self.cbxSplitWords.isChecked()

        # persist some settings
        self.options.autotag_save_on_low_confidence = self.auto_save_on_low
        self.options.autotag_dont_use_year_when_identifying = self.dont_use_year
        self.options.autotag_assume_1_if_no_issue_num = self.assume_issue_one
        self.options.autotag_ignore_leading_numbers_in_filename = self.ignore_leading_digits_in_filename
        self.options.autotag_remove_archive_after_successful_match = self.remove_after_success
        self.options.autotag_wait_and_retry_on_rate_limit = self.wait_and_retry_on_rate_limit

        if self.cbxSpecifySearchString.isChecked():
            self.search_string = self.leSearchString.text()
