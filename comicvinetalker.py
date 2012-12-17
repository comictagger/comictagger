"""
A python class to manage communication with Comic Vine's REST API
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


import json
from pprint import pprint 
import urllib2, urllib 
import math 
import re

try:
	from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest
	from PyQt4.QtCore import QUrl, pyqtSignal, QObject, QByteArray
except ImportError:
	# No Qt, so define a few dummy QObjects to help us compile
	class QObject():
		def __init__(self,*args):
			pass
	class pyqtSignal():
		def __init__(self,*args):
			pass
		def emit(a,b,c):
			pass

import utils
from settings import ComicTaggerSettings
from comicvinecacher import ComicVineCacher
from genericmetadata import GenericMetadata
from issuestring import IssueString


class ComicVineTalkerException(Exception):
	pass

class ComicVineTalker(QObject):

	def __init__(self, api_key=""):
		QObject.__init__(self)

		# key that is registered to comictagger
		self.api_key = '27431e6787042105bd3e47e169a624521f89f3a4'


	def testKey( self ):
	
		test_url = "http://api.comicvine.com/issue/1/?api_key=" + self.api_key + "&format=json&field_list=name"
		resp = urllib2.urlopen( test_url ) 
		content = resp.read()
	
		cv_response = json.loads( content )

		# Bogus request, but if the key is wrong, you get error 100: "Invalid API Key"
		return cv_response[ 'status_code' ] != 100

	def getUrlContent( self, url ):
		try:
			resp = urllib2.urlopen( url ) 
			return resp.read()
		except Exception as e:
			print e
			raise ComicVineTalkerException("Network Error!")

	def searchForSeries( self, series_name , callback=None, refresh_cache=False ):
		
		# remove cruft from the search string
		series_name = utils.removearticles( series_name ).lower().strip()
		
		# before we search online, look in our cache, since we might have
		# done this same search recently
		cvc = ComicVineCacher( )
		if not refresh_cache:
			cached_search_results = cvc.get_search_results( series_name )
			
			if len (cached_search_results) > 0:
				return cached_search_results
		
		original_series_name = series_name
	
		series_name = urllib.quote_plus(str(series_name))
		search_url = "http://api.comicvine.com/search/?api_key=" + self.api_key + "&format=json&resources=volume&query=" + series_name + "&field_list=name,id,start_year,publisher,image,description,count_of_issues&sort=start_year"

		content = self.getUrlContent(search_url) 
	
		cv_response = json.loads(content)
	
		if cv_response[ 'status_code' ] != 1:
			print ( "Comic Vine query failed with error:  [{0}]. ".format( cv_response[ 'error' ] ))
			return None

		search_results = list()
			
		# see http://api.comicvine.com/documentation/#handling_responses		

		limit = cv_response['limit']
		current_result_count = cv_response['number_of_page_results']
		total_result_count = cv_response['number_of_total_results']
		
		if callback is None:
			print ("Found {0} of {1} results".format( cv_response['number_of_page_results'], cv_response['number_of_total_results']))
		search_results.extend( cv_response['results'])
		offset = 0
		
		if callback is not None:
			callback( current_result_count, total_result_count )
			
		# see if we need to keep asking for more pages...
		while ( current_result_count < total_result_count ):
			if callback is None:
				print ("getting another page of results {0} of {1}...".format( current_result_count, total_result_count))
			offset += limit
			content = self.getUrlContent(search_url + "&offset="+str(offset)) 
		
			cv_response = json.loads(content)
		
			if cv_response[ 'status_code' ] != 1:
				print ( "Comic Vine query failed with error:  [{0}]. ".format( cv_response[ 'error' ] ))
				return None
			search_results.extend( cv_response['results'])
			current_result_count += cv_response['number_of_page_results']
			
			if callback is not None:
				callback( current_result_count, total_result_count )

	
		#for record in search_results: 
		#	print( "{0}: {1} ({2})".format(record['id'], smart_str(record['name']) , record['start_year'] ) )
		#	print( "{0}: {1} ({2})".format(record['id'], record['name'] , record['start_year'] ) )
		
		#print "{0}: {1} ({2})".format(search_results['results'][0]['id'], smart_str(search_results['results'][0]['name']) , search_results['results'][0]['start_year'] ) 
	
		# cache these search results
		cvc.add_search_results( original_series_name, search_results )

		return search_results

	def fetchVolumeData( self, series_id ):
		
		# before we search online, look in our cache, since we might already
		# have this info
		cvc = ComicVineCacher( )
		cached_volume_result = cvc.get_volume_info( series_id )
		
		if cached_volume_result is not None:
			return cached_volume_result

	
		volume_url = "http://api.comicvine.com/volume/" + str(series_id) + "/?api_key=" + self.api_key + "&format=json"

		content = self.getUrlContent(volume_url) 	
		cv_response = json.loads(content)

		if cv_response[ 'status_code' ] != 1:
			print ( "Comic Vine query failed with error:  [{0}]. ".format( cv_response[ 'error' ] ))
			return None

		volume_results = cv_response['results']
	
		cvc.add_volume_info( volume_results )

		return volume_results
				

	def fetchIssueData( self, series_id, issue_number, settings ):

		volume_results = self.fetchVolumeData( series_id )
	
		found = False
		for record in volume_results['issues']: 
			if float(record['issue_number']) == float(issue_number):
				found = True
				break
			
		if (found):
			issue_url = "http://api.comicvine.com/issue/" + str(record['id']) + "/?api_key=" + self.api_key + "&format=json"

			content = self.getUrlContent(issue_url) 
			cv_response = json.loads(content)
			if cv_response[ 'status_code' ] != 1:
				print ( "Comic Vine query failed with error:  [{0}]. ".format( cv_response[ 'error' ] ))
				return None
			issue_results = cv_response['results']

		else:
			return None
		
		# now, map the comicvine data to generic metadata
		metadata = GenericMetadata()
		
		metadata.series = issue_results['volume']['name']
		
		num_s = IssueString(issue_results['issue_number']).asString()
			
		metadata.issue = num_s
		metadata.title = issue_results['name']
		metadata.publisher = volume_results['publisher']['name']
		metadata.month = issue_results['publish_month']
		metadata.year = issue_results['publish_year']
		#metadata.issueCount = volume_results['count_of_issues']
		metadata.comments = self.cleanup_html(issue_results['description'])
		if settings.use_series_start_as_volume:
			metadata.volume = volume_results['start_year']
		
		metadata.notes   = "Tagged with ComicTagger app using info from Comic Vine." 
		#metadata.notes  += issue_results['site_detail_url']  
		
		metadata.webLink = issue_results['site_detail_url']
		
		person_credits = issue_results['person_credits']
		for person in person_credits: 
			for role in person['roles']:
				# can we determine 'primary' from CV??
				role_name = role['role'].title()
				metadata.addCredit( person['name'], role['role'].title(), False )			

		character_credits = issue_results['character_credits']
		character_list = list()
		for character in character_credits: 
			character_list.append( character['name'] )
		metadata.characters = utils.listToString( character_list )
	
		team_credits = issue_results['team_credits']
		team_list = list()
		for team in team_credits: 
			team_list.append( team['name'] )
		metadata.teams = utils.listToString( team_list )
	
		location_credits = issue_results['location_credits']
		location_list = list()
		for location in location_credits: 
			location_list.append( location['name'] )
		metadata.locations = utils.listToString( location_list )
	
		story_arc_credits = issue_results['story_arc_credits']
		for arc in story_arc_credits: 
			metadata.storyArc =  arc['name']
			#just use the first one, if at all
			break
	
		return metadata
	
	def cleanup_html( self, string):
		
		# remove all newlines first
		string = string.replace("\n", "")
		
		#put in our own
		string = string.replace("<br>", "\n")
		string = string.replace("</p>", "\n\n")
		string = string.replace("<h4>", "*")
		string = string.replace("</h4>", "*\n")
		
		# now strip all other tags
		p = re.compile(r'<[^<]*?>')
		newstring = p.sub('',string)

		newstring = newstring.replace('&nbsp;',' ')
		newstring = newstring.replace('&amp;','&')
	
		newstring = newstring.strip()

		
		return newstring

	def fetchIssueDate( self, issue_id ):
		image_url, thumb_url, month,year = self.fetchIssueSelectDetails( issue_id )
		return month, year

	def fetchIssueCoverURLs( self, issue_id ):
		image_url, thumb_url, month,year = self.fetchIssueSelectDetails( issue_id )
		return image_url, thumb_url
		
	def fetchIssueSelectDetails( self, issue_id ):

		cached_image_url,cached_thumb_url,cached_month,cached_year = self.fetchCachedIssueSelectDetails( issue_id )
		if cached_image_url is not None:
			return cached_image_url,cached_thumb_url, cached_month, cached_year

		issue_url = "http://api.comicvine.com/issue/" + str(issue_id) + "/?api_key=" + self.api_key + "&format=json&field_list=image,publish_month,publish_year"

		content = self.getUrlContent(issue_url) 
		
		cv_response = json.loads(content)
		if cv_response[ 'status_code' ] != 1:
			print ( "Comic Vine query failed with error:  [{0}]. ".format( cv_response[ 'error' ] ))
			return None, None,None,None
		
		image_url = cv_response['results']['image']['super_url']
		thumb_url = cv_response['results']['image']['thumb_url']
		year = cv_response['results']['publish_year']
		month = cv_response['results']['publish_month']
				
		if image_url is not None:
			self.cacheIssueSelectDetails( issue_id, image_url,thumb_url, month, year )
		return image_url,thumb_url,month,year
		
	def fetchCachedIssueSelectDetails( self, issue_id ):

		# before we search online, look in our cache, since we might already
		# have this info
		cvc = ComicVineCacher( )
		return  cvc.get_issue_select_details( issue_id )

	def cacheIssueSelectDetails( self, issue_id, image_url, thumb_url, month, year ):
		cvc = ComicVineCacher( )
		cvc.add_issue_select_details( issue_id, image_url, thumb_url, month, year )
		
		
#---------------------------------------------------------------------------
	urlFetchComplete = pyqtSignal( str , str, int)

	def asyncFetchIssueCoverURLs( self, issue_id ):
		
		self.issue_id = issue_id
		cached_image_url,cached_thumb_url,month,year = self.fetchCachedIssueSelectDetails( issue_id )
		if cached_image_url is not None:
			self.urlFetchComplete.emit( cached_image_url,cached_thumb_url, self.issue_id )
			return

		issue_url = "http://api.comicvine.com/issue/" + str(issue_id) + "/?api_key=" + self.api_key + "&format=json&field_list=image,publish_month,publish_year"
		self.nam = QNetworkAccessManager()
		self.nam.finished.connect( self.asyncFetchIssueCoverURLComplete )
		self.nam.get(QNetworkRequest(QUrl(issue_url)))

	def asyncFetchIssueCoverURLComplete( self, reply ):

		# read in the response
		data = reply.readAll()
		cv_response = json.loads(str(data))
		if cv_response[ 'status_code' ] != 1:
			print ( "Comic Vine query failed with error:  [{0}]. ".format( cv_response[ 'error' ] ))
			return 
		
		image_url = cv_response['results']['image']['super_url']
		thumb_url = cv_response['results']['image']['thumb_url']
		year = cv_response['results']['publish_year']
		month = cv_response['results']['publish_month']

		self.cacheIssueSelectDetails(  self.issue_id, image_url, thumb_url, month, year )

		self.urlFetchComplete.emit( image_url, thumb_url, self.issue_id ) 


