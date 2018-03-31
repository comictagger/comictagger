#!/bin/sh

# This is a lot of hoop-jumping to get the absolute path
# of this script, so that we can use the Symlinked python
# binary to call the CT script.  This is all so that the
# Mac menu doesn't say "Python".

realpath() 
{
    [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}

CTSCRIPT=%%CTSCRIPT%%

THIS=$(realpath $0)
THIS_FOLDER=$(dirname $THIS)
"$THIS_FOLDER/ComicTagger" "$CTSCRIPT"
