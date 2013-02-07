#!/usr/bin/env python

from distutils.core import setup
import comictaggerlib.ctversion

setup(name = "comictagger",
    version =  comictaggerlib.ctversion.version,
    description = "A cross-platorm GUI/CLI app for writing metadata to comic archives",
    author = "Anthony Beville",
    author_email = "comictagger@gmail.com",
    url = "http://code.google.com/p/comictagger/",
    packages =  [ "comictaggerlib", "comictaggerlib/UnRAR2" ] ,
    package_data = {
      'comictaggerlib': ['ui/*.ui', 'graphics/*'] ,
      'comictaggerlib/UnRAR2': ['UnRARDLL/*.*', 'UnRARDLL/x64/*.*'] ,
    },
    scripts = ["comictagger.py"],    
    license = "Apache License 2.0",
    
    long_description = """
ComicTagger is a multi-platform app for writing metadata to comic archives, written in Python and PyQt.

Features:

* Runs on Mac OSX, Microsoft Windows, and Linux systems
* Communicates with an online database (Comic Vine) for acquiring metadata
* Uses image processing to automatically match a given archive with the correct issue data
* Batch processing in the GUI for tagging hundreds or more comics at a time
* Reads and writes multiple tagging schemes ( ComicBookLover? and ComicRack?, with more planned).
* Reads and writes RAR, Zip, and folder archives (external tools needed for writing RAR)
* Command line interface (CLI) on all platforms (including Windows), which supports batch operations, and which can be used in native scripts for complex operations. 

Requires:

* python 2.6 or 2.7
* python imaging (PIL) >= 1.1.7
* beautifulsoup > 4.1
    
Optional requirement (for GUI):

* pyqt4
"""          
      )    
