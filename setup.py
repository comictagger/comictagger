#!/usr/bin/env python

from setuptools import setup
import comictaggerlib.ctversion

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(name="comictagger",
      install_requires=required,
      version=comictaggerlib.ctversion.version,
      description="A cross-platform GUI/CLI app for writing metadata to comic archives",
      author="Anthony Beville",
      author_email="comictagger@gmail.com",
      url="http://code.google.com/p/comictagger/",
      download_url="https://pypi.python.org/packages/source/c/comictagger/comictagger-{0}.zip".format(comictaggerlib.ctversion.version),
      packages=["comictaggerlib", "comicapi", "comicapi/UnRAR2"],
      package_data={
          'comictaggerlib': ['ui/*.ui', 'graphics/*'],
          'comicapi/UnRAR2': ['UnRARDLL/*.*', 'UnRARDLL/x64/*.*'],
      },
      scripts=["comictagger.py"],
      classifiers=[
          "Development Status :: 4 - Beta",
          "Environment :: Console",
          "Environment :: Win32 (MS Windows)",
          "Environment :: MacOS X",
          "Environment :: X11 Applications :: Qt",
          "Intended Audience :: End Users/Desktop",
          "License :: OSI Approved :: Apache Software License",
          "Natural Language :: English",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2.6",
          "Programming Language :: Python :: 2.7",
          "Topic :: Utilities",
          "Topic :: Other/Nonlisted Topic",
          "Topic :: Multimedia :: Graphics"
      ],
      license="Apache License 2.0",

      long_description="""
ComicTagger is a multi-platform app for writing metadata to digital comics, written in Python and PyQt.

Features:

* Runs on Mac OSX, Microsoft Windows, and Linux systems
* Communicates with an online database (Comic Vine) for acquiring metadata
* Uses image processing to automatically match a given archive with the correct issue data
* Batch processing in the GUI for tagging hundreds or more comics at a time
* Reads and writes multiple tagging schemes ( ComicBookLover and ComicRack, with more planned).
* Reads and writes RAR and Zip archives (external tools needed for writing RAR)
* Command line interface (CLI) on all platforms (including Windows), which supports batch operations, and which can be used in native scripts for complex operations.

Requires:

* python 2.6 or 2.7
* configparser
* python imaging (PIL) >= 1.1.6
* beautifulsoup > 4.1

Optional requirement (for GUI):

* pyqt4
"""
      )
