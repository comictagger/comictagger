"""
Functions for parsing comic info from filename 

This should probably be re-written, but, well, it mostly works!

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


# Some portions of this code were modified from pyComicMetaThis project
# http://code.google.com/p/pycomicmetathis/

import re
import os
from urllib import unquote

class FileNameParser:
	def fixSpaces( self, string ):
		placeholders = ['[-_]','  +']
		for ph in placeholders:
			string = re.sub(ph, ' ', string )
		return string.strip()

	# check for silly .1 or .5 style issue strings
	# allow up to 5 chars total
	def isPointIssue( self, word ):
		ret = False
		try:
			float(word)
			if (len(word) < 5 and not word.isdigit()):
				ret = True
		except ValueError:
			pass
		return ret
		
	def getIssueNumber( self,filename ):

		found = False
		issue = ''
		# guess based on position

		# replace any name seperators with spaces
		tmpstr = self.fixSpaces(filename)
		word_list = tmpstr.split(' ')
		
		# assume the last number in the filename that is under 4 digits is the issue number
		for word in reversed(word_list):			
			if ( 
				 (word.isdigit() and len(word) < 4) or
				 (self.isPointIssue(word))
				):
				issue = word
				found = True
				#print 'Assuming issue number is ' + str(issue) + ' based on the position.'
				break

		if not found:
			# try a regex
			issnum = re.search('(?<=[_#\s-])(\d+[a-zA-Z]|\d+\.\d|\d+)', filename)
			if issnum:
				issue = issnum.group()
				found = True
				#print 'Got the issue using regex. Issue is ' + issue 
		
		return issue.strip()

	def getSeriesName(self, filename, issue ):

		# use the issue number string to split the filename string
		# assume first element of list is the series name, plus cruft

		#!!! this could fail in the case of small numerics in the series name!!!
		
		tmpstr = self.fixSpaces(filename)
		if issue != "":			
			series = tmpstr.split(issue)[0]
		else:
			# no issue to work off of
			#!!! TODO we should look for the year, and split from that
			# and if that doesn't exist, remove parenthetical words
			series = tmpstr
			
		volume = ""
		
		series = series.rstrip("#")
			
		# search for volume number	
		match = re.search('(?<=v)(\d+)\s*$', series)
		if match:
			volume = match.group()
			series = series.split("v"+volume)[0]
			volume = volume.lstrip("0")
		
		return series.strip(), volume.strip()

	def getYear( self,filename):

		year = ""
		# look for four digit number with "(" ")" or "--" around it
		match = re.search('(\(\d\d\d\d\))|(--\d\d\d\d--)', filename)
		if match:
			year = match.group()
			# remove non-numerics
			year = re.sub("[^0-9]", "", year)
		return year

		self.issue = ""
		self.series = "" 
		self.volume = ""
		self.year = ""


	def parseFilename( self, filename ):
		
		# remove the path
		filename = os.path.basename(filename)

		# remove the extension
		filename = os.path.splitext(filename)[0]
		
		#url decvocde, just in case
		filename = unquote(filename)
			
		self.issue = self.getIssueNumber(filename)
		self.series, self.volume = self.getSeriesName(filename, self.issue)
		self.year = self.getYear(filename)
	
		if self.issue != "":
			# strip off leading zeros
			self.issue = self.issue.lstrip("0")
			if self.issue == "":
				self.issue = "0"
