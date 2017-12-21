TAGGER_BASE ?= .
TAGGER_SRC := $(TAGGER_BASE)/comictaggerlib
VERSION_STR := $(shell grep version $(TAGGER_SRC)/ctversion.py| cut -d= -f2 | sed 's/\"//g')
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
	make -C unrar clean

pydist:
	mkdir -p release
	rm -f release/*.zip
	python setup.py sdist --formats=zip  #,gztar
	mv dist/comictagger-$(VERSION_STR).zip release
		
upload:
	python setup.py register
	python setup.py sdist --formats=zip upload

.PHONY: unrar
unrar:
	make -C unrar lib