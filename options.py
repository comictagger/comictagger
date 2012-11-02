import sys
import getopt


class Enum(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError

class MetaDataStyle:
	CBI = 0
	CIX = 1


class Options:

	def __init__(self):
		self.data_style = MetaDataStyle.CBI
		self.no_gui = False
		
		# Some defaults for testing
		self.series_name = '' #'Watchmen'
		self.issue_number = '' #'1'
		self.filename = ''     # "Watchmen #01.cbz"

	def parseCmdLineArgs(self):	

		# parse command line options
		try:
			opts, args = getopt.getopt(sys.argv[1:], "cht:s:i:vf:", ["cli", "help", "type=", "series=", "issue=", "verbose", "file" ])
		except (getopt.error, msg):
			print( msg )
			print( "for help use --help" )
			sys.exit(2)
		# process options
		for o, a in opts:
			if o in ("-h", "--help"):
				print( __doc__ )
				sys.exit(0)
			if o in ("-v", "--verbose"):
				print( "Verbose output!" )
			if o in ("-c", "--cli"):
				self.no_gui = True
			if o in ("-s", "--series"):
				self.series_name = a
			if o in ("-i", "--issue"):
				self.issue_number = a
			if o in ("-f", "--file"):
				self.filename = a
			if o in ("-t", "--type"):
				if a == "cr":
					self.data_style = MetaDataStyle.CIX
				elif a == "cbl":
					self.data_style = MetaDataStyle.CBI
				else:
					print( __doc__ )
					sys.exit(0)
				
		# process arguments
		for arg in args:
			process(arg) # process() is defined elsewhere

		return opts
		