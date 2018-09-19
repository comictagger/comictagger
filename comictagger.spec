# -*- mode: python -*-

import platform

block_cipher = None

binaries = [
    ('./unrar/libunrar.so', './'),
]

if platform.system() == "Windows":
    # add ssl qt libraries not discovered automatically
    binaries.extend([
        ('./venv/Lib/site-packages/PyQt5/Qt/bin/libeay32.dll', './PyQt5/Qt/bin'),
        ('./venv/Lib/site-packages/PyQt5/Qt/bin/ssleay32.dll', './PyQt5/Qt/bin')
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
                'NSHighResolutionCapable': 'True'
            },
            bundle_identifier=None)