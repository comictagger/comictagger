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

import ctversion
from genericmetadata import GenericMetadata

class Enum(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError

class MetaDataStyle:
	CBI = 0
	CIX = 1
	COMET = 2
	name = [ 'ComicBookLover', 'ComicRack', 'CoMet' ]


class Options:
	help_text = """	
Usage: {0} [OPTION]... [FILE LIST]

A utility for reading and writing metadata to comic archives.

If no options are given, {0} will run in windowed mode

  -p, --print                Print out tag info from file.  Specify type
                             (via -t) to get only info of that tag type
      --raw                  With -p, will print out the raw tag block(s)
                             from the file
  -d, --delete               Deletes the tag block of specified type (via -t)
  -c, --copy=SOURCE          Copy the specified source tag block to destination style
                             specified via via -t (potentially lossy operation)
  -s, --save                 Save out tags as specified type (via -t)
                             Must specify also at least -o, -p, or -m
      --nooverwrite          Don't modify tag block if it already exists ( relevent for -s or -c )  
  -n, --dryrun               Don't actually modify file (only relevent for -d, -s, or -r)
  -t, --type=TYPE            Specify TYPE as either "CR", "CBL", or "COMET" (as either 
                             ComicRack, ComicBookLover, or CoMet style tags, respectivly)
  -f, --parsefilename        Parse the filename to get some info, specifically
                             series name, issue number, volume, and publication 
                             year
  -i, --interactive          Interactively query the user when there are multiple matches for
                             an online search
      --nosummary            Suppress the default summary after a save operation
  -o, --online               Search online and attempt to identify file using 
                             existing metadata and images in archive. May be used
                             in conjuntion with -f and -m
  -m, --metadata=LIST        Explicity define, as a list, some tags to be used                           
                                e.g. "series=Plastic Man , publisher=Quality Comics"
                                     "series=Kickers^, Inc., issue=1, year=1986"
                             Name-Value pairs are comma separated.  Use a "^" to 
                             escape an "=" or a ",", as shown in the example above
                             Some names that can be used:
                                 series, issue, issueCount, year, publisher, title
  -r, --rename               Rename the file based on specified tag style.
      --noabort              Don't abort save operation when online match is of low confidence  
  -v, --verbose              Be noisy when doing what it does                            
      --terse                Don't say much (for print mode)                            
      --version              Display version                            
  -h, --help                 Display this message                            
		"""


	def __init__(self):
		self.data_style = None
		self.no_gui = False
		self.filename = None  
		self.verbose = False
		self.terse = False
		self.metadata = None
		self.print_tags = False
		self.copy_tags = False
		self.delete_tags = False
		self.search_online = False
		self.dryrun = False
		self.abortOnLowConfidence = True
		self.save_tags = False
		self.parse_filename = False
		self.show_save_summary = True
		self.raw = False
		self.rename_file = False
		self.no_overwrite = False
		self.interactive = False
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
		
		if platform.system() == "Darwin" and hasattr(sys, "frozen") and sys.frozen == 1:
			# remove the PSN ("process serial number") argument from OS/X
			input_args = [a for a in sys.argv[1:] if "-psn_0_" not in  a ]
		else:
			input_args = sys.argv[1:]
			
		# parse command line options
		try:
			opts, args = getopt.getopt( input_args, 
			           "hpdt:fm:vonsrc:i", 
			           [ "help", "print", "delete", "type=", "copy=", "parsefilename", "metadata=", "verbose",
			            "online", "dryrun", "save", "rename" , "raw", "noabort", "terse", "nooverwrite",
			            "interactive", "nosummary", "version" ])
			           
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
			if o in ("-i", "--interactive"):
				self.interactive = True
			if o in ("-c", "--copy"):
				self.copy_tags = True
				if a.lower() == "cr":
					self.copy_source = MetaDataStyle.CIX
				elif a.lower() == "cbl":
					self.copy_source = MetaDataStyle.CBI
				elif a.lower() == "comet":
					self.copy_source = MetaDataStyle.COMET
				else:
					self.display_help_and_quit( "Invalid copy tag source type", 1 )
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
			if o == "--raw":
				self.raw = True
			if o  == "--noabort":
				self.abortOnLowConfidence = False
			if o == "--terse":
				self.terse = True
			if o == "--nosummary":
				self.show_save_summary = False
			if o  == "--nooverwrite":
				self.no_overwrite = True
			if o  == "--version":
				print "ComicTagger version: ", ctversion.version
				quit()
			if o in ("-t", "--type"):
				if a.lower() == "cr":
					self.data_style = MetaDataStyle.CIX
				elif a.lower() == "cbl":
					self.data_style = MetaDataStyle.CBI
				elif a.lower() == "comet":
					self.data_style = MetaDataStyle.COMET
				else:
					self.display_help_and_quit( "Invalid tag type", 1 )
			
		if self.print_tags or self.delete_tags or self.save_tags or self.copy_tags or self.rename_file:
			self.no_gui = True

		count = 0
		if self.print_tags: count += 1
		if self.delete_tags: count += 1
		if self.save_tags: count += 1
		if self.copy_tags: count += 1
		if self.rename_file: count += 1
		
		if count > 1:
			self.display_help_and_quit( "Must choose only one action of print, delete, save, copy, or rename", 1 )
		
		if len(args) > 0:
			if platform.system() == "Windows":
				# no globbing on windows shell, so do it for them
				import glob
				self.file_list = []
				for item in args:
					self.file_list.extend(glob.glob(item))
					print self.file_list
				self.filename = self.file_list[0]
			else:
				self.filename = args[0]
				self.file_list = args

		if self.no_gui and self.filename is None:
			self.display_help_and_quit( "Command requires a filename!", 1 )
			
		if self.delete_tags and self.data_style is None:
			self.display_help_and_quit( "Please specify the type to delete with -t", 1 )
			
		if self.save_tags and self.data_style is None:
			self.display_help_and_quit( "Please specify the type to save with -t", 1 )

		if self.copy_tags and self.data_style is None:
			self.display_help_and_quit( "Please specify the type to copy to with -t", 1 )
			
		#if self.rename_file and self.data_style is None:
		#	self.display_help_and_quit( "Please specify the type to use for renaming with -t", 1 )
		
