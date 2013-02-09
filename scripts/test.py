#!/usr/bin/python
"""
An experiment with comictaggerlib
"""

import sys
import os
import platform
import locale
import codecs

sys.path += ".." + os.pathsep

from comictaggerlib.comicarchive import *
from comictaggerlib.settings import *
from comictaggerlib.issuestring import *


#---------------------------------------
def init_output( ):

	# try to make stdout encodings happy for unicode printing
	if platform.system() == "Darwin":
		preferred_encoding = "utf-8"
	else:
		preferred_encoding = locale.getpreferredencoding()
	sys.stdout = codecs.getwriter(preferred_encoding)(sys.stdout)
	sys.stderr = codecs.getwriter(preferred_encoding)(sys.stderr)

#--------------------------------------
def get_recursive_filelist( pathlist ):
	filelist = []
	for p in pathlist:
		# if path is a folder, walk it recursivly, and all files underneath
		if type(p) == str:
			#make sure string is unicode
			filename_encoding = sys.getfilesystemencoding()
			p = p.decode(filename_encoding, 'replace')
		
		if os.path.isdir( unicode(p)):
			for root,dirs,files in os.walk( unicode(p) ):
				for f in files:
					filelist.append(os.path.join(root,unicode(f)))
		else:
			filelist.append(unicode(p))
	
	return filelist
#--------------------------------------


def main():
	init_output()
	settings = ComicTaggerSettings()
	
	filelist = get_recursive_filelist( sys.argv )
	
	#first read in CIX metadata from all files
	metadata_list = []	
	for filename in filelist:
		ca = ComicArchive(filename, settings )
		metadata_list.append((filename, ca.readCIX()))

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

	# now sort the list by year
	metadata_list.sort(key=lambda x: IssueString(x[1].issue).asString(3), reverse=False)
	metadata_list.sort(key=lambda x: str(x[1].series)+str(x[1].year), reverse=False)
	#metadata_list.sort(key=lambda x: x[1].series, reverse=False)
	
	# now print
	for filename,md in metadata_list:
		if not md.isEmpty:
			print fmt_str.format(os.path.split(filename)[1]+":", md.series, md.issue, md.year)
			"""
			if len(md.pages) != 0:
				for p in md.pages:
					if p.has_key('Type') and p['Type'] in [ 'Deleted', 'Advertisment' ]:
						print "-------Has pages to remove"
			"""

if __name__ == '__main__':
	main() 
