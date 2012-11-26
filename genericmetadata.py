"""
 A python class for internal metadata storage
 
 The goal of this class is to handle ALL the data that might come from various
 tagging schemes and databases, such as ComicVine or GCD.  This makes conversion 
 possible, however lossy it might be
 
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

import utils

# These page info classes are exactly the same as the CIX scheme, since it's unique
class PageType:
	FrontCover   = "FrontCover"
	InnerCover   = "InnerCover"
	Roundup      = "Roundup"
	Story        = "Story"
	Advertisment = "Advertisment"
	Story        = "Story"
	Editorial    = "Editorial"
	Letters      = "Letters"
	Preview      = "Preview"
	BackCover    = "BackCover"
	Other        = "Other"
	Deleted      = "Deleted"

"""
class PageInfo:
	Image = 0
	Type = PageType.Story
	DoublePage = False
	ImageSize = 0
	Key = ""
	ImageWidth = 0
	ImageHeight = 0
"""	

class GenericMetadata:

	def __init__(self):
		
		self.isEmpty = True
		self.tagOrigin = None
		
		self.series             = None
		self.issue              = None
		self.title              = None
		self.publisher          = None
		self.month              = None
		self.year               = None
		self.issueCount         = None
		self.volume             = None
		self.genre              = None
		self.language           = None  # 2 letter iso code
		self.comments           = None  # use same way as Summary in CIX

		self.volumeCount        = None
		self.criticalRating     = None
		self.country            = None
		
		self.alternateSeries    = None
		self.alternateNumber    = None
		self.alternateCount     = None
		self.imprint            = None
		self.notes              = None
		self.webLink            = None
		self.format             = None
		self.manga              = None
		self.blackAndWhite      = None
		self.pageCount          = None
		self.maturityRating     = None
		
		self.storyArc            = None
		self.seriesGroup         = None
		self.scanInfo            = None
		
		self.characters          = None
		self.teams               = None
		self.locations           = None
	
		self.credits            = list()		
		self.tags               = list()
		self.pages              = list()

	def overlay( self, new_md ):
		# Overlay a metadata object on this one
		# that is, when the new object has non-None
		# values, over-write them to this one
		
		def assign( cur, new ):
			if new is not None:
				if type(new) == str and len(new) == 0:
					setattr(self, cur, None)
				else:
					setattr(self, cur, new)
				
		if not new_md.isEmpty:
			self.isEmpty = False
				
		assign( 'series',            new_md.series )
		assign( "issue",             new_md.issue )
		assign( "issueCount",        new_md.issueCount )
		assign( "title",             new_md.title )
		assign( "publisher",         new_md.publisher )
		assign( "month",             new_md.month )
		assign( "year",              new_md.year )
		assign( "volume",            new_md.volume )
		assign( "volumeCount",       new_md.volumeCount )
		assign( "genre",             new_md.genre )
		assign( "language",          new_md.language )
		assign( "country",           new_md.country )
		assign( "alternateSeries",   new_md.criticalRating )
		assign( "alternateSeries",   new_md.alternateSeries )
		assign( "alternateNumber",   new_md.alternateNumber )
		assign( "alternateCount",    new_md.alternateCount )
		assign( "imprint",           new_md.imprint )
		assign( "web",               new_md.webLink )
		assign( "format",            new_md.format )
		assign( "manga",             new_md.manga )
		assign( "blackAndWhite",     new_md.blackAndWhite )
		assign( "maturityRating",    new_md.maturityRating )
		assign( "scanInfo",          new_md.scanInfo )
		assign( "scanInfo",          new_md.scanInfo )
		assign( "scanInfo",          new_md.scanInfo )
		assign( "characters",        new_md.characters )
		assign( "teams",             new_md.teams )
		assign( "locations",         new_md.locations )
		assign( "comments",          new_md.comments )
		assign( "notes",             new_md.notes )
		
		# TODO
		# not sure if the tags, credits, and pages should broken down, or treated
		# as whole lists.... 
		for c in new_md.credits:	
			if c.has_key('primary') and c['primary']:
				primary = True
			else:
				primary = False

			# Remove credit role if person is blank
			if c['person'] == "":			
				for r in reversed(self.credits):
					if r['role'].lower() == c['role'].lower():
						self.credits.remove(r)
			else:
				self.addCredit( c['person'], c['role'], primary )

			
		# For now, go the easy route, where any overlay
		# value wipes out the whole list
		if len(new_md.tags) > 0:
			assign( "tags",              new_md.tags )
		if len(new_md.pages) > 0:	
			assign( "pages",           new_md.pages )

		
	def addCredit( self, person, role, primary = False ):
		
		credit = dict()
		credit['person'] = person
		credit['role'] = role
		if primary:
			credit['primary'] = primary

		# look to see if it's not already there...
		found = False
		for c in self.credits:
			if (   c['person'].lower() == person.lower() and
				   c['role'].lower() == role.lower() ):
				# no need to add it. just adjust the "primary" flag as needed
				c['primary'] = primary
				found = True
				break
		
		if not found:
			self.credits.append(credit)

      		
	def __str__( self ):
		vals = []
		if self.isEmpty:
			return "No metadata"

		def add_string( tag, val ):
			if val is not None and u"{0}".format(val) != "":
				vals.append( (tag, val) )

		def add_attr_string( tag ):
			val = getattr(self,tag)
			add_string( tag, getattr(self,tag) )

		add_attr_string( "series" )
		add_attr_string( "issue" )
		add_attr_string( "issueCount" )
		add_attr_string( "title" )
		add_attr_string( "publisher" )
		add_attr_string( "month" )
		add_attr_string( "year" )
		add_attr_string( "volume" )
		add_attr_string( "volumeCount" )
		add_attr_string( "genre" )
		add_attr_string( "language" )
		add_attr_string( "country" )
		add_attr_string( "criticalRating" )
		add_attr_string( "alternateSeries" )
		add_attr_string( "alternateNumber" )
		add_attr_string( "alternateCount" )
		add_attr_string( "imprint" )
		add_attr_string( "webLink" )
		add_attr_string( "format" )
		add_attr_string( "manga" )
		if self.blackAndWhite:
			add_attr_string( "blackAndWhite" )
		add_attr_string( "maturityRating" )
		add_attr_string( "storyArc" )
		add_attr_string( "seriesGroup" )
		add_attr_string( "scanInfo" )
		add_attr_string( "characters" )
		add_attr_string( "teams" )
		add_attr_string( "locations" )
		add_attr_string( "comments" )
		add_attr_string( "notes" )
		
		add_string( "tags",  utils.listToString( self.tags ) )
		 
		for c in self.credits:
			primary = ""
			if c.has_key('primary') and c['primary']: 
				primary == " [P]"
			add_string( "credit",  c['role']+": "+c['person'] + primary)
			
		# find the longest field name
		flen = 0
		for i in vals:
			flen = max( flen, len(i[0]) )
		flen += 1
	
		#format the data nicely
		outstr = ""
		fmt_str = u"{0: <" + str(flen) + "} {1}\n"
		for i in vals:
			outstr += fmt_str.format( i[0]+":", i[1] )
	
		return outstr
