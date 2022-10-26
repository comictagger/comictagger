from __future__ import annotations

import os

from PyInstaller.utils.hooks import get_module_file_attribute

datas = [(os.path.join(os.path.dirname(get_module_file_attribute("wordninja")), "wordninja"), "wordninja")]
