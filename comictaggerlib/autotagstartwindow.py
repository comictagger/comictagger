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

import copy
import logging
from typing import NamedTuple

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from comicapi.genericmetadata import GenericMetadata
from comictaggerlib.ctsettings import ct_ns, settngs_namespace
from comictaggerlib.ui import ui_path

logger = logging.getLogger(__name__)


class AutoTagSettings(NamedTuple):
    settings: settngs_namespace.Auto_Tag
    remove_after_success: bool
    series_match_identify_thresh: bool
    split_words: bool
    search_string: str

    def new_settings(self, config: ct_ns) -> ct_ns:
        new = copy.copy(config)
        new.internal__remove_archive_after_successful_match = self.remove_after_success
        new.Issue_Identifier__series_match_identify_thresh = self.series_match_identify_thresh
        new.Filename_Parsing__split_words = self.split_words
        new.Auto_Tag__online = self.settings["online"]
        new.Auto_Tag__save_on_low_confidence = self.settings["save_on_low_confidence"]
        new.Auto_Tag__use_year_when_identifying = self.settings["use_year_when_identifying"]
        new.Auto_Tag__assume_issue_one = self.settings["assume_issue_one"]
        new.Auto_Tag__ignore_leading_numbers_in_filename = self.settings["ignore_leading_numbers_in_filename"]
        new.Auto_Tag__parse_filename = self.settings["parse_filename"]
        new.Auto_Tag__prefer_filename = self.settings["prefer_filename"]
        new.Auto_Tag__issue_id = self.settings["issue_id"]
        new.Auto_Tag__metadata = self.settings["metadata"]
        new.Auto_Tag__clear_tags = self.settings["clear_tags"]
        new.Auto_Tag__publisher_filter = self.settings["publisher_filter"]
        new.Auto_Tag__use_publisher_filter = self.settings["use_publisher_filter"]
        new.Auto_Tag__auto_imprint = self.settings["auto_imprint"]

        return new


class AutoTagStartWindow(QtWidgets.QDialog):
    startAutoTag = QtCore.pyqtSignal(AutoTagSettings)

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
        self.cbxDontUseYear.setChecked(not self.config.Auto_Tag__use_year_when_identifying)
        self.cbxAssumeIssueOne.setChecked(self.config.Auto_Tag__assume_issue_one)
        self.cbxIgnoreLeadingDigitsInFilename.setChecked(self.config.Auto_Tag__ignore_leading_numbers_in_filename)
        self.cbxRemoveAfterSuccess.setChecked(self.config.internal__remove_archive_after_successful_match)
        self.cbxAutoImprint.setChecked(self.config.Auto_Tag__auto_imprint)

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
        self.adjustSize()
        self.setModal(True)
        from . import gui

        if gui.tagger_window:
            self.addAction(gui.tagger_window.actionExit)
        # Qt sucks
        cancel = QtGui.QAction(self)
        cancel.triggered.connect(self.reject)
        cancel.setShortcut(QtGui.QKeySequence.StandardKey.Cancel)

        self.addAction(cancel)

    def search_string_toggle(self) -> None:
        enable = self.cbxSpecifySearchString.isChecked()
        self.leSearchString.setEnabled(enable)

    def accept(self) -> None:
        QtWidgets.QDialog.accept(self)

        self.startAutoTag.emit(
            AutoTagSettings(
                settings=settngs_namespace.Auto_Tag(
                    online=self.config.Auto_Tag__online,
                    save_on_low_confidence=self.cbxSaveOnLowConfidence.isChecked(),
                    use_year_when_identifying=not self.cbxDontUseYear.isChecked(),
                    assume_issue_one=self.cbxAssumeIssueOne.isChecked(),
                    ignore_leading_numbers_in_filename=self.cbxIgnoreLeadingDigitsInFilename.isChecked(),
                    parse_filename=self.config.Auto_Tag__parse_filename,
                    prefer_filename=self.config.Auto_Tag__prefer_filename,
                    issue_id=None,
                    metadata=GenericMetadata(),
                    clear_tags=self.config.Auto_Tag__clear_tags,
                    publisher_filter=self.config.Auto_Tag__publisher_filter,
                    use_publisher_filter=self.config.Auto_Tag__use_publisher_filter,
                    auto_imprint=self.cbxAutoImprint.isChecked(),
                    load_default_imprints=self.config.Auto_Tag__load_default_imprints,
                ),
                remove_after_success=self.cbxRemoveAfterSuccess.isChecked(),
                series_match_identify_thresh=self.sbNameMatchSearchThresh.value(),
                split_words=self.cbxSplitWords.isChecked(),
                search_string=self.leSearchString.text(),
            )
        )
