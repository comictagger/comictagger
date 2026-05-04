from __future__ import annotations

import importlib.resources

import comictaggerlib.graphics.resources  # noqa: F401

graphics_path = importlib.resources.files(__package__)
try:
    from . import resources

    assert resources.qInitResources
except Exception:
    ...
