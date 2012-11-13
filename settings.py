"""
Settings class for comictagger app
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

#import sys
import os
import sys
import ConfigParser
import platform

import utils

class ComicTaggerSettings:

	settings_file = ""
	folder = ""
	
	rar_exe_path = ""
	unrar_exe_path = ""
	cv_api_key = ""
	
	@staticmethod
	def getSettingsFolder():
		if platform.system() == "Windows":
			return os.path.join( os.environ['APPDATA'], 'ComicTagger' )
		else:
			return os.path.join( os.path.expanduser('~') , '.ComicTagger')

	@staticmethod
	def baseDir():
		if getattr(sys, 'frozen', None):
			 return sys._MEIPASS
		else:
			 return os.path.dirname(__file__)

		
	def __init__(self):
		
		self.config = ConfigParser.RawConfigParser()
		self.folder = ComicTaggerSettings.getSettingsFolder()
		
		if not os.path.exists( self.folder ):
			os.makedirs( self.folder )
		
		self.settings_file = os.path.join( self.folder, "settings")
		
		# if config file doesn't exist, write one out
		if not os.path.exists( self.settings_file ):
			self.save()
		else:
			self.load()
		
		# take a crack at finding rar exes, if not set already
		if self.rar_exe_path == "":
			if platform.system() == "Windows":
				# look in some likely places for windows machine
				if os.path.exists( "C:\Program Files\WinRAR\Rar.exe" ):
					self.rar_exe_path = "C:\Program Files\WinRAR\Rar.exe"
				elif os.path.exists( "C:\Program Files (x86)\WinRAR\Rar.exe" ):
					self.rar_exe_path = "C:\Program Files (x86)\WinRAR\Rar.exe"
			else:
				# see if it's in the path of unix user
				if utils.which("rar") is not None:
					self.rar_exe_path = utils.which("rar")
			if self.rar_exe_path != "":
				self.save()
					
		if self.unrar_exe_path == "":
			if platform.system() != "Windows":
				# see if it's in the path of unix user
				if utils.which("unrar") is not None:
					self.unrar_exe_path = utils.which("unrar")
			if self.unrar_exe_path != "":
				self.save()

	def load(self):
		
		#print "reading", self.path
		self.config.read( self.settings_file )
		
		self.rar_exe_path =    self.config.get( 'settings', 'rar_exe_path' )
		self.unrar_exe_path =  self.config.get( 'settings', 'unrar_exe_path' )
		self.cv_api_key =      self.config.get( 'settings', 'cv_api_key' )
    
    
	def save( self ):

		if not self.config.has_section( 'settings' ):
			self.config.add_section( 'settings' )
			
		self.config.set( 'settings', 'cv_api_key',     self.cv_api_key )
		self.config.set( 'settings', 'rar_exe_path',   self.rar_exe_path )
		self.config.set( 'settings', 'unrar_exe_path', self.unrar_exe_path )

		with open( self.settings_file, 'wb') as configfile:
			self.config.write(configfile)    
    
    
    
