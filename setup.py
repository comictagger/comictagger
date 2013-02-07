#!/usr/bin/env python

from distutils.core import setup
import distutils.command.install_scripts
import os
import shutil

# Things are weird if the script has a py.  Will this break things for windows???
if not os.path.exists('scripts/comictagger'):
    if not os.path.exists('scripts'):
        os.makedirs('scripts')
    shutil.copyfile('comictagger.py', 'scripts/comictagger')


setup(name = "comictagger",
      version = "1.1.1",
      description = "A cross-platorm GUI/CLI app for writing metadata to comic archives",
      author = "Anthony Beville",
      author_email = "comictagger@gmail.com",
      url = "http://code.google.com/p/comictagger/",
      packages =  [ "comictagger", "comictagger/UnRAR2" ] ,
      package_data = {
        'comictagger': ['ui/*.ui', 'graphics/*'] ,
      },
      scripts = ["scripts/comictagger"],
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
"""          
      )    
