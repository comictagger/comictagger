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

class PageInfo:
	SeqNum = 0
	Type = PageType.FrontCover
	DoublePage = False
	ImageSize = 0
	Key = ""
	ImageWidth = 0
	ImageHeight = 0
		

class GenericMetadata:

	def __init__(self):
		
		self.isEmpty = True
		self.tagOrigin = None
		
		self.series             = None
		self.issueNumber        = None
		self.title              = None
		self.publisher          = None
		self.publicationMonth   = None
		self.publicationYear    = None
		self.issueCount         = None
		self.volumeNumber       = None
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

	def addCredit( self, person, role, primary = False ):
		
		credit = dict()
		credit['person'] = person
		credit['role'] = role
		if primary:
			credit['primary'] = primary
			
		self.credits.append(credit)

      		
	def __str__( self ):
		vals = []
		if self.isEmpty:
			return "No metadata"

		def add( tag, val ):
			if val is not None and str(val) != "":
				vals.append( (tag, val) )

		add( "series",         self.series )
		add( "issue number",   self.issueNumber )
		add( "issue count",    self.issueCount )
		add( "title",          self.title )
		add( "publisher",      self.publisher )
		add( "month",          self.publicationMonth )
		add( "year",           self.publicationYear )
		add( "volume number",  self.volumeNumber )
		add( "volume count",   self.volumeCount )
		add( "genre",          self.genre )
		add( "language",       self.language )
		add( "country",        self.country )
		add( "user rating",    self.criticalRating )
		add( "alt. series",    self.alternateSeries )
		add( "alt. number",    self.alternateNumber )
		add( "alt. count",     self.alternateCount )
		add( "imprint",        self.imprint )
		add( "web",            self.webLink )
		add( "format",         self.format )
		add( "manga",          self.manga )
		add( "B&W",            self.blackAndWhite )
		add( "age rating",     self.maturityRating )
		add( "story arc",      self.storyArc )
		add( "series group",   self.seriesGroup )
		add( "scan info",      self.scanInfo )
		add( "characters",     self.characters )
		add( "teams",          self.teams )
		add( "locations",      self.locations )
		add( "comments",       self.comments )
		add( "notes",          self.notes )
		add( "tags",           utils.listToString( self.tags ) )
		for c in self.credits:
			add( "credit",     c['role']+": "+c['person'] )
			

		# find the longest field name
		flen = 0
		for i in vals:
			flen = max( flen, len(i[0]) )
		flen += 1
	
		#format the data nicely
		outstr = ""
		for i in vals:
			outstr += ("{0: <" + str(flen) + "}: {1}\n").format( i[0], i[1] )
	
		return outstr
