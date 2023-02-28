PIP ?= pip3
PYTHON ?= python3
VERSION_STR := $(shell $(PYTHON) setup.py --version)

SITE_PACKAGES := $(shell $(PYTHON) -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
PACKAGE_PATH = $(SITE_PACKAGES)/comictagger.egg-link

VENV := $(shell echo $${VIRTUAL_ENV-venv})
PY3 := $(shell command -v $(PYTHON) 2> /dev/null)
PYTHON_VENV := $(VENV)/bin/python
INSTALL_STAMP := $(VENV)/.install.stamp


ifeq ($(OS),Windows_NT)
	PYTHON_VENV := $(VENV)/Scripts/python.exe
	OS_VERSION=win-$(PROCESSOR_ARCHITECTURE)
	APP_NAME=comictagger.exe
	FINAL_NAME=ComicTagger-$(VERSION_STR)-$(OS_VERSION).exe
else ifeq ($(shell uname -s),Darwin)
	OS_VERSION=osx-$(shell defaults read loginwindow SystemVersionStampAsString)-$(shell uname -m)
	APP_NAME=ComicTagger.app
	FINAL_NAME=ComicTagger-$(VERSION_STR)-$(OS_VERSION).app
else
	APP_NAME=comictagger
	FINAL_NAME=ComicTagger-$(VERSION_STR)-$(shell uname -s)
endif

.PHONY: all clean pydist dist CI check appimage

all: clean dist

$(PYTHON_VENV):
	@if [ -z $(PY3) ]; then echo "Python 3 could not be found."; exit 2; fi
	$(PY3) -m venv $(VENV)

clean:
	find . -maxdepth 4 -type d -name "__pycache__" -print -depth -exec rm -rf {} \;
	rm -rf $(PACKAGE_PATH) $(INSTALL_STAMP) build dist MANIFEST comictaggerlib/ctversion.py
	$(MAKE) -C mac clean

CI: install
	$(PYTHON_VENV) -m black .
	$(PYTHON_VENV) -m isort .
	$(PYTHON_VENV) -m flake8 .
	$(PYTHON_VENV) -m pytest

check: install
	$(PYTHON_VENV) -m black --check .
	$(PYTHON_VENV) -m isort --check .
	$(PYTHON_VENV) -m flake8 .
	$(PYTHON_VENV) -m pytest

pydist:
	$(PYTHON_VENV) -m build

install: $(INSTALL_STAMP)
$(INSTALL_STAMP): $(PYTHON_VENV) requirements.txt requirements_dev.txt
	$(PYTHON_VENV) -m pip install -r requirements_dev.txt
	$(PYTHON_VENV) -m pip install -e .
	touch $(INSTALL_STAMP)

dist: dist/$(FINAL_NAME).zip

dist/$(FINAL_NAME).zip:
	pyinstaller -y comictagger.spec
	cd dist && zip -r $(FINAL_NAME).zip $(APP_NAME)

dist/appimagetool:
	curl -L https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage > dist/appimagetool
	chmod +x dist/appimagetool

appimage: dist dist/appimagetool
	rm -rf dist/appimage && cp -a dist/comictagger dist/appimage
	cd dist/appimage/ && ln -s comictaggerlib/graphics/app.png app.png && ln -s comictagger AppRun
	sed -e 's|/usr/local/share/comictagger/app.png|app|g' -e 's|%%CTSCRIPT%% %F|./comictagger|g' desktop-integration/linux/ComicTagger.desktop > dist/appimage/AppRun.desktop
	cd dist && ./appimagetool appimage
