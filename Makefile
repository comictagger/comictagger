TAGGER_BASE := $(HOME)/Dropbox/tagger/comictagger
VERSION_STR := $(shell grep version $(TAGGER_BASE)/ctversion.py| cut -d= -f2 | sed 's/\"//g')

all: clean

clean:
	rm -f *~ *.pyc *.pyo
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
	
svn_tag:
	svn copy https://comictagger.googlecode.com/svn/trunk \
      https://comictagger.googlecode.com/svn/tags/$(VERSION_STR) -m "Release $(VERSION_STR)"
	
