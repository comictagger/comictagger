# coding=utf-8
"""
A PyQt4 widget for managing list of files
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
from PyQt4.QtCore import pyqtSignal

from settings import ComicTaggerSettings
from comicarchive import ComicArchive
from genericmetadata import GenericMetadata, PageType
from options import MetaDataStyle

class FileTableWidget( QTableWidget ):

	def __init__(self, parent ):
		super(FileTableWidget, self).__init__(parent)
		
		
		self.setColumnCount(5)
		self.setHorizontalHeaderLabels (["File", "Folder", "CR", "CBL", ""])
		self.horizontalHeader().setStretchLastSection( True )


class FileTableWidgetItem(QTableWidgetItem):
   def __lt__(self, other):
        return (self.data(Qt.UserRole).toBool() <
                other.data(Qt.UserRole).toBool())


class FileInfo(  ):
	def __init__(self, path, ca, cix_md, cbi_md ):
		self.path = path
		self.cix_md = cix_md
		self.cbi_md = cbi_md
		self.ca = ca

class FileSelectionList(QWidget):

	selectionChanged = pyqtSignal(QVariant)
	listCleared = pyqtSignal()

	def __init__(self, parent , settings ):
		super(FileSelectionList, self).__init__(parent)

		uic.loadUi(os.path.join(ComicTaggerSettings.baseDir(), 'fileselectionlist.ui' ), self)
		
		self.settings = settings
		#self.twList = FileTableWidget( self )
		#gridlayout = QGridLayout( self )
		#gridlayout.addWidget( self.twList )
		self.setAcceptDrops(True)
		
		self.twList.itemSelectionChanged.connect( self.itemSelectionChangedCB )
		
		self.setContextMenuPolicy(Qt.ActionsContextMenu)
		
		selectAllAction = QAction("Select All", self)
		invertSelectionAction = QAction("Invert Selection", self)
		removeAction = QAction("Remove Selected Items", self)
		
		selectAllAction.triggered.connect(self.selectAll)
		removeAction.triggered.connect(self.removeSelection)

		self.addAction(selectAllAction)			
		self.addAction(removeAction)		

	def selectAll( self ):
		self.twList.setRangeSelected( QTableWidgetSelectionRange ( 0, 0, self.twList.rowCount()-1, 1 ), True )
	
	def removeSelection( self ):
		row_list = []
		for item in self.twList.selectedItems():
			if item.column() == 0:
			    row_list.append(item.row())

		if len(row_list) == 0:
			return
		
		row_list.sort()
		row_list.reverse()

		self.twList.itemSelectionChanged.disconnect( self.itemSelectionChangedCB )

		for i in row_list:
			self.twList.removeRow(i)
			
		self.twList.itemSelectionChanged.connect( self.itemSelectionChangedCB )
		
		if self.twList.rowCount() > 0:
			self.twList.selectRow(0)
		else:
			self.listCleared.emit()
			
		
	def dragEnterEvent(self, event):
		self.droppedFiles = None
		if event.mimeData().hasUrls():
					
			# walk through the URL list and build a file list
			for url in event.mimeData().urls():
				if url.isValid() and url.scheme() == "file":
					if self.droppedFiles is None:
						self.droppedFiles = []
					self.droppedFiles.append(url.toLocalFile())
					
			if self.droppedFiles is not None:	
				event.accept()

	def dropEvent(self, event):
		self.addPathList( self.droppedFiles)
		event.accept()
	
	def addPathList( self, pathlist ):
		filelist = []
		for p in pathlist:
			# if path is a folder, walk it recursivly, and all files underneath
			if os.path.isdir( unicode(p)):
				for root,dirs,files in os.walk( unicode(p) ):
					for f in files:
						filelist.append(os.path.join(root,unicode(f)))
			else:
				filelist.append(unicode(p))
			
		# we now have a list of files to add

		progdialog = QProgressDialog("", "Cancel", 0, len(filelist), self)
		progdialog.setWindowTitle( "Adding Files" )
		progdialog.setWindowModality(Qt.WindowModal)
		
		self.twList.setSortingEnabled(False)
		for idx,f in enumerate(filelist):
			QCoreApplication.processEvents()
			if progdialog.wasCanceled():
				break
			progdialog.setValue(idx)
			self.addPathItem( f )

		progdialog.close()
		self.twList.setSortingEnabled(True)
		
		#Maybe set a max size??
		self.twList.resizeColumnsToContents()

		
	def isListDupe( self, path ):
		r = 0
		while r < self.twList.rowCount():
			fi = self.twList.item(r, 0).data( Qt.UserRole ).toPyObject()
			if fi.path == path:
				return True
			r = r + 1
			
		return False		
		
	def addPathItem( self, path):
		path = unicode( path )
		#print "processing", path
		
		if self.isListDupe(path):
			return
		
		ca = ComicArchive( path )
		if self.settings.rar_exe_path != "":
			ca.setExternalRarProgram( self.settings.rar_exe_path )
			
		if ca.seemsToBeAComicArchive() :
			
			row = self.twList.rowCount()
			self.twList.insertRow( row )
			
			cix_md = None
			cbi_md = None
			
			has_cix = ca.hasCIX()
			if has_cix:
				cix_md = ca.readCIX()
				
			has_cbi = ca.hasCBI()
			if has_cbi:
				cbi_md = ca.readCBI()
			
			fi = FileInfo( path, ca, cix_md, cbi_md )
			
			item_text = os.path.split(path)[1]
			item = QTableWidgetItem(item_text)			
			item.setFlags(Qt.ItemIsSelectable| Qt.ItemIsEnabled)
			item.setData( Qt.UserRole , fi )
			item.setData( Qt.ToolTipRole ,item_text)
			self.twList.setItem(row, 0, item)
			
			item_text = os.path.split(path)[0]
			item = QTableWidgetItem(item_text)			
			item.setFlags(Qt.ItemIsSelectable| Qt.ItemIsEnabled)
			item.setData( Qt.ToolTipRole ,item_text)
			self.twList.setItem(row, 1, item)

			# Attempt to use a special checkbox widget in the cell.
			# Couldn't figure out how to disable it with "enabled" colors
			#w = QWidget()
			#cb = QCheckBox(w)
			#cb.setCheckState(Qt.Checked)
			#layout = QHBoxLayout()
			#layout.addWidget( cb )
			#layout.setAlignment(Qt.AlignHCenter)
			#layout.setMargin(2)
			#w.setLayout(layout)
			#self.twList.setCellWidget( row, 2, w )

			item = FileTableWidgetItem()
			item.setFlags(Qt.ItemIsSelectable| Qt.ItemIsEnabled)
			item.setTextAlignment(Qt.AlignHCenter)
			if has_cix:
				item.setCheckState(Qt.Checked)       
				item.setData(Qt.UserRole, True)
			else:
				item.setData(Qt.UserRole, False)
			self.twList.setItem(row, 2, item)

			item = FileTableWidgetItem()
			item.setFlags(Qt.ItemIsSelectable| Qt.ItemIsEnabled)
			item.setTextAlignment(Qt.AlignHCenter)
			if has_cbi:
				item.setCheckState(Qt.Checked)       
				item.setData(Qt.UserRole, True)
			else:
				item.setData(Qt.UserRole, False)
			self.twList.setItem(row, 3, item)
			
	def itemSelectionChangedCB( self ):
		idx = self.twList.currentRow()
		
		fi = self.twList.item(idx, 0).data( Qt.UserRole ).toPyObject()
		
		#if fi.cix_md is not None:
		#	print u"{0}".format(fi.cix_md)
			
		self.selectionChanged.emit( QVariant(fi))
