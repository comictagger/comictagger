# This Makefile expects that certain GNU utils are available:
# rm, cp, grep, cut, cat

HOMEPATH ?= $(HOME)
TAGGER_BASE:= $(HOMEPATH)/Dropbox/tagger/comictagger
TAGGER_SRC := $(TAGGER_BASE)/comictaggerlib
DIST_DIR := $(TAGGER_BASE)\windows\dist
NSIS_CMD :=	"C:\Program Files (x86)\NSIS\makensis.exe"
VERSION := $(shell grep version "$(TAGGER_SRC)/ctversion.py" | cut -d= -f2)

all: clean dist package

dist:
	cd "$(TAGGER_BASE)" &
		"C:\Python27\Scripts\cxfreeze.bat" $(TAGGER_BASE)\comictagger.py --icon nsis\app.ico  
#--base-name=Win32GUI 
	cp -R C:\Python27\Lib\site-packages\PyQt4\plugins\imageformats $(DIST_DIR)
	cp "$(TAGGER_SRC)\UnRAR2\UnRARDLL\unrar.dll" $(DIST_DIR)
	cp -r "$(TAGGER_SRC)\ui" $(DIST_DIR)
	cp -r "$(TAGGER_SRC)\graphics" $(DIST_DIR)
	
	rm "$(DIST_DIR)\QtWebKit4.dll"
	rm "$(DIST_DIR)\PyQt4.QtWebKit.pyd"
	
package:
	echo !define RELEASE_STR $(VERSION) > $(TAGGER_BASE)\windows\nsis\release.nsh
	$(NSIS_CMD) "$(TAGGER_BASE)\windows\nsis\comictagger.nsi"
	mv  "$(TAGGER_BASE)\windows\nsis\ComicTagger*.exe" "$(TAGGER_BASE)\release"

clean:
	-rm -rf dist
	-rm -rf nsis/release.nsh
