"""
A python class to represent a single comic, be it file or folder of images
"""

import zipfile
import os
import struct

from options import Options, MetaDataStyle
from comicinfoxml import ComicInfoXml
from comicbookinfo import ComicBookInfo
from genericmetadata import GenericMetadata
from filenameparser import FileNameParser


#  This is a custom function for writing a comment to a zip file,
#  since the built-in one doesn't seem to work on Windows and Mac OS/X

#  Fortunately, the zip comment is at the end of the file, and it's
#  easy to manipulate.  See this website for more info:
#  see: http://en.wikipedia.org/wiki/Zip_(file_format)#Structure

def writeZipComment( filename, comment ):

	#get file size
	statinfo = os.stat(filename)
	file_length = statinfo.st_size

	fo = open(filename, "r+b")

	#the starting position, relative to EOF
	pos = -4

	found = False
	value = bytearray()

	# walk backwards to find the "End of Central Directory" record
	while ( not found ) and ( -pos != file_length ):
		# seek, relative to EOF	
		fo.seek( pos,  2)

		value = fo.read( 4 )

		#look for the end of central directory signature
		if bytearray(value) == bytearray([ 0x50, 0x4b, 0x05, 0x06 ]):
			found = True
		else:
			# not found, step back another byte
			pos = pos - 1
		#print pos,"{1} int: {0:x}".format(bytearray(value)[0], value)
	
	if found:
		
		# now skip forward 20 bytes to the comment length word
		pos += 20
		fo.seek( pos,  2)

		# Pack the length of the comment string
		format = "H"                   # one 2-byte integer
		comment_length = struct.pack(format, len(comment)) # pack integer in a binary string
		
		# write out the length
		fo.write( comment_length )
		fo.seek( pos+2,  2)
		
		# write out the comment itself
		fo.write( comment )
		fo.truncate()
		fo.close()

	else:
		raise Exception('Failed to write comment to zip file!')
	
#------------------------------------------


class ComicArchive:
	
	def __init__( self, path ):
		self.path = path
		self.ci_xml_filename = 'ComicInfo.xml'
		
	def isZip( self ):
		return zipfile.is_zipfile( self.path )
		
	def isFolder( self ):
		return False

	def isNonWritableArchive( self ):
		# TODO check for rar, maybe others
		# also check permissions
		return False

	def seemsToBeAComicArchive( self ):
		# TODO this will need to be fleshed out to support RAR and Folder

		ext = os.path.splitext(self.path)[1].lower()
		
		if (  
		      ( self.isZip() ) and 
		      ( ext in [ '.zip', '.cbz' ] ) and 
		      ( self.getNumberOfPages() > 3) 
			):
			return True
		else:	
			return False

	def readMetadata( self, style ):
		
		if style == MetaDataStyle.CIX:
			return self.readCIX()
		elif style == MetaDataStyle.CBI:
			return self.readCBI()
		else:
			return GenericMetadata()

	def writeMetadata( self, metadata, style ):
		
		if style == MetaDataStyle.CIX:
			self.writeCIX( metadata )
		elif style == MetaDataStyle.CBI:
			self.writeCBI( metadata )

	def hasMetadata( self, syle ):
		
		if style == MetaDataStyle.CIX:
			return self.hasCIX()
		elif style == MetaDataStyle.CBI:
			return self.hasCBI()
		else:
			return False
	
	def clearMetadata( self, style ):
		return 

	def getCoverPage(self):
		
		if self.getNumberOfPages() == 0:
			return None
			
		zf = zipfile.ZipFile (self.path, 'r')
		
		# get the list file names in the archive, and sort
		files = zf.namelist()
		files.sort()
		
		# find the first image file, assume it's the cover
		for name in files:
			if ( name[-4:].lower() in [ ".jpg", "jpeg", ".png" ] ):
				break

		image_data = zf.read( name )
		zf.close()
	
		return image_data

	def getNumberOfPages(self):

		count = 0
		
		if self.isZip():
			zf = zipfile.ZipFile (self.path, 'r')
			for item in zf.infolist():
				if ( item.filename[-4:].lower() in [ ".jpg", "jpeg", ".png" ] ):
					count += 1
			zf.close()

		return count

	def readCBI( self ):

		if ( not self.hasCBI() ):
			print self.path, " isn't a zip or doesn't has CBI data!"
			return GenericMetadata()

		zf = zipfile.ZipFile( self.path, "r" )
		cbi_string = zf.comment
		zf.close()
		
		metadata = ComicBookInfo().metadataFromString( cbi_string )
		return metadata

	def writeCBI( self, metadata ):

		cbi_string = ComicBookInfo().stringFromMetadata( metadata )
		writeZipComment( self.path, cbi_string )
		
	def readCIX( self ):

		# !!!ATB TODO add support for folders
		
		if (not self.isZip()) or ( not self.hasCIX()):
			print self.path, " isn't a zip or doesn't has ComicInfo.xml data!"
			return GenericMetadata()
			
		zf = zipfile.ZipFile( self.path, 'r' )
		cix_string = zf.read( self.ci_xml_filename )
		zf.close()
		
		metadata = ComicInfoXml().metadataFromString( cix_string )		
		return metadata

	def writeCIX(self, metadata):

		# !!!ATB TODO add support for folders
		if (not self.isZip()): 
			print self.path, "isn't a zip archive!"
			return
		
		cix_string = ComicInfoXml().stringFromMetadata( metadata )
		
		# check if an XML file already exists in archive
		if not self.hasCIX():

			#simple case: just add the new archive file
			zf = zipfile.ZipFile(self.path, mode='a', compression=zipfile.ZIP_DEFLATED ) 
			zf.writestr( self.ci_xml_filename, cix_string )
			zf.close()
				
		else:
			# If we need to replace it, well, at the moment, no other option
			# but to rebuild the whole zip again.
			# very sucky, but maybe another solution can be found
			
			print "{0} already exists in {1}.  Rebuilding it...".format( self.ci_xml_filename, self.path)			
			zin = zipfile.ZipFile (self.path, 'r')
			zout = zipfile.ZipFile ('tmpnew.zip', 'w')
			for item in zin.infolist():
				buffer = zin.read(item.filename)
				if ( item.filename != self.ci_xml_filename ):
					zout.writestr(item, buffer)
					
			# now write out the new xml file
			zout.writestr( self.ci_xml_filename, cix_string )
			
			#preserve the old comment
			zout.comment = zin.comment
			
			zout.close()
			zin.close()
			
			# replace with the new file 
			os.remove( self.path )
			os.rename( 'tmpnew.zip', self.path )
	
	def hasCIX(self):

		has = False
		
		zf = zipfile.ZipFile( self.path, 'r' )
		if self.ci_xml_filename in zf.namelist():
			has = True
		zf.close()
		
		return has

	def hasCBI(self):
		if (not self.isZip() ): 
			return False
		zf = zipfile.ZipFile( self.path, 'r' )
		comment = zf.comment
		zf.close()
		
		return ComicBookInfo().validateString( comment )	

	def metadataFromFilename( self ):
		 
		metadata = GenericMetadata()
		
		fnp = FileNameParser()
		fnp.parseFilename( self.path )

		if fnp.issue != "":
			metadata.issueNumber = fnp.issue
		if fnp.series != "":
			metadata.series = fnp.series
		if fnp.volume != "":
			metadata.volumeNumber = fnp.volume
		if fnp.year != "":
			metadata.publicationYear = fnp.year

		metadata.isEmpty = False
		
		return metadata