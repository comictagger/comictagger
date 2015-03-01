This is a fork derived from google code:

  https://code.google.com/p/comictagger/


Changes in this fork:
 - using different unrar library https://pypi.python.org/pypi/unrar/. The previous one used unrar.dll on windows and
   hackish wrapping of unrar command on linux, while this new one should use unrarlib on both platforms. From my tests
   it is more stable and faster. *Requires unrarlib availability, check unrar module documentation for more
   information*.
 - extracted core libraries in its own package comicapi, shared in a new repository using git subtree for better
   alignment with comicstreamer
 - support for *day of month* field in the GUI
 - merge of changes from fcanc fork

Todo:
 - more tests in non-linux platforms
 - repackage for simple user installation

Follows original readme:

ComicTagger is a multi-platform app for writing metadata to digital comics, written in Python and PyQt.

Features:

* Runs on Mac OSX, Microsoft Windows, and Linux systems
* Communicates with an online database (Comic Vine) for acquiring metadata
* Uses image processing to automatically match a given archive with the correct issue data
* Batch processing in the GUI for tagging hundreds or more comics at a time
* Reads and writes multiple tagging schemes ( ComicBookLover and ComicRack, with more planned).
* Reads and writes RAR and Zip archives (external tools needed for writing RAR)
* Command line interface (CLI) on all platforms (including Windows), which supports batch operations, and which can be
  used in native scripts for complex operations. For example, to recursively scrape and tag all archives in a folder
	comictagger.py -R -s -o -f -t cr -v -i --nooverwrite /path/to/comics/

For details, screen-shots, release notes, and more, visit http://code.google.com/p/comictagger/

Requires:

* python 2.6 or 2.7
* configparser
* python imaging (PIL) >= 1.1.6
* beautifulsoup > 4.1
    
Optional requirement (for GUI):

* pyqt4

Install and run:

* ComicTagger can be run directly from this directory, using the launcher script "comictagger.py"

* To install on your system use:  "python setup.py install".  Take note in the output where comictagger.py goes!
