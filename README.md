
ComicTagger is a multi-platform app for writing metadata to digital comics, written in Python and PyQt.

Features:

* Runs on Mac OSX, Microsoft Windows, and Linux systems
* Communicates with an online database (Comic Vine) for acquiring metadata
* Uses image processing to automatically match a given archive with the correct issue data
* Batch processing in the GUI for tagging hundreds or more comics at a time
* Reads and writes multiple tagging schemes (ComicBookLover and ComicRack).
* Reads and writes RAR and Zip archives (external tools needed for writing RAR)
* Can run without PyQt5 installed 


Recent changes:
 - Ported to Python 3
 - Ported to PyQt5
 - Added more application and GUI awareness of the unrar library, and removed references to the old scheme that used the unrar executable.  
 - Got setup.py working again to build sdist packages, suitable (I think) for PyPI. An install from the package will attempt to build unrar library.  It should work on most Linux distros, and was tested on a Mac OSX system with dev tools from homebrew.  If the library doesn't build, the GUI has instructions on where to download the library.
 - Removed/changes obsolete links to old Google code website.
 - Set a environment variable to scale the GUI on 4k displays
 
Notes:
- I did some testing with the pyinstaller build, and it worked on both platforms.  I did encounter two problems:
  - Mac build showed the wrong widget set. I found a solution here that seemed to work: https://stackoverflow.com/questions/48626999/packaging-with-pyinstaller-pyqt5-setstyle-ignored
  - Windows build had problems grabbing images from ComicVine using SSL.  It think that some libraries are missing from the monolithic exe, but I couldn't figure out how to fix the problem. 
- In setup.py you can also find the remains of an attempt to do some desktop integration from a pip install.  It does work, but can cause problems with wheel installs, and I don't know if it's worth the bother.  I kept the commented-out code in place, just in case.

With Python 3, it's much easier to get the app working from scratch on a new distro, as all of the dependencies are available as wheels, including PyQt5, so just a simple "pip install comictagger.zip" is all that's needed.
