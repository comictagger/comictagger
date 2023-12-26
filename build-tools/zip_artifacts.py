from __future__ import annotations

import os
import pathlib
import platform
import sys
import tarfile
import zipfile

from dmgbuild.__main__ import main as dmg_main

from comictaggerlib.ctversion import __version__


def addToZip(zf: zipfile.ZipFile, path: str, zippath: str) -> None:
    if os.path.isfile(path):
        zf.write(path, zippath)
    elif os.path.isdir(path):
        if zippath:
            zf.write(path, zippath)
        for nm in sorted(os.listdir(path)):
            addToZip(zf, os.path.join(path, nm), os.path.join(zippath, nm))


def Zip(zip_file: pathlib.Path, path: pathlib.Path) -> None:
    zip_file.unlink(missing_ok=True)
    with zipfile.ZipFile(f"{zip_file}.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        zippath = os.path.basename(path)
        if not zippath:
            zippath = os.path.basename(os.path.dirname(path))
        if zippath in ("", os.curdir, os.pardir):
            zippath = ""
        addToZip(zf, str(path), zippath)


def addToTar(tf: tarfile.TarFile, path: str, zippath: str) -> None:
    if os.path.isfile(path):
        tf.add(path, zippath)
    elif os.path.isdir(path):
        if zippath:
            tf.add(path, zippath, recursive=False)
        for nm in sorted(os.listdir(path)):
            addToTar(tf, os.path.join(path, nm), os.path.join(zippath, nm))


def Tar(tar_file: pathlib.Path, path: pathlib.Path) -> None:
    tar_file.unlink(missing_ok=True)
    with tarfile.TarFile(f"{tar_file}.tar.gz", "w:gz") as tf:  # type: ignore[arg-type]
        zippath = os.path.basename(path)
        if not zippath:
            zippath = os.path.basename(os.path.dirname(path))
        if zippath in ("", os.curdir, os.pardir):
            zippath = ""
        addToTar(tf, str(path), zippath)


if __name__ == "__main__":
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
        final_name = f"{app}-{__version__}-{os_version}"
    else:
        app_name = exe
        final_name = f"ComicTagger-{__version__}-{platform.system()}"

    path = pathlib.Path(f"dist/{app_name}")
    zip_file = pathlib.Path(f"dist/{final_name}")

    if platform.system() == "Darwin":
        sys.argv = [
            "zip_artifacts",
            "-s",
            str(pathlib.Path(__file__).parent / "dmgbuild.conf"),
            f"{app} {__version__}",
            f"dist/{final_name}.dmg",
        ]
        dmg_main()
    elif platform.system() == "Windows":
        Zip(zip_file, path)
    else:
        Tar(zip_file, path)
