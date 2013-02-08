ComicTagger is a multi-platform app for writing metadata to comic archives, written in Python and PyQt.

Features:

* Runs on Mac OSX, Microsoft Windows, and Linux systems
* Communicates with an online database (Comic Vine) for acquiring metadata
* Uses image processing to automatically match a given archive with the correct issue data
* Batch processing in the GUI for tagging hundreds or more comics at a time
* Reads and writes multiple tagging schemes ( ComicBookLover and ComicRack, with more planned).
* Reads and writes RAR, Zip, and folder archives (external tools needed for writing RAR)
* Command line interface (CLI) on all platforms (including Windows), which supports batch operations, and which can be used in native scripts for complex operations. For example, to scrape and tag a folder, just one line
	ComicTagger -s -o -f -t cr -v -i --nooverwrite *.cb?

For details, screenshots, release notes, and more, visit http://code.google.com/p/comictagger/

Requires:

* python 2.6 or 2.7
* python imaging (PIL) >= 1.1.6
* beautifulsoup > 4.1
    
Optional requirement (for GUI):

* pyqt4

Install and run:

* ComicTagger can be run directly from this directory, using the launcher script "comictagger.py"

* To install on your system use:  "python setup.py install".  Make note in the output where comictagger.py goes!
