PIP ?= pip3
PYTHON ?= python3
VERSION_STR := $(shell $(PYTHON) setup.py --version)

ifeq ($(OS),Windows_NT)
	OS_VERSION=win-$(PROCESSOR_ARCHITECTURE)
	APP_NAME=comictagger.exe
	FINAL_NAME=ComicTagger-$(VERSION_STR)-$(OS_VERSION).exe
else ifeq ($(shell uname -s),Darwin)
	OS_VERSION=osx-$(shell defaults read loginwindow SystemVersionStampAsString)-$(shell uname -m)
	APP_NAME=ComicTagger.app
	FINAL_NAME=ComicTagger-$(VERSION_STR)-$(OS_VERSION).app
else
	APP_NAME=comictagger
	FINAL_NAME=ComicTagger-$(VERSION_STR)
endif

.PHONY: all clean pydist upload dist
	
all: clean dist

clean:
	rm -rf *~ *.pyc *.pyo
	rm -rf scripts/*.pyc
	cd comictaggerlib; rm -f *~ *.pyc *.pyo
	rm -rf dist MANIFEST
	rm -rf *.deb
	rm -rf logdict*.log
	$(MAKE) -C mac clean   
	rm -rf build
	rm -rf comictaggerlib/ui/__pycache__
	rm comictaggerlib/ctversion.py

pydist:
	make clean
	mkdir -p piprelease
	rm -f comictagger-$(VERSION_STR).zip
	$(PYTHON) setup.py sdist --formats=gztar
	mv dist/comictagger-$(VERSION_STR).tar.gz piprelease
	rm -rf comictagger.egg-info dist
		
upload:
	$(PYTHON) setup.py register
	$(PYTHON) setup.py sdist --formats=gztar upload

dist:
	$(PIP) install .
	pyinstaller -y comictagger.spec
	cd dist && zip -r $(FINAL_NAME).zip $(APP_NAME)
