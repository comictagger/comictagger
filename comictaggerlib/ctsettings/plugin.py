from __future__ import annotations

import logging
import os

import settngs

import comicapi.comicarchive
import comictaggerlib.ctsettings

logger = logging.getLogger("comictagger")


def archiver(manager: settngs.Manager) -> None:
    for archiver in comicapi.comicarchive.archivers:
        if archiver.exe:
            # add_setting will overwrite anything with the same name.
            # So we only end up with one option even if multiple archivers use the same exe.
            manager.add_setting(
                f"--{settngs.sanitize_name(archiver.exe)}",
                default=archiver.exe,
                help="Path to the %(default)s executable\n\n",
            )


def register_talker_settings(manager: settngs.Manager) -> None:
    for talker_id, talker in comictaggerlib.ctsettings.talkers.items():

        def api_options(manager: settngs.Manager) -> None:
            manager.add_setting(
                f"--{talker_id}-key",
                default="",
                display_name="API Key",
                help=f"API Key for {talker.name} (default: {talker.default_api_key})",
            )
            manager.add_setting(
                f"--{talker_id}-url",
                default="",
                display_name="URL",
                help=f"URL for {talker.name} (default: {talker.default_api_url})",
            )

        try:
            manager.add_persistent_group("talker_" + talker_id, api_options, False)
            manager.add_persistent_group("talker_" + talker_id, talker.register_settings, False)
        except Exception:
            logger.exception("Failed to register settings for %s", talker_id)


def validate_archive_settings(config: settngs.Config[settngs.Namespace]) -> settngs.Config[settngs.Namespace]:
    if "archiver" not in config[1]:
        return config
    cfg = settngs.normalize_config(config, file=True, cmdline=True, defaults=False)
    for archiver in comicapi.comicarchive.archivers:
        exe_name = settngs.sanitize_name(archiver.exe)
        if exe_name in cfg[0]["archiver"] and cfg[0]["archiver"][exe_name]:
            if os.path.basename(cfg[0]["archiver"][exe_name]) == archiver.exe:
                comicapi.utils.add_to_path(os.path.dirname(cfg[0]["archiver"][exe_name]))
            else:
                archiver.exe = cfg[0]["archiver"][exe_name]

    return config


def validate_talker_settings(config: settngs.Config[settngs.Namespace]) -> settngs.Config[settngs.Namespace]:
    # Apply talker settings from config file
    cfg = settngs.normalize_config(config, True, True)
    for talker_id, talker in list(comictaggerlib.ctsettings.talkers.items()):
        try:
            cfg[0]["talker_" + talker_id] = talker.parse_settings(cfg[0]["talker_" + talker_id])
        except Exception as e:
            # Remove talker as we failed to apply the settings
            del comictaggerlib.ctsettings.talkers[talker_id]
            logger.exception("Failed to initialize talker settings: %s", e)

    return settngs.get_namespace(cfg)


def validate_plugin_settings(config: settngs.Config[settngs.Namespace]) -> settngs.Config[settngs.Namespace]:
    config = validate_archive_settings(config)
    config = validate_talker_settings(config)
    return config


def register_plugin_settings(manager: settngs.Manager) -> None:
    manager.add_persistent_group("archiver", archiver, False)
    register_talker_settings(manager)
