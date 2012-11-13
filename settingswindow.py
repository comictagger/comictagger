"""
A PyQT4 dialog to enter app settings
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

import platform
import os
from PyQt4 import QtCore, QtGui, uic

from settings import ComicTaggerSettings
from comicvinetalker import *


windowsRarHelp = """
                 <html><head/><body><p>In order to write to CBR/RAR archives, 
                 you will need to have the tools from 
                 <a href="http://www.win-rar.com/download.html">
                 <span style=" text-decoration: underline; color:#0000ff;">WinRAR</span>
                 </a> installed. </p></body></html>
                """
                
linuxRarHelp = """
               <html><head/><body><p>In order to read/write to CBR/RAR archives, you will
               need to have the shareware tools from WinRar installed.  Your package manager
               should have unrar, and probably rar.  If not, download them <a href="http://www.win-rar.com/download.html">
               <span style=" text-decoration: underline; color:#0000ff;">here</span></a>, and install in your path.</p>
               </body></html>                
               """
macRarHelp = """
                 <html><head/><body><p>In order to read/write to CBR/RAR archives, 
                 you will need the shareware tools from <a href="http://www.win-rar.com/download.html">
                 <span style=" text-decoration: underline; color:#0000ff;">WinRAR</span></a>.  
                 </p></body></html>
                """


class SettingsWindow(QtGui.QDialog):
	
	
	def __init__(self, parent, settings ):
		super(SettingsWindow, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'settingswindow.ui' ), self)

		self.settings = settings
		
		if platform.system() == "Windows":
			self.lblUnrar.hide()
			self.leUnrarExePath.hide()
			self.btnBrowseUnrar.hide()			
			self.lblRarHelp.setText( windowsRarHelp )
			
		elif platform.system() == "Linux":
			self.lblRarHelp.setText( linuxRarHelp )
			
		elif platform.system() == "Darwin":
			self.lblRarHelp.setText( macRarHelp )
			
		# Copy values from settings to form
		self.leCVAPIKey.setText( self.settings.cv_api_key )
		self.leRarExePath.setText( self.settings.rar_exe_path )
		self.leUnrarExePath.setText( self.settings.unrar_exe_path )
		
		
		self.btnTestKey.clicked.connect(self.testAPIKey)
		self.btnBrowseRar.clicked.connect(self.selectRar)
		self.btnBrowseUnrar.clicked.connect(self.selectUnrar)

	def accept( self ):
		
		# Copy values from form to settings and save
		self.settings.cv_api_key = str(self.leCVAPIKey.text())
		self.settings.rar_exe_path = str(self.leRarExePath.text())
		self.settings.unrar_exe_path = str(self.leUnrarExePath.text())
		
		# make sure unrar program is now in the path for the UnRAR class
		utils.addtopath(os.path.dirname(self.settings.unrar_exe_path))
		
		self.settings.save()
		QtGui.QDialog.accept(self)
	
	def testAPIKey( self ):
		# TODO hourglass

		palette = self.lblResult.palette()
		bad_color = QtGui.QColor(255, 0, 0)
		good_color = QtGui.QColor(0, 255, 0)

		comicVine = ComicVineTalker( str(self.leCVAPIKey.text()) )
		if comicVine.testKey( ):
			palette.setColor(self.lblResult.foregroundRole(), good_color)
			self.lblResult.setText("Good Key!")
		else:
			palette.setColor(self.lblResult.foregroundRole(), bad_color)
			self.lblResult.setText("Bad Key :(")

		self.lblResult.setPalette(palette)
	
	
	def selectRar( self ):
		self.selectFile(  self.leRarExePath, "RAR" )
	
	def selectUnrar( self ):
		self.selectFile( self.leUnrarExePath, "UnRAR" )

	
	def selectFile( self, control, name ):
		
		dialog = QtGui.QFileDialog(self)
		dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
		
		if platform.system() == "Windows":
			if name == "RAR":
				filter  = self.tr("Rar Program (Rar.exe)")						
			else:
				filter  = self.tr("Programs (*.exe)")	
			dialog.setNameFilter(filter)		
		else:
			dialog.setFilter(QtCore.QDir.Files) #QtCore.QDir.Executable | QtCore.QDir.Files)
			pass
			
		dialog.setDirectory(os.path.dirname(str(control.text())))
		dialog.setWindowTitle("Find " + name + " program")
		
		if (dialog.exec_()):
			fileList = dialog.selectedFiles()
			control.setText( str(fileList[0]) )

			
		
