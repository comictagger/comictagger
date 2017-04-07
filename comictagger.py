#!/usr/bin/env python
import os
import sys

if getattr(sys, 'frozen', False):
    # we are running in a bundle
    frozen = 'ever so'
    bundle_dir = sys._MEIPASS
else:
    # we are running in a normal Python environment
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# setup libunrar
if not os.environ.get("UNRAR_LIB_PATH", None):
    os.environ["UNRAR_LIB_PATH"] = bundle_dir + "/libunrar.so"

print os.environ.get("UNRAR_LIB_PATH", None)
print bundle_dir    

from comictaggerlib.main import ctmain

if __name__ == '__main__':
    ctmain()
