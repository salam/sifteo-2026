import sys, os, logging, unittest

# to get *
directory = os.path.dirname(os.path.abspath( __file__ ))
libpath = os.path.join(directory, "..", "..")
sys.path.append(libpath)

# to get helpers.*
directory = os.path.dirname(os.path.abspath( __file__ ))
libpath = os.path.join(directory, "..", "..", "helpers")
sys.path.append(libpath)

# to get sift.*
directory = os.path.dirname(os.path.abspath( __file__ ))
libpath = os.path.join(directory, "..", "..", "..", "..", "..")
sys.path.append(libpath)
	
def teardown_package():
	import fixtures
	fixtures.dongle.close()
