from __future__ import annotations

from PyInstaller.utils.hooks import collect_data_files, collect_entry_point, collect_submodules

datas, hiddenimports = collect_entry_point("comictagger.talker")
hiddenimports += collect_submodules("comictaggerlib")
datas += collect_data_files("comictaggerlib.ui")
datas += collect_data_files("comictaggerlib.graphics")
