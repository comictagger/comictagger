TAGGER_BASE := $(HOME)/Dropbox/tagger/comictagger
TAGGER_SRC := $(TAGGER_BASE)/comictaggerlib
VERSION_STR := $(shell grep version $(TAGGER_SRC)/ctversion.py| cut -d= -f2 | sed 's/\"//g')
PASSWORD    := $(shell cat $(TAGGER_BASE)/project_password.txt)  
UPLOAD_TOOL := $(TAGGER_BASE)/google/googlecode_upload.py
all: clean

clean:
	rm -rf *~ *.pyc *.pyo
	rm -rf scripts/*.pyc
	cd comictaggerlib; rm -f *~ *.pyc *.pyo
	rm -rf dist MANIFEST
	rm -rf *.deb
	rm -rf logdict*.log
	make -C mac clean
	make -C windows clean
	rm -rf build

pydist:
	mkdir -p release
	rm -f release/*.zip
	python setup.py sdist --formats=zip  #,gztar
	mv dist/comictagger-$(VERSION_STR).zip release
	@echo When satisfied with release, do this:
	@echo make svn_tag

remove_test_install:
	sudo rm -rf /usr/local/bin/comictagger.py
	sudo rm -rf /usr/local/lib/python2.7/dist-packages/comictagger*
	
#deb:
#	fpm -s python -t deb \
#		-n 'comictagger' \
#		--category 'utilities' \
#		--maintainer 'comictagger@gmail.com' \
#		--after-install debian_scripts/after_install.sh \
#		--before-remove debian_scripts/before_remove.sh \
#		-d 'python >= 2.6' \
#		-d 'python < 2.8' \
#		-d 'python-imaging' \
#		-d 'python-bs4' \
#		--deb-suggests 'rar' \
#		--deb-suggests 'unrar-free' \
#		--python-install-bin /usr/share/comictagger \
#		--python-install-lib /usr/share/comictagger \
#		setup.py 
#
#		# For now, don't require PyQt, since command-line is available without it
#		#-d 'python-qt4 >= 4.8' 
		
upload:
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR) Source" -l Featured,Type-Source -u beville -w $(PASSWORD) "release/comictagger-$(VERSION_STR).zip"
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR)  Mac OS X" -l Featured,Type-Archive -u beville -w $(PASSWORD) "release/ComicTagger-$(VERSION_STR).dmg"
	$(UPLOAD_TOOL) -p comictagger -s "ComicTagger $(VERSION_STR)  Windows" -l Featured,Type-Installer -u beville -w $(PASSWORD) "release/ComicTagger v$(VERSION_STR).exe"

	@echo ----------------------------------- 
	@echo	??? python setup.py register
	@echo ----------------------------------- 
 
svn_tag:
	svn copy https://comictagger.googlecode.com/svn/trunk \
		https://comictagger.googlecode.com/svn/tags/$(VERSION_STR) -m "Release $(VERSION_STR)"

