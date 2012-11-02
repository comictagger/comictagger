import sys
from PyQt4 import QtCore, QtGui, uic

from PyQt4.QtCore import QUrl
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest

from comicvinetalker import *

class IssueSelectionWindow(QtGui.QDialog):
	
	volume_id = 0
	
	def __init__(self, parent, series_id, issue_number):
		super(IssueSelectionWindow, self).__init__(parent)
		
		uic.loadUi('issueselectionwindow.ui', self)
		
		self.series_id  = series_id

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
		
		while self.twList.rowCount() > 0:
			self.twList.removeRow(0)
		
		comicVine = ComicVineTalker()
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
			
			record['url'] = None  
			
			if float(record['issue_number']) == float(self.issue_number):
				self.initial_id = record['id']
			
			row += 1
			
		#TODO look for given issue in list, and select that one

		self.twList.setSortingEnabled(True)
		self.twList.sortItems( 0 , QtCore.Qt.AscendingOrder )

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
				
				# We don't yet have an image URL for this issue.  Make a request for URL, and hold onto it
				# TODO: this should be reworked...  too much UI latency, maybe chain the NAMs??
				if record['url'] == None:
					record['url'] = ComicVineTalker().fetchIssueCoverURL( self.issue_id )				
				
				self.labelThumbnail.setText("loading...")
				self.nam = QNetworkAccessManager()

				self.nam.finished.connect(self.finishedImageRequest)
				self.nam.get(QNetworkRequest(QUrl(record['url'])))
				break

	# called when the image is done loading
	def finishedImageRequest(self, reply):
		img = QtGui.QImage()
		img.loadFromData(reply.readAll())
		self.labelThumbnail.setPixmap(QtGui.QPixmap(img))
		