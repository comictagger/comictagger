#!/usr/bin/python
"""
An experiment with comictaggerlib
"""

import sys
import os
import platform
import locale
import codecs

sys.path.append("..")

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
from comictaggerlib.issuestring import *
import comictaggerlib.utils


def main():

	utils.fix_output_encoding()
	settings = ComicTaggerSettings()
	
	filelist = utils.get_recursive_filelist( sys.argv[1:] )
	
	#first read in CIX metadata from all files
	metadata_list = []	
	max_name_len = 2
	for filename in filelist:
		ca = ComicArchive(filename, settings )
		metadata_list.append((filename, ca.readCIX()))

		fmt_str = u"{{0:{0}}}".format(max_name_len)
		print fmt_str.format( filename ) + "\r",
		sys.stdout.flush()
	print fmt_str.format( "" ) + "\r",
		
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
	fmt_str = "{0:" + str(w0) + "} {1:" + str(w1) + "} #{2:6} ({3})"

	# now sort the list by series, and then issue
	metadata_list.sort(key=lambda x: IssueString(x[1].issue).asString(3), reverse=False)
	metadata_list.sort(key=lambda x: str(x[1].series).lower()+str(x[1].year), reverse=False)
	#metadata_list.sort(key=lambda x: x[1].series, reverse=False)
	
	# now print
	for filename,md in metadata_list:
		if not md.isEmpty:
			print fmt_str.format(os.path.split(filename)[1]+":", md.series, md.issue, md.year)


if __name__ == '__main__':
	main() 
