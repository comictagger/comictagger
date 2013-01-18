"""
A PyQT4 dialog to confirm rename 
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

class RenameWindow(QtGui.QDialog):
		
	def __init__( self, parent, comic_archive, metadata, settings ):
		super(RenameWindow, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'renamewindow.ui' ), self)

		self.settings = settings
		self.metadata = metadata
		self.comic_archive = comic_archive
		self.new_name = None
		
		self.btnSettings.clicked.connect( self.modifySettings )
		self.configRenamer()
		self.doPreview()

	def configRenamer( self ):
		self.renamer = FileRenamer( self.metadata )
		self.renamer.setTemplate( self.settings.rename_template )
		self.renamer.setIssueZeroPadding( self.settings.rename_issue_number_padding )
		self.renamer.setSmartCleanup( self.settings.rename_use_smart_string_cleanup )		
		
	def doPreview( self ):
		self.new_name = self.renamer.determineName( self.comic_archive.path )		
		preview = u"\"{0}\"  ==>  \"{1}\"".format( self.comic_archive.path, self.new_name )
		self.textEdit.setPlainText( preview )
		
	def modifySettings( self ):
		settingswin = SettingsWindow( self, self.settings )
		settingswin.setModal(True)
		settingswin.showRenameTab()
		settingswin.exec_()
		if settingswin.result():
			self.configRenamer()
			self.doPreview()
				
	def accept( self ):
		QtGui.QDialog.accept(self)		
		
		if self.new_name == os.path.basename( self.comic_archive.path ):
			#print msg_hdr + "Filename is already good!"
			return
		
		folder = os.path.dirname( os.path.abspath( self.comic_archive.path ) )
		new_abs_path = utils.unique_file( os.path.join( folder, self.new_name ) )

		os.rename( self.comic_archive.path, new_abs_path )

		self.new_name = new_abs_path
		self.comic_archive.rename( new_abs_path )
		