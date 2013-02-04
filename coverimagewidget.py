"""
A PyQt4 widget display cover images from either local archive, or from ComicVine
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

import os

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic

from settings import ComicTaggerSettings
from genericmetadata import GenericMetadata, PageType
from options import MetaDataStyle
from comicvinetalker import ComicVineTalker, ComicVineTalkerException
from imagefetcher import  ImageFetcher
from pageloader import PageLoader
from imagepopup import ImagePopup

# helper func to allow a label to be clickable
def clickable(widget):

	class Filter(QObject):
	
		dblclicked = pyqtSignal()
		
		def eventFilter(self, obj, event):
		
			if obj == widget:
				if event.type() == QEvent.MouseButtonDblClick:
					self.dblclicked.emit()
					return True
			
			return False
	
	filter = Filter(widget)
	widget.installEventFilter(filter)
	return filter.dblclicked


class CoverImageWidget(QWidget):
	
	ArchiveMode = 0
	AltCoverMode = 1
	
	def __init__(self, parent, mode ):
		super(CoverImageWidget, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'coverimagewidget.ui' ), self )

		f = self.label.font()
		if f.pointSize() > 10:
			f.setPointSize( f.pointSize() - 2 )
		self.label.setFont( f )		

		self.mode = mode
		self.comicVine = ComicVineTalker()
		self.page_loader = None
		
		self.btnLeft.clicked.connect( self.decrementImage )
		self.btnRight.clicked.connect( self.incrementImage )
		self.resetWidget()
		clickable(self.lblImage).connect(self.showPopup)

		self.updateContent()

	def resetWidget(self):
		self.comic_archive = None
		self.issue_id = None
		self.comicVine = None
		self.cover_fetcher = None
		self.url_list = []
		if self.page_loader is not None:
			self.page_loader.abandoned = True
		self.page_loader = None
		self.imageIndex = -1
		self.imageCount = 1
		
	def incrementImage( self ):
		self.imageIndex += 1
		if self.imageIndex == self.imageCount:
			self.imageIndex = 0
		self.updateContent()

	def decrementImage( self ):
		self.imageIndex -= 1
		if self.imageIndex == -1:
			self.imageIndex = self.imageCount -1
		self.updateContent()
			
	def setArchive( self, ca ):
		if self.mode == CoverImageWidget.ArchiveMode:
			self.resetWidget()
			self.comic_archive = ca
			self.imageIndex = 0
			self.imageCount = ca.getNumberOfPages()
			self.updateContent()

	def setIssueID( self, issue_id ):
		if self.mode == CoverImageWidget.AltCoverMode:
			self.resetWidget()
			self.updateContent()
			
			self.issue_id = issue_id

			self.comicVine = ComicVineTalker()
			self.comicVine.urlFetchComplete.connect( self.primaryUrlFetchComplete )	
			self.comicVine.asyncFetchIssueCoverURLs( int(self.issue_id) )
	
	def primaryUrlFetchComplete( self, primary_url, thumb_url, issue_id ):
		self.url_list.append(str(primary_url))
		self.imageIndex = 0
		self.imageCount = len(self.url_list)
		self.updateContent()

		#defer the alt cover search 		
		QTimer.singleShot(1, self.startAltCoverSearch)

	def startAltCoverSearch( self ):

		# now we need to get the list of alt cover URLs
		self.label.setText("Searching for alt. covers...")
		
		# page URL should already be cached, so no need to defer
		self.comicVine = ComicVineTalker()
		issue_page_url = self.comicVine.fetchIssuePageURL( self.issue_id )
		self.comicVine.altUrlListFetchComplete.connect( self.altCoverUrlListFetchComplete )	
		self.comicVine.asyncFetchAlternateCoverURLs( int(self.issue_id),  issue_page_url)
		
	def altCoverUrlListFetchComplete( self, url_list, issue_id ):
		if len(url_list) > 0:
			self.url_list.extend(url_list)
			self.imageCount = len(self.url_list)
		self.updateButtons()

	
	def updateContent( self ):
		self.updateImage()
		self.updateButtons()
		
	def updateImage( self ):
		if self.imageIndex == -1:
			self.loadDefault()
		elif self.mode == CoverImageWidget.AltCoverMode:
			self.loadURL()
		else:
			self.loadPage()
	
	def updateButtons( self ):
		if self.imageIndex == -1  or self.imageCount == 1:
			self.btnLeft.setEnabled(False)
			self.btnRight.setEnabled(False)
			self.btnLeft.hide()
			self.btnRight.hide()
		else:
			self.btnLeft.setEnabled(True)
			self.btnRight.setEnabled(True)
			self.btnLeft.show()
			self.btnRight.show()
		
		if self.imageIndex == -1  or self.imageCount == 1:
			self.label.setText("")		
		elif self.mode == CoverImageWidget.AltCoverMode:		
			if self.imageIndex == 0:
				self.label.setText("Primary Cover")
			else:
				self.label.setText("Alt. Cover {0}".format(self.imageIndex))
		else:
			self.label.setText("Page {0}".format(self.imageIndex+1))
	
	def loadURL( self ):
		self.loadDefault()
		self.cover_fetcher = ImageFetcher( )
		self.cover_fetcher.fetchComplete.connect(self.coverRemoteFetchComplete)
		self.cover_fetcher.fetch( self.url_list[self.imageIndex] )
				
	# called when the image is done loading from internet
	def coverRemoteFetchComplete( self, image_data, issue_id ):
		img = QImage()
		img.loadFromData( image_data )
		self.current_pixmap = QPixmap(img)
		self.setDisplayPixmap( 0, 0)

	def loadPage( self ):
		if self.comic_archive is not None:
			if self.page_loader is not None:
				self.page_loader.abandoned = True
			self.page_loader = PageLoader( self.comic_archive, self.imageIndex )
			self.page_loader.loadComplete.connect( self.actualChangePageImage )	
			self.page_loader.start()

	def actualChangePageImage( self, img ):
		self.page_loader = None
		self.current_pixmap = QPixmap(img)
		self.setDisplayPixmap( 0, 0)
					
	def loadDefault( self ):
		self.current_pixmap = QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' ))
		self.setDisplayPixmap( 0, 0)

	def resizeEvent( self, resize_event ):
		if self.current_pixmap is not None:
			delta_w = resize_event.size().width() - resize_event.oldSize().width()
			delta_h = resize_event.size().height() - resize_event.oldSize().height()
			self.setDisplayPixmap( delta_w , delta_h )
							
	def setDisplayPixmap( self, delta_w , delta_h ):
			# the deltas let us know what the new width and height of the label will be
			new_h = self.frame.height() + delta_h
			new_w = self.frame.width() + delta_w
			frame_w = new_w
			frame_h = new_h

			new_h -= 4
			new_w -= 4
			
			if new_h < 0:
				new_h = 0;
			if new_w < 0:
				new_w = 0;
					
			# scale the pixmap to fit in the frame
			scaled_pixmap = self.current_pixmap.scaled(new_w, new_h, Qt.KeepAspectRatio)			
			self.lblImage.setPixmap( scaled_pixmap )
			
			# move and resize the label to be centered in the fame
			img_w = scaled_pixmap.width()
			img_h = scaled_pixmap.height()
			self.lblImage.resize( img_w, img_h )
			self.lblImage.move( (frame_w - img_w)/2, (frame_h - img_h)/2 )
			
	def showPopup( self ):
		self.popup = ImagePopup(self, self.current_pixmap)
