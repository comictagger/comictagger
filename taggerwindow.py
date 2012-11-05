
from PyQt4 import QtCore, QtGui, uic
import locale

from volumeselectionwindow import VolumeSelectionWindow
from options import Options, MetaDataStyle
from genericmetadata import GenericMetadata
from comicvinetalker import ComicVineTalker
from comicarchive import ComicArchive
from crediteditorwindow import CreditEditorWindow
import utils

# this reads the environment and inits the right locale
locale.setlocale(locale.LC_ALL, "")


import os
class TaggerWindow( QtGui.QMainWindow):
	
	appName = "ComicTagger"
	
	def __init__(self, opts , parent = None):
		super(TaggerWindow, self).__init__(parent)

		uic.loadUi('taggerwindow.ui', self)
		self.setWindowIcon(QtGui.QIcon('app.png'))
		self.center()
		self.raise_()
		
		self.dirtyFlag = False
		self.opts = opts
		self.data_style = opts.data_style
		
		#set up a default metadata object
		self.metadata = GenericMetadata()
		self.comic_archive = None

		self.configMenus()
		self.statusBar()
		self.updateAppTitle()
		self.setAcceptDrops(True)
		self.droppedFile=None

			
		self.populateComboBoxes()	

		# hook up the callbacks		
		self.cbDataStyle.currentIndexChanged.connect(self.setDataStyle)
		self.btnEditCredit.clicked.connect(self.editCredit)	
		self.btnAddCredit.clicked.connect(self.addCredit)	
		self.btnRemoveCredit.clicked.connect(self.removeCredit)	
		self.twCredits.cellDoubleClicked.connect(self.editCredit)
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
		if self.dirtyFlag:
			dirty_str = " [modified]"
		else:
			dirty_str = ""
			
		if self.comic_archive is None:
			self.setWindowTitle( self.appName )
		else:
			self.setWindowTitle( self.appName + " - " + self.comic_archive.path + dirty_str)

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
		
		# Tag Menu
		self.actionParse_Filename.setShortcut( 'Ctrl+F' )
		self.actionParse_Filename.setStatusTip( 'Try to extract tags from filename' )
		self.actionParse_Filename.triggered.connect( self.useFilename )

		self.actionQuery_Online.setShortcut( 'Ctrl+W' )
		self.actionQuery_Online.setStatusTip( 'Search online for tags' )
		self.actionQuery_Online.triggered.connect( self.queryOnline )
		
		#self.actionClearEntryForm.setShortcut( 'Ctrl+C' )
		self.actionClearEntryForm.setStatusTip( 'Clear all the data on the screen' )
		self.actionClearEntryForm.triggered.connect( self.clearForm )

		# Help Menu
		self.actionAbout.setShortcut( 'Ctrl+A' )
		self.actionAbout.setStatusTip( 'Show the ' + self.appName + ' info' )
		self.actionAbout.triggered.connect( self.aboutApp )
	
		# ToolBar
	
		self.toolBar.addAction( self.actionLoad )
		self.toolBar.addAction( self.actionWrite_Tags )
		self.toolBar.addAction( self.actionParse_Filename )
		self.toolBar.addAction( self.actionQuery_Online )
		self.toolBar.addAction( self.actionClearEntryForm )
		#self.toolBar.addAction( self.actionRemoveCBLTags )
		#self.toolBar.addAction( self.actionRemoveCRTags )
        
	def repackageArchive( self ):
		QtGui.QMessageBox.information(self, self.tr("Repackage Comic Archive"), self.tr("TBD"))

	def aboutApp( self ):
		QtGui.QMessageBox.information(self, self.tr("About " + self.appName ), self.tr(self.appName + " 0.1"))

		
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

			self.metadataToForm()
			self.clearDirtyFlag()  # also updates the app title
			self.updateInfoBox()			
			
		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops!"), self.tr("That file doesn't appear to be a comic archive!"))

	def updateInfoBox( self ):
		
		ca = self.comic_archive
		info_text = os.path.basename( ca.path ) + "\n"
		info_text += str(ca.getNumberOfPages()) + " pages \n"
		if ca.hasCIX():
			info_text += "* ComicRack tags\n"
		if ca.hasCBI():
			info_text += "* ComicBookLover tags\n"
			
		self.lblArchiveInfo.setText( info_text )


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
		assignText( self.leMaturityRating, md.maturityRating )
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
		assignText( self.leFormat,        md.format )
		
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
		md.maturityRating =     xlate( self.leMaturityRating.text(), "str" )

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

		md.format =             xlate( self.leFormat.text(), "str" )
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

			

	def queryOnline(self):
	
		if str(self.leSeries.text()).strip() != "":
			series_name = str(self.leSeries.text()).strip()
		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops"), self.tr("Need to enter a series name to query."))
			return
			
		issue_number = str(self.leIssueNum.text()).strip()
		
		selector = VolumeSelectionWindow( self, series_name, issue_number )
		selector.setModal(True)
		selector.exec_()
		
		if selector.result():
			#we should now have a volume ID

			comicVine = ComicVineTalker()
			self.metadata = comicVine.fetchIssueData( selector.volume_id, selector.issue_number )

			# Now push the right data into the edit controls
			self.metadataToForm()
			#!!!ATB should I clear the form???

	def commitMetadata(self):

		if ( self.metadata is not None and self.comic_archive is not None):	
			self.formToMetadata()
			self.comic_archive.writeMetadata( self.metadata, self.data_style )
			self.clearDirtyFlag()
			self.updateInfoBox()
			
			QtGui.QMessageBox.information(self, self.tr("Yeah!"), self.tr("File written."))


		else:
			QtGui.QMessageBox.information(self, self.tr("Whoops!"), self.tr("No data to commit!"))


	def setDataStyle(self, s):
		self.data_style, b = self.cbDataStyle.itemData(s).toInt()
		self.updateStyleTweaks()

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
				if type(item) == QtGui.QCheckBox:
					item.setEnabled( True )
				elif type(item) == QtGui.QComboBox:
					item.setEnabled( True )
				else:
					item.setReadOnly( False )
			else:
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
						self.teLocations, self.leMaturityRating, self.leFormat
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
					
			self.setDirtyFlag()

	def removeCredit( self ):
		row = self.twCredits.currentRow()
		if row != -1 :
			self.twCredits.removeRow( row )
		self.setDirtyFlag()


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

