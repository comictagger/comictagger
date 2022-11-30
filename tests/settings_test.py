from __future__ import annotations

import pytest

from comictaggerlib import settings as ctsettings


def test_settings_manager():
    manager = ctsettings.Manager()
    defaults = manager.defaults()
    assert manager is not None and defaults is not None


settings_cases = [
    (
        {
            "test": (
                {
                    "args": ["--test"],
                    "kwargs": dict(
                        action=None,
                        nargs=None,
                        const=None,
                        default=None,
                        type=None,
                        choices=None,
                        required=None,
                        help=None,
                        metavar=None,
                        dest=None,
                        cmdline=True,
                        file=True,
                    ),
                },
            ),
        },
        dict({"test": {"test": {"names": ["--test"], "dest": "test", "default": None}}}),
    )
]


@pytest.mark.parametrize("settings, expected", settings_cases)
def test_add_setting(settings, expected, settings_manager, tmp_path):
    for group, settings in settings.items():

        def add_settings(parser):
            for setting in settings:
                settings_manager.add_setting(*setting["args"], **setting["kwargs"])

        settings_manager.add_group(group, add_settings)

    parsed_settings = settings_manager.parse_options(ctsettings.ComicTaggerPaths(tmp_path), args=[])

    # print(parsed_settings)
    # print(expected)
    for group, settings in expected.items():
        for setting_name, setting in settings.items():
            assert parsed_settings[group][setting_name] == setting["default"]
    assert False
