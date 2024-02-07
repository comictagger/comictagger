from __future__ import annotations

import logging
import os
from typing import Any, cast

import settngs

import comicapi.comicarchive
import comicapi.utils
import comictaggerlib.ctsettings
from comicapi.comicarchive import Archiver
from comictaggerlib.ctsettings.settngs_namespace import SettngsNS as ct_ns
from comictalker.comictalker import ComicTalker

logger = logging.getLogger("comictagger")


def group_for_plugin(plugin: Archiver | ComicTalker | type[Archiver]) -> str:
    if isinstance(plugin, ComicTalker):
        return f"Source {plugin.id}"
    if isinstance(plugin, Archiver) or plugin == Archiver:
        return "Archive"
    raise NotImplementedError(f"Invalid plugin received: {plugin=}")


def archiver(manager: settngs.Manager) -> None:
    for archiver in comicapi.comicarchive.archivers:
        if archiver.exe:
            # add_setting will overwrite anything with the same name.
            # So we only end up with one option even if multiple archivers use the same exe.
            manager.add_setting(
                f"--{settngs.sanitize_name(archiver.exe)}",
                default=archiver.exe,
                help="Path to the %(default)s executable",
            )


def register_talker_settings(manager: settngs.Manager, talkers: dict[str, ComicTalker]) -> None:
    for talker in talkers.values():

        def api_options(manager: settngs.Manager) -> None:
            # The default needs to be unset or None.
            # This allows this setting to be unset with the empty string, allowing the default to change
            manager.add_setting(
                f"--{talker.id}-key",
                display_name="API Key",
                help=f"API Key for {talker.name} (default: {talker.default_api_key})",
            )
            manager.add_setting(
                f"--{talker.id}-url",
                display_name="URL",
                help=f"URL for {talker.name} (default: {talker.default_api_url})",
            )

        try:
            manager.add_persistent_group(group_for_plugin(talker), api_options, False)
            if hasattr(talker, "register_settings"):
                manager.add_persistent_group(group_for_plugin(talker), talker.register_settings, False)
        except Exception:
            logger.exception("Failed to register settings for %s", talker.id)


def validate_archive_settings(config: settngs.Config[ct_ns]) -> settngs.Config[ct_ns]:
    cfg = settngs.normalize_config(config, file=True, cmdline=True, default=False)
    for archiver in comicapi.comicarchive.archivers:
        group = group_for_plugin(archiver())
        exe_name = settngs.sanitize_name(archiver.exe)
        if not exe_name:
            continue

        if exe_name in cfg[0][group] and cfg[0][group][exe_name]:
            path = cfg[0][group][exe_name]
            name = os.path.basename(path)
            # If the path is not the basename then this is a relative or absolute path.
            # Ensure it is absolute
            if path != name:
                path = os.path.abspath(path)

            archiver.exe = path

    return config


def validate_talker_settings(config: settngs.Config[ct_ns], talkers: dict[str, ComicTalker]) -> settngs.Config[ct_ns]:
    # Apply talker settings from config file
    cfg = cast(settngs.Config[dict[str, Any]], settngs.normalize_config(config, True, True))
    for talker in list(talkers.values()):
        try:
            cfg[0][group_for_plugin(talker)] = talker.parse_settings(cfg[0][group_for_plugin(talker)])
        except Exception as e:
            # Remove talker as we failed to apply the settings
            del comictaggerlib.ctsettings.talkers[talker.id]
            logger.exception("Failed to initialize talker settings: %s", e)

    return cast(settngs.Config[ct_ns], settngs.get_namespace(cfg, file=True, cmdline=True))


def validate_plugin_settings(config: settngs.Config[ct_ns], talkers: dict[str, ComicTalker]) -> settngs.Config[ct_ns]:
    config = validate_archive_settings(config)
    config = validate_talker_settings(config, talkers)
    return config


def register_plugin_settings(manager: settngs.Manager, talkers: dict[str, ComicTalker]) -> None:
    manager.add_persistent_group("Archive", archiver, False)
    register_talker_settings(manager, talkers)
