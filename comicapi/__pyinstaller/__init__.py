from __future__ import annotations

import os


def get_hook_dirs() -> list[str]:
    return [os.path.dirname(__file__)]
