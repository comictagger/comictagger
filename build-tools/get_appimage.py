from __future__ import annotations

import os
import pathlib
import stat

import requests


def urlretrieve(url: str, dest: str) -> None:
    resp = requests.get(url)
    if resp.status_code == 200:
        pathlib.Path(dest).write_bytes(resp.content)


APPIMAGETOOL = "build/appimagetool-x86_64.AppImage"
if os.path.exists(APPIMAGETOOL):
    raise SystemExit(0)

urlretrieve(
    "https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage", APPIMAGETOOL
)
os.chmod(APPIMAGETOOL, stat.S_IRWXU)

if not os.path.exists(APPIMAGETOOL):
    raise SystemExit(1)
