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
		self.criticalRating      = None
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
		
		