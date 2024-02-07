"""A PyQT4 dialog to confirm and set config for auto-tag"""

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

from PyQt5 import QtCore, QtWidgets, uic

from comictaggerlib.ctsettings import ct_ns
from comictaggerlib.ui import ui_path

logger = logging.getLogger(__name__)


class AutoTagStartWindow(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, config: ct_ns, msg: str) -> None:
        super().__init__(parent)

        with (ui_path / "autotagstartwindow.ui").open(encoding="utf-8") as uifile:
            uic.loadUi(uifile, self)
        self.label.setText(msg)

        self.setWindowFlags(
            QtCore.Qt.WindowType(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)
        )

        self.config = config

        self.cbxSpecifySearchString.setChecked(False)
        self.cbxSplitWords.setChecked(False)
        self.sbNameMatchSearchThresh.setValue(self.config.Issue_Identifier__series_match_identify_thresh)
        self.leSearchString.setEnabled(False)

        self.cbxSaveOnLowConfidence.setChecked(self.config.Auto_Tag__save_on_low_confidence)
        self.cbxDontUseYear.setChecked(self.config.Auto_Tag__dont_use_year_when_identifying)
        self.cbxAssumeIssueOne.setChecked(self.config.Auto_Tag__assume_issue_one)
        self.cbxIgnoreLeadingDigitsInFilename.setChecked(self.config.Auto_Tag__ignore_leading_numbers_in_filename)
        self.cbxRemoveAfterSuccess.setChecked(self.config.Auto_Tag__remove_archive_after_successful_match)
        self.cbxAutoImprint.setChecked(self.config.Issue_Identifier__auto_imprint)

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
        self.search_string = ""
        self.name_length_match_tolerance = self.config.Issue_Identifier__series_match_search_thresh
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
        self.split_words = self.cbxSplitWords.isChecked()

        # persist some settings
        self.config.Auto_Tag__save_on_low_confidence = self.auto_save_on_low
        self.config.Auto_Tag__dont_use_year_when_identifying = self.dont_use_year
        self.config.Auto_Tag__assume_issue_one = self.assume_issue_one
        self.config.Auto_Tag__ignore_leading_numbers_in_filename = self.ignore_leading_digits_in_filename
        self.config.Auto_Tag__remove_archive_after_successful_match = self.remove_after_success

        if self.cbxSpecifySearchString.isChecked():
            self.search_string = self.leSearchString.text()
