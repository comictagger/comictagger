PY2INSTALLER_CMD := python $(HOME)/pyinstaller-2.0/pyinstaller.py
TAGGER_BASE := $(HOME)/Dropbox/tagger/comictagger

APP_NAME := ComicTagger
VERSION_STR := $(shell grep version $(TAGGER_BASE)/ctversion.py| cut -d= -f2 | sed 's/\"//g')



MAC_BASE := $(TAGGER_BASE)/mac
DIST_DIR := $(MAC_BASE)/dist
STAGING := $(MAC_BASE)/$(APP_NAME)
APP_BUNDLE := $(DIST_DIR)/$(APP_NAME).app
VOLUME_NAME := $(APP_NAME)-$(VERSION_STR)
DMG_FILE := $(VOLUME_NAME).dmg

all: clean dist diskimage

dist:
	$(PY2INSTALLER_CMD) tagger.py -o $(MAC_BASE) -w -n $(APP_NAME) -s 
	cp $(TAGGER_BASE)/*.ui $(APP_BUNDLE)/Contents/MacOS
	cp -a $(TAGGER_BASE)/graphics $(APP_BUNDLE)/Contents/MacOS
	cp $(MAC_BASE)/app.icns $(APP_BUNDLE)/Contents/Resources/icon-windowed.icns
	
clean:
	rm -rf $(DIST_DIR) $(MAC_BASE)/build
	rm -f $(MAC_BASE)/*.spec
	rm -f "*~" *.pyc *.pyo
	echo $(VERSION_STR)
diskimage:
	#Set up disk image staging folder
	rm -rf $(STAGING)
	mkdir $(STAGING)
	#cp $(TAGGER_BASE)/README.txt $(STAGING)
	cp -a $(APP_BUNDLE) $(STAGING)
	cp $(MAC_BASE)/volume.icns $(STAGING)/.VolumeIcon.icns
	SetFile -c icnC $(STAGING)/.VolumeIcon.icns

	##generate raw disk image
	rm -f $(DMG_FILE)
	hdiutil create -srcfolder $(STAGING) -volname $(VOLUME_NAME) -format UDRW -ov raw-$(DMG_FILE)	

	#remove working files and folders
	rm -rf $(STAGING)
	
	# we now have a raw DMG file.
	
	# remount it so we can set the volume icon properly
	mkdir -p $(STAGING)
	hdiutil attach raw-$(DMG_FILE) -mountpoint $(STAGING)
	SetFile -a C $(STAGING)
	hdiutil detach $(STAGING)
	rm -rf $(STAGING)
	
	# convert the raw image
	rm -f $(DMG_FILE)
	hdiutil convert raw-$(DMG_FILE) -format UDZO -o $(DMG_FILE)
	rm -f raw-$(DMG_FILE)
	