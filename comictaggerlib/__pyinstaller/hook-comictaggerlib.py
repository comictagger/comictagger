from __future__ import annotations

from PyInstaller.utils.hooks import collect_data_files, collect_entry_point

datas, hiddenimports = collect_entry_point("comictagger.talker")
datas += collect_data_files("comictaggerlib.ui")
datas += collect_data_files("comictaggerlib.graphics")
