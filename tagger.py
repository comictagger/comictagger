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
import math
import urllib2, urllib 

from settings import ComicTaggerSettings

from taggerwindow import TaggerWindow
from options import Options, MetaDataStyle
from comicarchive import ComicArchive

from comicvinetalker import ComicVineTalker
from comicvinecacher import ComicVineCacher
from comicinfoxml import ComicInfoXml
from comicbookinfo import ComicBookInfo
from imagehasher import ImageHasher
import utils

#-----------------------------
def cliProcedure( opts, settings ):

	ca = ComicArchive(opts.filename)
	if not ca.seemsToBeAComicArchive():
		print "Sorry, but "+ opts.filename + "  is not a comic archive!"
		return
	
	cover_image_data = ca.getCoverPage()
	#cover_hash = ImageHasher( data=cover_image_data ).average_hash() 
	#print "Cover hash = ",cover_hash

	cover_hash = ImageHasher( data=cover_image_data ).average_hash2() 
	#print "Cover hash = ",cover_hash

	#cover_hash = ImageHasher( data=cover_image_data , width=32, height=32 ).perceptual_hash() 

	# see if the archive has any useful meta data for searching with
	if ca.hasCIX():
		internal_metadata = ca.readCIX()
	elif ca.hasCBI():
		internal_metadata = ca.readCBI()
	else:
		internal_metadata = ca.readCBI()

	# try to get some metadata from filename
	md_from_filename = ca.metadataFromFilename()
	
	# now figure out what we have to search with
	search_series = internal_metadata.series
	search_issue_number = internal_metadata.issueNumber
	search_year = internal_metadata.publicationYear
	search_month = internal_metadata.publicationMonth
	
	if search_series is None:
		search_series = md_from_filename.series
	
	if search_issue_number is None:
		search_issue_number = md_from_filename.issueNumber
		
	if search_year is None:
		search_year = md_from_filename.publicationYear
		
	# we need, at minimum, a series and issue number
	if search_series is None or search_issue_number is None:
		print "Not enough info for a search!"
		return

	print ( "Going to search for:" )
	print ( "Series: ", search_series )
	print ( "Issue : ", search_issue_number ) 
	if search_year is not None:
		print ( "Year :  ", search_year ) 
	if search_month is not None:
		print ( "Month : ", search_month )
	
	
	comicVine = ComicVineTalker( settings.cv_api_key )

	print ( "Searching for " + search_series + "...")

	cv_search_results = comicVine.searchForSeries( search_series )
	
	#----------    TEST
	#cvc = ComicVineCacher( settings.folder )
	#cvc.add_search_results( search_series, cv_search_results )
	#cached_search_results = cvc.get_search_results( search_series)
	#for r in cached_search_results:
	#	print "{0}: {1} ({2})".format(  r['id'],  r['name'],  r['start_year'])
	#quit()
	#----------    TEST
	

	print "Found " + str(len(cv_search_results)) + " initial results"
	
	series_shortlist = []
	
	print "Removing results with too long names"
	for item in cv_search_results:
		#assume that our search name is close to the actual name, say within 8 characters
		if len( item['name']) < len( search_series ) + 8:
			series_shortlist.append(item)
	
	# if we don't think it's an issue number 1, remove any series' that are one-shots
	if search_issue_number != '1':
		print "Removing one-shots"
		series_shortlist[:] = [x for x in series_shortlist if not x['count_of_issues'] == 1]	

	print "Finally, searching in " + str(len(series_shortlist)) +" series" 
	
	# now sort the list by name length
	series_shortlist.sort(key=lambda x: len(x['name']), reverse=False)
	
	# Now we've got a list of series that we can dig into, 
	# and look for matching issue number, date, and cover image
	
	match_list = []

	for series in series_shortlist:
		#print series['id'], series['name'], series['start_year'], series['count_of_issues']
		print "Fetching info for  ID: {0} {1} ({2}) ...".format(
		               series['id'], 
		               series['name'], 
		               series['start_year'])
		
		cv_series_results = comicVine.fetchVolumeData( series['id'] )
		issue_list = cv_series_results['issues']
		for issue in issue_list:
			
			# format the issue number string nicely, since it's usually something like "2.00"
			num_f = float(issue['issue_number'])
			num_s = str( int(math.floor(num_f)) )
			if math.floor(num_f) != num_f:
				num_s = str( num_f )			

			# look for a matching issue number
			if num_s == search_issue_number:
				# found a matching issue number!  now get the issue data 
				img_url = comicVine.fetchIssueCoverURL( issue['id'] )
				#TODO get the URL, and calc hash!!
				url_image_data = urllib.urlopen(img_url).read()
				#url_image_hash = ImageHasher( data=url_image_data ).average_hash() 
				url_image_hash = ImageHasher( data=url_image_data,   ).average_hash2() 
				#url_image_hash = ImageHasher( data=url_image_data, width=32, height=32  ).perceptual_hash() 
				
				match = dict()
				match['series'] = "{0} ({1})".format(series['name'], series['start_year'])
				match['distance'] = ImageHasher.hamming_distance(cover_hash, url_image_hash)
				match['issue_number'] = num_s
				match['issue_title'] = issue['name']
				match['img_url'] = img_url
				match_list.append(match)
				
				break
	
	print "Compared covers for {0} issues".format(len(match_list))
	
	# sort list by image match scores
	match_list.sort(key=lambda k: k['distance'])

	#helper
	def print_match(item):
		print u"-----> {0} #{1} {2} -- score: {3}\n-------> url:{4}".format(
								item['series'], 
								item['issue_number'], 
								item['issue_title'],
								item['distance'],
								item['img_url'])
	
	best_score = match_list[0]['distance']

	if len(match_list) == 0:
		print "No matches found :("
		return

	if len(match_list) == 1:
		print_match(match_list[0])
		return

	elif best_score > 20 and len(match_list) > 1:
		print "No good image matches!  Need to use other info..."
		return
	
	#now pare down list, remove any item more than 2 distant from the top scores
	for item in reversed(match_list):
		if item['distance'] > best_score + 2:
			match_list.remove(item)

	if len(match_list) == 1:
		print_match(match_list[0])
		return
			
	else:
		print "More than one likley candiate.  Maybe a lexical comparison??"
		for item in match_list:
			print_match(item)
			
	"""
	# now get the particular issue data
	metadata = comicVine.fetchIssueData( series_id, opts.issue_number )

	#pprint( cv_volume_data, indent=4 )

	ca = ComicArchive(opts.filename)
	ca.writeMetadata( metadata, opts.data_style )

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

		cliProcedure( opts, settings )
		
	else:

		app = QtGui.QApplication(sys.argv)
		tagger_window = TaggerWindow( opts, settings )
		tagger_window.show()
		sys.exit(app.exec_())

if __name__ == "__main__":
    main()
    
    
    
    
    
