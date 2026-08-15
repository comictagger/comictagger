from __future__ import annotations

import logging
import os

import settngs

import comicapi.comicarchive
import comictaggerlib.ctsettings

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


def register_talker_settings(manager: settngs.Manager) -> None:
    for talker_name, talker in comictaggerlib.ctsettings.talkers.items():
        try:
            manager.add_persistent_group("talker_" + talker_name, talker.register_settings, False)
        except Exception:
            logger.exception("Failed to register settings for %s", talker_name)


def validate_archive_settings(config: settngs.Config[settngs.Namespace]) -> settngs.Config[settngs.Namespace]:
    if "archiver" not in config[1]:
        return config
    cfg = settngs.normalize_config(config, file=True, cmdline=True, defaults=False)
    for archiver in comicapi.comicarchive.archivers:
        exe_name = settngs.sanitize_name(archiver.exe)
        if (
            exe_name in cfg[0]["archiver"]
            and cfg[0]["archiver"][exe_name]
            and cfg[0]["archiver"][exe_name] != archiver.exe
        ):
            if os.path.basename(cfg[0]["archiver"][exe_name]) == archiver.exe:
                comicapi.utils.add_to_path(os.path.dirname(cfg[0]["archiver"][exe_name]))
            else:
                archiver.exe = cfg[0]["archiver"][exe_name]

    return config


def validate_talker_settings(config: settngs.Config[settngs.Namespace]) -> settngs.Config[settngs.Namespace]:
    # Apply talker settings from config file
    cfg = settngs.normalize_config(config, True, True)
    for talker_name, talker in list(comictaggerlib.ctsettings.talkers.items()):
        try:
            talker.parse_settings(cfg[0]["talker_" + talker_name])
        except Exception as e:
            # Remove talker as we failed to apply the settings
            del comictaggerlib.ctsettings.talkers[talker_name]
            logger.exception("Failed to initialize talker settings: %s", e)

    return config


def validate_plugin_settings(config: settngs.Config[settngs.Namespace]) -> settngs.Config[settngs.Namespace]:
    config = validate_archive_settings(config)
    config = validate_talker_settings(config)
    return config


def register_plugin_settings(manager: settngs.Manager) -> None:
    manager.add_persistent_group("archiver", archiver, False)
    register_talker_settings(manager)
