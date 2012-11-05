"""
A python class to represent a single comic, be it file or folder of images
"""

import zipfile
import os
import struct
import sys
import tempfile
from subprocess import call

sys.path.insert(0, os.path.abspath(".") )
import UnRAR2
from UnRAR2.rar_exceptions import *

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
	
	class ArchiveType:
		Zip, Rar, Folder, Unknown = range(4)
    
	def __init__( self, path ):
		self.path = path
		self.ci_xml_filename = 'ComicInfo.xml'
		self.rar_exe_path = None

		if self.zipTest():
			self.archive_type =  self.ArchiveType.Zip
			self.getArchiveComment = self.getArchiveComment_zip
			self.setArchiveComment = self.setArchiveComment_zip
			self.readArchiveFile = self.readArchiveFile_zip
			self.writeArchiveFile = self.writeArchiveFile_zip
			self.removeArchiveFile = self.removeArchiveFile_zip
			self.getArchiveFilenameList = self.getArchiveFilenameList_zip
			
		elif self.rarTest(): 
			self.archive_type =  self.ArchiveType.Rar
			self.getArchiveComment = self.getArchiveComment_rar
			self.setArchiveComment = self.setArchiveComment_rar
			self.readArchiveFile = self.readArchiveFile_rar
			self.writeArchiveFile = self.writeArchiveFile_rar
			self.removeArchiveFile = self.removeArchiveFile_rar
			self.getArchiveFilenameList = self.getArchiveFilenameList_rar

		elif os.path.isdir( self.path ):
			self.archive_type =  self.ArchiveType.Folder
			self.getArchiveComment = self.getArchiveComment_folder
			self.setArchiveComment = self.setArchiveComment_folder
			self.readArchiveFile = self.readArchiveFile_folder
			self.writeArchiveFile = self.writeArchiveFile_folder
			self.removeArchiveFile = self.removeArchiveFile_folder
			self.getArchiveFilenameList = self.getArchiveFilenameList_folder
			
		else:
			self.archive_type =  self.ArchiveType.Unknown
			self.getArchiveComment = self.getArchiveComment_unknown
			self.setArchiveComment = self.setArchiveComment_unknown
			self.readArchiveFile = self.readArchiveFile_unknown
			self.writeArchiveFile = self.writeArchiveFile_unknown
			self.removeArchiveFile = self.removeArchiveFile_unknown
			self.getArchiveFilenameList = self.getArchiveFilenameList_unknown


	def setExternalRarProgram( self, rar_exe_path ):
		self.rar_exe_path = rar_exe_path

	def zipTest( self ):
		return zipfile.is_zipfile( self.path )

	def rarTest( self ):
		try:
			rarc = UnRAR2.RarFile( self.path )
		except InvalidRARArchive:
			return False
		else:
			return True

			
	def isZip( self ):
		return self.archive_type ==  self.ArchiveType.Zip
		
	def isRar( self ):
		return self.archive_type ==  self.ArchiveType.Rar
	
	def isFolder( self ):
		return self.archive_type ==  self.ArchiveType.Folder

	def isWritable( self ):
		if self.archive_type == self.ArchiveType.Unknown :
			return False
		
		elif self.isRar() and self.rar_exe_path is None:
			return False
			
		elif not os.access(self.path, os.W_OK):
			return False

		return True

	def seemsToBeAComicArchive( self ):
		# TODO this will need to be fleshed out to support RAR and Folder

		ext = os.path.splitext(self.path)[1].lower()
		
		if (  
		      ( ( ( self.isZip() ) and 
		      ( ext in [ '.zip', '.cbz' ] ))  
		        or
		      (( self.isRar() ) and 
		      ( ext in [ '.rar', '.cbr' ] ))  
		        or
		      ( self.isFolder()   ) )  

		      and
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

	def hasMetadata( self, style ):
		
		if style == MetaDataStyle.CIX:
			return self.hasCIX()
		elif style == MetaDataStyle.CBI:
			return self.hasCBI()
		else:
			return False
	
	def removeMetadata( self, style ):
		if style == MetaDataStyle.CIX:
			self.removeCIX()
		elif style == MetaDataStyle.CBI:
			self.removeCBI()

	def getCoverPage(self):
		
		if self.getNumberOfPages() == 0:
			return None
			
		# get the list file names in the archive, and sort
		files = self.getArchiveFilenameList()
		files.sort()
		
		# find the first image file, assume it's the cover
		for name in files:
			if ( name[-4:].lower() in [ ".jpg", "jpeg", ".png" ] ):
				break

		image_data = self.readArchiveFile( name )
	
		return image_data

	def getNumberOfPages(self):

		count = 0
		
		for item in self.getArchiveFilenameList():
			if ( item[-4:].lower() in [ ".jpg", "jpeg", ".png" ] ):
				count += 1

		return count

	def readCBI( self ):

		if ( not self.hasCBI() ):
			return GenericMetadata()

		cbi_string = self.getArchiveComment()
		
		metadata = ComicBookInfo().metadataFromString( cbi_string )
		return metadata

	def writeCBI( self, metadata ):

		cbi_string = ComicBookInfo().stringFromMetadata( metadata )
		self.setArchiveComment( cbi_string )
		
	def removeCBI( self ):
		self.setArchiveComment( "" )
		
	def readCIX( self ):
		
		if not self.hasCIX():
			print self.path, "doesn't has ComicInfo.xml data!"
			return GenericMetadata()

		cix_string = self.readArchiveFile( self.ci_xml_filename )
		
		metadata = ComicInfoXml().metadataFromString( cix_string )		
		return metadata

	def writeCIX(self, metadata):

		if metadata is not None:
			cix_string = ComicInfoXml().stringFromMetadata( metadata )
			self.writeArchiveFile( self.ci_xml_filename, cix_string )

	def removeCIX( self ):

		self.removeArchiveFile( self.ci_xml_filename )
		
	def hasCIX(self):
		if not self.seemsToBeAComicArchive():
			return False
		elif self.ci_xml_filename in self.getArchiveFilenameList():
			return True
		else:
			return False

	def hasCBI(self):

		if ( not ( self.isZip() or self.isRar()) or not self.seemsToBeAComicArchive() ): 
			return False

		comment = self.getArchiveComment()
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
	
	#---------------
	# Zip implementation
	#---------------
	
	def getArchiveComment_zip( self ):
		zf = zipfile.ZipFile( self.path, 'r' )
		comment = zf.comment
		zf.close()
		return comment

	def setArchiveComment_zip( self, comment ):
		writeZipComment( self.path, comment )

	def readArchiveFile_zip( self, archive_file ):
		zf = zipfile.ZipFile( self.path, 'r' )
		data = zf.read( archive_file )
		zf.close()
		return data

	def removeArchiveFile_zip( self, archive_file ):
		self.rebuildZipFile(  [ archive_file ] )

	def writeArchiveFile_zip( self, archive_file, data ):
		#  At the moment, no other option but to rebuild the whole 
		#  zip archive w/o the indicated file. Very sucky, but maybe 
		# another solution can be found
		self.rebuildZipFile(  [ archive_file ] )
		
		#now just add the archive file as a new one
		zf = zipfile.ZipFile(self.path, mode='a', compression=zipfile.ZIP_DEFLATED ) 
		zf.writestr( archive_file, data )
		zf.close()

	def getArchiveFilenameList_zip( self ):		
		zf = zipfile.ZipFile( self.path, 'r' )
		namelist = zf.namelist()
		zf.close()
		return namelist
	
	# zip helper func
	def rebuildZipFile( self, exclude_list ):
		
		# TODO: use tempfile.mkstemp
		# this recompresses the zip archive, without the files in the exclude_list
		print "Rebuilding zip {0} without {1}".format( self.path, exclude_list )
		zin = zipfile.ZipFile (self.path, 'r')
		zout = zipfile.ZipFile ('tmpnew.zip', 'w')
		for item in zin.infolist():
			buffer = zin.read(item.filename)
			if ( item.filename not in exclude_list ):
				zout.writestr(item, buffer)
		
		#preserve the old comment
		zout.comment = zin.comment
		
		zout.close()
		zin.close()
		
		# replace with the new file 
		os.remove( self.path )
		os.rename( 'tmpnew.zip', self.path )		
	
	#---------------
	# RAR implementation
	#---------------
	
	def getArchiveComment_rar( self ):
		
		rarc = UnRAR2.RarFile( self.path )
		return rarc.comment		

	def setArchiveComment_rar( self, comment ):

		if self.rar_exe_path is not None:
			# write comment to temp file
			tmp_fd, tmp_name = tempfile.mkstemp()
			f = os.fdopen(tmp_fd, 'w+b')
			f.write( comment )		
			f.close()

			# use external program to write comment to Rar archive
			call([self.rar_exe_path, 'c', '-z' + tmp_name, self.path])

			os.remove( tmp_name)

	def readArchiveFile_rar( self, archive_file ):

		entries = UnRAR2.RarFile( self.path ).read_files( archive_file )

		#entries is a list of of tuples:  ( rarinfo, filedata)
		if (len(entries) == 1):
			return entries[0][1]
		else:
			return ""

	def writeArchiveFile_rar( self, archive_file, data ):

		if self.rar_exe_path is not None:
			
			tmp_folder = tempfile.mkdtemp()

			tmp_file = os.path.join( tmp_folder, archive_file )

			f = open(tmp_file, 'w')
			f.write( data )		
			f.close()

			# use external program to write comment to Rar archive
			call([self.rar_exe_path, 'a', '-ep', self.path, tmp_file])
			
			os.remove( tmp_file)
			os.rmdir( tmp_folder)


	
	def removeArchiveFile_rar( self, archive_file ):
		if self.rar_exe_path is not None:

			# use external program to remove file from Rar archive
			call([self.rar_exe_path, 'd', self.path, archive_file])

	
	def getArchiveFilenameList_rar( self ):

		rarc = UnRAR2.RarFile( self.path )

		return [ item.filename for item in rarc.infolist() ]

	
	#---------------
	# Folder implementation
	#---------------
	
	def getArchiveComment_folder( self ):
		pass
	def setArchiveComment_folder( self, comment ):
		pass	
	def readArchiveFile_folder( self ):
		pass
	def writeArchiveFile_folder( self, archive_file, data ):
		pass
	def removeArchiveFile_folder( self, archive_file ):
		pass
	def getArchiveFilenameList_folder( self ):
		pass	

	#---------------
	# Unknown implementation
	#---------------
	
	def getArchiveComment_unknown( self ):
		return ""
	def setArchiveComment_unknown( self, comment ):
		return
	def readArchiveFile_unknown( self ):
		return ""
	def writeArchiveFile_unknown( self, archive_file, data ):
		return
	def removeArchiveFile_unknown( self, archive_file ):
		return
	def getArchiveFilenameList_unknown( self ):
		return []
	