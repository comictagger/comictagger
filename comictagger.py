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
from pprint import pprint
import json
import platform

try:
	qt_available = True
	from PyQt4 import QtCore, QtGui
	from taggerwindow import TaggerWindow
except ImportError as e:
	qt_available = False
	print e

from settings import ComicTaggerSettings
from options import Options, MetaDataStyle
from comicarchive import ComicArchive
from issueidentifier import IssueIdentifier
from genericmetadata import GenericMetadata
from comicvinetalker import ComicVineTalker, ComicVineTalkerException

import utils
import codecs

#-----------------------------
def cli_mode( opts, settings ):
	if len( opts.file_list ) < 1:
		print "You must specify at least one filename.  Use the -h option for more info"
		return
	
	for f in opts.file_list:
		if len( opts.file_list ) > 1:
			print "Processing: ", f
		process_file_cli( f, opts, settings )

def process_file_cli( filename, opts, settings ):

	
	ca = ComicArchive(filename)
	if settings.rar_exe_path != "":
		ca.setExternalRarProgram( settings.rar_exe_path )	
	
	if not ca.seemsToBeAComicArchive():
		print "Sorry, but "+ filename + "  is not a comic archive!"
		return
	
	#if not ca.isWritableForStyle( opts.data_style ) and ( opts.delete_tags or opts.save_tags or opts.rename_file ):
	if not ca.isWritable(  ) and ( opts.delete_tags or opts.save_tags or opts.rename_file ):
		print "This archive is not writable for that tag type"
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
				brief += "none "
			else:
				if cbi: brief += "CBL "
				if cix: brief += "CR "
			brief += "]"
				
			print brief
			print
			
		if opts.data_style is None or opts.data_style == MetaDataStyle.CIX:
			if cix:
				print "------ComicRack tags--------"
				if opts.raw:
					print u"{0}".format(ca.readRawCIX())
				else:
					print u"{0}".format(ca.readCIX())
				
		if opts.data_style is None or opts.data_style == MetaDataStyle.CBI:
			if cbi:
				print "------ComicBookLover tags--------"
				if opts.raw:
					pprint(json.loads(ca.readRawCBI()))
				else:
					print u"{0}".format(ca.readCBI())
			
			
	elif opts.delete_tags:		
		if opts.data_style == MetaDataStyle.CIX:
			if cix:
				if not opts.dryrun:
					if not ca.removeCIX():
						print "Tag removal seemed to fail!"
					else:
						print "Removed ComicRack tags."
				else:
					print "dry-run.  ComicRack tags not removed"					
			else:
				print "This archive doesn't have ComicRack tags."
					
		if opts.data_style == MetaDataStyle.CBI:
			if cbi:
				if not opts.dryrun:
					if not ca.removeCBI():
						print "Tag removal seemed to fail!"
					else:
						print "Removed ComicBookLover tags."
				else:
					print "dry-run.  ComicBookLover tags not removed"					
			else:
				print "This archive doesn't have ComicBookLover tags."
		
	elif opts.save_tags:
		
		# OK we're gonna do a save of some new data		
		md = GenericMetadata()

		# First read in existing data, if it's there		
		if opts.data_style == MetaDataStyle.CIX and cix:
				md = ca.readCIX()
		elif opts.data_style == MetaDataStyle.CBI and cbi:
				md = ca.readCBI()
				
		# now, overlay the new data onto the old, in order
		
		if opts.parse_filename:
			md.overlay( ca.metadataFromFilename() )
		
		if opts.metadata is not None:
			md.overlay( opts.metadata )
			

		# finally, search online
		if opts.search_online:
	
			ii = IssueIdentifier( ca, settings )
			
			if md is None or md.isEmpty:
				print "No metadata given to search online with!"
				return

			def myoutput( text ):
				if opts.verbose:
					IssueIdentifier.defaultWriteOutput( text )
				
			# use our overlayed MD struct to search
			ii.setAdditionalMetadata( md )
			ii.onlyUseAdditionalMetaData = True
			ii.setOutputFunction( myoutput )
			matches = ii.search()
			
			result = ii.search_result
			
			found_match = False
			choices = False
			low_confidence = False
			
			if result == ii.ResultNoMatches:
				pass
			elif result == ii.ResultFoundMatchButBadCoverScore:
				#low_confidence = True
				found_match = True
			elif result == ii.ResultFoundMatchButNotFirstPage :
				found_match = True
			elif result == ii.ResultMultipleMatchesWithBadImageScores:
				low_confidence = True
				choices = True
			elif result == ii.ResultOneGoodMatch:
				found_match = True
			elif result == ii.ResultMultipleGoodMatches:
				choices = True

			if choices:
				print "Online search: Multiple matches.  Save aborted"
				return
			if low_confidence:
				print "Online search: Low confidence match.  Save aborted"
				return
			if not found_match:
				print "Online search: No match found.  Save aborted"
				return
			
			# we got here, so we have a single match
			
			# now get the particular issue data
			try:
				cv_md = ComicVineTalker().fetchIssueData( matches[0]['volume_id'],  matches[0]['issue_number'] )
			except ComicVineTalkerException:
				print "Network error while getting issue details.  Save aborted"
				return
				
			md.overlay( cv_md )
		# ok, done building our metadata. time to save

		#HACK 
		opts.dryrun = True
		#HACK 
		
		if not opts.dryrun:
			# write out the new data
			if not ca.writeMetadata( md, opts.data_style ):
				print "The tag save seemed to fail!"
			else:
				print "Save complete."				
		else:
			print "dry-run option was set, so nothing was written, but here is the final set of tags:"
			print u"{0}".format(md)

	elif opts.rename_file:

		md = GenericMetadata()
		# First read in existing data, if it's there		
		if opts.data_style == MetaDataStyle.CIX and cix:
				md = ca.readCIX()
		elif opts.data_style == MetaDataStyle.CBI and cbi:
				md = ca.readCBI()

		if md.isEmpty:
			print "Comic archive contains no tags!"

		if opts.data_style == MetaDataStyle.CIX:
			if cix:
				md = ca.readCIX()
			else:
				print "Comic archive contains no ComicRack tags!"
				
		if opts.data_style == MetaDataStyle.CBI:
			if cbi:
				md = ca.readCBI()
			else:
				print "Comic archive contains no ComicBookLover tags!"
		
		# TODO move this to ComicArchive, or maybe another class???
		new_name = ""
		if md.series is not None:
			new_name += "{0}".format( md.series )
		else:
			print "Can't rename without series name"
			return
			
		if md.volume is not None:
			new_name += " v{0}".format( md.volume )

		if md.issue is not None:
			new_name += " #{:03d}".format( int(md.issue) )
		else:
			print "Can't rename without issue number"
			return
		
		if md.issueCount is not None:
			new_name += " (of {0})".format( md.issueCount )
		
		if md.year is not None:
			new_name += " ({0})".format( md.year )
		
		if ca.isZip():
			new_name += ".cbz"
		elif ca.isRar():
			new_name += ".cbr"
			
		#HACK 
		opts.dryrun = True
		#HACK 
			
		if not opts.dryrun:
			# write out the new data
			#ca.rename()
			pass
		else:
			print "dry-run option was set, so nothing was changed, but here is the proposed filename:"
			print "'{0}'".format(new_name)


			
		
#-----------------------------

def main():
	
	# try to make stdout encodings happy for unicode
	sys.stdout = codecs.getwriter('utf8')(sys.stdout)

	opts = Options()
	opts.parseCmdLineArgs()

	settings = ComicTaggerSettings()
	# make sure unrar program is in the path for the UnRAR class
	utils.addtopath(os.path.dirname(settings.unrar_exe_path))
	
	signal.signal(signal.SIGINT, signal.SIG_DFL)
	
	if not qt_available:
		opts.no_gui = True
		print "QT is not available.  Running in text mode"
	
	if opts.no_gui:
		cli_mode( opts, settings )
		
	else:

		app = QtGui.QApplication(sys.argv)
		
		if platform.system() != "Linux":
			img =  QtGui.QPixmap(os.path.join(ComicTaggerSettings.baseDir(), 'graphics/tags.png' ))
			splash = QtGui.QSplashScreen(img)
			splash.show()
			splash.raise_()
			app.processEvents()
	
		try:
			tagger_window = TaggerWindow( opts.filename, settings )
			tagger_window.show()

			if platform.system() != "Linux":
				splash.finish( tagger_window )

			sys.exit(app.exec_())
		except Exception, e:
			QtGui.QMessageBox.critical(QtGui.QMainWindow(), "Error", "Unhandled exception in app:\n" + traceback.format_exc() )
			
			
if __name__ == "__main__":
    main()
    
    
    
    
    
