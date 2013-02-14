#!/usr/bin/python
"""
An example script using the comictagger library
"""

import sys
import os

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
from comictaggerlib.issuestring import *
import comictaggerlib.utils

def main():
	utils.fix_output_encoding()
	settings = ComicTaggerSettings()

	style = MetaDataStyle.CIX

	if len(sys.argv) < 2:
		print "usage:  {0} comic_folder ".format(sys.argv[0])
		return
	
	filelist = utils.get_recursive_filelist( sys.argv[1:] )
			
	#first read in metadata from all files
	metadata_list = []	
	max_name_len = 2
	for filename in filelist:
		ca = ComicArchive(filename, settings )
		#make a list of paired filenames and metadata objects
		metadata_list.append((filename, ca.readMetadata( style )))

		fmt_str = u"{{0:{0}}}".format(max_name_len)
		print fmt_str.format( filename ) + "\r",
		sys.stdout.flush()
		max_name_len = max ( max_name_len, len(filename))

	print fmt_str.format( "" ) + "\r",
	print "-----------------------------------------------"
	print "Found {0} comics with {1} tags".format( len(metadata_list), MetaDataStyle.name[style])
	print "-----------------------------------------------"

	# now, figure out column widths	
	w0 = 4
	w1 = 4
	for filename,md in metadata_list: 
		if not md.isEmpty:
			w0 = max( len((os.path.split(filename)[1])), w0)
			if md.series is not None:
				w1 = max( len(md.series), w1)
	w0 += 2
	
	# build a format string
	fmt_str = u"{0:" + str(w0) + "} {1:" + str(w1) + "} #{2:6} ({3})"

	# now sort the list by series, and then issue
	metadata_list.sort(key=lambda x: IssueString(x[1].issue).asString(3), reverse=False)
	metadata_list.sort(key=lambda x: unicode(x[1].series).lower()+str(x[1].year), reverse=False)
	
	# now print
	for filename, md in metadata_list:
		if not md.isEmpty:
			print fmt_str.format(os.path.split(filename)[1]+":", md.series, md.issue, md.year), md.title

if __name__ == '__main__':
	main() 
