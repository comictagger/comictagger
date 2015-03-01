This folder contains a set of example scripts that be used to extend the
capabilities of the ComicTagger app.  They can be run either directly through
the python interpreter, or via the ComicTagger app.

To run via python directly, install ComicTagger source on your system using
the setup.py file.

To run via the ComicTagger app, invoke:

$ comictagger.py -S script.py [script args]

(This will work also for binary distributions on Mac and Windows.  No need for
an extra python install.)

The script must have an entry point function called "main()" to be invoked
via the app.

-----------------------------------------------------------------------------

This feature is UNSUPPORTED, and is for the convenience of development-minded
users of ComicTagger.  The comictaggerlib module will remain largely
undocumented, and it will be up to the crafty script developer to look through
the code to discern APIs and such.

That said, if there are questions, please post in the forums, and hopefully we
can get your add-on scripts working!

http://comictagger.forumotion.com/
