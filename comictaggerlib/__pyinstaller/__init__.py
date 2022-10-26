from __future__ import annotations

import os

import comicapi.__pyinstaller


def get_hook_dirs() -> list[str]:
    hooks = [os.path.dirname(__file__)]
    hooks.extend(comicapi.__pyinstaller.get_hook_dirs())
    return hooks
