VERSION_STR := $(shell python -c 'import comictaggerlib.ctversion; print( comictaggerlib.ctversion.version)')

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

.PHONY: all clean pydist upload unrar dist
	
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
	$(MAKE) -C unrar clean
	rm -f unrar/libunrar.so unrar/libunrar.a unrar/unrar
	rm -f comictaggerlib/libunrar.so
	rm -rf comictaggerlib/ui/__pycache__

pydist:
	make clean
	mkdir -p piprelease
	rm -f comictagger-$(VERSION_STR).zip
	python setup.py sdist --formats=zip  #,gztar
	mv dist/comictagger-$(VERSION_STR).zip piprelease
	rm -rf comictagger.egg-info dist
		
upload:
	python setup.py register
	python setup.py sdist --formats=zip upload

unrar:
ifeq ($(OS),Windows_NT)
		# statically compile mingw dependencies
		# https://stackoverflow.com/questions/18138635/mingw-exe-requires-a-few-gcc-dlls-regardless-of-the-code
		$(MAKE) -C unrar LDFLAGS='-Wl,-Bstatic,--whole-archive -lwinpthread -Wl,--no-whole-archive -pthread -static-libgcc -static-libstdc++' lib
else
		$(MAKE) -C unrar lib
endif

dist: unrar
	pyinstaller -y comictagger.spec
	cd dist && zip -r $(FINAL_NAME).zip $(APP_NAME)
