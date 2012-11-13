TAGGER_BASE:= c:\Users\tony\Dropbox\tagger\comictagger
DIST_DIR := $(TAGGER_BASE)\windows\dist
NSIS_CMD :=	"C:\Program Files (x86)\NSIS\makensis.exe"

all: clean

win_dist:
	cd "$(TAGGER_BASE)" &
		"C:\Python27\Scripts\cxfreeze.bat" $(TAGGER_BASE)\tagger.py --icon nsis\app.ico --base-name=Win32GUI 
	cp -R C:\Python27\Lib\site-packages\PyQt4\plugins\imageformats $(DIST_DIR)
	cp  "$(TAGGER_BASE)\UnRAR2\UnRARDLL\unrar.dll" $(DIST_DIR)
	cp  "$(TAGGER_BASE)\*.ui" $(DIST_DIR)
	cp  "$(TAGGER_BASE)\nocover.png" $(DIST_DIR)
	cp  "$(TAGGER_BASE)\app.png" $(DIST_DIR)
	
	rm "$(DIST_DIR)\QtWebKit4.dll"
	rm "$(DIST_DIR)\PyQt4.QtWebKit.pyd"
	
	$(NSIS_CMD) "$(TAGGER_BASE)\windows\nsis\comictagger.nsi"
	mv  "$(TAGGER_BASE)\windows\nsis\ComicTagger*.exe" "$(TAGGER_BASE)\windows"

clean:
	rm -rf dist
	-rm -f "*~" *.pyc *.pyo
	-rm "$(TAGGER_BASE)\windows\*.exe"
