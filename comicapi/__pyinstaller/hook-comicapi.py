from __future__ import annotations

from PyInstaller.utils.hooks import collect_data_files, collect_entry_point

datas, hiddenimports = collect_entry_point("comicapi.archiver")
mdatas, mhiddenimports = collect_entry_point("comicapi.tags")

hiddenimports += mhiddenimports
datas += mdatas
datas += collect_data_files("comicapi.data")
