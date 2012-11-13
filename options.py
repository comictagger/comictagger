"""
CLI options class for comictagger app
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

class Enum(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError

class MetaDataStyle:
	CBI = 0
	CIX = 1
	name = [ 'ComicBookLover', 'ComicRack' ]


class Options:

	def __init__(self):
		self.data_style = MetaDataStyle.CIX
		self.no_gui = False
		
		self.series_name = '' 
		self.issue_number = '' 
		self.filename = ''  
		self.image_hasher = 1     

	def parseCmdLineArgs(self):
			
		# mac no likey this from .app bundle
		if getattr(sys, 'frozen', None):
			 return 

		# parse command line options
		try:
			opts, args = getopt.getopt(sys.argv[1:], "cht:s:i:vf:m:", ["cli", "help", "type=", "series=", "issue=", "verbose", "file", "imagehasher=" ])
		except (getopt.error, msg):
			print( msg )
			print( "for help use --help" )
			sys.exit(2)
		# process options
		for o, a in opts:
			if o in ("-h", "--help"):
				print( __doc__ )
				sys.exit(0)
			if o in ("-v", "--verbose"):
				print( "Verbose output!" )
			if o in ("-c", "--cli"):
				self.no_gui = True
			if o in ("-m", "--imagehasher"):
				self.image_hasher = a
			if o in ("-s", "--series"):
				self.series_name = a
			if o in ("-i", "--issue"):
				self.issue_number = a
			if o in ("-f", "--file"):
				self.filename = a
			if o in ("-t", "--type"):
				if a == "cr":
					self.data_style = MetaDataStyle.CIX
				elif a == "cbl":
					self.data_style = MetaDataStyle.CBI
				else:
					print( __doc__ )
					sys.exit(0)
				
		# process arguments
		for arg in args:
			process(arg) # process() is defined elsewhere

		return opts
		