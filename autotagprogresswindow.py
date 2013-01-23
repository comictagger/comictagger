"""
A PyQT4 dialog to show ID log and progress
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

import sys
from PyQt4 import QtCore, QtGui, uic
import os
from settings import ComicTaggerSettings


class AutoTagProgressWindow(QtGui.QDialog):
	
	
	def __init__(self, parent):
		super(AutoTagProgressWindow, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'autotagprogresswindow.ui' ), self)
		self.lblTest.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' )))
		self.lblArchive.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' )))
		self.isdone = False
		
		# we can't specify relative font sizes in the UI designer, so
		# make font for scroll window a smidge smaller
		f = self.textEdit.font()
		if f.pointSize() > 10:
			f.setPointSize( f.pointSize() - 2 )
		self.textEdit.setFont( f )		
		
	def setArchiveImage( self, img_data):
		self.setCoverImage( img_data, self.lblArchive )

	def setTestImage( self, img_data):
		self.setCoverImage( img_data, self.lblTest )

	def setCoverImage( self, img_data , label):
		if img_data is not None:
			img = QtGui.QImage()
			img.loadFromData( img_data )
			label.setPixmap(QtGui.QPixmap(img))
			label.setScaledContents(True)
		else:
			label.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' )))
			label.setScaledContents(True)
		QtCore.QCoreApplication.processEvents()
		QtCore.QCoreApplication.processEvents()
			
	def reject(self):
		QtGui.QDialog.reject(self)		
		self.isdone = True

		