"""
A PyQT4 dialog to show pages of a comic archive
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


class PageBrowserWindow(QtGui.QDialog):
	
	
	def __init__(self, parent):
		super(PageBrowserWindow, self).__init__(None)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'pagebrowser.ui' ), self)
		
		self.lblPage.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'nocover.png' )))
		self.lblPage.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
		self.comic_archive = None
		self.current_pixmap = None
		self.page_count = 0
		self.current_page_num = 0
		
		self.btnNext.clicked.connect( self.nextPage )
		self.btnPrev.clicked.connect( self.prevPage )
		self.show()
		
	def setComicArchive(self, ca):

		self.comic_archive = ca
		self.page_count = ca.getNumberOfPages()
		self.current_page_num = 0
		
		self.setPage()

	def nextPage(self):
		
		if self.current_page_num + 1 < self.page_count:
			self.current_page_num += 1
		self.setPage()

	def prevPage(self):
		
		if self.current_page_num - 1 >= 0:
			self.current_page_num -= 1
		self.setPage()
			
	def setPage( self ):
		image_data = self.comic_archive.getPage( self.current_page_num )

		if  image_data is not None:
			self.setCurrentPixmap( image_data )
			self.setDisplayPixmap( 0, 0)
		self.setWindowTitle("Page Browser - Page {0} (of {1}) ".format(self.current_page_num+1, self.page_count ) )

	def setCurrentPixmap( self, image_data ):
		if image_data is not None:
			img = QtGui.QImage()
			img.loadFromData( image_data )
			self.current_pixmap = QtGui.QPixmap(QtGui.QPixmap(img))
		
	def resizeEvent( self, resize_event ):
		if self.current_pixmap is not None:
			delta_w = resize_event.size().width() - resize_event.oldSize().width()
			delta_h = resize_event.size().height() - resize_event.oldSize().height()
			
			self.setDisplayPixmap( delta_w , delta_h )

	def setDisplayPixmap( self, delta_w , delta_h ):
			# the deltas let us know what the new width and height of the label will be
			new_h = self.lblPage.height() + delta_h
			new_w = self.lblPage.width() + delta_w
			
			if new_h < 0:
				new_h = 0;
			if new_w < 0:
				new_w = 0;
			scaled_pixmap = self.current_pixmap.scaled(new_w, new_h, QtCore.Qt.KeepAspectRatio)			
			self.lblPage.setPixmap( scaled_pixmap )
		
	
			