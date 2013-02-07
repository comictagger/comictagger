"""
A PyQT4 dialog to confirm and set options for auto-tag
"""

"""
Copyright 2012  Anthony Beville

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""


from PyQt4 import QtCore, QtGui, uic
from settings import ComicTaggerSettings
from settingswindow import SettingsWindow
from filerenamer import FileRenamer
import os
import utils

	
class AutoTagStartWindow(QtGui.QDialog):
		
	def __init__( self, parent,  settings, msg ):
		super(AutoTagStartWindow, self).__init__(parent)
		
		uic.loadUi(ComicTaggerSettings.getUIFile('autotagstartwindow.ui' ), self)
		self.label.setText( msg )

		self.setWindowFlags(self.windowFlags() &
									  ~QtCore.Qt.WindowContextHelpButtonHint )

		self.settings = settings
		
		self.cbxSaveOnLowConfidence.setCheckState( QtCore.Qt.Unchecked )
		self.cbxDontUseYear.setCheckState( QtCore.Qt.Unchecked )
		self.cbxAssumeIssueOne.setCheckState( QtCore.Qt.Unchecked )
		self.cbxIgnoreLeadingDigitsInFilename.setCheckState( QtCore.Qt.Unchecked )
		self.cbxRemoveAfterSuccess.setCheckState( QtCore.Qt.Unchecked )
		self.cbxSpecifySearchString.setCheckState( QtCore.Qt.Unchecked )
		self.leNameLengthMatchTolerance.setText( str(self.settings.id_length_delta_thresh) )
		self.leSearchString.setEnabled( False )

		nlmtTip = (
			""" <html>The <b>Name Length Match Tolerance</b> is for eliminating automatic
			    search matches that are too long compared to your series name search. The higher
			    it is, the more likely to have a good match, but each search will take longer and
				use more bandwidth. Too low, and only the very closest lexical matches will be
				explored.</html>""" )
		
		self.leNameLengthMatchTolerance.setToolTip(nlmtTip)
			
		ssTip = (
			"""<html>
			The <b>series search string</b> specifies the search string to be used for all selected archives.
			Use this when trying to match archives with hard-to-parse or incorrect filenames.  All archives selected
			should be from the same series.
			</html>"""
		)
		self.leSearchString.setToolTip(ssTip)
		self.cbxSpecifySearchString.setToolTip(ssTip)
		
				
		validator = QtGui.QIntValidator(0, 99, self)
		self.leNameLengthMatchTolerance.setValidator(validator)
				
		self.cbxSpecifySearchString.stateChanged.connect(self.searchStringToggle)
		
		self.autoSaveOnLow = False
		self.dontUseYear = False
		self.assumeIssueOne = False
		self.ignoreLeadingDigitsInFilename = False
		self.removeAfterSuccess = False
		self.searchString = None
		self.nameLengthMatchTolerance =  self.settings.id_length_delta_thresh

	def searchStringToggle(self):
		enable = self.cbxSpecifySearchString.isChecked()
		self.leSearchString.setEnabled( enable )

	
	def accept( self ):
		QtGui.QDialog.accept(self)		

		self.autoSaveOnLow = self.cbxSaveOnLowConfidence.isChecked()
		self.dontUseYear = self.cbxDontUseYear.isChecked()
		self.assumeIssueOne = self.cbxAssumeIssueOne.isChecked()
		self.ignoreLeadingDigitsInFilename = self.cbxIgnoreLeadingDigitsInFilename.isChecked()
		self.removeAfterSuccess = self.cbxRemoveAfterSuccess.isChecked()
		self.nameLengthMatchTolerance = int(self.leNameLengthMatchTolerance.text())
		
		if self.cbxSpecifySearchString.isChecked():
			self.searchString = unicode(self.leSearchString.text())
			if len(self.searchString) == 0:
				self.searchString = None
			
