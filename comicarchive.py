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

import StringIO
try: 
	import Image
	pil_available = True
except ImportError:
	pil_available = False
	
sys.path.insert(0, os.path.abspath(".") )
import UnRAR2
from UnRAR2.rar_exceptions import *

from options import Options, MetaDataStyle
from comicinfoxml import ComicInfoXml
from comicbookinfo import ComicBookInfo
from comet import CoMet
from genericmetadata import GenericMetadata, PageType
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
		return self.writeZipComment( self.path, comment )

	def readArchiveFile( self, archive_file ):
		zf = zipfile.ZipFile( self.path, 'r' )
		data = zf.read( archive_file )
		zf.close()
		return data

	def removeArchiveFile( self, archive_file ):
		try:
			self.rebuildZipFile(  [ archive_file ] )
		except:
			return False
		else:
			return True
			
	def writeArchiveFile( self, archive_file, data ):
		#  At the moment, no other option but to rebuild the whole 
		#  zip archive w/o the indicated file. Very sucky, but maybe 
		# another solution can be found
		try:
			self.rebuildZipFile(  [ archive_file ] )
			
			#now just add the archive file as a new one
			zf = zipfile.ZipFile(self.path, mode='a', compression=zipfile.ZIP_DEFLATED ) 
			zf.writestr( archive_file, data )
			zf.close()
			return True
		except:
			return False
			
	def getArchiveFilenameList( self ):		
		zf = zipfile.ZipFile( self.path, 'r' )
		namelist = zf.namelist()
		zf.close()
		return namelist
	
	# zip helper func
	def rebuildZipFile( self, exclude_list ):
		
		# this recompresses the zip archive, without the files in the exclude_list
		#print "Rebuilding zip {0} without {1}".format( self.path, exclude_list )
		
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

		try:
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
		except:
			return False
		else:
			return True

	def copyFromArchive( self, otherArchive ):
		# Replace the current zip with one copied from another archive
		try:		
			zout = zipfile.ZipFile (self.path, 'w')
			for fname in otherArchive.getArchiveFilenameList():
				data = otherArchive.readArchiveFile( fname )
				zout.writestr( fname, data )
			zout.close()
			
			#preserve the old comment
			comment = otherArchive.getArchiveComment()
			if comment is not None:
				if not self.writeZipComment( self.path, comment ):
					return False
		except:
			return False
		else:
			return True

		
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
			try:
				# write comment to temp file
				tmp_fd, tmp_name = tempfile.mkstemp()
				f = os.fdopen(tmp_fd, 'w+b')
				f.write( comment )		
				f.close()

				working_dir = os.path.dirname( os.path.abspath( self.path ) )

				# use external program to write comment to Rar archive
				subprocess.call([self.rar_exe_path, 'c', '-w' + working_dir , '-c-', '-z' + tmp_name, self.path], 
					startupinfo=self.startupinfo, 
					stdout=self.devnull)
				
				if platform.system() == "Darwin":
					time.sleep(1)
					
				os.remove( tmp_name)
			except:
				return False
			else:
				return True
		else:
			return False
			
	def readArchiveFile( self, archive_file ):

		entries = UnRAR2.RarFile( self.path ).read_files( archive_file )

		#entries is a list of of tuples:  ( rarinfo, filedata)
		if (len(entries) == 1):
			return entries[0][1]
		else:
			return ""

	def writeArchiveFile( self, archive_file, data ):

		if self.rar_exe_path is not None:
			try:
				tmp_folder = tempfile.mkdtemp()

				tmp_file = os.path.join( tmp_folder, archive_file )
				
				working_dir = os.path.dirname( os.path.abspath( self.path ) )

				# TODO: will this break if 'archive_file' is in a subfolder. i.e. "foo/bar.txt"
				# will need to create the subfolder above, I guess...
				f = open(tmp_file, 'w')
				f.write( data )		
				f.close()
				
				# use external program to write file to Rar archive
				subprocess.call([self.rar_exe_path, 'a', '-w' + working_dir ,'-c-', '-ep', self.path, tmp_file], 
					startupinfo=self.startupinfo,
					stdout=self.devnull)

				if platform.system() == "Darwin":
					time.sleep(1)
				os.remove( tmp_file)
				os.rmdir( tmp_folder)
			except:
				return False
			else:
				return True
		else:
			return False
			
	def removeArchiveFile( self, archive_file ):
		if self.rar_exe_path is not None:
			try:
				# use external program to remove file from Rar archive
				subprocess.call([self.rar_exe_path, 'd','-c-', self.path, archive_file], 
					startupinfo=self.startupinfo, 				   
					stdout=self.devnull)

				if platform.system() == "Darwin":
					time.sleep(1)
			except:
				return False
			else:
				return True
		else:
			return False
			
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
		return self.writeArchiveFile( self.comment_file_name, comment )
		
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
		except:
			return False
		else:
			return True
		
	def removeArchiveFile( self, archive_file ):

		fname = os.path.join( self.path, archive_file )
		try:
			os.remove( fname )
		except:
			return False
		else:
			return True
		
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
		return False
	def readArchiveFilen( self ):
		return ""
	def writeArchiveFile( self, archive_file, data ):
		return False
	def removeArchiveFile( self, archive_file ):
		return False
	def getArchiveFilenameList( self ):
		return []

#------------------------------------------------------------------
class ComicArchive:
	
	class ArchiveType:
		Zip, Rar, Folder, Unknown = range(4)
    
	def __init__( self, path ):
		self.path = path
		self.ci_xml_filename = 'ComicInfo.xml'
		self.comet_default_filename = 'CoMet.xml'
		self.resetCache()
		
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

	# Clears the cached data
	def resetCache( self ):
		self.has_cix = None
		self.has_cbi = None
		self.comet_filename = None
		self.page_count  = None
		self.page_list  = None
		
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
		elif style == MetaDataStyle.COMET:
			return self.readCoMet()
		else:
			return GenericMetadata()

	def writeMetadata( self, metadata, style ):
		
		retcode = None
		if style == MetaDataStyle.CIX:
			retcode = self.writeCIX( metadata )
		elif style == MetaDataStyle.CBI:
			retcode = self.writeCBI( metadata )
		elif style == MetaDataStyle.COMET:
			retcode = self.writeCoMet( metadata )
		self.resetCache()
		return retcode
		

	def hasMetadata( self, style ):
		
		if style == MetaDataStyle.CIX:
			return self.hasCIX()
		elif style == MetaDataStyle.CBI:
			return self.hasCBI()
		elif style == MetaDataStyle.COMET:
			return self.hasCoMet()
		else:
			return False
	
	def removeMetadata( self, style ):
		if style == MetaDataStyle.CIX:
			return self.removeCIX()
		elif style == MetaDataStyle.CBI:
			return self.removeCBI()
		elif style == MetaDataStyle.COMET:
			return self.removeCoMet()
	
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
		
		if self.page_list is None:
			# get the list file names in the archive, and sort
			files = self.archiver.getArchiveFilenameList()
			
			# seems like some archive creators are on  Windows, and don't know about case-sensitivity!
			if sort_list:
				files.sort(key=lambda x: x.lower())
			
			# make a sub-list of image files
			self.page_list = []
			for name in files:
				if ( name[-4:].lower() in [ ".jpg", "jpeg", ".png" ] and os.path.basename(name)[0] != "." ):
					self.page_list.append(name)
				
		return self.page_list

	def getNumberOfPages( self ):
		
		if self.page_count is None:
			self.page_count = len( self.getPageNameList( ) )
		return self.page_count

	def readCBI( self ):
		raw_cbi = self.readRawCBI()
		if raw_cbi is None:
			md = GenericMetadata()
		else:
			md = ComicBookInfo().metadataFromString( raw_cbi )
		
		md.setDefaultPageList( self.getNumberOfPages() )
				
		return md
	
	def readRawCBI( self ):
		if ( not self.hasCBI() ):
			return None

		return self.archiver.getArchiveComment()

	def hasCBI(self):
		if self.has_cbi is None:

			#if ( not ( self.isZip() or self.isRar()) or not self.seemsToBeAComicArchive() ): 
			if not self.seemsToBeAComicArchive(): 
				self.has_cbi = False
			else:
				comment = self.archiver.getArchiveComment()
				self.has_cbi = ComicBookInfo().validateString( comment )
			
		return self.has_cbi
	
	def writeCBI( self, metadata ):
		self.applyArchiveInfoToMetadata( metadata )
		cbi_string = ComicBookInfo().stringFromMetadata( metadata )
		return self.archiver.setArchiveComment( cbi_string )
		
	def removeCBI( self ):
		return self.archiver.setArchiveComment( "" )
		
	def readCIX( self ):
		raw_cix = self.readRawCIX()
		if raw_cix is None:
			md = GenericMetadata()
		else:
			md = ComicInfoXml().metadataFromString( raw_cix )

		#validate the existing page list (make sure count is correct)
		if len ( md.pages ) !=  0 :
			if len ( md.pages ) != self.getNumberOfPages():
				# pages array doesn't match the actual number of images we're seeing
				# in the archive, so discard the data
				md.pages = []
			
		if len( md.pages ) == 0:
			md.setDefaultPageList( self.getNumberOfPages() )
		return md		

	def readRawCIX( self ):
		if not self.hasCIX():
			return None

		return  self.archiver.readArchiveFile( self.ci_xml_filename )
		
	def writeCIX(self, metadata):

		if metadata is not None:
			self.applyArchiveInfoToMetadata( metadata, calc_page_sizes=True )
			cix_string = ComicInfoXml().stringFromMetadata( metadata )
			return self.archiver.writeArchiveFile( self.ci_xml_filename, cix_string )
		else:
			return False
			
	def removeCIX( self ):

		return self.archiver.removeArchiveFile( self.ci_xml_filename )
		
	def hasCIX(self):
		if self.has_cix is None:

			if not self.seemsToBeAComicArchive():
				self.has_cix = False
			elif self.ci_xml_filename in self.archiver.getArchiveFilenameList():
				self.has_cix = True
			else:
				self.has_cix = False
		return self.has_cix


	def readCoMet( self ):
		raw_comet = self.readRawCoMet()
		if raw_comet is None:
			md = GenericMetadata()
		else:
			md = CoMet().metadataFromString( raw_comet )
		
		md.setDefaultPageList( self.getNumberOfPages() )
		#use the coverImage value from the comet_data to mark the cover in this struct
		# walk through list of images in file, and find the matching one for md.coverImage
		# need to remove the existing one in the default
		if md.coverImage is not None:
			cover_idx = 0
			for idx,f in enumerate(self.getPageNameList()):
				if md.coverImage == f:
					cover_idx = idx
					break
			if cover_idx != 0:
				del (md.pages[0]['Type'] )
				md.pages[ cover_idx ]['Type'] = PageType.FrontCover
					
				
		return md	

	def readRawCoMet( self ):
		if not self.hasCoMet():
			print self.path, "doesn't have CoMet data!"
			return None

		return self.archiver.readArchiveFile( self.comet_filename )
		
	def writeCoMet(self, metadata):

		if metadata is not None:
			if not self.hasCoMet():
				self.comet_filename = self.comet_default_filename
			
			self.applyArchiveInfoToMetadata( metadata )
			# Set the coverImage value, if it's not the first page
			cover_idx = int(metadata.getCoverPageIndexList()[0])
			if cover_idx != 0:
				metadata.coverImage = self.getPageName( cover_idx )
		
			comet_string = CoMet().stringFromMetadata( metadata )
			return self.archiver.writeArchiveFile( self.comet_filename, comet_string )
		else:
			return False
			
	def removeCoMet( self ):
		if self.hasCoMet():
			retcode = self.archiver.removeArchiveFile( self.comet_filename )
			self.comet_filename = None
			return retcode
		return True
		
	def hasCoMet(self):
		if not self.seemsToBeAComicArchive():
			return False
		
		#Use the existence of self.comet_filename as a cue that the tag block exists
		if self.comet_filename is None:
			#TODO look at all xml files in root, and search for CoMet data, get first
			for n in self.archiver.getArchiveFilenameList():
				if ( os.path.dirname(n) == "" and
					os.path.splitext(n)[1].lower() == '.xml'):
					# read in XML file, and validate it
					data = self.archiver.readArchiveFile( n )
					if CoMet().validateString( data ):
						# since we found it, save it!
						self.comet_filename = n
						return True
			# if we made it through the loop, no CoMet here...
			return False
			
		else:
			return True

	def applyArchiveInfoToMetadata( self, md, calc_page_sizes=False):
		md.pageCount = self.getNumberOfPages()
		
		if calc_page_sizes:
			for p in md.pages:
				idx = int( p['Image'] )
				if pil_available:
					if 'ImageSize' not in p or 'ImageHeight' not in p or 'ImageWidth' not in p:
						data = self.getPage( idx )
						
						im = Image.open(StringIO.StringIO(data))
						w,h = im.size
						
						p['ImageSize'] = str(len(data))
						p['ImageHeight'] = str(h)
						p['ImageWidth'] = str(w)
				else:
					if 'ImageSize' not in p:
						data = self.getPage( idx )
						p['ImageSize'] = str(len(data))


			
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

	def exportAsZip( self, zipfilename ):
		if self.archive_type == self.ArchiveType.Zip:
			# nothing to do, we're already a zip
			return True
		
		zip_archiver = ZipArchiver( zipfilename )
		return zip_archiver.copyFromArchive( self.archiver )
		
