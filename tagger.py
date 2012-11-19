#!/usr/bin/python

"""
A python script to tag comic archives
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
import signal
import os
import traceback
import time

from PyQt4 import QtCore, QtGui

from settings import ComicTaggerSettings
from taggerwindow import TaggerWindow
from options import Options, MetaDataStyle
from comicarchive import ComicArchive
from issueidentifier import IssueIdentifier

import utils


#-----------------------------
def cli_mode( opts, settings ):

	if opts.filename is None:
		return
	ca = ComicArchive(opts.filename)
	if settings.rar_exe_path != "":
		ca.setExternalRarProgram( settings.rar_exe_path )	
	
	if not ca.seemsToBeAComicArchive():
		print "Sorry, but "+ opts.filename + "  is not a comic archive!"
		return

	cix = False
	cbi = False
	if ca.hasCIX(): cix = True
	if ca.hasCBI(): cbi = True

	if opts.print_tags:

		if opts.data_style is None:
			page_count = ca.getNumberOfPages()

			brief = ""
			if ca.isZip():      brief = "ZIP archive    "
			elif ca.isRar():    brief = "RAR archive    "
			elif ca.isFolder(): brief = "Folder archive "
				
			brief += "({0: >3} pages)".format(page_count)			
			brief += "  tags:[ "

			if not (cbi or cix):
				brief += "none"
			else:
				if cbi: brief += "CBL "
				if cix: brief += "CR "
			brief += "]"
				
			print brief
			print
			
		if opts.data_style is None or opts.data_style == MetaDataStyle.CIX:
			if cix:
				print "------ComicRack tags--------"
				print ca.readCIX()
		if opts.data_style is None or opts.data_style == MetaDataStyle.CBI:
			if cbi:
				print "------ComicBookLover tags--------"
				print ca.readCBI()
			
			
	elif opts.delete_tags:
		if not ca.isWritable():
			print "This archive is not writable."
			return
		
		if opts.data_style == MetaDataStyle.CIX:
			if cix:
				ca.removeCIX()
				print "Removed ComicRack tags."
			else:
				print "This archive doesn't have ComicRack tags."
					
		if opts.data_style == MetaDataStyle.CBI:
			if cbi:
				ca.removeCBI()
				print "Removed ComicBookLover tags."
			else:
				print "This archive doesn't have ComicBookLover tags."
		
	#elif opt.rename:
	#	print "Gonna rename file"

	elif opts.save_tags:
		if opts.data_style == MetaDataStyle.CIX:
			print "Gonna save ComicRack tags"
		if opts.data_style == MetaDataStyle.CBI:
			print "Gonna save ComicBookLover tags"
		
		"""
		ii = IssueIdentifier( ca, settings.cv_api_key )
		matches = ii.search()
		

		if len(matches) == 1:
			
			# now get the particular issue data
			metadata = comicVine.fetchIssueData( match[0]['series'],  match[0]['issue_number'] )
			
			# write out the new data
			ca.writeMetadata( metadata, opts.data_style )
			
		elif len(matches) == 0:
			pass

		elif len(matches) == 0:
			# print match options, with CV issue ID's
			pass
		"""
#-----------------------------

def main():
	opts = Options()
	opts.parseCmdLineArgs()

	settings = ComicTaggerSettings()
	# make sure unrar program is in the path for the UnRAR class
	utils.addtopath(os.path.dirname(settings.unrar_exe_path))
	
	signal.signal(signal.SIGINT, signal.SIG_DFL)
	
	if opts.no_gui:

		cli_mode( opts, settings )
		
	else:

		app = QtGui.QApplication(sys.argv)
		
		img =  QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/tags.png' ))
		splash = QtGui.QSplashScreen(img)
		splash.show()
		splash.raise_()
		app.processEvents()

		try:
			tagger_window = TaggerWindow( opts.filename, settings )
			tagger_window.show()
			splash.finish( tagger_window )
			sys.exit(app.exec_())
		except Exception, e:
			QtGui.QMessageBox.critical(QtGui.QMainWindow(), "Error", "Unhandled exception in app:\n" + traceback.format_exc() )
			
			
if __name__ == "__main__":
    main()
    
    
    
    
    
