from __future__ import annotations

import os
import pathlib
import platform
import zipfile

from comictaggerlib.ctversion import __version__

app = "ComicTagger"
exe = app.casefold()
if platform.system() == "Windows":
    os_version = f"win-{platform.machine()}"
    app_name = f"{exe}.exe"
    final_name = f"{app}-{__version__}-{os_version}.exe"
elif platform.system() == "Darwin":
    ver = platform.mac_ver()
    os_version = f"osx-{ver[0]}-{ver[2]}"
    app_name = f"{app}.app"
    final_name = f"{app}-{__version__}-{os_version}.app"
else:
    app_name = exe
    final_name = f"ComicTagger-{__version__}-{platform.system()}"

path = f"dist/{app_name}"
zip_file = pathlib.Path(f"dist/{final_name}.zip")


def addToZip(zf, path, zippath):
    if os.path.isfile(path):
        zf.write(path, zippath)
    elif os.path.isdir(path):
        if zippath:
            zf.write(path, zippath)
        for nm in sorted(os.listdir(path)):
            addToZip(zf, os.path.join(path, nm), os.path.join(zippath, nm))
    # else: ignore


zip_file.unlink(missing_ok=True)
with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
    zippath = os.path.basename(path)
    if not zippath:
        zippath = os.path.basename(os.path.dirname(path))
    if zippath in ("", os.curdir, os.pardir):
        zippath = ""
    addToZip(zf, path, zippath)
