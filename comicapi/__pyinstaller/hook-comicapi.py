from __future__ import annotations

from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files("comicapi.data")
