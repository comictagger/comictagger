TAGGER_BASE := $(HOME)/Dropbox/tagger/comictagger
TAGGER_SRC := $(TAGGER_BASE)/src
VERSION_STR := $(shell grep version $(TAGGER_SRC)/ctversion.py| cut -d= -f2 | sed 's/\"//g')
PASSWORD    := $(shell cat $(TAGGER_BASE)/project_password.txt)  
UPLOAD_TOOL := $(TAGGER_BASE)/google/googlecode_upload.py
all: clean

clean:
	rm -f *~ *.pyc *.pyo
	cd comictagger; rm -f *~ *.pyc *.pyo
	sudo rm -rf MANIFEST dist scripts
	rm -f logdict*.log
	make -C mac clean
	make -C windows clean

zip:
	cd release; \
		rm -rf *zip comictagger-src-$(VERSION_STR) ;  \
		svn export https://comictagger.googlecode.com/svn/trunk/ comictagger-src-$(VERSION_STR); \
		zip -r comictagger-src-$(VERSION_STR).zip comictagger-src-$(VERSION_STR); \
		rm -rf comictagger-src-$(VERSION_STR)
	
	@echo When satisfied with release, do this:
	@echo make svn_tag

pkg:
	python setup.py sdist	

svn_tag:
	svn copy https://comictagger.googlecode.com/svn/trunk \
      https://comictagger.googlecode.com/svn/tags/$(VERSION_STR) -m "Release $(VERSION_STR)"

upload:
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR) Source" -l Featured,Type-Source -u beville -w $(PASSWORD) "release/comictagger-src-$(VERSION_STR).zip"
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR)  Mac OS X" -l Featured,Type-Archive -u beville -w $(PASSWORD) "release/ComicTagger-$(VERSION_STR).dmg"
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR)  Windows" -l Featured,Type-Installer -u beville -w $(PASSWORD) "release/ComicTagger v$(VERSION_STR).exe"
