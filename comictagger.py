#!/usr/bin/env python3
from __future__ import annotations

import localefix
from comictaggerlib.main import ctmain

if __name__ == "__main__":
    localefix.configure_locale()
    ctmain()
