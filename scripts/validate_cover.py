#!/usr/bin/python
"""
test archive cover against comicvine for a given issue ID
"""
import sys
sys.path.append("..")
import os

import comictaggerlib.utils
from comictaggerlib.settings import *
from comictaggerlib.comicarchive import *
from comictaggerlib.issueidentifier import *
from comictaggerlib.comicvinetalker import *

def main():

	utils.fix_output_encoding()
	settings = ComicTaggerSettings()
	
	if len(sys.argv) < 3:
		print "usage:  {0} comicfile issueid".format(sys.argv[0])
		return
	
	filename = sys.argv[1]
	issue_id = sys.argv[2]

	if not os.path.exists(filename):
		print opts.filename + ": not found!"
		return
		
	ca = ComicArchive(filename, settings )
	if not ca.seemsToBeAComicArchive():
		print "Sorry, but "+ opts.filename + "  is not a comic archive!"
		return

	ii = IssueIdentifier( ca, settings )
	
	# calculate the hashes of the first two pages
	cover_image_data = ca.getPage( 0 )
	cover_hash0 = ii.calculateHash( cover_image_data )		
	cover_image_data = ca.getPage( 1 )
	cover_hash1 = ii.calculateHash( cover_image_data )
	hash_list = [ cover_hash0, cover_hash1 ]
	
	comicVine = ComicVineTalker( )
	result = ii.getIssueCoverMatchScore( comicVine, issue_id, hash_list, useRemoteAlternates=True, useLog=False)
	
	print "Best cover match score is :", result['score']
	if result['score'] < ii.min_alternate_score_thresh:
		print "Looks like a match!"
	else:
		print "Bad score, maybe not a match?"
	print result['url']
	
	
if __name__ == '__main__':
	main() 
