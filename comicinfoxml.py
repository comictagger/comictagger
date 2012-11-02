"""
A python class to encapsulate ComicRack's ComicInfo.xml data and file handling
"""

from datetime import datetime
import zipfile
from pprint import pprint 
import xml.etree.ElementTree as ET
from genericmetadata import GenericMetadata


class ComicInfoXml:

	def metadataFromString( self, string ):

		tree = ET.ElementTree(ET.fromstring( string ))
		return self.convertXMLToMetadata( tree )

	def stringFromMetadata( self, metadata ):

		tree = self.convertMetadataToXML( self, metadata )
		return ET.tostring(tree.getroot())

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
		root = ET.Element("ComicInfo")


		#helper func
		def assign( cix_entry, md_entry):
			if md_entry is not None:
				ET.SubElement(root, cix_entry).text = u"{0}".format(md_entry)

		assign( 'Series', md.series )
		assign( 'Number', md.issueNumber )
		assign( 'Title', md.title )
		assign( 'Count', md.issueCount )
		assign( 'Volume', md.volumeNumber )
		assign( 'AlternateSeries', md.alternateSeries )
		assign( 'AlternateNumber', md.alternateNumber )
		assign( 'AlternateCount', md.alternateCount )
		assign( 'Summary', md.comments )
		assign( 'Notes', md.notes )
		assign( 'Year', md.publicationYear )
		assign( 'Month', md.publicationMonth )
		assign( 'Publisher', md.publisher )
		assign( 'Imprint', md.imprint )
		assign( 'Genre', md.genre )
		assign( 'Web', md.webLink )
		assign( 'PageCount', md.pageCount )
		assign( 'Format', md.format )
		assign( 'LanguageISO', md.language )
		assign( 'Manga', md.manga )
		assign( 'Characters', md.characters )
		assign( 'Teams', md.teams )
		assign( 'Locations', md.locations )
		assign( 'ScanInformation', md.scanInfo )
		assign( 'StoryArc', md.storyArc )
		assign( 'SeriesGroup', md.seriesGroup )
		assign( 'AgeRating', md.maturityRating )

		if md.blackAndWhite is not None and md.blackAndWhite:
			ET.SubElement(root, 'BlackAndWhite').text = "Yes"

		# need to specially process the credits, since they are structured differently than CIX	
		credit_writer    = None
		credit_penciller = None
		credit_inker     = None
		credit_colorist  = None
		credit_letterer  = None
		credit_cover     = None
		credit_editor    = None
				
		for credit in metadata.credits:
			if credit['role'].title() in set( ['Writer', 'Plotter'] ):
				if credit_writer == None:
					credit_writer  = ET.SubElement(root, 'Writer')
					credit_writer.text  = ""
				if len(credit_writer.text) > 0:
					credit_writer.text += ", "
				credit_writer.text += credit['person']
				
			if credit['role'].title() in set( [ 'Inker', 'Artist', 'Finishes' ] ):
				if credit_inker == None:
					credit_inker  = ET.SubElement(root, 'Inker')
					credit_inker.text  = ""
				if len(credit_inker.text) > 0:
					credit_inker.text += ", "
				credit_inker.text += credit['person']

			if credit['role'].title() in set( [ 'Artist', 'Penciller', 'Penciler', 'Breakdowns' ] ):
				if credit_penciller == None:
					credit_penciller  = ET.SubElement(root, 'Penciller')
					credit_penciller.text  = ""
				if len(credit_penciller.text) > 0:
					credit_penciller.text += ", "
				credit_penciller.text += credit['person']

			if credit['role'].title() in set( [ 'Colorist', 'Colourist' ]):
				if credit_colorist == None:
					credit_colorist  = ET.SubElement(root, 'Colorist')
					credit_colorist.text  = ""
				if len(credit_colorist.text) > 0:
					credit_colorist.text += ", "
				credit_colorist.text += credit['person']

			if credit['role'].title() == 'Letterer':
				if credit_letterer == None:
					credit_letterer  = ET.SubElement(root, 'Letterer')
					credit_letterer.text  = ""
				if len(credit_letterer.text) > 0:
					credit_letterer.text += ", "
				credit_letterer.text += credit['person']

			if credit['role'].title() in set( [ 'Cover', 'Covers', 'CoverArtist', 'Cover Artist' ] ):
				if credit_cover == None:
					credit_cover  = ET.SubElement(root, 'CoverArtist')
					credit_cover.text  = ""
				if len(credit_cover.text) > 0:
					credit_cover.text += ", "
				credit_cover.text += credit['person']

			if credit['role'].title() in set( [ 'Editor'] ):
				if credit_editor == None:
					credit_editor  = ET.SubElement(root, 'Editor')
					credit_editor.text  = ""
				if len(credit_editor.text) > 0:
					credit_editor.text += ", "
				credit_editor.text += credit['person']
				
		# !!!ATB todo: loop and add the page entries under pages node
		#pages = ET.SubElement(root, 'Pages')

		# self pretty-print
		self.indent(root)

		# wrap it in an ElementTree instance, and save as XML
		tree = ET.ElementTree(root)
		return tree
				 

	def convertXMLToMetadata( self, tree ):
			
		root = tree.getroot()

		if root.tag != 'ComicInfo':
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
				
		md.series =           xlate( 'Series' )
		md.title =            xlate( 'Title' )
		md.issueNumber =      xlate( 'Number' )
		md.issueCount =       xlate( 'Count' )
		md.volumeNumber =     xlate( 'Volume' )
		md.alternateSeries =  xlate( 'AlternateSeries' )
		md.alternateNumber =  xlate( 'AlternateNumber' )
		md.alternateCount =   xlate( 'AlternateCount' )
		md.comments =         xlate( 'Summary' )
		md.notes =            xlate( 'Notes' )
		md.publicationYear =  xlate( 'Year' )
		md.publicationMonth = xlate( 'Month' )
		md.publisher =        xlate( 'Publisher' )
		md.imprint =          xlate( 'Imprint' )
		md.genre =            xlate( 'Genre' )
		md.webLink =          xlate( 'Web' )
		md.language =         xlate( 'LanguageISO' )
		md.format =           xlate( 'Format' )
		md.manga =            xlate( 'Manga' )
		md.characters =       xlate( 'Characters' )
		md.teams =            xlate( 'Teams' )
		md.locations =        xlate( 'Locations' )
		md.pageCount =        xlate( 'PageCount' )
		md.scanInfo =         xlate( 'ScanInformation' )
		md.storyArc =         xlate( 'StoryArc' )
		md.seriesGroup =      xlate( 'SeriesGroup' )
		md.maturityRating =   xlate( 'AgeRating' )

		tmp = xlate( 'BlackAndWhite' )
		md.blackAndWhite = False
		if tmp is not None and tmp.lower() in [ "yes", "true", "1" ]:
			md.blackAndWhite = True
		# Now extract the credit info
		for n in root:
			if (  n.tag == 'Writer' or 
				n.tag == 'Penciller' or
				n.tag == 'Inker' or
				n.tag == 'Colorist' or
				n.tag == 'Letterer' or
				n.tag == 'Editor' 
			):
				for name in n.text.split(','):
					metadata.addCredit( name.strip(), n.tag )

			if n.tag == 'CoverArtist':
				for name in n.text.split(','):
					metadata.addCredit( name.strip(), "Cover" )

			#!!! ATB parse page data now	
			


		metadata.isEmpty = False
		
		return metadata

	def writeToExternalFile( self, filename, metadata ):
		
		tree = self.convertMetadataToXML( self, metadata )
		#ET.dump(tree)		
		tree.write(filename, encoding='utf-8')
	
	def readFromExternalFile( self, filename ):

		tree = ET.parse( filename )
		return self.convertXMLToMetadata( tree )

