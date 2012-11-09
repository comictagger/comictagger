
import Image
import StringIO




class ImageHasher(object):
	def __init__(self, path=None, data=None, width=8, height=8):
		#self.hash_size = size
		self.width = width
		self.height = height

		if path is None and data is None:
			raise IOError
		elif path is not None:
			self.image = Image.open(path)
		else:
			self.image = Image.open(StringIO.StringIO(data))
			

	def average_hash(self):
		image = self.image.resize((self.width, self.height), Image.ANTIALIAS).convert("L")
		pixels = list(image.getdata())
		avg = sum(pixels) / len(pixels)
		
		def compare_value_to_avg(i):
			return ( 1 if i > avg else 0 )
				
		bitlist = map(compare_value_to_avg, pixels)
		
		# build up an int value from the bit list, one bit at a time
		def set_bit( x, (idx, val) ):
			return (x | (val << idx))
			
		result = reduce(set_bit, enumerate(bitlist), 0)
		
		#print "{0:016x}".format(result)
		return result

	def average_hash2( self ):
		# Got this one from somewhere on the net.  Not a clue how the 'convolve2d'
		# works! 

		from numpy import array 
		from scipy.signal import convolve2d
				
		im = self.image.resize((self.width, self.height), Image.ANTIALIAS).convert('L')

		in_data = array((im.getdata())).reshape(self.width, self.height)
		filt = array([[0,1,0],[1,-4,1],[0,1,0]])
		filt_data = convolve2d(in_data,filt,mode='same',boundary='symm').flatten()
		
		result = reduce(lambda x, (y, z): x | (z << y),
		                 enumerate(map(lambda i: 0 if i < 0 else 1, filt_data)),
		                 0)
		#print "{0:016x}".format(result)
		return result

	def dct_average_hash(self):
		"""
		# Algorithm source: http://syntaxcandy.blogspot.com/2012/08/perceptual-hash.html
		
		1. Reduce size. Like Average Hash, pHash starts with a small image. 
		However, the image is larger than 8x8; 32x32 is a 	good size. This 
		is really done to simplify the DCT computation and not because it 
		is needed to reduce the high frequencies.

		2. Reduce color. The image is reduced to a grayscale just to further 
		simplify the number of computations.
		
		3. Compute the DCT. The DCT separates the image into a collection of
		frequencies and scalars. While JPEG uses 	an 8x8 DCT, this algorithm 
		uses a 32x32 DCT.
		
		4. Reduce the DCT. This is the magic step. While the DCT is 32x32, 
		just keep the top-left 8x8. Those represent the lowest frequencies in 
		the picture.
		
		5. Compute the average value. Like the Average Hash, compute the mean DCT 
		value (using only the 8x8 DCT low-frequency values and excluding the first 
		term since the DC coefficient can be significantly different 	from the other 
		values and will throw off the average). Thanks to David Starkweather for the 
		added information about pHash. He wrote: "the dct hash is based on the low 2D
		DCT coefficients starting at the second from lowest, leaving out the first DC
		term. This excludes completely flat image information (i.e. solid colors) from
		being included in the hash description."
		
		6. Further reduce the DCT. This is the magic step. Set the 64 hash bits to 0 or
		1 depending on whether 	each of the 64 DCT values is above or below the average 
		value. The result doesn't tell us the actual low frequencies; it just tells us
		the very-rough relative scale of the frequencies to the mean. The result will not
		vary as long as the overall structure of the image remains the same; this can 
		survive gamma and color histogram adjustments without a problem.
		
		7. Construct the hash. Set the 64 bits into a 64-bit integer. The order does not 
		matter, just as long as you are consistent. 
		"""
		import numpy
		import scipy.fftpack
		# Step 1,2
		im = self.image.resize((32, 32), Image.ANTIALIAS).convert("L")
		in_data = numpy.array(im.getdata(), dtype=numpy.dtype('float')).reshape(32, 32)
		#print len(im.getdata())
		#print in_data
		
		# Step 3
		dct = scipy.fftpack.dct( in_data )
		
		# Step 4
		# NO! -- lofreq_dct = dct[:8,:8].flatten()
		# NO? -- lofreq_dct = dct[24:32, 24:32].flatten()
		#lofreq_dct = dct[:8, 24:32].flatten()
		#print dct[24:32, :8]
		# NO! -- lofreq_dct = dct[24:32, :8 ].flatten()
		#lofreq_dct = dct[1:9, 1:9].flatten()
		lofreq_dct = dct[:8, 24:32].flatten()
		
		#omit = 0
		#omit = 7
		#omit = 56
		#omit = 63
		
		# Step 5
		#avg = ( lofreq_dct.sum() - lofreq_dct[omit] ) / ( lofreq_dct.size - 1 )
		avg = ( lofreq_dct.sum() ) / ( lofreq_dct.size  )
		#print  lofreq_dct.sum()
		#print lofreq_dct[0]
		#print avg, lofreq_dct.size

		# Step 6
		def compare_value_to_avg(i):
			return ( 1 if i > avg else 0 )
				
		bitlist = map(compare_value_to_avg, lofreq_dct)
		
		#Step 7
		def set_bit( x, (idx, val) ):
			return (x | (val << idx))
			
		result = reduce(set_bit, enumerate(bitlist), long(0))


		#print "{0:016x}".format(result)
		return result


	
	#accepts 2 hashes (longs or hex strings) and returns the hamming distance
	
	@staticmethod
	def hamming_distance(h1, h2):

		if type(h1) == long:
			n1 = h1
			n2 = h2
		else:
			# convert hex strings to ints
			n1 = long( h1, 16)
			n2 = long( h2, 16)
			
		# xor the two numbers
		n = n1 ^ n2

		#count up the 1's in the binary string 
		return sum( b == '1' for b in bin(n)[2:] )






