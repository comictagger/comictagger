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
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'autotagstartwindow.ui' ), self)
		self.label.setText( msg )

		self.settings = settings
		
		self.cbxNoAutoSaveOnLow.setCheckState( QtCore.Qt.Unchecked )
		self.cbxDontUseYear.setCheckState( QtCore.Qt.Unchecked )
		
		self.noAutoSaveOnLow = False
		self.dontUseYear = False


	def accept( self ):
		QtGui.QDialog.accept(self)		

		self.noAutoSaveOnLow = self.cbxNoAutoSaveOnLow.isChecked()
		self.dontUseYear = self.cbxDontUseYear.isChecked()
	