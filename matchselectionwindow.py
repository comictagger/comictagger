"""
A PyQT4 dialog to select from automated issue matches
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
import os
from PyQt4 import QtCore, QtGui, uic

from PyQt4.QtCore import QUrl, pyqtSignal, QByteArray

from comicvinetalker import ComicVineTalker
from imagefetcher import  ImageFetcher
from settings import ComicTaggerSettings

class MatchSelectionWindow(QtGui.QDialog):
	
	volume_id = 0
	
	def __init__(self, parent, matches):
		super(MatchSelectionWindow, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'matchselectionwindow.ui' ), self)
		
		self.matches = matches
		self.populateTable( )
		self.twList.resizeColumnsToContents()	
		self.twList.currentItemChanged.connect(self.currentItemChanged)	
		self.twList.cellDoubleClicked.connect(self.cellDoubleClicked)
		
		self.current_row = 0
		self.twList.selectRow( 0 )

					
	def populateTable( self  ):

		while self.twList.rowCount() > 0:
			self.twList.removeRow(0)
		
		self.twList.setSortingEnabled(False)

		row = 0
		for match in self.matches: 
			self.twList.insertRow(row)
			
			item_text = match['series']  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 0, item)
			
			"""
			item_text = u"{0}".format(match['issue_number'])  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 1, item)
			"""
			if match['publisher'] is not None:
				item_text = u"{0}".format(match['publisher'])
			else:
				item_text = u"Unknown"
			item = QtGui.QTableWidgetItem(item_text)
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 1, item)
			
			item_text = ""
			if match['month'] is not None:
				item_text = u"{0}/".format(match['month'])
			if match['year'] is not None:
				item_text += u"{0}".format(match['year'])
			else:
				item_text += u"????"
			item = QtGui.QTableWidgetItem(item_text)			
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 2, item)
			
			row += 1
			

	def cellDoubleClicked( self, r, c ):
		self.accept()
			
	def currentItemChanged( self, curr, prev ):

		if curr is None:
			return
		if prev is not None and prev.row() == curr.row():
				return

		self.current_row = curr.row()
		
		# list selection was changed, update the the issue cover				
		self.labelThumbnail.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' )))
				
		self.cover_fetcher = ImageFetcher( )
		self.cover_fetcher.fetchComplete.connect(self.coverFetchComplete)
		self.cover_fetcher.fetch( self.matches[self.current_row]['img_url'] )
				
	# called when the image is done loading
	def coverFetchComplete( self, image_data, issue_id ):
		img = QtGui.QImage()
		img.loadFromData( image_data )
		self.labelThumbnail.setPixmap(QtGui.QPixmap(img))
		
