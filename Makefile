TAGGER_BASE := $(HOME)/Dropbox/tagger/comictagger
TAGGER_SRC := $(TAGGER_BASE)/comictaggerlib
VERSION_STR := $(shell grep version $(TAGGER_SRC)/ctversion.py| cut -d= -f2 | sed 's/\"//g')
PASSWORD    := $(shell cat $(TAGGER_BASE)/project_password.txt)  
UPLOAD_TOOL := $(TAGGER_BASE)/google/googlecode_upload.py
all: clean

clean:
	rm -rf *~ *.pyc *.pyo
	cd comictagger; rm -f *~ *.pyc *.pyo
	sudo rm -rf dist MANIFEST
	rm -rf *.deb
	rm -rf logdict*.log
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

pydist:
	python setup.py sdist --formats=gztar,zip

remove_test_install:
	sudo rm -rf /usr/local/bin/comictagger.py
	sudo rm -rf /usr/local/lib/python2.7/dist-packages/comictagger*
	
deb:
	fpm -s python -t deb \
		-n 'comictagger' \
		--category 'utilities' \
		--maintainer 'comictagger@gmail.com' \
		--after-install debian_scripts/after_install.sh \
		--before-remove debian_scripts/before_remove.sh \
		-d 'python >= 2.6' \
		-d 'python < 2.8' \
		-d 'python-imaging >= 1.1.7' \
		-d 'python-bs4 >= 4.1' \
		setup.py 

		# For now, don't require PyQt, since command-line is available without it
		#-d 'python-qt4 >= 4.8' 

svn_tag:
	svn copy https://comictagger.googlecode.com/svn/trunk \
      https://comictagger.googlecode.com/svn/tags/$(VERSION_STR) -m "Release $(VERSION_STR)"

upload:
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR) Source" -l Featured,Type-Source -u beville -w $(PASSWORD) "release/comictagger-src-$(VERSION_STR).zip"
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR)  Mac OS X" -l Featured,Type-Archive -u beville -w $(PASSWORD) "release/ComicTagger-$(VERSION_STR).dmg"
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR)  Windows" -l Featured,Type-Installer -u beville -w $(PASSWORD) "release/ComicTagger v$(VERSION_STR).exe"
