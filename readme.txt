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

