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

import signal
import locale
import platform
import os
import pprint
import json

from volumeselectionwindow import VolumeSelectionWindow
from options import MetaDataStyle
from comicinfoxml import ComicInfoXml
from genericmetadata import GenericMetadata
from comicvinetalker import ComicVineTalker, ComicVineTalkerException
from comicarchive import ComicArchive
from crediteditorwindow import CreditEditorWindow
from settingswindow import SettingsWindow
from settings import ComicTaggerSettings
from pagebrowser import PageBrowserWindow
from filenameparser import FileNameParser
from logwindow import LogWindow
from optionalmsgdialog import OptionalMessageDialog
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



class TaggerWindow( QtGui.QMainWindow):
	
	appName = "ComicTagger"
	version = ctversion.version
	
	def __init__(self, filename, settings, parent = None):
		super(TaggerWindow, self).__init__(parent)

		# Set up a timer so the interpreter runs every so often
		# This helps catch and process SIGINT from console
		#self.timer = QtCore.QTimer()
		#self.timer.start(500)  
		#self.timer.timeout.connect(lambda: None)
		#signal.signal(signal.SIGINT, self.sigint_handler)

		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'taggerwindow.ui' ), self)
		self.setWindowIcon(QtGui.QIcon(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/app.png' )))
		
		self.lblCover.setPixmap(QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/nocover.png' )))
		
		#print platform.system(), platform.release()
		self.dirtyFlag = False
		self.settings = settings
		self.data_style = settings.last_selected_data_style

		#set up a default metadata object
		self.metadata = GenericMetadata()
		self.comic_archive = None

		self.configMenus()
		self.statusBar()
		self.updateAppTitle()
		self.setAcceptDrops(True)
		self.updateSaveMenu()
		self.droppedFile = None

		self.page_browser = None
	
		self.populateComboBoxes()	

		# set up some basic field validators
		validator = QtGui.QIntValidator(1900, 2099, self)
		self.lePubYear.setValidator(validator)

		validator = QtGui.QIntValidator(1, 12, self)
		self.lePubMonth.setValidator(validator)
		
		validator = QtGui.QIntValidator(1, 99999, self)
		self.leIssueCount.setValidator(validator)
		self.leVolumeNum.setValidator(validator)
		self.leVolumeCount.setValidator(validator)
		self.leAltIssueNum.setValidator(validator)
		self.leAltIssueCount.setValidator(validator)
		
		#TODO set up an RE validator for issueNum that allows
		# for all sorts of wacky things

		# hook up the callbacks		
		self.cbDataStyle.currentIndexChanged.connect(self.setDataStyle)
		self.btnEditCredit.clicked.connect(self.editCredit)	
		self.btnAddCredit.clicked.connect(self.addCredit)	
		self.btnRemoveCredit.clicked.connect(self.removeCredit)	
		self.twCredits.cellDoubleClicked.connect(self.editCredit)
		clickable(self.lblCover).connect(self.showPageBrowser)
		self.connectDirtyFlagSignals()
		
		self.updateStyleTweaks()

		self.show()
		self.setAppPosition()
		self.raise_()
		QtCore.QCoreApplication.processEvents()

		if filename is not None:
			self.openArchive( filename )
		
		if self.settings.show_disclaimer:
			checked = OptionalMessageDialog.msg(  self, "Welcome!",
								"""
								Thanks for trying ComicTagger!<br><br>
								Be aware that this is beta-level software, and consider it experimental.
								You should use it very carefully when modifying your data files.  As the
								license says, it's "AS IS!"<br><br>
								Also, be aware that writing tags to comic archives will change their file hashes,
								which has implications with respect to other software packages.  It's best to
								use ComicTagger on local copies of your comics.<br><br>
								Have fun!
								"""
								)
			self.settings.show_disclaimer = not checked
		
	def sigint_handler(self, *args):
		# defer the actual close in the app loop thread
		QtCore.QTimer.singleShot(200, self.close)

	def updateAppTitle( self ):
			
		if self.comic_archive is None:
			self.setWindowTitle( self.appName )
		else:
			mod_str = ""
			ro_str = ""
			
			if self.dirtyFlag:
				mod_str = " [modified]"
			
			if not self.comic_archive.isWritable():
				ro_str = " [read only]"
				
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
	
		self.actionViewRawCRTags.setStatusTip( 'View raw ComicRack tag block from file' )
		self.actionViewRawCRTags.triggered.connect( self.viewRawCRTags )

		self.actionViewRawCBLTags.setStatusTip( 'View raw ComicBookLover tag block from file' )
		self.actionViewRawCBLTags.triggered.connect( self.viewRawCBLTags )

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
       
	def repackageArchive( self ):
		QtGui.QMessageBox.information(self, self.tr("Repackage Comic Archive"), self.tr("TBD"))

	def aboutApp( self ):
		
		website = "http://code.google.com/p/comictagger"
		email = "comictagger@gmail.com"
		
		msgBox = QtGui.QMessageBox()
		msgBox.setWindowTitle( self.tr("About " + self.appName ) )
		msgBox.setTextFormat( QtCore.Qt.RichText )
		msgBox.setIconPixmap( QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/about.png' )) )
		msgBox.setText( "<br><br><br>" 
		               + self.appName + " v" + self.version + "<br>" 
		               + "(c)2012 Anthony Beville<br><br>"
		               + "<a href='{0}'>{0}</a><br><br>".format(website)
		               + "<a href='mailto:{0}'>{0}</a>".format(email)  )
							
		msgBox.setStandardButtons( QtGui.QMessageBox.Ok )
		msgBox.exec_()
		


		
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

			self.settings.last_opened_folder = os.path.dirname( os.path.abspath(path) )  
			
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
			self.updateSaveMenu()
			#self.updatePagesInfo()
			
		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops!"), self.tr("That file doesn't appear to be a comic archive!"))

	def updateSaveMenu( self ):

		if ( self.comic_archive is not None and 
		     self.comic_archive.isWritable( )  
		   ):
			self.actionWrite_Tags.setEnabled( True )
		else:
			self.actionWrite_Tags.setEnabled( False )
			
			
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
		assignText( self.leIssueNum,     md.issue )
		assignText( self.leIssueCount,   md.issueCount )
		assignText( self.leVolumeNum,    md.volume )
		assignText( self.leVolumeCount,  md.volumeCount )
		assignText( self.leTitle,        md.title )
		assignText( self.lePublisher,    md.publisher )
		assignText( self.lePubMonth,     md.month )
		assignText( self.lePubYear,      md.year )
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
				
				self.addNewCreditEntry( row, credit['role'].title(), credit['person'], (credit['primary'] if credit.has_key('primary') else False ) )

				row += 1
				
		self.twCredits.setSortingEnabled( True )
		self.updateCreditColors()

	def addNewCreditEntry( self, row, role, name, primary_flag=False ):
		self.twCredits.insertRow(row)
		
		item_text = role
		item = QtGui.QTableWidgetItem(item_text)			
		item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
		self.twCredits.setItem(row, 0, item)
		
		item_text = name
		item = QtGui.QTableWidgetItem(item_text)			
		item.setFlags(QtCore.Qt.ItemIsSelectable| QtCore.Qt.ItemIsEnabled)
		self.twCredits.setItem(row, 1, item)
		# for now, jusr preserve the primary flag
		item.setData( QtCore.Qt.UserRole, primary_flag)
		
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
		md.issue =              xlate( self.leIssueNum.text(), "str" )
		md.issueCount =         xlate( self.leIssueCount.text(), "int" )
		md.volume =             xlate( self.leVolumeNum.text(), "int" )
		md.volumeCount =        xlate( self.leVolumeCount.text(), "int" )
		md.title =              xlate( self.leTitle.text(), "str" )
		md.publisher =          xlate( self.lePublisher.text(), "str" )
		md.month =              xlate( self.lePubMonth.text(), "int" )
		md.year =               xlate( self.lePubYear.text(), "int" )
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
			primary_flag = self.twCredits.item( row, 1 ).data( QtCore.Qt.UserRole ).toBool()

			md.addCredit( name, role, bool(primary_flag) )
			row += 1


	def useFilename( self ):
		if self.comic_archive is not None:
			self.metadata = self.comic_archive.metadataFromFilename( )
			self.metadataToForm()

	def selectFile( self ):
		
		dialog = QtGui.QFileDialog(self)
		dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
		if self.settings.last_opened_folder is not None:
			dialog.setDirectory( self.settings.last_opened_folder )
		#dialog.setFileMode(QtGui.QFileDialog.Directory )
		
		if platform.system() != "Windows" and utils.which("unrar") is None:
			archive_filter = "Comic archive files (*.cbz *.zip)"
		else:
			archive_filter = "Comic archive files (*.cbz *.zip *.cbr *.rar)"
			
		filters  = [ 
		             archive_filter,
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
			QtGui.QMessageBox.warning(self, self.tr("Automatic Online Search"), 
			       self.tr("You need to load a comic first!"))
			return
		
		self.queryOnline( autoselect=True )
		
	def queryOnline(self, autoselect=False):
		
		issue_number = str(self.leIssueNum.text()).strip()

		if autoselect and issue_number == "":
			QtGui.QMessageBox.information(self,"Automatic Online Search", "Can't auto-select without an issue number (yet!)")
			return
	
		if str(self.leSeries.text()).strip() != "":
			series_name = str(self.leSeries.text()).strip()
		else:
			QtGui.QMessageBox.information(self, self.tr("Online Search"), self.tr("Need to enter a series name to search."))
			return
			

		year = str(self.lePubYear.text()).strip()
		if year == "":
			year = None

		selector = VolumeSelectionWindow( self, series_name, issue_number, year, self.comic_archive, self.settings, autoselect )

		title = "Search: '" + series_name + "' - "
		selector.setWindowTitle( title + "Select Series")

		selector.setModal(True)
		selector.exec_()
		
		if selector.result():
			#we should now have a volume ID
			QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))

			#copy the form onto metadata object
			self.formToMetadata()
			
			try:
				comicVine = ComicVineTalker( )
				new_metadata = comicVine.fetchIssueData( selector.volume_id, selector.issue_number )
			except ComicVineTalkerException:
				QtGui.QApplication.restoreOverrideCursor()		
				QtGui.QMessageBox.critical(self, self.tr("Network Issue"), self.tr("Could not connect to ComicVine to get issue details!"))
			else:
				self.metadata.overlay( new_metadata )				
				# Now push the new combined data into the edit controls
				self.metadataToForm()
			finally:			
				QtGui.QApplication.restoreOverrideCursor()		

	def commitMetadata(self):

		if ( self.metadata is not None and self.comic_archive is not None):	
		
			if self.comic_archive.isRar() and self.data_style == MetaDataStyle.CBI:
				if self.settings.ask_about_cbi_in_rar:
					answered_yes, checked = OptionalMessageDialog.question(  self, "RAR and ComicBookLover", 
										"""
										You are about to write a CBL tag block to a RAR archive!<br><br>
										While technically possible, no known reader can read those tags from RAR
										yet.  If you would like this feature in ComicBookLover, please go  to their
										forums and add your voice to a feature request!<br><br>
										<a href=http://forums.comicbooklover.com/categories/ipad-features>
										http://forums.comicbooklover.com/categories/ipad-features</a><br>
										<a href=http://forums.comicbooklover.com/categories/mac-features>
										http://forums.comicbooklover.com/categories/mac-features</a><br><br>
										Do you want to continue with the save?
										""",
										)
					self.settings.ask_about_cbi_in_rar = not checked
					if not answered_yes:
						return
		
		
			reply = QtGui.QMessageBox.question(self, 
			     self.tr("Save Tags"), 
			     self.tr("Are you sure you wish to save " +  MetaDataStyle.name[self.data_style] + " tags to this archive?"),
			     QtGui.QMessageBox.Yes, QtGui.QMessageBox.No )
			     
			if reply == QtGui.QMessageBox.Yes:		
				QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
				self.formToMetadata()
				
				success = self.comic_archive.writeMetadata( self.metadata, self.data_style )
				QtGui.QApplication.restoreOverrideCursor()
				
				if not success:
					QtGui.QMessageBox.warning(self, self.tr("Save failed"), self.tr("The tag save operation seemed to fail!"))
				else:
					self.clearDirtyFlag()
					self.updateInfoBox()
					#QtGui.QMessageBox.information(self, self.tr("Yeah!"), self.tr("File written."))

		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops!"), self.tr("No data to commit!"))


	def setDataStyle(self, s):
		self.data_style, b = self.cbDataStyle.itemData(s).toInt()

		self.settings.last_selected_data_style = self.data_style
		self.updateStyleTweaks()
		self.updateSaveMenu()
		
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

	def setAppPosition( self ):
		if self.settings.last_main_window_width != 0:
			self.move( self.settings.last_main_window_x, self.settings.last_main_window_y )
			self.resize( self.settings.last_main_window_width, self.settings.last_main_window_height )
		else:
			screen = QtGui.QDesktopWidget().screenGeometry()
			size =  self.frameGeometry()
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
				if not self.comic_archive.removeMetadata( style ):
					QtGui.QMessageBox.warning(self, self.tr("Remove failed"), self.tr("The tag removal operation seemed to fail!"))
				else:
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
			appsize = self.size()
			self.settings.last_main_window_width = appsize.width()
			self.settings.last_main_window_height = appsize.height()
			self.settings.last_main_window_x = self.x()
			self.settings.last_main_window_y = self.y()
			self.settings.save()
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
			
	def viewRawCRTags( self ):
		if self.comic_archive is not None and self.comic_archive.hasCIX():
			dlg = LogWindow( self )
			dlg.setText( self.comic_archive.readRawCIX() )
			dlg.setWindowTitle( "Raw ComicRack Tag View" )
			dlg.exec_()
		
	def viewRawCBLTags( self ):
		if self.comic_archive is not None and self.comic_archive.hasCBI():
			dlg = LogWindow( self )
			text = pprint.pformat( json.loads(self.comic_archive.readRawCBI()), indent=4  )
			print text
			dlg.setText(text )
			dlg.setWindowTitle( "Raw ComicBookLover Tag View" )
			dlg.exec_()
		
		
