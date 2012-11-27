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
import platform
import os

from genericmetadata import GenericMetadata

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
	help_text = """	
Usage: {0} [OPTION]... [FILE]

A utility for read and writing metadata to comic archives.

If no options are given, {0} will run in windowed mode

  -p, --print                Print out tag info from file.  Specify type
                             (via -t) to get only info of that tag type
      --raw                  With -p, will print out the raw tag block(s)
                             from the file
  -d, --delete               Deletes the tag block of specified type (via -t)
  -s, --save                 Save out tags as specified type (via -t)
                             Must specify also at least -o, -p, or -m
  -n, --dryrun               Don't actually modify file (only relevent for -d, -s, or -r)
  -t, --type=TYPE            Specify TYPE as either "CR" or "CBL", (as either 
                             ComicRack or ComicBookLover style tags, respectivly)
  -f, --parsefilename        Parse the filename to get some info, specifically
                             series name, issue number, volume, and publication 
                             year
  -o, --online               Search online and attempt to identify file using 
                             existing metadata and images in archive. May be used
                             in conjuntion with -f and -m
  -m, --metadata=LIST        Explicity define, as a list, some tags to be used                           
                                e.g. "series=Plastic Man , publisher=Quality Comics"
                                     "series=Kickers^, Inc., issue=1, year=1986"
                             Name-Value pairs are comma separated.  Use a "^" to 
                             escape an "=" or a ",", ash show in the example above
                             Some names that can be used:
                                 series, issue, issueCount, year, publisher, title
  -r, --rename               Rename the file based on specified tag style.
  -a, --abort                Abort save operation when online match is of low confidence TBD!  
  -v, --verbose              Be noisy when doing what it does                            
  -h, --help                 Display this message                            
		"""


	def __init__(self):
		self.data_style = None
		self.no_gui = False
		self.filename = None  
		self.verbose = False
		self.metadata = None
		self.print_tags = False
		self.delete_tags = False
		self.search_online = False
		self.dryrun = False
		self.save_tags = False
		self.parse_filename = False
		self.raw = False
		self.rename_file = False
		self.file_list = []
		
	def display_help_and_quit( self, msg, code ):
		appname = os.path.basename(sys.argv[0])
		if msg is not None:
			print( msg )
		print self.help_text.format(appname)
		sys.exit(code)
	
	def parseMetadataFromString( self, mdstr ):
		# The metadata string is a comma separated list of name-value pairs
		# The names match the attributes of the internal metadata struct (for now)
		# The caret is the special "escape character", since it's not common in 
		# natural language text

		# example = "series=Kickers^, Inc. ,issue=1, year=1986"
		
		escaped_comma = "^,"
		escaped_equals = "^="		
		replacement_token = "<_~_>"
		
		md = GenericMetadata()

		# First, replace escaped commas with with a unique token (to be changed back later)
		mdstr = mdstr.replace( escaped_comma, replacement_token)
		tmp_list = mdstr.split(",")
		md_list = []
		for item in tmp_list:
			item = item.replace( replacement_token, "," )
			md_list.append(item)
			
		# Now build a nice dict from the list
		md_dict = dict()
		for item in md_list:
			# Make sure to fix any escaped equal signs
			i = item.replace( escaped_equals, replacement_token)
			key,value = i.split("=")
			value = value.replace( replacement_token, "=" ).strip()
			key = key.strip()
			if key.lower() == "credit":
				cred_attribs = value.split(":")
				role = cred_attribs[0]
				person = ( cred_attribs[1] if len( cred_attribs ) > 1 else  "" )
				primary = (cred_attribs[2] if len( cred_attribs ) > 2 else None )
				md.addCredit( person.strip(), role.strip(), True if primary is not None else False )
			else:			
				md_dict[key] = value
		
		# Map the dict to the metadata object
		for key in md_dict:
			if not hasattr(md, key):
				print "Warning: '{0}' is not a valid tag name".format(key)
			else:
				md.isEmpty = False
				setattr( md, key, md_dict[key] )
		#print md
		return md
		
	def parseCmdLineArgs(self):
			
		# mac no likey this from .app bundle
		if platform.system() == "Darwin" and getattr(sys, 'frozen', None):
			 return 


		# parse command line options
		try:
			opts, args = getopt.getopt(sys.argv[1:], 
			           "hpdt:fm:vonsr", 
			           [ "help", "print", "delete", "type=", "parsefilename", "metadata=", "verbose", "online", "dryrun", "save", "rename" , "raw" ])
			           
		except getopt.GetoptError as err:
			self.display_help_and_quit( str(err), 2 )
			
		# process options
		for o, a in opts:
			if o in ("-h", "--help"):
				self.display_help_and_quit( None, 0 )
			if o in ("-v", "--verbose"):
				self.verbose = True
			if o in ("-p", "--print"):
				self.print_tags = True
			if o in ("-d", "--delete"):
				self.delete_tags = True
			if o in ("-o", "--online"):
				self.search_online = True
			if o in ("-n", "--dryrun"):
				self.dryrun = True
			if o in ("-m", "--metadata"):
				self.metadata = self.parseMetadataFromString(a)
			if o in ("-s", "--save"):
				self.save_tags = True
			if o in ("-r", "--rename"):
				self.rename_file = True
			if o in ("-f", "--parsefilename"):
				self.parse_filename = True
			if o in ("--raw"):
				self.raw = True
			if o in ("-t", "--type"):
				if a.lower() == "cr":
					self.data_style = MetaDataStyle.CIX
				elif a.lower() == "cbl":
					self.data_style = MetaDataStyle.CBI
				else:
					self.display_help_and_quit( "Invalid tag type", 1 )
			
		if self.print_tags or self.delete_tags or self.save_tags or self.rename_file:
			self.no_gui = True

		count = 0
		if self.print_tags: count += 1
		if self.delete_tags: count += 1
		if self.save_tags: count += 1
		if self.rename_file: count += 1
		
		if count > 1:
			self.display_help_and_quit( "Must choose only one action of print, delete, save, or rename", 1 )
		
		if len(args) > 0:
			self.filename = args[0]
			self.file_list = args

		if self.no_gui and self.filename is None:
			self.display_help_and_quit( "Command requires a filename!", 1 )
			
		if self.delete_tags and self.data_style is None:
			self.display_help_and_quit( "Please specify the type to delete with -t", 1 )
			
		if self.save_tags and self.data_style is None:
			self.display_help_and_quit( "Please specify the type to save with -t", 1 )
			
		if self.rename_file and self.data_style is None:
			self.display_help_and_quit( "Please specify the type to use for renaming with -t", 1 )
		
