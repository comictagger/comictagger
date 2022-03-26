import sys

import natsort

import localefix
from comicapi import comicarchive
from comictaggerlib import settings

sett = settings.ComicTaggerSettings()

ca = comicarchive.ComicArchive(sys.argv[1], sett.rar_exe_path, sett.getGraphic("nocover.png"))
for page in ca.getPageNameList():
    print(page)
