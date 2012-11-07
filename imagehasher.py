
import Image
#import numpy
#import math
#import operator
import StringIO

#from bitarray import bitarray

class ImageHasher(object):
	def __init__(self, path=None, data=None, size=8):
		self.hash_size = size

		if path is None and data is None:
			raise IOError
		elif path is not None:
			self.image = Image.open(path)
		else:
			self.image = Image.open(StringIO.StringIO(data))
			
	def average_hash(self):
		image = self.image.resize((self.hash_size, self.hash_size), Image.ANTIALIAS).convert("L")
		pixels = list(image.getdata())
		avg = sum(pixels) / len(pixels)

		diff = []
		for pixel in pixels:
			value = 1 if pixel > avg else 0
			diff.append(str(value))

		#ba = bitarray("".join(diff), endian='little')
		#h = ba.tobytes().encode('hex')
		
		# This isn't super pretty, but we avoid the bitarray inclusion.
		# (Build up a hex string from the binary list of bits)
		hash = ""
		binary_string = "".join(diff)
		for i in range(0,self.hash_size**2,8):
			# 8 bits at time, reverse, for little-endian
			s = binary_string[i:i+8][::-1]
			hash = hash + "{0:02x}".format( int(s,2))
			
		return hash

	@staticmethod
	def count_bits(number):
		bit = 1
		count = 0
		while number >= bit:
			if number & bit:
				count += 1
			bit <<= 1
		return count   
	
	#accepts 2 hash strings, and returns the hamming distance
	
	@staticmethod
	def hamming_distance(h1, h2):

		# conver hex strings to ints
		n1 = long( h1, 16)
		n2 = long( h2, 16)
		# xor the two numbers
		n = n1 ^ n2
		
		# now count the ones
		return ImageHasher.count_bits( n )





