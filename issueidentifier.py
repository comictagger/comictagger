"""
A python class to automatically identify a comic archive
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
import math
import urllib2, urllib

from settings import ComicTaggerSettings
from comicvinecacher import ComicVineCacher
from genericmetadata import GenericMetadata
from comicvinetalker import ComicVineTalker
from imagehasher import ImageHasher
import utils 

class IssueIdentifier:

	def __init__(self, comic_archive, cv_api_key ):
		self.comic_archive = comic_archive
		self.image_hasher = 1
		self.additional_metadata = None
		self.min_score_thresh = 22
		self.min_score_distance = 2
		self.additional_metadata = GenericMetadata()
		self.cv_api_key = cv_api_key
	
	def setScoreMinThreshold( self, thresh ):
		self.min_score_thresh = thresh

	def setScoreMinDistance( self, distance ):
		self.min_score_distance = distance
		
	def setAdditionalMetadata( self, md ):
		self.additional_metadata = md

	def setHasherAlgorithm( self, algo ):
		self.image_hasher = algo
		pass
	
	def calculateHash( self, image_data ):
		if self.image_hasher == '3':
			return ImageHasher( data=image_data ).dct_average_hash() 
		elif self.image_hasher == '2':
			return ImageHasher( data=image_data ).average_hash2() 
		else:
			return ImageHasher( data=image_data ).average_hash() 
	
	def getSearchKeys( self ):
	
		ca = self.comic_archive
		search_keys = dict()
		search_keys['series'] = None
		search_keys['issue_number'] = None
		search_keys['month'] = None
		search_keys['year'] = None
		
		if ca is None:
			return
		
		# see if the archive has any useful meta data for searching with
		if ca.hasCIX():
			internal_metadata = ca.readCIX()
		elif ca.hasCBI():
			internal_metadata = ca.readCBI()
		else:
			internal_metadata = ca.readCBI()

		# try to get some metadata from filename
		md_from_filename = ca.metadataFromFilename()

		# preference order:
			#1. Additional metadata
			#1. Internal metadata
			#1. Filename metadata
		
		if self.additional_metadata.series is not None:
			search_keys['series'] = self.additional_metadata.series
		elif internal_metadata.series is not None:
			search_keys['series'] = internal_metadata.series
		else:
			search_keys['series'] = md_from_filename.series

		if self.additional_metadata.issueNumber is not None:
			search_keys['issue_number'] = self.additional_metadata.issueNumber
		elif internal_metadata.issueNumber is not None:
			search_keys['issue_number'] = internal_metadata.issueNumber
		else:
			search_keys['issue_number'] = md_from_filename.issueNumber
			
		if self.additional_metadata.publicationYear is not None:
			search_keys['year'] = self.additional_metadata.publicationYear
		elif internal_metadata.publicationYear is not None:
			search_keys['year'] = internal_metadata.publicationYear
		else:
			search_keys['year'] = md_from_filename.publicationYear
			
		if self.additional_metadata.publicationMonth is not None:
			search_keys['month'] = self.additional_metadata.publicationMonth
		elif internal_metadata.publicationMonth is not None:
			search_keys['month'] = internal_metadata.publicationMonth
		else:
			search_keys['month'] = md_from_filename.publicationMonth
			
		return search_keys
	
	@staticmethod
	def log_msg( msg , newline=True ):
		sys.stdout.write(msg)
		if newline:
			sys.stdout.write("\n")
		sys.stdout.flush()
		
	def search( self ):
	
		ca = self.comic_archive
		if not ca.seemsToBeAComicArchive():
			IssueIdentifier.log_msg( "Sorry, but "+ opts.filename + "  is not a comic archive!")
			return
		
		cover_image_data = ca.getCoverPage()

		cover_hash = self.calculateHash( cover_image_data )

		#IssueIdentifier.log_msg( "Cover hash = {0:016x}".format(cover_hash) )

		keys = self.getSearchKeys()
		
		# we need, at minimum, a series and issue number
		if keys['series'] is None or keys['issue_number'] is None:
			IssueIdentifier.log_msg("Not enough info for a search!")
			return None
		
		"""
		IssueIdentifier.log_msg( "Going to search for:" )
		IssueIdentifier.log_msg( "Series: " + keys['series'] )
		IssueIdentifier.log_msg( "Issue : " + keys['issue_number']  )
		if keys['year'] is not None:
			IssueIdentifier.log_msg( "Year :  " + keys['year'] )
		if keys['month'] is not None:
			IssueIdentifier.log_msg( "Month : " + keys['month'] )
		"""
		comicVine = ComicVineTalker( self.cv_api_key )

		#IssueIdentifier.log_msg( ( "Searching for " + keys['series'] + "...")
		IssueIdentifier.log_msg( "Searching for  {0} #{1} ...".format( keys['series'], keys['issue_number']) )

		keys['series'] = utils.removearticles( keys['series'] )
		
		cv_search_results = comicVine.searchForSeries( keys['series'] )
		
		#IssueIdentifier.log_msg( "Found " + str(len(cv_search_results)) + " initial results" )
		
		series_shortlist = []
		
		#IssueIdentifier.log_msg( "Removing results with too long names" )
		for item in cv_search_results:
			#assume that our search name is close to the actual name, say within 5 characters
			if len( utils.removearticles(item['name'])) < len( keys['series'] ) + 5:
				series_shortlist.append(item)
		
		# if we don't think it's an issue number 1, remove any series' that are one-shots
		if keys['issue_number'] != '1':
			#IssueIdentifier.log_msg( "Removing one-shots" )
			series_shortlist[:] = [x for x in series_shortlist if not x['count_of_issues'] == 1]	

		IssueIdentifier.log_msg( "Searching in " + str(len(series_shortlist)) +" series" )
		
		# now sort the list by name length
		series_shortlist.sort(key=lambda x: len(x['name']), reverse=False)
		
		# Now we've got a list of series that we can dig into, 
		# and look for matching issue number, date, and cover image
		
		match_list = []

		IssueIdentifier.log_msg( "Fetching issue data", newline=False)

		for series in series_shortlist:
			#IssueIdentifier.log_msg( "Fetching info for  ID: {0} {1} ({2}) ...".format(
			#               series['id'], 
			#               series['name'], 
			#               series['start_year']) )
			IssueIdentifier.log_msg( ".", newline=False)
			
			cv_series_results = comicVine.fetchVolumeData( series['id'] )
			issue_list = cv_series_results['issues']
			for issue in issue_list:
				
				# format the issue number string nicely, since it's usually something like "2.00"
				num_f = float(issue['issue_number'])
				num_s = str( int(math.floor(num_f)) )
				if math.floor(num_f) != num_f:
					num_s = str( num_f )			

				# look for a matching issue number
				if num_s == keys['issue_number']:
					# found a matching issue number!  now get the issue data 
					img_url, thumb_url = comicVine.fetchIssueCoverURLs( issue['id'] )
					#TODO get the image from URL, and calc hash!!
					url_image_data = urllib.urlopen(thumb_url).read()

					url_image_hash = self.calculateHash( url_image_data )
					
					match = dict()
					match['series'] = "{0} ({1})".format(series['name'], series['start_year'])
					match['distance'] = ImageHasher.hamming_distance(cover_hash, url_image_hash)
					match['issue_number'] = num_s
					match['url_image_hash'] = url_image_hash
					match['issue_title'] = issue['name']
					match['img_url'] = thumb_url
					match_list.append(match)
					
					break
		IssueIdentifier.log_msg( "done!" )
		
		if len(match_list) == 0:
			IssueIdentifier.log_msg( ":-(  no matches!" )
			return
		
		# sort list by image match scores
		match_list.sort(key=lambda k: k['distance'])		
		
		l = []
		for i in match_list:
			l.append( i['distance'] )

		IssueIdentifier.log_msg( "Compared {0} covers".format(len(match_list)), newline=False)
		IssueIdentifier.log_msg( str(l))

		def print_match(item):
			IssueIdentifier.log_msg( u"-----> {0} #{1} {2} -- score: {3}\n-------> url:{4}".format(
									item['series'], 
									item['issue_number'], 
									item['issue_title'],
									item['distance'],
									item['img_url']) )
		
		best_score = match_list[0]['distance']

		if len(match_list) == 1:
			if best_score > self.min_score_thresh:
				IssueIdentifier.log_msg( "!!!! Very weak score for the cover.  Maybe it's not the cover?" )
			print_match(match_list[0])
			return

		elif best_score > self.min_score_thresh and len(match_list) > 1:
			IssueIdentifier.log_msg( "No good image matches!  Need to use other info..." )
			return
		
		#now pare down list, remove any item more than specified distant from the top scores
		for item in reversed(match_list):
			if item['distance'] > best_score + self.min_score_distance:
				match_list.remove(item)

		if len(match_list) == 1:
			print_match(match_list[0])
			return
		elif len(match_list) == 0:
			IssueIdentifier.log_msg( "No matches found :(" )
			return
			
		else:
			print 
			IssueIdentifier.log_msg( "More than one likley candiate.  Maybe a lexical comparison??" )
			for item in match_list:
				print_match(item)
	
	