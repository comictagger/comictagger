"""
A python class to represent a single comic, be it file or folder of images
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

import zipfile
import os
import struct
import sys
import tempfile
import subprocess
import platform
if platform.system() == "Windows":
	import _subprocess
import time

sys.path.insert(0, os.path.abspath(".") )
import UnRAR2
from UnRAR2.rar_exceptions import *

from options import Options, MetaDataStyle
from comicinfoxml import ComicInfoXml
from comicbookinfo import ComicBookInfo
from genericmetadata import GenericMetadata
from filenameparser import FileNameParser


class ZipArchiver:
	
	def __init__( self, path ):
		self.path = path
	
	def getArchiveComment( self ):
		zf = zipfile.ZipFile( self.path, 'r' )
		comment = zf.comment
		zf.close()
		return comment

	def setArchiveComment( self, comment ):
		self.writeZipComment( self.path, comment )

	def readArchiveFile( self, archive_file ):
		zf = zipfile.ZipFile( self.path, 'r' )
		data = zf.read( archive_file )
		zf.close()
		return data

	def removeArchiveFile( self, archive_file ):
		self.rebuildZipFile(  [ archive_file ] )

	def writeArchiveFile( self, archive_file, data ):
		#  At the moment, no other option but to rebuild the whole 
		#  zip archive w/o the indicated file. Very sucky, but maybe 
		# another solution can be found
		self.rebuildZipFile(  [ archive_file ] )
		
		#now just add the archive file as a new one
		zf = zipfile.ZipFile(self.path, mode='a', compression=zipfile.ZIP_DEFLATED ) 
		zf.writestr( archive_file, data )
		zf.close()

	def getArchiveFilenameList( self ):		
		zf = zipfile.ZipFile( self.path, 'r' )
		namelist = zf.namelist()
		zf.close()
		return namelist
	
	# zip helper func
	def rebuildZipFile( self, exclude_list ):
		
		# TODO: use tempfile.mkstemp
		# this recompresses the zip archive, without the files in the exclude_list
		print "Rebuilding zip {0} without {1}".format( self.path, exclude_list )
		
		# generate temp file
		tmp_fd, tmp_name = tempfile.mkstemp( dir=os.path.dirname(self.path) )
		os.close( tmp_fd )
		
		zin = zipfile.ZipFile (self.path, 'r')
		zout = zipfile.ZipFile (tmp_name, 'w')
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
		os.rename( tmp_name, self.path )


	def writeZipComment( self, filename, comment ):
		"""
		This is a custom function for writing a comment to a zip file,
		since the built-in one doesn't seem to work on Windows and Mac OS/X

		Fortunately, the zip comment is at the end of the file, and it's
		easy to manipulate.  See this website for more info:
		see: http://en.wikipedia.org/wiki/Zip_(file_format)#Structure
		"""

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
# RAR implementation
	
class RarArchiver:
	
	def __init__( self, path ):
		self.path = path
		self.rar_exe_path = None
		self.devnull = open(os.devnull, "w")

		# windows only, keeps the cmd.exe from popping up
		if platform.system() == "Windows":
			self.startupinfo = subprocess.STARTUPINFO()
			self.startupinfo.dwFlags |= _subprocess.STARTF_USESHOWWINDOW
		else:
			self.startupinfo = None

	def __del__(self):
		self.devnull.close()
		
	def getArchiveComment( self ):
		
		rarc = UnRAR2.RarFile( self.path )
		return rarc.comment		

	def setArchiveComment( self, comment ):

		if self.rar_exe_path is not None:
			# write comment to temp file
			tmp_fd, tmp_name = tempfile.mkstemp()
			f = os.fdopen(tmp_fd, 'w+b')
			f.write( comment )		
			f.close()

			# use external program to write comment to Rar archive
			subprocess.call([self.rar_exe_path, 'c', '-c-', '-z' + tmp_name, self.path], 
                   startupinfo=self.startupinfo, 
				   stdout=self.devnull)
			
			if platform.system() == "Darwin":
				time.sleep(1)
				
			os.remove( tmp_name)

	def readArchiveFile( self, archive_file ):

		entries = UnRAR2.RarFile( self.path ).read_files( archive_file )

		#entries is a list of of tuples:  ( rarinfo, filedata)
		if (len(entries) == 1):
			return entries[0][1]
		else:
			return ""

	def writeArchiveFile( self, archive_file, data ):

		if self.rar_exe_path is not None:
			
			tmp_folder = tempfile.mkdtemp()

			tmp_file = os.path.join( tmp_folder, archive_file )

			f = open(tmp_file, 'w')
			f.write( data )		
			f.close()

			# use external program to write file to Rar archive
			subprocess.call([self.rar_exe_path, 'a', '-c-', '-ep', self.path, tmp_file], 
                   startupinfo=self.startupinfo,
				   stdout=self.devnull)

			if platform.system() == "Darwin":
				time.sleep(1)
			os.remove( tmp_file)
			os.rmdir( tmp_folder)

	def removeArchiveFile( self, archive_file ):
		if self.rar_exe_path is not None:

			# use external program to remove file from Rar archive
			subprocess.call([self.rar_exe_path, 'd','-c-', self.path, archive_file], 
                   startupinfo=self.startupinfo, 				   
                   stdout=self.devnull)

			if platform.system() == "Darwin":
				time.sleep(1)

	def getArchiveFilenameList( self ):

		rarc = UnRAR2.RarFile( self.path )

		return [ item.filename for item in rarc.infolist() ]

#------------------------------------------
# Folder implementation
class FolderArchiver:
	
	def __init__( self, path ):
		self.path = path
		self.comment_file_name = "ComicTaggerFolderComment.txt" 

	def getArchiveComment( self ):
		return self.readArchiveFile( self.comment_file_name )
	
	def setArchiveComment( self, comment ):
		self.writeArchiveFile( self.comment_file_name, comment )
		
	def readArchiveFile( self, archive_file ):
		
		data = ""
		fname = os.path.join( self.path, archive_file )
		try:
			with open( fname, 'rb' ) as f: 
				data = f.read()
				f.close()			
		except IOError as e:
			pass
		
		return data

	def writeArchiveFile( self, archive_file, data ):

		fname = os.path.join( self.path, archive_file )
		try:
			with open(fname, 'w+') as f: 
				f.write( data )
				f.close()
		except IOError as e:
			pass
		
	def removeArchiveFile( self, archive_file ):

		fname = os.path.join( self.path, archive_file )
		try:
			os.remove( fname )
		except:
			pass
		
	def getArchiveFilenameList( self ):
		return self.listFiles( self.path )
		
	def listFiles( self, folder ):
		
		itemlist = list()

		for item in os.listdir( folder ):
			itemlist.append( item )
			if os.path.isdir( item ):
				itemlist.extend( self.listFiles( os.path.join( folder, item ) ))

		return itemlist

#------------------------------------------
# Unknown implementation
class UnknownArchiver:
	
	def __init__( self, path ):
		self.path = path

	def getArchiveComment( self ):
		return ""
	def setArchiveComment( self, comment ):
		return
	def readArchiveFilen( self ):
		return ""
	def writeArchiveFile( self, archive_file, data ):
		return
	def removeArchiveFile( self, archive_file ):
		return
	def getArchiveFilenameList( self ):
		return []

#------------------------------------------------------------------
class ComicArchive:
	
	class ArchiveType:
		Zip, Rar, Folder, Unknown = range(4)
    
	def __init__( self, path ):
		self.path = path
		self.ci_xml_filename = 'ComicInfo.xml'

		if self.zipTest():
			self.archive_type =  self.ArchiveType.Zip
			self.archiver = ZipArchiver( self.path )
			
		elif self.rarTest(): 
			self.archive_type =  self.ArchiveType.Rar
			self.archiver = RarArchiver( self.path )
			
		elif os.path.isdir( self.path ):
			self.archive_type =  self.ArchiveType.Folder
			self.archiver = FolderArchiver( self.path )			
		else:
			self.archive_type =  self.ArchiveType.Unknown
			self.archiver = UnknownArchiver( self.path )

	def setExternalRarProgram( self, rar_exe_path ):
		if self.isRar():
			self.archiver.rar_exe_path = rar_exe_path

	def zipTest( self ):
		return zipfile.is_zipfile( self.path )

	def rarTest( self ):
		try:
			rarc = UnRAR2.RarFile( self.path )
		except: # InvalidRARArchive:
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
		
		elif self.isRar() and self.archiver.rar_exe_path is None:
			return False
			
		elif not os.access(self.path, os.W_OK):
			return False
		
		elif ((self.archive_type != self.ArchiveType.Folder) and 
		        (not os.access( os.path.dirname( os.path.abspath(self.path)), os.W_OK ))):
			return False

		return True

	def isWritableForStyle( self, data_style ):

		if self.isRar() and data_style == MetaDataStyle.CBI:
			return False

		return self.isWritable()

	def seemsToBeAComicArchive( self ):

		# Do we even care about extensions??
		ext = os.path.splitext(self.path)[1].lower()

		if ( 
		      ( self.isZip() or  self.isRar() or self.isFolder() )
		      and
		      ( self.getNumberOfPages() > 2)

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
		
		# assume first page is the cover (for now)
		return self.getPage( 0 )
	
	def getPage( self, index ):
		
		image_data = None
		
		filename = self.getPageName( index )

		if filename is not None:
			image_data = self.archiver.readArchiveFile( filename )

		return image_data

	def getPageName( self, index ):
		
		page_list = self.getPageNameList()
		
		num_pages = len( page_list )
		if num_pages == 0 or index >= num_pages:
			return None
	
		return  page_list[index]

	def getPageNameList( self , sort_list=True):
		
		# get the list file names in the archive, and sort
		files = self.archiver.getArchiveFilenameList()
		
		# seems like some archive creators are on  Windows, and don't know about case-sensitivity!
		if sort_list:
			files.sort(key=lambda x: x.lower())
		
		# make a sub-list of image files
		page_list = []
		for name in files:
			if ( name[-4:].lower() in [ ".jpg", "jpeg", ".png" ] ):
				page_list.append(name)
				
		return page_list

	def getNumberOfPages( self ):
		
		return len( self.getPageNameList( sort_list=False ) )

	def readCBI( self ):
		raw_cbi = self.readRawCBI()
		if raw_cbi is None:
			return GenericMetadata()
		
		return ComicBookInfo().metadataFromString( raw_cbi )
	
	def readRawCBI( self ):
		if ( not self.hasCBI() ):
			return None

		return self.archiver.getArchiveComment()


	def writeCBI( self, metadata ):
		cbi_string = ComicBookInfo().stringFromMetadata( metadata )
		self.archiver.setArchiveComment( cbi_string )
		
	def removeCBI( self ):
		self.archiver.setArchiveComment( "" )
		
	def readCIX( self ):
		raw_cix = self.readRawCIX()
		if raw_cix is None:
			return GenericMetadata()
			
		return ComicInfoXml().metadataFromString( raw_cix )		

	def readRawCIX( self ):
		if not self.hasCIX():
			print self.path, "doesn't has ComicInfo.xml data!"
			return None

		return  self.archiver.readArchiveFile( self.ci_xml_filename )
		
	def writeCIX(self, metadata):

		if metadata is not None:
			cix_string = ComicInfoXml().stringFromMetadata( metadata )
			self.archiver.writeArchiveFile( self.ci_xml_filename, cix_string )

	def removeCIX( self ):

		self.archiver.removeArchiveFile( self.ci_xml_filename )
		
	def hasCIX(self):
		if not self.seemsToBeAComicArchive():
			return False
		elif self.ci_xml_filename in self.archiver.getArchiveFilenameList():
			return True
		else:
			return False

	def hasCBI(self):

		#if ( not ( self.isZip() or self.isRar()) or not self.seemsToBeAComicArchive() ): 
		if not self.seemsToBeAComicArchive(): 
			return False

		comment = self.archiver.getArchiveComment()
		return ComicBookInfo().validateString( comment )	

	def metadataFromFilename( self ):
		 
		metadata = GenericMetadata()
		
		fnp = FileNameParser()
		fnp.parseFilename( self.path )

		if fnp.issue != "":
			metadata.issue = fnp.issue
		if fnp.series != "":
			metadata.series = fnp.series
		if fnp.volume != "":
			metadata.volume = fnp.volume
		if fnp.year != "":
			metadata.year = fnp.year
		if fnp.issue_count != "":
			metadata.issueCount = fnp.issue_count

		metadata.isEmpty = False

		return metadata
