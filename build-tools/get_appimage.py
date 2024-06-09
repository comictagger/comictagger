from __future__ import annotations

import argparse
import os
import pathlib
import stat

try:
    import niquests as requests
except ImportError:
    import requests

parser = argparse.ArgumentParser()
parser.add_argument("APPIMAGETOOL", default="build/appimagetool-x86_64.AppImage", type=pathlib.Path, nargs="?")

opts = parser.parse_args()
opts.APPIMAGETOOL = opts.APPIMAGETOOL.absolute()


def urlretrieve(url: str, dest: pathlib.Path) -> None:
    resp = requests.get(url)
    if resp.status_code == 200:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)


if opts.APPIMAGETOOL.exists():
    raise SystemExit(0)

urlretrieve(
    "https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage", opts.APPIMAGETOOL
)
os.chmod(opts.APPIMAGETOOL, stat.S_IRWXU)

if not opts.APPIMAGETOOL.exists():
    raise SystemExit(1)
