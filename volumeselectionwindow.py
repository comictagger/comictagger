"""
A PyQT4 dialog to select specific series/volume from list
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

from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest

from comicvinetalker import ComicVineTalker
from issueselectionwindow import IssueSelectionWindow
from issueidentifier import IssueIdentifier
from genericmetadata import GenericMetadata

class VolumeSelectionWindow(QtGui.QDialog):
	
	volume_id = 0
	
	def __init__(self, parent, cv_api_key, series_name, issue_number, comic_archive):
		super(VolumeSelectionWindow, self).__init__(parent)
		
		uic.loadUi('volumeselectionwindow.ui', self)
		
		self.series_name = series_name
		self.issue_number = issue_number
		self.cv_api_key = cv_api_key
		self.comic_archive = comic_archive

		self.performQuery()
		
		self.twList.resizeColumnsToContents()	
		self.twList.currentItemChanged.connect(self.currentItemChanged)
		self.twList.cellDoubleClicked.connect(self.cellDoubleClicked)
		self.btnRequery.clicked.connect(self.requery)			
		self.btnIssues.clicked.connect(self.showIssues)	
		self.btnAutoSelect.clicked.connect(self.autoSelect)	
		
		self.twList.selectRow(0)

	def requery( self ):
		self.performQuery()
		self.twList.selectRow(0)

	def autoSelect( self ):
		ii = IssueIdentifier( self.comic_archive, self.cv_api_key )
		
		md = GenericMetadata()
		md.series = self.series_name
		md.issue_number = self.issue_number
		ii.setAdditionalMetadata( md )
		
		matches = ii.search()
		if len(matches) == 1:
			print "VolumeSelectionWindow found a match!!", matches[0]['volume_id'], matches[0]['issue_number']
			self.volume_id = matches[0]['volume_id']
			self.issue_number = matches[0]['issue_number']
			self.selectByID()
			self.showIssues()

	def showIssues( self ):
		selector = IssueSelectionWindow( self, self.cv_api_key, self.volume_id, self.issue_number )
		selector.setModal(True)
		selector.exec_()
		if selector.result():
			#we should now have a volume ID
			self.issue_number = selector.issue_number
			self.accept()
		return

	def selectByID( self ):
		for r in range(0, self.twList.rowCount()):
			volume_id, b = self.twList.item( r, 0 ).data( QtCore.Qt.UserRole ).toInt()
			if (volume_id == self.volume_id):
				self.twList.selectRow( r )
				break
		
	def performQuery( self ):
		
		while self.twList.rowCount() > 0:
			self.twList.removeRow(0)
		
		comicVine = ComicVineTalker( self.cv_api_key )
		self.cv_search_results = comicVine.searchForSeries( self.series_name )

		self.twList.setSortingEnabled(False)

		row = 0
		for record in self.cv_search_results: 
			self.twList.insertRow(row)
			
			item_text = record['name']  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setData( QtCore.Qt.UserRole ,record['id'])
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 0, item)
			
			item_text = str(record['start_year'])  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 1, item)

			item_text = record['count_of_issues']  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setData(QtCore.Qt.DisplayRole, record['count_of_issues'])
			item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 2, item)
			
			if record['publisher'] is not None:
				item_text = record['publisher']['name']
				item = QtGui.QTableWidgetItem(item_text)			
				item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
				self.twList.setItem(row, 3, item)
				
			record['cover_image'] = None
			
			row += 1

		self.twList.setSortingEnabled(True)
		self.twList.sortItems( 2 , QtCore.Qt.DescendingOrder )

	
	def cellDoubleClicked( self, r, c ):
		self.showIssues()
		
	def currentItemChanged( self, curr, prev ):

		if curr is None:
			return
		if prev is not None and prev.row() == curr.row():
				return

		
		self.volume_id, b = self.twList.item( curr.row(), 0 ).data( QtCore.Qt.UserRole ).toInt()

		# list selection was changed, update the info on the volume
		for record in self.cv_search_results: 
			if record['id'] == self.volume_id:

				self.teDetails.setText ( record['description'] )
				
				if record['cover_image'] == None:
					url = record['image']['super_url']
					self.labelThumbnail.setText("loading...")
					self.nam = QNetworkAccessManager()

					self.nam.finished.connect(self.finishRequest)
					self.nam.get(QNetworkRequest(QUrl(url)))
					self.pending_cover_record = record
				else:
					self.setCover(record['cover_image'])
	
	# called when the image is done loading
	def finishRequest(self, reply):
		img = QtGui.QImage()
		img.loadFromData(reply.readAll())
		
		self.pending_cover_record['cover_image'] = img
		self.pending_cover_record = None
		
		self.setCover( img )
		
	def setCover( self, img ):
		self.labelThumbnail.setPixmap(QtGui.QPixmap(img))



