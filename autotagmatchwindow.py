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

from imagefetcher import  ImageFetcher
from settings import ComicTaggerSettings

class AutoTagMatchWindow(QtGui.QDialog):
	
	volume_id = 0
	
	def __init__(self, parent, match_set_list, style, fetch_func):
		super(AutoTagMatchWindow, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'autotagmatchwindow.ui' ), self)

		self.skipButton = QtGui.QPushButton(self.tr("Skip"))
		self.buttonBox.addButton(self.skipButton, QtGui.QDialogButtonBox.ActionRole)		
		self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setText("Accept and Next")		

		self.match_set_list = match_set_list
		self.style = style
		self.fetch_func = fetch_func

		self.current_match_set_idx = 0
		
		self.twList.currentItemChanged.connect(self.currentItemChanged)	
		self.twList.cellDoubleClicked.connect(self.cellDoubleClicked)
		self.skipButton.clicked.connect(self.skipToNext)
		
		self.updateData()		

	def updateData( self):

		self.current_match_set = self.match_set_list[ self.current_match_set_idx ]


		if self.current_match_set_idx + 1 == len( self.match_set_list ):
			self.skipButton.setDisabled(True)
			
		self.setCoverImage()
		self.populateTable()
		self.twList.resizeColumnsToContents()	
		self.current_row = 0
		self.twList.selectRow( 0 )
		
		path = self.current_match_set.ca.path
		self.setWindowTitle( "Select correct match ({0} of {1}): {2}".format(
						self.current_match_set_idx+1,
						len( self.match_set_list ),
						os.path.split(path)[1] ))
		
	def populateTable( self  ):

		while self.twList.rowCount() > 0:
			self.twList.removeRow(0)
		
		self.twList.setSortingEnabled(False)

		row = 0
		for match in self.current_match_set.matches: 
			self.twList.insertRow(row)
			
			item_text = match['series']  
			item = QtGui.QTableWidgetItem(item_text)			
			item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
			self.twList.setItem(row, 0, item)

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
		self.cover_fetcher.fetch( self.current_match_set.matches[self.current_row]['img_url'] )
				
	# called when the image is done loading
	def coverFetchComplete( self, image_data, issue_id ):
		img = QtGui.QImage()
		img.loadFromData( image_data )
		self.labelThumbnail.setPixmap(QtGui.QPixmap(img))
		
	def setCoverImage( self ):
		ca = self.current_match_set.ca
		cover_idx = ca.readMetadata(self.style).getCoverPageIndexList()[0]
		image_data = ca.getPage( cover_idx )		
		self.labelCover.setScaledContents(True)
		if image_data is not None:
			img = QtGui.QImage()
			img.loadFromData( image_data )
			self.labelCover.setPixmap(QtGui.QPixmap(img))
		else:
			self.labelCover.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' )))

	def accept(self):

		self.saveMatch()
		self.current_match_set_idx += 1
		
		if self.current_match_set_idx == len( self.match_set_list ):
			# no more items
			QtGui.QDialog.accept(self)				
		else:
			self.updateData()

	def skipToNext( self ):
		self.current_match_set_idx += 1
		
		if self.current_match_set_idx == len( self.match_set_list ):
			# no more items
			QtGui.QDialog.reject(self)				
		else:
			self.updateData()
		
	def reject(self):
		reply = QtGui.QMessageBox.question(self, 
			 self.tr("Cancel Matching"), 
			 self.tr("Are you sure you wish to cancel the matching process?"),
			 QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			 
		if reply == QtGui.QMessageBox.No:
			return

		QtGui.QDialog.reject(self)				
			
	def saveMatch( self ):
		
		match = self.current_match_set.matches[self.current_row]
		ca = self.current_match_set.ca

		md = ca.readMetadata( self.style )
		if md.isEmpty:
			md = ca.metadataFromFilename()		
		
		# now get the particular issue data
		cv_md = self.fetch_func( match )
		if cv_md is None:
			QtGui.QMessageBox.critical(self, self.tr("Network Issue"), self.tr("Could not connect to ComicVine to get issue details!"))
			return

		QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))			
		md.overlay( cv_md )
		success = ca.writeMetadata( md, self.style )
		QtGui.QApplication.restoreOverrideCursor()
		
		if not success:		
			QtGui.QMessageBox.warning(self, self.tr("Write Error"), self.tr("Saving the tags to the archive seemed to fail!"))
