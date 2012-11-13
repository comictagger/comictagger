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

from PyQt4 import QtCore, QtGui

from settings import ComicTaggerSettings
from taggerwindow import TaggerWindow
from options import Options, MetaDataStyle
from comicarchive import ComicArchive
from issueidentifier import IssueIdentifier

import utils


#-----------------------------
def cli_mode( opts, settings ):

	ca = ComicArchive(opts.filename)
	if not ca.seemsToBeAComicArchive():
		print "Sorry, but "+ opts.filename + "  is not a comic archive!"
		return
	
	ii = IssueIdentifier( ca, settings.cv_api_key )
	matches = ii.search()
	
	"""
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
		
		tagger_window = TaggerWindow( opts, settings )
		tagger_window.show()
		sys.exit(app.exec_())

if __name__ == "__main__":
    main()
    
    
    
    
    
