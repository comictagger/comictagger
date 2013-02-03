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

class CoverImageWidget(QWidget):
	
	ArchiveMode = 0
	AltCoverMode = 1
	
	def __init__(self, parent, mode ):
		super(CoverImageWidget, self).__init__(parent)
		
		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'coverimagewidget.ui' ), self )

		self.mode = mode
		self.comic_archive = None
		self.issue_id = None
		self.url_list = []
		self.comicVine = ComicVineTalker()
		self.page_loader = None
		self.imageIndex = 0
		self.imageCount = 1
		
		self.btnLeft.clicked.connect( self.decrementImage )
		self.btnRight.clicked.connect( self.incrementImage )
		
		self.resetImage()

	def incrementImage( self ):
		self.imageIndex += 1
		if self.imageIndex == self.imageCount:
			self.imageIndex = 0
		self.updateImage()

	def decrementImage( self ):
		self.imageIndex -= 1
		if self.imageIndex == -1:
			self.imageIndex = self.imageCount -1
		self.updateImage()
			
	def setArchive( self, ca ):
		if self.mode == CoverImageWidget.ArchiveMode:
			self.comic_archive = ca
			self.imageIndex = 0
			self.imageCount = ca.getNumberOfPages()
			self.updateImage()

	def setIssueID( self, issue_id ):
		if self.mode == CoverImageWidget.AltCoverMode:
			self.issue_id = issue_id
			self.url_list = []
			self.imageIndex = 0
			self.imageCount = 1
	
			# get the URL list
			try: 
				alt_img_url_list = self.comicVine.fetchAlternateCoverURLs( issue_id )	
				primary_url, thumb_url = self.comicVine.fetchIssueCoverURLs( issue_id  )
			except:
				return

			self.url_list.append(primary_url)
			self.url_list.extend(alt_img_url_list)
			self.imageIndex = 0
			self.imageCount = len(self.url_list)
			self.updateImage()
	
	def updateImage( self ):
		if self.mode == CoverImageWidget.AltCoverMode:
			if self.imageIndex == 0:
				self.label.setText("Primary Cover")
			else:
				self.label.setText("Alt. Cover {0}".format(self.imageIndex))
			self.loadURL()
		else:
			self.label.setText("Page {0}".format(self.imageIndex+1))
			self.loadPage()
			pass
	
	def loadURL( self ):
		self.cover_fetcher = ImageFetcher( )
		self.cover_fetcher.fetchComplete.connect(self.coverRemoteFetchComplete)
		self.cover_fetcher.fetch( self.url_list[self.imageIndex] )
				
	# called when the image is done loading from internet
	def coverRemoteFetchComplete( self, image_data, issue_id ):
		img = QImage()
		img.loadFromData( image_data )
		self.current_pixmap = QPixmap(img)
		self.setDisplayPixmap( 0, 0)
		QCoreApplication.processEvents()

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
					
	def resetImage( self ):
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
