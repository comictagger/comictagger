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


from settings import ComicTaggerSettings
from options import Options, MetaDataStyle
from comicarchive import ComicArchive
from issueidentifier import IssueIdentifier
from genericmetadata import GenericMetadata
from comicvinetalker import ComicVineTalker, ComicVineTalkerException
from filerenamer import FileRenamer

import utils
import codecs

class MultipleMatch():
	def __init__( self, filename, match_list):
		self.filename = filename  
		self.matches = match_list  

class OnlineMatchResults():
	def __init__(self):
		self.goodMatches = []  
		self.noMatches = []    
		self.multipleMatches = []  
		self.writeFailures = []  

#-----------------------------

def actual_issue_data_fetch( match, settings ):

	# now get the particular issue data
	try:
		cv_md = ComicVineTalker().fetchIssueData( match['volume_id'],  match['issue_number'], settings )
	except ComicVineTalkerException:
		print "Network error while getting issue details.  Save aborted"
		return None
	return cv_md

def actual_metadata_save( ca, opts, md ):

	if not opts.dryrun:
		# write out the new data
		if not ca.writeMetadata( md, opts.data_style ):
			print "The tag save seemed to fail!"
			return False
		else:
			print "Save complete."				
	else:
		if opts.terse:
			print "dry-run option was set, so nothing was written"
		else:
			print "dry-run option was set, so nothing was written, but here is the final set of tags:"
			print u"{0}".format(md)
	return True
		

def post_process_matches( match_results, opts, settings ):
	# now go through the match results
	if opts.show_save_summary:
		if len( match_results.goodMatches ) > 0:
			print "\nSuccessful matches:"
			print "------------------"
			for f in match_results.goodMatches:
				print f
				
		if len( match_results.noMatches ) > 0:
			print "\nNo matches:"
			print "------------------"
			for f in match_results.noMatches:
				print f
	
		if len( match_results.writeFailures ) > 0:
			print "\nFile Write Failures:"
			print "------------------"
			for f in match_results.writeFailures:
				print f

	if not opts.show_save_summary and not opts.interactive:
		#jusr quit if we're not interactive or showing the summary
		return
	
	if len( match_results.multipleMatches ) > 0:
		print "\nMultiple matches:"
		print "------------------"
		for mm in match_results.multipleMatches:
			print mm.filename
			for (counter,m) in enumerate(mm.matches):
				print "  {0}. {1} #{2} [{3}] ({4}/{5}) - {6}".format(counter,
											   m['series'],
											   m['issue_number'],
											   m['publisher'],
											   m['month'],
											   m['year'],
											   m['issue_title'])
			if opts.interactive:
				while True:
					i = raw_input("Choose a match #, or 's' to skip: ")
					if (i.isdigit() and int(i) in range(len(mm.matches))) or i == 's':
						break
				if i != 's':
					# save the data!
					# we know at this point, that the file is all good to go
					ca = ComicArchive( mm.filename )
					md = create_local_metadata( opts, ca, ca.hasMetadata(opts.data_style) )
					cv_md = actual_issue_data_fetch(mm.matches[int(i)], settings)
					md.overlay( cv_md )
					actual_metadata_save( ca, opts, md )
					
					
			print


def cli_mode( opts, settings ):
	if len( opts.file_list ) < 1:
		print "You must specify at least one filename.  Use the -h option for more info"
		return
	
	match_results = OnlineMatchResults()
	
	for f in opts.file_list:
		process_file_cli( f, opts, settings, match_results )
		sys.stdout.flush()
		
	post_process_matches( match_results, opts, settings )	


def create_local_metadata( opts, ca, has_desired_tags ):
	
	md = GenericMetadata()
	md.setDefaultPageList( ca.getNumberOfPages() )
	
	if has_desired_tags:
		md = ca.readMetadata( opts.data_style )
		
	# now, overlay the parsed filename info	
	if opts.parse_filename:
		md.overlay( ca.metadataFromFilename() )
	
	# finally, use explicit stuff	
	if opts.metadata is not None:
		md.overlay( opts.metadata )

	return md

def process_file_cli( filename, opts, settings, match_results ):

	batch_mode = len( opts.file_list ) > 1
		
	ca = ComicArchive(filename)
	if settings.rar_exe_path != "":
		ca.setExternalRarProgram( settings.rar_exe_path )	
	
	if not ca.seemsToBeAComicArchive():
		print "Sorry, but "+ filename + "  is not a comic archive!"
		return
	
	#if not ca.isWritableForStyle( opts.data_style ) and ( opts.delete_tags or opts.save_tags or opts.rename_file ):
	if not ca.isWritable(  ) and ( opts.delete_tags or opts.copy_tags or opts.save_tags or opts.rename_file ):
		print "This archive is not writable for that tag type"
		return

	has = [ False, False, False ]
	if ca.hasCIX(): has[ MetaDataStyle.CIX ] = True
	if ca.hasCBI(): has[ MetaDataStyle.CBI ] = True
	if ca.hasCoMet(): has[ MetaDataStyle.COMET ] = True

	if opts.print_tags:


		if opts.data_style is None:
			page_count = ca.getNumberOfPages()

			brief = ""

			if batch_mode:
				brief = "{0}: ".format(filename)

			if ca.isZip():      brief += "ZIP archive    "
			elif ca.isRar():    brief += "RAR archive    "
			elif ca.isFolder(): brief += "Folder archive "
				
			brief += "({0: >3} pages)".format(page_count)			
			brief += "  tags:[ "

			if not ( has[ MetaDataStyle.CBI ] or has[ MetaDataStyle.CIX ] or has[ MetaDataStyle.COMET ] ):
				brief += "none "
			else:
				if has[ MetaDataStyle.CBI ]: brief += "CBL "
				if has[ MetaDataStyle.CIX ]: brief += "CR "
				if has[ MetaDataStyle.COMET ]: brief += "CoMet "
			brief += "]"
				
			print brief

		if opts.terse:
			return

		print
		
		if opts.data_style is None or opts.data_style == MetaDataStyle.CIX:
			if has[ MetaDataStyle.CIX ]:
				print "------ComicRack tags--------"
				if opts.raw:
					print u"{0}".format(unicode(ca.readRawCIX(), errors='ignore'))
				else:
					print u"{0}".format(ca.readCIX())
				
		if opts.data_style is None or opts.data_style == MetaDataStyle.CBI:
			if has[ MetaDataStyle.CBI ]:
				print "------ComicBookLover tags--------"
				if opts.raw:
					pprint(json.loads(ca.readRawCBI()))
				else:
					print u"{0}".format(ca.readCBI())
					
		if opts.data_style is None or opts.data_style == MetaDataStyle.COMET:
			if has[ MetaDataStyle.COMET ]:
				print "------CoMet tags--------"
				if opts.raw:
					print u"{0}".format(ca.readRawCoMet())
				else:
					print u"{0}".format(ca.readCoMet())
			
			
	elif opts.delete_tags:
		style_name = MetaDataStyle.name[ opts.data_style ]
		if has[ opts.data_style ]:
			if not opts.dryrun:
				if not ca.removeMetadata( opts.data_style ):
					print "{0}: Tag removal seemed to fail!".format( filename )
				else:
					print "{0}: Removed {1} tags.".format( filename, style_name )
			else:
				print "{0}: dry-run.  {1} tags not removed".format( filename, style_name )		
		else:
			print "{0}: This archive doesn't have {1} tags to remove.".format( filename, style_name )

	elif opts.copy_tags:
		dst_style_name = MetaDataStyle.name[ opts.data_style ]
		if opts.no_overwrite and has[ opts.data_style ]:
			print "{0}: Already has {1} tags.  Not overwriting.".format(filename, dst_style_name)
			return
		if opts.copy_source == opts.data_style:
			print "{0}: Destination and source are same: {1}.  Nothing to do.".format(filename, dst_style_name)
			return
			
		src_style_name = MetaDataStyle.name[ opts.copy_source ]
		if has[ opts.copy_source ]:
			if not opts.dryrun:
				md = ca.readMetadata( opts.copy_source )
				if not ca.writeMetadata( md, opts.data_style ):
					print "{0}: Tag copy seemed to fail!".format( filename )
				else:
					print "{0}: Copied {1} tags to {2} .".format( filename, src_style_name, dst_style_name )
			else:
				print "{0}: dry-run.  {1} tags not copied".format( filename, src_style_name )		
		else:
			print "{0}: This archive doesn't have {1} tags to copy.".format( filename, src_style_name )

		
	elif opts.save_tags:

		if opts.no_overwrite and has[ opts.data_style ]:
			print "{0}: Already has {1} tags.  Not overwriting.".format(filename, MetaDataStyle.name[ opts.data_style ])
			return
		
		if batch_mode:
			print "Processing {0}: ".format(filename)
			
		md = create_local_metadata( opts, ca, has[ opts.data_style ] )

		# now, search online
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
			ii.cover_page_index = md.getCoverPageIndexList()[0]
			matches = ii.search()
			
			result = ii.search_result
			
			found_match = False
			choices = False
			low_confidence = False
			
			if result == ii.ResultNoMatches:
				pass
			elif result == ii.ResultFoundMatchButBadCoverScore:
				low_confidence = True
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
				match_results.multipleMatches.append(MultipleMatch(filename,matches))
				return
			if low_confidence and opts.abortOnLowConfidence:
				print "Online search: Low confidence match.  Save aborted"
				match_results.noMatches.append(filename)
				return
			if not found_match:
				print "Online search: No match found.  Save aborted"
				match_results.noMatches.append(filename)
				return


			# we got here, so we have a single match
			
			# now get the particular issue data
			cv_md = actual_issue_data_fetch(matches[0], settings)
			if cv_md is None:
				return
			
			md.overlay( cv_md )
			
		# ok, done building our metadata. time to save
		if not actual_metadata_save( ca, opts, md ):
				match_results.writeFailures.append(filename)
		else:
				match_results.goodMatches.append(filename)

	elif opts.rename_file:

		msg_hdr = ""
		if batch_mode:
			msg_hdr = "{0}: ".format(filename)

		if opts.data_style is not None:
			use_tags = has[ opts.data_style ]
		else:
			use_tags = False
			
		md = create_local_metadata( opts, ca, use_tags )
		
		if md.series is None:
			print msg_hdr + "Can't rename without series name"
			return

		if ca.isZip():
			new_ext = ".cbz"
		elif ca.isRar():
			new_ext = ".cbr"
		else:
			new_ext = None  # default
			
		renamer = FileRenamer( md )
		renamer.setTemplate( "%series% v%volume% %issue% (of %issuecount%) (%year%)" )
		new_name = renamer.determineName( filename, ext=new_ext )
			
		if new_name == os.path.basename(filename):
			print msg_hdr + "Filename is already good!"
			return
		
		folder = os.path.dirname( os.path.abspath( filename ) )
		new_abs_path = utils.unique_file( os.path.join( folder, new_name ) )

		suffix = ""
		if not opts.dryrun:
			# rename the file
			os.rename( filename, new_abs_path )
		else:
			suffix = " (dry-run, no change)"

		print "renamed '{0}' -> '{1}' {2}".format(os.path.basename(filename), new_name, suffix)


			
		
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
	
	if not qt_available and not opts.no_gui:
		opts.no_gui = True
		print "QT is not available."
	
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
    
    
    
    
    
