PIP ?= pip3
PYTHON ?= python3
VERSION_STR := $(shell $(PYTHON) setup.py --version)

SITE_PACKAGES := $(shell $(PYTHON) -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
PACKAGE_PATH = $(SITE_PACKAGES)/comictagger-$(VERSION_STR).dist-info

VENV := $(shell echo $${VIRTUAL_ENV-venv})
PY3 := $(shell command -v $(PYTHON) 2> /dev/null)
PYTHON_VENV := $(VENV)/bin/python
INSTALL_STAMP := $(VENV)/.install.stamp
INSTALL_GUI_STAMP := $(VENV)/.install-GUI.stamp


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

.PHONY: all clean pydist upload dist CI check run

all: clean dist

$(PYTHON_VENV):
	@if [ -z $(PY3) ]; then echo "Python 3 could not be found."; exit 2; fi
	$(PY3) -m venv --system-site-packages $(VENV)

clean:
	find . -type d -name "__pycache__" | xargs rm -rf {};
	rm -rf $(INSTALL_STAMP)
	rm -rf dist MANIFEST
	$(MAKE) -C mac clean
	rm -rf build
	rm comictaggerlib/ctversion.py

CI: ins
	black .
	isort .
	flake8 .
	pytest

check: install
	$(VENV)/bin/black --check .
	$(VENV)/bin/isort --check .
	$(VENV)/bin/flake8 .
	$(VENV)/bin/pytest

pydist: CI
	make clean
	mkdir -p piprelease
	rm -f comictagger-$(VERSION_STR).zip
	$(PYTHON) setup.py sdist --formats=gztar
	mv dist/comictagger-$(VERSION_STR).tar.gz piprelease
	rm -rf comictagger.egg-info dist

upload:
	$(PYTHON) setup.py register
	$(PYTHON) setup.py sdist --formats=gztar upload

install: $(INSTALL_STAMP)
$(INSTALL_STAMP): $(PYTHON_VENV) requirements.txt requirements_dev.txt
	$(PYTHON_VENV) -m pip install -r requirements_dev.txt
	$(PYTHON_VENV) -m pip install -e .
	touch $(INSTALL_STAMP)

install-GUI: $(INSTALL_GUI_STAMP)
$(INSTALL_GUI_STAMP): requirements-GUI.txt
	$(PYTHON_VENV) -m pip install -r requirements-GUI.txt
	touch $(INSTALL_GUI_STAMP)

ins: $(PACKAGE_PATH)
$(PACKAGE_PATH):
	$(PIP) install .

dist: CI
	pyinstaller -y comictagger.spec
	cd dist && zip -r $(FINAL_NAME).zip $(APP_NAME)
