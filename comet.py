"""
A python class to encapsulate CoMets's data and file handling
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

from datetime import datetime
import zipfile
from pprint import pprint 
import xml.etree.ElementTree as ET
from genericmetadata import GenericMetadata
import utils

class CoMet:
	
	writer_synonyms = ['writer', 'plotter', 'scripter']
	penciller_synonyms = [ 'artist', 'penciller', 'penciler', 'breakdowns' ]
	inker_synonyms = [ 'inker', 'artist', 'finishes' ]
	colorist_synonyms = [ 'colorist', 'colourist', 'colorer', 'colourer' ]
	letterer_synonyms = [ 'letterer']
	cover_synonyms = [ 'cover', 'covers', 'coverartist', 'cover artist' ]
	editor_synonyms = [ 'editor']
		
	def metadataFromString( self, string ):

		tree = ET.ElementTree(ET.fromstring( string ))
		return self.convertXMLToMetadata( tree )

	def stringFromMetadata( self, metadata ):

		header = '<?xml version="1.0" encoding="UTF-8"?>\n'
		
		tree = self.convertMetadataToXML( self, metadata )
		return header + ET.tostring(tree.getroot())

	def indent( self, elem, level=0 ):
		# for making the XML output readable
		i = "\n" + level*"  "
		if len(elem):
			if not elem.text or not elem.text.strip():
				elem.text = i + "  "
			if not elem.tail or not elem.tail.strip():
				elem.tail = i
			for elem in elem:
				self.indent( elem, level+1 )
			if not elem.tail or not elem.tail.strip():
				elem.tail = i
		else:
			if level and (not elem.tail or not elem.tail.strip()):
				elem.tail = i
	
	def convertMetadataToXML( self, filename, metadata ):

		#shorthand for the metadata
		md = metadata

		# build a tree structure
		root = ET.Element("comet")
		root.attrib['xmlns:comet'] = "http://www.denvog.com/comet/"
		root.attrib['xmlns:xsi'] = "http://www.w3.org/2001/XMLSchema-instance"
		root.attrib['xsi:schemaLocation'] = "http://www.denvog.com http://www.denvog.com/comet/comet.xsd"
		
		#helper func
		def assign( comet_entry, md_entry):
			if md_entry is not None:
				ET.SubElement(root, comet_entry).text = u"{0}".format(md_entry)
		
		# title is manditory
		if md.title is None:
			md.title = ""
		assign( 'title', md.title )
		assign( 'series', md.series )
		assign( 'issue', md.issue )  #must be int...
		assign( 'volume', md.volume )
		assign( 'description', md.comments )
		#assign( 'date', md.year )  #need to make a date from month, year
		assign( 'publisher', md.publisher )
		assign( 'genre', md.genre )
		assign( 'pages', md.pageCount )
		assign( 'format', md.format )
		assign( 'language', md.language )
		#assign( 'readingDirection', md.??? )

		assign( 'character', md.characters )
		assign( 'rating', md.maturityRating )
		#assign( 'price', md.??? )
		#assign( 'isVersionOf', md.??? )
		#assign( 'rights', md.??? )
		#assign( 'identifier', md.??? )
		#assign( 'coverImage', md.??? )
		#assign( 'lastMark', md.??? )

		# need to specially process the credits, since they are structured differently than CIX	
		credit_writer_list    = list()
		credit_penciller_list = list()
		credit_inker_list     = list()
		credit_colorist_list  = list()
		credit_letterer_list  = list()
		credit_cover_list     = list()
		credit_editor_list    = list()
		
		#  loop thru credits, and build a list for each role that CoMet supports
		for credit in metadata.credits:

			if credit['role'].lower() in set( self.writer_synonyms ):
				ET.SubElement(root, 'writer').text = u"{0}".format(credit['person'])

			if credit['role'].lower() in set( self.penciller_synonyms ):
				ET.SubElement(root, 'penciller').text = u"{0}".format(credit['person'])
				
			if credit['role'].lower() in set( self.inker_synonyms ):
				ET.SubElement(root, 'inker').text = u"{0}".format(credit['person'])
				
			if credit['role'].lower() in set( self.colorist_synonyms ):
				ET.SubElement(root, 'inker').text = u"{0}".format(credit['person'])
				credit_colorist_list.append(credit['person'].replace(",",""))

			if credit['role'].lower() in set( self.letterer_synonyms ):
				ET.SubElement(root, 'letterer').text = u"{0}".format(credit['person'])

			if credit['role'].lower() in set( self.cover_synonyms ):
				ET.SubElement(root, 'coverDesigner').text = u"{0}".format(credit['person'])

			if credit['role'].lower() in set( self.editor_synonyms ):
				ET.SubElement(root, 'editor').text = u"{0}".format(credit['person'])
		

		# self pretty-print
		self.indent(root)

		# wrap it in an ElementTree instance, and save as XML
		tree = ET.ElementTree(root)
		return tree
				 

	def convertXMLToMetadata( self, tree ):
			
		root = tree.getroot()

		if root.tag != 'comet':
			raise 1
			return None

		metadata = GenericMetadata()
		md = metadata
	
		# Helper function
		def xlate( tag ):
			node = root.find( tag )
			if node is not None:
				return node.text
			else:
				return None
				
		md.series =           xlate( 'series' )
		md.title =            xlate( 'title' )
		md.issue =            xlate( 'issue' )
		md.volume =           xlate( 'volume' )
		md.comments =         xlate( 'description' )
		#md.year =             xlate( 'Year' )
		#md.month =            xlate( 'Month' )
		md.publisher =        xlate( 'publisher' )
		md.genre =            xlate( 'genre' )
		md.language =         xlate( 'language' )
		md.format =           xlate( 'format' )
		#md.manga =            xlate( 'readingDirection' )
		#md.characters =       xlate( 'character' )
		md.pageCount =        xlate( 'pages' )
		md.maturityRating =   xlate( 'rating' )

		# Now extract the credit info
		for n in root:
			if (  n.tag == 'writer' or 
				n.tag == 'penciller' or
				n.tag == 'inker' or
				n.tag == 'colorist' or
				n.tag == 'letterer' or
				n.tag == 'editor' 
			):
				metadata.addCredit( n.text.strip(), n.tag.title() )

			if n.tag == 'coverDesigner':
				metadata.addCredit( n.text.strip(), "Cover" )


		metadata.isEmpty = False
		
		return metadata

	def writeToExternalFile( self, filename, metadata ):
		
		tree = self.convertMetadataToXML( self, metadata )
		#ET.dump(tree)		
		tree.write(filename, encoding='utf-8')
	
	def readFromExternalFile( self, filename ):

		tree = ET.parse( filename )
		return self.convertXMLToMetadata( tree )

