import sys
from PyQt4 import QtCore, QtGui, uic

from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest

from comicvinetalker import ComicVineTalker
from issueselectionwindow import IssueSelectionWindow

class VolumeSelectionWindow(QtGui.QDialog):
	
	volume_id = 0
	
	def __init__(self, parent, cv_api_key, series_name, issue_number):
		super(VolumeSelectionWindow, self).__init__(parent)
		
		uic.loadUi('volumeselectionwindow.ui', self)
		
		self.series_name = series_name
		self.issue_number = issue_number
		self.cv_api_key = cv_api_key

		self.performQuery()
		
		self.twList.resizeColumnsToContents()	
		self.twList.currentItemChanged.connect(self.currentItemChanged)
		self.twList.cellDoubleClicked.connect(self.cellDoubleClicked)
		self.btnRequery.clicked.connect(self.requery)			
		self.btnIssues.clicked.connect(self.showIssues)	
		
		self.twList.selectRow(0)

	def requery( self ):
		self.performQuery()
		self.twList.selectRow(0)

	def showIssues( self ):
		selector = IssueSelectionWindow( self, self.cv_api_key, self.volume_id, self.issue_number )
		selector.setModal(True)
		selector.exec_()
		if selector.result():
			#we should now have a volume ID
			self.issue_number = selector.issue_number
			self.accept()
		return

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



