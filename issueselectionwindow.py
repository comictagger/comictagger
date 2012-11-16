"""
A PyQT4 dialog to select specific issue from list
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
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest

from comicvinetalker import ComicVineTalker
from  imagefetcher import  ImageFetcher
from settings import ComicTaggerSettings

class IssueSelectionWindow(QtGui.QDialog):
	
	volume_id = 0
	
	def __init__(self, parent, settings, series_id, issue_number):
		super(IssueSelectionWindow, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'issueselectionwindow.ui' ), self)
		
		self.series_id  = series_id
		self.settings = settings
		self.url_fetch_thread = None
		
		if issue_number is None or issue_number == "":
			self.issue_number = 1
		else:
			self.issue_number = issue_number

		self.initial_id = None
		self.performQuery()
		
		self.twList.resizeColumnsToContents()	
		self.twList.currentItemChanged.connect(self.currentItemChanged)	
		self.twList.cellDoubleClicked.connect(self.cellDoubleClicked)
		
		#now that the list has been sorted, find the initial record, and select it
		if self.initial_id is None:
			self.twList.selectRow( 0 )
		else:
			for r in range(0, self.twList.rowCount()):
				issue_id, b = self.twList.item( r, 0 ).data( QtCore.Qt.UserRole ).toInt()
				if (issue_id == self.initial_id):
					self.twList.selectRow( r )
					break
					


	def performQuery( self ):
		
		QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

		while self.twList.rowCount() > 0:
			self.twList.removeRow(0)
		
		comicVine = ComicVineTalker( self.settings.cv_api_key )
		volume_data = comicVine.fetchVolumeData( self.series_id )
		self.issue_list = volume_data['issues']

		self.twList.setSortingEnabled(False)

		row = 0
		for record in self.issue_list: 
			self.twList.insertRow(row)
			
			item_text = record['issue_number']  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setData( QtCore.Qt.UserRole ,record['id'])
			item.setData(QtCore.Qt.DisplayRole, float(item_text))
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 0, item)
			
			item_text = u"{0}".format(record['name'])  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 1, item)
			
			if float(record['issue_number']) == float(self.issue_number):
				self.initial_id = record['id']
			
			row += 1
			
		#TODO look for given issue in list, and select that one

		self.twList.setSortingEnabled(True)
		self.twList.sortItems( 0 , QtCore.Qt.AscendingOrder )

		QtGui.QApplication.restoreOverrideCursor()		

	def cellDoubleClicked( self, r, c ):
		self.accept()
			
	def currentItemChanged( self, curr, prev ):

		if curr is None:
			return
		if prev is not None and prev.row() == curr.row():
				return

		
		self.issue_id, b = self.twList.item( curr.row(), 0 ).data( QtCore.Qt.UserRole ).toInt()

		# list selection was changed, update the the issue cover
		for record in self.issue_list: 
			if record['id'] == self.issue_id:
				
				self.issue_number = record['issue_number']

				self.labelThumbnail.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' )))

				self.cv = ComicVineTalker( self.settings.cv_api_key )
				self.cv.urlFetchComplete.connect( self.urlFetchComplete )	
				self.cv.asyncFetchIssueCoverURLs( int(self.issue_id) )
				
				break

	# called when the cover URL has been fetched 
	def urlFetchComplete( self, image_url, thumb_url, issue_id ):

		self.cover_fetcher = ImageFetcher( )
		self.cover_fetcher.fetchComplete.connect(self.coverFetchComplete)
		self.cover_fetcher.fetch( str(image_url), user_data=issue_id )
				
	# called when the image is done loading
	def coverFetchComplete( self, image_data, issue_id ):
		if self.issue_id == issue_id:
			img = QtGui.QImage()
			img.loadFromData( image_data )
			self.labelThumbnail.setPixmap(QtGui.QPixmap(img))
		
