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
import getopt
import json
import xml
from pprint import pprint 
from PyQt4 import QtCore, QtGui
import signal
import os


from settings import ComicTaggerSettings

from taggerwindow import TaggerWindow
from options import Options, MetaDataStyle
from comicarchive import ComicArchive

from comicvinetalker import ComicVineTalker
from comicinfoxml import ComicInfoXml
from comicbookinfo import ComicBookInfo
import utils

#-----------------------------
def cliProcedure( opts ):

	pass
	"""
	comicVine = ComicVineTalker()

	cv_search_results = comicVine.searchForSeries( opts.series_name )

	#error checking here:  did we get any results?

	# we will eventualy  want user interaction to choose the appropriate result, but for now, assume the first one
	series_id = cv_search_results[0]['id'] 

	print( "-->Auto-selecting volume ID:", cv_search_results[0]['id'] )
	print(" ") 

	# now get the particular issue data
	metadata = comicVine.fetchIssueData( series_id, opts.issue_number )

	#pprint( cv_volume_data, indent=4 )

	ca = ComicArchive(opts.filename)
	ca.writeMetadata( metadata, opts.data_style )

	#debugging
	ComicBookInfo().writeToExternalFile( "test.json" )
	ComicBookInfo().writeToExternalFile( "test.xml" )
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

		cliProcedure( opts )
		
	else:

		app = QtGui.QApplication(sys.argv)
		tagger_window = TaggerWindow( opts, settings )
		tagger_window.show()
		sys.exit(app.exec_())

if __name__ == "__main__":
    main()
    
    
    
    
    
