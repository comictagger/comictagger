# -*- mode: python -*-

import platform
from comictaggerlib import ctversion

block_cipher = None

if platform.system() == "Windows":
    from site import getsitepackages
    sitepackages = getsitepackages()[1]
    # add ssl qt libraries not discovered automatically
    binaries.extend([
        ('%s/PyQt5/Qt/bin/libeay32.dll' % sitepackages, './PyQt5/Qt/bin'),
        ('%s/PyQt5/Qt/bin/ssleay32.dll' % sitepackages, './PyQt5/Qt/bin')
    ])

a = Analysis(['comictagger.py'],
             binaries=binaries,
             datas=[('comictaggerlib/ui/*.ui', 'ui'), ('comictaggerlib/graphics', 'graphics')],
             hiddenimports=['PIL'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          # single file setup
          exclude_binaries=False,
          name='comictagger',
          debug=False,
          strip=False,
          upx=True,
          console=False,
          icon="windows/app.ico" )

app = BUNDLE(exe,
            name='ComicTagger.app',
            icon='mac/app.icns',
            info_plist={
                'NSHighResolutionCapable': 'True',
                'CFBundleDisplayName': 'ComicTagger',
                'CFBundleShortVersionString': ctversion.version,
                'CFBundleVersion': ctversion.version
            },
            bundle_identifier=None)