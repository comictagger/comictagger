#! python3
from __future__ import annotations

import os
import subprocess
import sys

ts_dirs = ["comictaggerlib", "comictaggerlib/ui", "comictalker/talkers"]


def find_files(s_dir):
    files_for_ts = []
    for filename in os.listdir(s_dir):
        if filename.endswith(".py") or filename.endswith(".ui"):
            files_for_ts.append(os.path.join(s_dir, filename))

    return files_for_ts


def generate_ts_files():
    """Generate ts file from the ts_dirs list"""
    cwd = os.getcwd()
    filenames = []
    for s_dir in ts_dirs:
        filenames.extend(find_files(s_dir))

    filenames_str = " ".join(filenames)

    try:
        # Need to run as shell for filename splitting to work
        subprocess.run(
            [f"pylupdate5 {filenames_str} -ts -verbose -noobsolete comictaggerlib/i18n/en_GB.ts"],
            cwd=cwd,
            check=True,
            shell=True,
        )
    except Exception as e:
        print(e)  # noqa: T201


def generate_gm_files():
    """Run lrelease for each ts file"""
    lrelease_cmd = "lrelease"
    cwd = os.getcwd() + "/comictaggerlib/i18n/"
    try:
        subprocess.run([lrelease_cmd])
    except OSError as e:
        if e.errno == 2:
            lrelease_cmd = "lrelease-qt5"

    for filename in os.listdir(cwd):
        if filename.endswith(".ts"):
            try:
                subprocess.run([lrelease_cmd, filename], cwd=cwd, check=True)
            except Exception as e:
                print(e)  # noqa: T201


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "ts":
            generate_ts_files()
        if sys.argv[1] == "gm":
            generate_gm_files()
