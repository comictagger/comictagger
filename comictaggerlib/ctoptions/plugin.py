from __future__ import annotations

import logging
import os

import settngs

import comicapi.comicarchive

logger = logging.getLogger("comictagger")


def archiver(manager: settngs.Manager) -> None:
    exe_registered: set[str] = set()
    for archiver in comicapi.comicarchive.archivers:
        if archiver.exe and archiver.exe not in exe_registered:
            manager.add_setting(
                f"--{archiver.exe.replace(' ', '-').replace('_', '-').strip().strip('-')}",
                default=archiver.exe,
                help="Path to the %(default)s executable\n\n",
            )
            exe_registered.add(archiver.exe)


def validate_plugin_settings(options: settngs.Config) -> settngs.Config:
    if "archiver" not in options[1]:
        return options
    cfg = settngs.normalize_config(options, file=True, cmdline=True, defaults=False)
    for archiver in comicapi.comicarchive.archivers:
        exe_name = archiver.exe.replace(" ", "-").replace("_", "-").strip().strip("-").replace("-", "_")
        if (
            exe_name in cfg[0]["archiver"]
            and cfg[0]["archiver"][exe_name]
            and cfg[0]["archiver"][exe_name] != archiver.exe
        ):
            if os.path.basename(cfg[0]["archiver"][exe_name]) == archiver.exe:
                comicapi.utils.add_to_path(os.path.dirname(cfg[0]["archiver"][exe_name]))
            else:
                archiver.exe = cfg[0]["archiver"][exe_name]

    return options


def register_plugin_settings(manager: settngs.Manager):
    manager.add_persistent_group("archiver", archiver, False)
