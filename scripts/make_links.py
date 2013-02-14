#!/usr/bin/python
"""
find all duplicate comics
"""

import sys
import os

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
from comictaggerlib.issuestring import *
import comictaggerlib.utils

def make_folder( folder ):
	if not os.path.exists( folder ):
		try:
			os.makedirs(folder)
		except Exception as e:
			print "{0} Can't make {1} -- quitting".format(e, folder)
			quit()
			
def make_link( source, link ):
	if not os.path.exists( link ):
		os.symlink( source , link )

def main():
	utils.fix_output_encoding()
	settings = ComicTaggerSettings()

	style = MetaDataStyle.CBI
	
	if len(sys.argv) < 3:
		print "usage:  {0} comic_root link_root".format(sys.argv[0])
		return
	
	comic_root = sys.argv[1]
	link_root = sys.argv[2]
	
	print "root is : ", comic_root
	filelist = utils.get_recursive_filelist( [ comic_root ] )
	make_folder( link_root )
		
	#first find all comics with metadata
	print "reading in all comics..."
	comic_list = []
	max_name_len = 2
	for filename in filelist:
		ca = ComicArchive(filename, settings )
		if ca.seemsToBeAComicArchive() and ca.hasMetadata( style ):

			comic_list.append((filename, ca.readMetadata( style )))
			
			fmt_str = u"{{0:{0}}}".format(max_name_len)
			print fmt_str.format( filename ) + "\r",
			sys.stdout.flush()
			max_name_len = max ( max_name_len, len(filename))

	print fmt_str.format( "" )
	print "Found {0} tagged comics.".format( len(comic_list))

	# walk through the comic list and add subdirs and links for each one	
	for filename, md in comic_list:
		print fmt_str.format( filename ) + "\r",
		sys.stdout.flush()
		
		#do date organizing:
		if md.month is not None:
			month_str = "{0:02d}".format(int(md.month))
		else:
			month_str = "00"
		date_folder = os.path.join(link_root, "date", str(md.year), month_str)
		make_folder( date_folder )
		make_link( filename, os.path.join(date_folder, os.path.basename(filename)) )
		
		#do publisher/series organizing:
		series_folder = os.path.join(link_root, "series", str(md.publisher), str(md.series))
		make_folder( series_folder )
		make_link( filename, os.path.join(series_folder, os.path.basename(filename)) )
		
if __name__ == '__main__':
	main() 
