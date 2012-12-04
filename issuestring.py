"""
Class for handling the odd permutations of an 'issue number' that the comics industry throws at us

e.g.:

"12"
"12.1"
"0"
"-1"
"5AU"

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

import utils
import math
import re

class IssueString:
	def __init__(self, text):
		self.text = text
		
		#strip out non float-y stuff
		tmp_num_str = re.sub('[^0-9.-]',"", text )

		if tmp_num_str == "":
			self.num = None
			self.suffix = text
			
		else:
			if tmp_num_str.count(".") > 1:
				#make sure it's a valid float or int.
				parts = tmp_num_str.split('.')
				self.num = float( parts[0] + '.' + parts[1] )
			else:	
				self.num = float( tmp_num_str )
				
			self.suffix = ""		
			parts = text.split(tmp_num_str)
			if len( parts ) > 1 :
				self.suffix = parts[1]

	def asString( self, pad = 0 ):
		#return the float, left size zero-padded, with suffix attached
		negative = self.num < 0

		num_f = abs(self.num)
			
		num_int = int( num_f )
		num_s = str( num_int ) 
		if float( num_int ) != num_f:
			num_s = str( num_f )
			
		num_s += self.suffix
		
		# create padding
		padding = ""
		l = len( str(num_int))
		if l < pad :
			padding = "0" * (pad - l)
		
		num_s = padding + num_s
		if negative:
			num_s = "-" + num_s

		return num_s
	
	def asFloat( self ):
		#return the float, left size zero-padded, with suffix attached
		return self.num
	
	def asInt( self ):
		#return the int, left size zero-padded, with suffix attached
		return  int( self.num )
	
	
