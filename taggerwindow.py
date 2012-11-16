# coding=utf-8
"""
The main window of the comictagger app
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

from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import QUrl,pyqtSignal

import locale
import platform
import os

from volumeselectionwindow import VolumeSelectionWindow
from options import Options, MetaDataStyle
from comicinfoxml import ComicInfoXml
from genericmetadata import GenericMetadata
from comicvinetalker import ComicVineTalker
from comicarchive import ComicArchive
from crediteditorwindow import CreditEditorWindow
from settingswindow import SettingsWindow
from settings import ComicTaggerSettings
from pagebrowser import PageBrowserWindow
from filenameparser import FileNameParser
import utils
import ctversion


# this reads the environment and inits the right locale
locale.setlocale(locale.LC_ALL, "")

# helper func to allow a label to be clickable
def clickable(widget):

	class Filter(QtCore.QObject):
	
		dblclicked = pyqtSignal()
		
		def eventFilter(self, obj, event):
		
			if obj == widget:
				if event.type() == QtCore.QEvent.MouseButtonDblClick:
					self.dblclicked.emit()
					return True
			
			return False
	
	filter = Filter(widget)
	widget.installEventFilter(filter)
	return filter.dblclicked

"""
class PageTableModel(QtCore.QAbstractTableModel):
	
	def __init__(self, comic_archive, parent=None, *args):	
		QtCore.QAbstractTableModel.__init__(self, parent, *args)
		
		self.comic_archive = comic_archive
		page_list = comic_archive.getPageNameList()
		
		self.page_model = []
		i = 0
		for page in page_list:
			item = dict()
			item['number'] = i
			item['filename'] = page
			item['thumb'] = None
			
			self.page_model.append( item )
			i +=1


	def rowCount(self, parent):
		return len(self.page_model)

	def columnCount(self, parent):
		return 3

	def data(self, index, role):
		
		if not index.isValid():
			return QtCore.QVariant()
		
		elif role == QtCore.Qt.DisplayRole:
			# page num
			if index.column() == 0:
				return QtCore.QVariant(self.page_model[index.row()]['number'])
			
			# page filename
			if index.column() == 1:
				return QtCore.QVariant(self.page_model[index.row()]['filename'])			

		elif role == QtCore.Qt.DecorationRole:
			
			if index.column() == 2:
				if self.page_model[index.row()]['thumb'] is None:
				
					image_data = self.comic_archive.getPage( self.page_model[index.row()]['number'] )
					img = QtGui.QImage()
					img.loadFromData( image_data )
					pixmap = QtGui.QPixmap(QtGui.QPixmap(img))
					#scaled_pixmap = pixmap.scaled(100, 150, QtCore.Qt.KeepAspectRatio)

					self.page_model[index.row()]['thumb'] = pixmap #scaled_pixmap
				
				return QtCore.QVariant(self.page_model[index.row()]['thumb'])		
		
		else:
			return QtCore.QVariant()
"""	
class PageListModel(QtCore.QAbstractListModel):
	
	def __init__(self, comic_archive, parent=None, *args):	
		QtCore.QAbstractTableModel.__init__(self, parent, *args)
		
		self.comic_archive = comic_archive
		page_list = comic_archive.getPageNameList()
		
		self.page_model = []
		i = 0
		for page in page_list:
			item = dict()
			item['number'] = i
			item['filename'] = page
			item['thumb'] = None
			
			self.page_model.append( item )
			i +=1

	def rowCount(self, parent):
		return len(self.page_model)

	def data(self, index, role):
		
		if not index.isValid():
			return QtCore.QVariant()
		
		elif role == QtCore.Qt.DisplayRole:
			# page num
			return QtCore.QVariant(self.page_model[index.row()]['number'])

		elif role == QtCore.Qt.DecorationRole:
			
			if self.page_model[index.row()]['thumb'] is None:

				#timestamp = datetime.datetime.now()
			
				image_data = self.comic_archive.getPage( self.page_model[index.row()]['number'] )
				img = QtGui.QImage()
				img.loadFromData( image_data )
				pixmap = QtGui.QPixmap(QtGui.QPixmap(img))
				scaled_pixmap = pixmap.scaled(100, 150, QtCore.Qt.KeepAspectRatio)

				self.page_model[index.row()]['thumb'] = scaled_pixmap
			
			return QtCore.QVariant(self.page_model[index.row()]['thumb'])		
		
		else:
			return QtCore.QVariant()
		
	def flags( self, index):
		defaultFlags = 	QtCore.QAbstractTableModel.flags(self, index)
		if index.isValid():
			return QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled | defaultFlags
		else:
			return QtCore.Qt.ItemIsDropEnabled | defaultFlags

	def removeRows(self, row, count, parent=QtCore.QModelIndex()):
		
		print "removeRows", row, count
		return True
	
	def insertRows(self, row, count, parent=QtCore.QModelIndex()):
		
		print "insertRows", row, count
		return False	

	def beginRemoveRows(self, sourceParent, start, end, destinationParent, dest):
		print "beginRemoveRows"

	def dropMimeData(self,data, action, row, col, parent):     
		print "dropMimeData", action, row, col
		

		if (row != -1):
			beginRow = row

		elif (parent.isValid()):
			beginRow = parent.row()	
		
		print beginRow
		
		return True
		if (action == QtCore.Qt.IgnoreAction):
			return True

		#if ( not data.hasFormat("application/vnd.text.list"))
		#	return False

		if (column > 0):
			return False	
	#def beginMoveRows(self, sourceParent, start, end, destinationParent, dest):
	#	print "rowsMoved"
		
	def	supportedDropActions(self):
		#print "supportedDropActions"
		return QtCore.Qt.CopyAction | QtCore.Qt.MoveAction


class TaggerWindow( QtGui.QMainWindow):
	
	appName = "ComicTagger"
	version = ctversion.version
	
	def __init__(self, opts, settings, parent = None):
		super(TaggerWindow, self).__init__(parent)

		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'taggerwindow.ui' ), self)
		self.setWindowIcon(QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(), 'app.png' )))
		
		self.lblCover.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'nocover.png' )))
		self.center()
		self.show()
		self.raise_()
		
		#print platform.system(), platform.release()
		self.dirtyFlag = False
		self.opts = opts
		self.settings = settings
		self.data_style = opts.data_style
		
		#set up a default metadata object
		self.metadata = GenericMetadata()
		self.comic_archive = None

		self.configMenus()
		self.statusBar()
		self.updateAppTitle()
		self.setAcceptDrops(True)
		self.droppedFile=None

		self.page_browser = None
	
		self.populateComboBoxes()	

		# hook up the callbacks		
		self.cbDataStyle.currentIndexChanged.connect(self.setDataStyle)
		self.btnEditCredit.clicked.connect(self.editCredit)	
		self.btnAddCredit.clicked.connect(self.addCredit)	
		self.btnRemoveCredit.clicked.connect(self.removeCredit)	
		self.twCredits.cellDoubleClicked.connect(self.editCredit)
		clickable(self.lblCover).connect(self.showPageBrowser)
		self.connectDirtyFlagSignals()
		
		self.updateStyleTweaks()


		self.openArchive( opts.filename )

		# fill in some explicit metadata stuff from our options
		# this overrides what we just read in
		if self.metadata.series is None:
			self.metadata.series = opts.series_name
		if self.metadata.issueNumber is None:
			self.metadata.issueNumber = opts.issue_number


	def updateAppTitle( self ):
			
		if self.comic_archive is None:
			self.setWindowTitle( self.appName )
		else:
			mod_str = ""
			ro_str = ""
			
			if self.dirtyFlag:
				mod_str = " [modified]"
			
			if not self.comic_archive.isWritable():
				ro_str = " [read only ]"
				
			self.setWindowTitle( self.appName + " - " + self.comic_archive.path + mod_str + ro_str)

	def configMenus( self):
		
		# File Menu
		self.actionExit.setShortcut( 'Ctrl+Q' )
		self.actionExit.setStatusTip( 'Exit application' )
		self.actionExit.triggered.connect( self.close )

		self.actionLoad.setShortcut( 'Ctrl+O' )
		self.actionLoad.setStatusTip( 'Load comic archive' )
		self.actionLoad.triggered.connect( self.selectFile )

		self.actionWrite_Tags.setShortcut( 'Ctrl+S' )
		self.actionWrite_Tags.setStatusTip( 'Save tags to comic archive' )
		self.actionWrite_Tags.triggered.connect( self.commitMetadata )

		self.actionRemoveCBLTags.setStatusTip( 'Remove ComicBookLover tags from comic archive' )
		self.actionRemoveCBLTags.triggered.connect( self.removeCBLTags )

		self.actionRemoveCRTags.setStatusTip( 'Remove ComicRack tags from comic archive' )
		self.actionRemoveCRTags.triggered.connect( self.removeCRTags )

		self.actionReloadAuto.setShortcut( 'Ctrl+R' )
		self.actionReloadAuto.setStatusTip( 'Reload selected style tags from archive' )
		self.actionReloadAuto.triggered.connect( self.reloadAuto )

		self.actionReloadCBLTags.setStatusTip( 'Reload ComicBookLover tags' )
		self.actionReloadCBLTags.triggered.connect( self.reloadCBLTags )

		self.actionReloadCRTags.setStatusTip( 'Reload ComicRack tags' )
		self.actionReloadCRTags.triggered.connect( self.reloadCRTags )
	
		#self.actionRepackage.setShortcut(  )
		self.actionRepackage.setStatusTip( 'Re-create archive as CBZ' )
		self.actionRepackage.triggered.connect( self.repackageArchive )
		
		#self.actionRepackage.setShortcut(  )
		self.actionSettings.setStatusTip( 'Configure ComicTagger' )
		self.actionSettings.triggered.connect( self.showSettings )
		
		# Tag Menu
		self.actionParse_Filename.setShortcut( 'Ctrl+F' )
		self.actionParse_Filename.setStatusTip( 'Try to extract tags from filename' )
		self.actionParse_Filename.triggered.connect( self.useFilename )

		self.actionSearchOnline.setShortcut( 'Ctrl+W' )
		self.actionSearchOnline.setStatusTip( 'Search online for tags' )
		self.actionSearchOnline.triggered.connect( self.queryOnline )

		self.actionAutoSearch.triggered.connect( self.autoSelectSearch )
		
		#self.actionClearEntryForm.setShortcut( 'Ctrl+C' )
		self.actionClearEntryForm.setStatusTip( 'Clear all the data on the screen' )
		self.actionClearEntryForm.triggered.connect( self.clearForm )

		# Window Menu
		self.actionPageBrowser.setShortcut( 'Ctrl+P' )
		self.actionPageBrowser.setStatusTip( 'Show the page browser' )
		self.actionPageBrowser.triggered.connect( self.showPageBrowser )

		# Help Menu
		self.actionAbout.setShortcut( 'Ctrl+A' )
		self.actionAbout.setStatusTip( 'Show the ' + self.appName + ' info' )
		self.actionAbout.triggered.connect( self.aboutApp )
	
		# ToolBar
	
		self.actionLoad.setIcon( QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(),'graphics/open.png')) )
		self.actionWrite_Tags.setIcon( QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(),'graphics/save.png')) )
		self.actionParse_Filename.setIcon( QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(),'graphics/parse.png')) )
		self.actionSearchOnline.setIcon( QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(),'graphics/search.png')) )
		self.actionAutoSearch.setIcon( QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(),'graphics/auto.png')) )
		self.actionClearEntryForm.setIcon( QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(),'graphics/clear.png')) )
		self.actionPageBrowser.setIcon( QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(),'graphics/browse.png') ))
		
		self.toolBar.addAction( self.actionLoad )
		self.toolBar.addAction( self.actionWrite_Tags )
		self.toolBar.addAction( self.actionParse_Filename )
		self.toolBar.addAction( self.actionSearchOnline )
		self.toolBar.addAction( self.actionAutoSearch )
		self.toolBar.addAction( self.actionClearEntryForm )
		self.toolBar.addAction( self.actionPageBrowser )
		#self.toolBar.addAction( self.actionRemoveCBLTags )
		#self.toolBar.addAction( self.actionRemoveCRTags )
        
	def repackageArchive( self ):
		QtGui.QMessageBox.information(self, self.tr("Repackage Comic Archive"), self.tr("TBD"))

	def aboutApp( self ):
		QtGui.QMessageBox.about (self, self.tr("About " + self.appName ), 
							self.tr(self.appName) + " " 
							+ self.version 
							+"\n(c)2012 Anthony Beville")

		
	def dragEnterEvent(self, event):
		self.droppedFile=None
		if event.mimeData().hasUrls():
			url=event.mimeData().urls()[0]
			if url.isValid():
				if url.scheme()=="file":
					self.droppedFile=url.toLocalFile()
					event.accept()
 
	def dropEvent(self, event):
		if self.dirtyFlagVerification( "Open Archive",
									"If you open a new archive now, data in the form will be lost.  Are you sure?"):
			self.openArchive( str(self.droppedFile) ) 
					
	def openArchive( self, path, explicit_style=None, clear_form=True ):
		
		if path is None or path == "":
			return
		
		ca = ComicArchive( path )
		if self.settings.rar_exe_path != "":
			ca.setExternalRarProgram( self.settings.rar_exe_path )	
				
		if ca is not None and ca.seemsToBeAComicArchive():

			# clear form and current metadata, we're all in!
			if clear_form:
				self.clearForm()
			
			self.comic_archive = ca
			
			if explicit_style is None:
				hasCBI = ca.hasCBI()
				hasCIX = ca.hasCIX()			
				hasNeither = not hasCIX and not hasCBI
				
				# no style indicated, so try to choose
				if hasNeither:
					self.metadata = self.comic_archive.metadataFromFilename( )
				else:	
					if hasCBI and not hasCIX:
						self.data_style = MetaDataStyle.CBI
					elif hasCIX and not hasCBI:
						self.data_style = MetaDataStyle.CIX
					else:  #both
						reply = QtGui.QMessageBox.question(self, 
														self.tr("Multiple Tag Types!"), 
														self.tr("This archive has both ComicBookLover and ComicRack type tags.  Which do you want to load?"),
														self.tr("ComicBookLover"), self.tr("ComicRack" ))

						if reply == 0: 
							# ComicBookLover
							self.data_style = MetaDataStyle.CBI
						else:
							self.data_style = MetaDataStyle.CIX
					self.adjustStyleCombo()
					self.metadata = self.comic_archive.readMetadata( self.data_style )
			else:
				if ca.hasMetadata( explicit_style ):
					self.data_style = explicit_style
					self.adjustStyleCombo()
					self.metadata = self.comic_archive.readMetadata( self.data_style )
				else:
					return
					
			if self.metadata.isEmpty:
				self.metadata = self.comic_archive.metadataFromFilename( )
				
			image_data = self.comic_archive.getCoverPage()
			if not image_data is None:
				img = QtGui.QImage()
				img.loadFromData( image_data )
				self.lblCover.setPixmap(QtGui.QPixmap(img))
				self.lblCover.setScaledContents(True)
			
			if self.page_browser is not None:
				self.page_browser.setComicArchive( self.comic_archive )

			self.metadataToForm()
			self.clearDirtyFlag()  # also updates the app title
			self.updateInfoBox()		
			#self.updatePagesInfo()
			
		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops!"), self.tr("That file doesn't appear to be a comic archive!"))

	def updateInfoBox( self ):
		
		ca = self.comic_archive
	
		filename = os.path.basename( ca.path )
		filename = os.path.splitext(filename)[0]
		filename = FileNameParser().fixSpaces(filename)

		self.lblFilename.setText( filename )

		if ca.isZip():
			self.lblArchiveType.setText( "ZIP archive" )
		elif ca.isRar():
			self.lblArchiveType.setText( "RAR archive" )
		elif ca.isFolder():
			self.lblArchiveType.setText( "Folder archive" )
		else:
			self.lblArchiveType.setText( "" )
			
		page_count = " ({0} pages)".format(ca.getNumberOfPages())
		self.lblPageCount.setText( page_count)
		
		tag_info = ""
		if ca.hasCIX():
			tag_info = u"• ComicRack tags"
		if ca.hasCBI():
			if tag_info != "":
				tag_info += "\n"
			tag_info += u"• ComicBookLover tags"

		self.lblTagList.setText( tag_info )

	def updatePagesInfo( self ):
		
		#tablemodel = PageTableModel( self.comic_archive, self )
		#self.tableView.setModel(tablemodel)

		listmodel = PageListModel( self.comic_archive, self )
		self.listView.setModel(listmodel)

		#self.listView.setDragDropMode(self.InternalMove)
		#listmodel.installEventFilter(self)
		
		self.listView.setDragEnabled(True)
		self.listView.setAcceptDrops(True)
		self.listView.setDropIndicatorShown(True)
		
		#listmodel.rowsMoved.connect( self.rowsMoved )
		#listmodel.rowsRemoved.connect( self.rowsRemoved )
		#listmodel.beginMoveRows.connect( self.beginMoveRows )
	
	#def rowsMoved( self, b, c, d):
	#	print "rowsMoved"
	#def rowsRemoved( self,b, c, d):
	#	print "rowsRemoved"
	

	"""
	def eventFilter(self, sender, event):
		if (event.type() == QtCore.QEvent.ChildRemoved):
			print "QEvent::ChildRemoved"
		return False # don't actually interrupt anything
	"""
        
        
	def setDirtyFlag( self, param1=None, param2=None, param3=None  ):
		if not self.dirtyFlag:
			self.dirtyFlag = True
			self.updateAppTitle()

	def clearDirtyFlag( self ):
		if self.dirtyFlag:
			self.dirtyFlag = False
			self.updateAppTitle()
		
	def connectDirtyFlagSignals( self ):		
		# recursivly connect the tab form child slots
		self.connectChildDirtyFlagSignals( self.tabWidget )
		
	def connectChildDirtyFlagSignals (self, widget ):

		if ( isinstance(widget, QtGui.QLineEdit)):
			widget.textEdited.connect(self.setDirtyFlag)
		if ( isinstance(widget, QtGui.QTextEdit)):
			widget.textChanged.connect(self.setDirtyFlag)
		if ( isinstance(widget, QtGui.QComboBox) ):
			widget.currentIndexChanged.connect(self.setDirtyFlag)
		if ( isinstance(widget, QtGui.QCheckBox) ):
			widget.stateChanged.connect(self.setDirtyFlag)

		# recursive call on chillun
		for child in widget.children():
			self.connectChildDirtyFlagSignals( child )

	
	def clearForm( self ):		
	
		# get a minty fresh metadata object
		self.metadata = GenericMetadata()
		
		# recursivly clear the tab form
		self.clearChildren( self.tabWidget )
		
		# clear the dirty flag, since there is nothing in there now to lose
		self.clearDirtyFlag()  
		
		
	def clearChildren (self, widget ):

		if ( isinstance(widget, QtGui.QLineEdit) or   
				isinstance(widget, QtGui.QTextEdit)):
			widget.setText("")
		if ( isinstance(widget, QtGui.QComboBox) ):
			widget.setCurrentIndex( 0 )
		if ( isinstance(widget, QtGui.QCheckBox) ):
			widget.setChecked( False )
		if ( isinstance(widget, QtGui.QTableWidget) ):
			while widget.rowCount() > 0:
				widget.removeRow(0)

		# recursive call on chillun
		for child in widget.children():
			self.clearChildren( child )

		
	def metadataToForm( self ):
		# copy the the metadata object into to the form
		
		#helper func
		def assignText( field, value):
			if value is not None:
				field.setText( u"{0}".format(value) )
			
		md = self.metadata
		
		assignText( self.leSeries,       md.series )
		assignText( self.leIssueNum,     md.issueNumber )
		assignText( self.leIssueCount,   md.issueCount )
		assignText( self.leVolumeNum,    md.volumeNumber )
		assignText( self.leVolumeCount,  md.volumeCount )
		assignText( self.leTitle,        md.title )
		assignText( self.lePublisher,    md.publisher )
		assignText( self.lePubMonth,     md.publicationMonth )
		assignText( self.lePubYear,      md.publicationYear )
		assignText( self.leGenre,        md.genre )
		assignText( self.leImprint,      md.imprint )
		assignText( self.teComments,     md.comments )
		assignText( self.teNotes,        md.notes )
		assignText( self.leCriticalRating, md.criticalRating )
		assignText( self.leStoryArc,      md.storyArc )
		assignText( self.leScanInfo,      md.scanInfo )
		assignText( self.leSeriesGroup,   md.seriesGroup )
		assignText( self.leAltSeries,     md.alternateSeries )
		assignText( self.leAltIssueNum,   md.alternateNumber )
		assignText( self.leAltIssueCount, md.alternateCount )
		assignText( self.leWebLink,       md.webLink )
		assignText( self.teCharacters,    md.characters )
		assignText( self.teTeams,         md.teams )
		assignText( self.teLocations,     md.locations )
		
		if md.format is not None and md.format != "":
			i = self.cbFormat.findText( md.format )
			if i == -1:
				self.cbFormat.setEditText( md.format  )
			else:	
				self.cbFormat.setCurrentIndex( i )

		if md.maturityRating is not None and md.maturityRating != "":
			i = self.cbMaturityRating.findText( md.maturityRating )
			if i == -1:
				self.cbMaturityRating.setEditText( md.maturityRating  )
			else:	
				self.cbMaturityRating.setCurrentIndex( i )
			
		if md.language is not None:
			i = self.cbLanguage.findData( md.language )
			self.cbLanguage.setCurrentIndex( i )

		if md.country is not None:
			i = self.cbCountry.findText( md.country )
			self.cbCountry.setCurrentIndex( i )
		
		if md.manga is not None:
			i = self.cbManga.findData( md.manga )
			self.cbManga.setCurrentIndex( i )
		
		if md.blackAndWhite is not None and md.blackAndWhite:
			self.cbBW.setChecked( True )

		assignText( self.teTags, utils.listToString( md.tags ) )
			
		# !!! Should we clear the credits table or just avoid duplicates?
		while self.twCredits.rowCount() > 0:
			self.twCredits.removeRow(0)

		if md.credits is not None and len(md.credits) != 0:
		
			self.twCredits.setSortingEnabled( False )
	
			row = 0
			for credit in md.credits: 
				# if the role-person pair already exists, just skip adding it to the list
				if self.isDupeCredit( credit['role'].title(), credit['person']):
					continue
				
				self.addNewCreditEntry( row, credit['role'].title(), credit['person'] )

				row += 1
				
		self.twCredits.setSortingEnabled( True )
		self.updateCreditColors()

	def addNewCreditEntry( self, row, role, name ):
		self.twCredits.insertRow(row)
		
		item_text = role
		item = QtGui.QTableWidgetItem(item_text)			
		item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
		self.twCredits.setItem(row, 0, item)
		
		item_text = name
		item = QtGui.QTableWidgetItem(item_text)			
		item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
		self.twCredits.setItem(row, 1, item)
		
		
	def isDupeCredit( self, role, name ):
		r = 0
		while r < self.twCredits.rowCount():
			if ( self.twCredits.item(r, 0).text() == role and
					self.twCredits.item(r, 1).text() == name ):
				return True
			r = r + 1
			
		return False

	def formToMetadata( self ):
		
		#helper func
		def xlate( data, type_str):
			s = u"{0}".format(data).strip()
			if s == "":
				return None
			elif type_str == "str":
				return s
			else:
				return int(s)

		# copy the data from the form into the metadata
		md = self.metadata
		md.series =             xlate( self.leSeries.text(), "str" )
		md.issueNumber =        xlate( self.leIssueNum.text(), "str" )
		md.issueCount =         xlate( self.leIssueCount.text(), "int" )
		md.volumeNumber =       xlate( self.leVolumeNum.text(), "int" )
		md.volumeCount =        xlate( self.leVolumeCount.text(), "int" )
		md.title =              xlate( self.leTitle.text(), "str" )
		md.publisher =          xlate( self.lePublisher.text(), "str" )
		md.publicationMonth =   xlate( self.lePubMonth.text(), "int" )
		md.publicationYear =    xlate( self.lePubYear.text(), "int" )
		md.genre =              xlate( self.leGenre.text(), "str" )
		md.imprint =            xlate( self.leImprint.text(), "str" )
		md.comments =           xlate( self.teComments.toPlainText(), "str" )
		md.notes =              xlate( self.teNotes.toPlainText(), "str" )
		md.criticalRating =     xlate( self.leCriticalRating.text(), "int" )
		md.maturityRating =     xlate( self.cbMaturityRating.currentText(), "str" )

		md.storyArc =           xlate( self.leStoryArc.text(), "str" )
		md.scanInfo =           xlate( self.leScanInfo.text(), "str" )
		md.seriesGroup =        xlate( self.leSeriesGroup.text(), "str" )
		md.alternateSeries =    xlate( self.leAltSeries.text(), "str" )
		md.alternateNumber =    xlate( self.leAltIssueNum.text(), "int" )
		md.alternateCount =     xlate( self.leAltIssueCount.text(), "int" )
		md.webLink =            xlate( self.leWebLink.text(), "str" )
		md.characters =         xlate( self.teCharacters.toPlainText(), "str" )
		md.teams =              xlate( self.teTeams.toPlainText(), "str" )
		md.locations =          xlate( self.teLocations.toPlainText(), "str" )

		md.format =             xlate( self.cbFormat.currentText(), "str" )
		md.country =            xlate( self.cbCountry.currentText(), "str" )
		
		langiso = self.cbLanguage.itemData(self.cbLanguage.currentIndex()).toString()
		md.language =           xlate( langiso, "str" )

		manga_code = self.cbManga.itemData(self.cbManga.currentIndex()).toString()
		md.manga =           xlate( manga_code, "str" )
	
		# Make a list from the coma delimited tags string
		tmp = xlate( self.teTags.toPlainText(), "str" )
		if tmp != None:
			def striplist(l):
				return([x.strip() for x in l])

			md.tags = striplist(tmp.split( "," ))

		if ( self.cbBW.isChecked() ):
			md.blackAndWhite = True
		else:
			md.blackAndWhite = False

		# get the credits from the table
		md.credits = list()
		row = 0
		while row < self.twCredits.rowCount():
			role = str(self.twCredits.item(row, 0).text())
			name = str(self.twCredits.item(row, 1).text())
			md.addCredit( name, role, False )
			row += 1


	def useFilename( self ):
		self.metadata = self.comic_archive.metadataFromFilename( )
		self.metadataToForm()


	def selectFile( self ):
		
		dialog = QtGui.QFileDialog(self)
		dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
		#dialog.setFileMode(QtGui.QFileDialog.Directory )
		filters  = [ 
		             "Comic archive files (*.cbz *.zip *.cbr *.rar)",
		             "Any files (*)"
		             ]
		
		dialog.setNameFilters(filters)
		#dialog.setFilter (self, QString filter)
		
		if (dialog.exec_()):
			fileList = dialog.selectedFiles()
			if self.dirtyFlagVerification( "Open Archive",
										"If you open a new archive now, data in the form will be lost.  Are you sure?"):
				self.openArchive( str(fileList[0]) )  

			
	def autoSelectSearch(self):
		if self.comic_archive is None:
			QtGui.QMessageBox.warning(self, self.tr("Automatic Search"), 
			       self.tr("You need to load a comic first!"))
			return
		
		self.queryOnline( autoselect=True )
		
	def queryOnline(self, autoselect=False):
		
		if self.settings.cv_api_key == "":
			QtGui.QMessageBox.warning(self, self.tr("Online Search"), 
			       self.tr("You need an API key from ComicVine to search online. " + 
			                "Go to settings and enter it."))
			return
		
	
		if str(self.leSeries.text()).strip() != "":
			series_name = str(self.leSeries.text()).strip()
		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops"), self.tr("Need to enter a series name to query."))
			return
			
		issue_number = str(self.leIssueNum.text()).strip()
		
		selector = VolumeSelectionWindow( self, self.settings.cv_api_key, series_name, issue_number, self.comic_archive, self.settings, autoselect )
		selector.setModal(True)
		selector.exec_()

		
		if selector.result():
			#we should now have a volume ID
			QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

			comicVine = ComicVineTalker( self.settings.cv_api_key )
			self.metadata = comicVine.fetchIssueData( selector.volume_id, selector.issue_number )

			# Now push the right data into the edit controls
			self.metadataToForm()
			#!!!ATB should I clear the form???
			QtGui.QApplication.restoreOverrideCursor()		

	def commitMetadata(self):

		if ( self.metadata is not None and self.comic_archive is not None):	
			QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
			self.formToMetadata()
			self.comic_archive.writeMetadata( self.metadata, self.data_style )
			self.clearDirtyFlag()
			self.updateInfoBox()
			QtGui.QApplication.restoreOverrideCursor()		
			
			QtGui.QMessageBox.information(self, self.tr("Yeah!"), self.tr("File written."))


		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops!"), self.tr("No data to commit!"))


	def setDataStyle(self, s):
		self.data_style, b = self.cbDataStyle.itemData(s).toInt()
		self.updateStyleTweaks()
		
	def updateCreditColors( self ):
		inactive_color = QtGui.QColor(255, 170, 150)
		active_palette = self.leSeries.palette()
		active_color = active_palette.color( QtGui.QPalette.Base )

		cix_credits = ComicInfoXml().getParseableCredits()

		if self.data_style == MetaDataStyle.CIX:
			#loop over credit table, mark selected rows
			r = 0
			while r < self.twCredits.rowCount():
				if str(self.twCredits.item(r, 0).text()).lower() not in cix_credits:
					print "Bad credit for CIX:", self.twCredits.item(r, 0).text()
					self.twCredits.item(r, 0).setBackgroundColor( inactive_color )
				else:
					self.twCredits.item(r, 0).setBackgroundColor( active_color )
				r = r + 1
		
		if self.data_style == MetaDataStyle.CBI:
			#loop over credit table, make all active color
			r = 0
			while r < self.twCredits.rowCount():
				self.twCredits.item(r, 0).setBackgroundColor( active_color )
				r = r + 1
		

	def updateStyleTweaks( self ):

		# depending on the current data style, certain fields are disabled
		
		inactive_color = QtGui.QColor(255, 170, 150)
		active_palette = self.leSeries.palette()
		
		inactive_palette1 = self.leSeries.palette()
		inactive_palette1.setColor(QtGui.QPalette.Base, inactive_color)

		inactive_palette2 = self.leSeries.palette()

		inactive_palette3 = self.leSeries.palette()
		inactive_palette3.setColor(QtGui.QPalette.Base, inactive_color)
		
		inactive_palette3.setColor(QtGui.QPalette.Base, inactive_color)

		#helper func
		def enableWidget( item, enable ):
			inactive_palette3.setColor(item.backgroundRole(), inactive_color)
			inactive_palette2.setColor(item.backgroundRole(), inactive_color)
			inactive_palette3.setColor(item.foregroundRole(), inactive_color)

			if enable:
				item.setPalette(active_palette)
				item.setAutoFillBackground( False )
				if type(item) == QtGui.QCheckBox:
					item.setEnabled( True )
				elif type(item) == QtGui.QComboBox:
					item.setEnabled( True )
				else:
					item.setReadOnly( False )
			else:
				item.setAutoFillBackground( True )
				if type(item) == QtGui.QCheckBox:
					item.setPalette(inactive_palette2)
					item.setEnabled( False )
				elif type(item) == QtGui.QComboBox:
					item.setPalette(inactive_palette3)
					item.setEnabled( False )
				else:
					item.setReadOnly( True )
					item.setPalette(inactive_palette1)

		
		cbi_only = [ self.leVolumeCount, self.cbCountry, self.leCriticalRating, self.teTags ]
		cix_only = [ 
						self.leImprint, self.teNotes, self.cbBW, self.cbManga,
						self.leStoryArc, self.leScanInfo, self.leSeriesGroup, 
						self.leAltSeries, self.leAltIssueNum, self.leAltIssueCount,
						self.leWebLink, self.teCharacters, self.teTeams,
						self.teLocations, self.cbMaturityRating, self.cbFormat
					]
							
		if self.data_style == MetaDataStyle.CIX:
			for item in cix_only:
				enableWidget( item, True )
			for item in cbi_only:
				enableWidget(item, False )
		
		if self.data_style == MetaDataStyle.CBI:
			for item in cbi_only:
				enableWidget( item, True )
			for item in cix_only:
				enableWidget(item, False )
		
		self.updateCreditColors()
	
	def cellDoubleClicked( self, r, c ):
		self.editCredit()

	def addCredit( self ):
		self.modifyCredits( "add" )
		
	def editCredit( self ):
		if ( self.twCredits.currentRow() > -1 ):
			self.modifyCredits( "edit" )
		
	def modifyCredits( self , action ):
		
		if action == "edit":
			row = self.twCredits.currentRow()
			role = self.twCredits.item( row, 0 ).text()
			name = self.twCredits.item( row, 1 ).text()
		else:
			role = ""
			name = ""
		
		editor = CreditEditorWindow( self, CreditEditorWindow.ModeEdit, role, name )
		editor.setModal(True)
		editor.exec_()
		if editor.result():
			new_role, new_name =  editor.getCredits()
			
			if new_name == name and new_role == role:
				#nothing has changed, just quit
				return
			
			# check for dupes
			ok_to_mod = True
			if self.isDupeCredit( new_role, new_name):
				# delete the dupe credit from list
				#TODO warn user!!
				reply = QtGui.QMessageBox.question(self, 
								self.tr("Duplicate Credit!"), 
								self.tr("This will create a duplicate credit entry. Would you like to merge the entries, or create a duplicate?"),
								self.tr("Merge"), self.tr("Duplicate" ))

				if reply == 0: 
					# merge
					if action == "edit":
						# just remove the row that would be same
						self.twCredits.removeRow( row )
						
					ok_to_mod = False

		
			if ok_to_mod:
				#modify it
				if action == "edit":
					self.twCredits.item(row, 0).setText( new_role )
					self.twCredits.item(row, 1).setText( new_name )
				else:
					# add new entry
					row = self.twCredits.rowCount()
					self.addNewCreditEntry( row, new_role, new_name)

			self.updateCreditColors()	
			self.setDirtyFlag()

	def removeCredit( self ):
		row = self.twCredits.currentRow()
		if row != -1 :
			self.twCredits.removeRow( row )
		self.setDirtyFlag()

	def showSettings( self ):

		settingswin = SettingsWindow( self, self.settings )
		settingswin.setModal(True)
		settingswin.exec_()
		if settingswin.result():
			pass

	def center(self):
		screen = QtGui.QDesktopWidget().screenGeometry()
		size =  self.geometry()
		self.move((screen.width()-size.width())/2, (screen.height()-size.height())/2)
		
	def adjustStyleCombo( self ):
		# select the current style
		if ( self.data_style == MetaDataStyle.CBI ):
			self.cbDataStyle.setCurrentIndex ( 0 )
		elif ( self.data_style == MetaDataStyle.CIX ):
			self.cbDataStyle.setCurrentIndex ( 1 )
		self.updateStyleTweaks()
		

	def populateComboBoxes( self ):
		    
		# Add the entries to the tag style combobox
		self.cbDataStyle.addItem( "ComicBookLover", MetaDataStyle.CBI )
		self.cbDataStyle.addItem( "ComicRack", MetaDataStyle.CIX )
		self.adjustStyleCombo()
			
		# Add the entries to the country combobox
		self.cbCountry.addItem( "", "" )
		for c in utils.countries:
			self.cbCountry.addItem( c[1], c[0] )
		
		# Add the entries to the language combobox
		self.cbLanguage.addItem( "", "" )
		lang_dict = utils.getLanguageDict()
		for key in sorted(lang_dict, cmp=locale.strcoll, key=lang_dict.get):
			self.cbLanguage.addItem(  lang_dict[key], key )
		
		# Add the entries to the manga combobox
		self.cbManga.addItem( "", "" )
		self.cbManga.addItem( "Yes", "Yes" )
		self.cbManga.addItem( "Yes (Right to Left)", "YesAndRightToLeft" )
		self.cbManga.addItem( "No", "No" )

		# Add the entries to the maturity combobox
		self.cbMaturityRating.addItem( "", "" )
		self.cbMaturityRating.addItem( "Everyone", "" )
		self.cbMaturityRating.addItem( "G", "" )
		self.cbMaturityRating.addItem( "Early Childhood", "" )
		self.cbMaturityRating.addItem( "Everyone 10+", "" )
		self.cbMaturityRating.addItem( "PG", "" )
		self.cbMaturityRating.addItem( "Kids to Adults", "" )
		self.cbMaturityRating.addItem( "Teen", "" )
		self.cbMaturityRating.addItem( "MA15+", "" )
		self.cbMaturityRating.addItem( "Mature 17+", "" )
		self.cbMaturityRating.addItem( "R18+", "" )
		self.cbMaturityRating.addItem( "X18+", "" )
		self.cbMaturityRating.addItem( "Adults Only 18+", "" )
		self.cbMaturityRating.addItem( "Rating Pending", "" )
		
		# Add entries to the format combobox
		self.cbFormat.addItem("")
		self.cbFormat.addItem(".1")
		self.cbFormat.addItem("-1")
		self.cbFormat.addItem("1 Shot")
		self.cbFormat.addItem("1/2")
		self.cbFormat.addItem("1-Shot")
		self.cbFormat.addItem("Annotation")
		self.cbFormat.addItem("Annotations")
		self.cbFormat.addItem("Annual")
		self.cbFormat.addItem("Anthology")
		self.cbFormat.addItem("B&W")
		self.cbFormat.addItem("B/W")
		self.cbFormat.addItem("B&&W")
		self.cbFormat.addItem("Black & White")
		self.cbFormat.addItem("Box Set")
		self.cbFormat.addItem("Box-Set")
		self.cbFormat.addItem("Crossover")
		self.cbFormat.addItem("Director's Cut")
		self.cbFormat.addItem("Epilogue")
		self.cbFormat.addItem("Event")
		self.cbFormat.addItem("FCBD")
		self.cbFormat.addItem("Flyer")
		self.cbFormat.addItem("Giant")
		self.cbFormat.addItem("Giant Size")
		self.cbFormat.addItem("Giant-Size")
		self.cbFormat.addItem("Graphic Novel")
		self.cbFormat.addItem("Hardcover")
		self.cbFormat.addItem("Hard-Cover")
		self.cbFormat.addItem("King")
		self.cbFormat.addItem("King Size")
		self.cbFormat.addItem("King-Size")
		self.cbFormat.addItem("Limited Series")
		self.cbFormat.addItem("Magazine")
		self.cbFormat.addItem("-1")
		self.cbFormat.addItem("NSFW")
		self.cbFormat.addItem("One Shot")
		self.cbFormat.addItem("One-Shot")
		self.cbFormat.addItem("Point 1")
		self.cbFormat.addItem("Preview")
		self.cbFormat.addItem("Prologue")
		self.cbFormat.addItem("Reference")
		self.cbFormat.addItem("Review")
		self.cbFormat.addItem("Reviewed")
		self.cbFormat.addItem("Scanlation")
		self.cbFormat.addItem("Script")
		self.cbFormat.addItem("Series")
		self.cbFormat.addItem("Sketch")
		self.cbFormat.addItem("Special")
		self.cbFormat.addItem("TPB")
		self.cbFormat.addItem("Trade Paper Back")
		self.cbFormat.addItem("WebComic")
		self.cbFormat.addItem("Web Comic")
		self.cbFormat.addItem("Year 1")
		self.cbFormat.addItem("Year One")
		

	def removeCBLTags( self ):
		self.removeTags(  MetaDataStyle.CBI )
			
	def removeCRTags( self ):
		self.removeTags(  MetaDataStyle.CIX )
			
	def removeTags( self, style):
		# remove the indicated tags from the archive
		# ( keep the form and the current metadata object intact. )
		if self.comic_archive is not None and self.comic_archive.hasMetadata( style ):
			reply = QtGui.QMessageBox.question(self, 
			     self.tr("Remove Tags"), 
			     self.tr("Are you sure you wish to remove the " +  MetaDataStyle.name[style] + " tags from this archive?"),
			     QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			     
			if reply == QtGui.QMessageBox.Yes:
				path = self.comic_archive.path
				self.comic_archive.removeMetadata( style )
				self.updateInfoBox()
				

	def reloadAuto( self ):
		self.actualReload( self.data_style )

	def reloadCBLTags( self ):
		self.actualReload( MetaDataStyle.CBI )

	def reloadCRTags( self ):
		self.actualReload( MetaDataStyle.CIX )

	def actualReload( self, style ):
		if self.comic_archive is not None and self.comic_archive.hasMetadata( style ):
			if self.dirtyFlagVerification( "Load Tags",
										"If you load tags now, data in the form will be lost.  Are you sure?"):
				self.openArchive( self.comic_archive.path, explicit_style=style )
	                       
	
	def dirtyFlagVerification( self, title, desc):
		if self.dirtyFlag:
			reply = QtGui.QMessageBox.question(self, 
			     self.tr(title), 
			     self.tr(desc),
			     QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			     
			if reply != QtGui.QMessageBox.Yes:
				return False
		return True
			
	def closeEvent(self, event):

		if self.dirtyFlagVerification( "Exit " + self.appName,
		                             "If you quit now, data in the form will be lost.  Are you sure?"):
			event.accept()
		else:
			event.ignore()

	def showPageBrowser( self ):
		if self.page_browser is None:
			self.page_browser = PageBrowserWindow( self )
			if self.comic_archive is not None:
				self.page_browser.setComicArchive( self.comic_archive )
			self.page_browser.finished.connect(self.pageBrowserClosed)
			
	def pageBrowserClosed( self ):
		self.page_browser = None
			