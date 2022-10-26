# -*- mode: python ; coding: utf-8 -*-

import platform

from comictaggerlib import ctversion

enable_console = False
block_cipher = None


a = Analysis(
    ["comictagger.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

exe_binaries = []
exe_zipfiles = []
exe_datas = []
exe_exclude_binaries = True

coll_binaries = a.binaries
coll_zipfiles = a.zipfiles
coll_datas = a.datas

if platform.system() in ["Windows"]:
    enable_console = True
    exe_binaries = a.binaries
    exe_zipfiles = a.zipfiles
    exe_datas = a.datas
    exe_exclude_binaries = False

    coll_binaries = []
    coll_zipfiles = []
    coll_datas = []


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    exe_binaries,
    exe_zipfiles,
    exe_datas,
    [],
    exclude_binaries=exe_exclude_binaries,
    name="comictagger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=enable_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="windows/app.ico",
)
if platform.system() not in ["Windows"]:
    coll = COLLECT(
        exe,
        coll_binaries,
        coll_zipfiles,
        coll_datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="comictagger",
    )
    app = BUNDLE(
        coll,
        name="ComicTagger.app",
        icon="mac/app.icns",
        info_plist={
            "NSHighResolutionCapable": "True",
            "NSPrincipalClass": "NSApplication",
            "NSRequiresAquaSystemAppearance": "False",
            "CFBundleDisplayName": "ComicTagger",
            "CFBundleShortVersionString": ctversion.version,
            "CFBundleVersion": ctversion.version,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeRole": "Viewer",
                    "LSItemContentTypes": [
                        "com.rarlab.rar-archive",
                    ],
                    "CFBundleTypeName": "RAR Archive",
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Default",
                },
                {
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Default",
                    "LSItemContentTypes": [
                        "public.folder",
                    ],
                    "CFBundleTypeName": "Folder",
                },
                {
                    "CFBundleTypeExtensions": [
                        "cbz",
                    ],
                    "LSTypeIsPackage": False,
                    "NSPersistentStoreTypeKey": "Binary",
                    "CFBundleTypeIconSystemGenerated": True,
                    "CFBundleTypeName": "ZIP Comic Archive",
                    # 'CFBundleTypeIconFile': 'cbz',
                    "LSItemContentTypes": [
                        "public.zip-comic-archive",
                        "com.simplecomic.cbz-archive",
                        "com.macitbetter.cbz-archive",
                        "public.cbz-archive",
                        "cx.c3.cbz-archive",
                        "com.yacreader.yacreader.cbz",
                        "com.milke.cbz-archive",
                        "com.bitcartel.comicbooklover.cbz",
                        "public.archive.cbz",
                    ],
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Default",
                },
                {
                    "CFBundleTypeExtensions": [
                        "cb7",
                    ],
                    "LSTypeIsPackage": False,
                    "NSPersistentStoreTypeKey": "Binary",
                    "CFBundleTypeIconSystemGenerated": True,
                    "CFBundleTypeName": "7-Zip Comic Archive",
                    # 'CFBundleTypeIconFile': 'cb7',
                    "LSItemContentTypes": [
                        "com.simplecomic.cb7-archive",
                        "public.cb7-archive",
                        "com.macitbetter.cb7-archive",
                        "cx.c3.cb7-archive",
                        "org.7-zip.7-zip-comic-archive",
                    ],
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Default",
                },
                {
                    "CFBundleTypeExtensions": [
                        "cbr",
                    ],
                    "LSTypeIsPackage": False,
                    "NSPersistentStoreTypeKey": "Binary",
                    "CFBundleTypeIconSystemGenerated": True,
                    "CFBundleTypeName": "RAR Comic Archive",
                    # 'CFBundleTypeIconFile': 'cbr',
                    "LSItemContentTypes": [
                        "com.rarlab.rar-comic-archive",
                        "com.simplecomic.cbr-archive",
                        "com.macitbetter.cbr-archive",
                        "public.cbr-archive",
                        "cx.c3.cbr-archive",
                        "com.bitcartel.comicbooklover.cbr",
                        "com.milke.cbr-archive",
                        "public.archive.cbr",
                        "com.yacreader.yacreader.cbr",
                    ],
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Default",
                },
            ],
            "UTImportedTypeDeclarations": [
                {
                    "UTTypeIdentifier": "com.rarlab.rar-archive",
                    "UTTypeDescription": "RAR Archive",
                    "UTTypeConformsTo": [
                        "public.data",
                        "public.archive",
                    ],
                    "UTTypeTagSpecification": {
                        "public.mime-type": [
                            "application/x-rar",
                            "application/x-rar-compressed",
                        ],
                        "public.filename-extension": [
                            "rar",
                        ],
                    },
                },
                {
                    # 'UTTypeIcons': {
                    #     'UTTypeIconText': 'cbr',
                    #     'UTTypeIconBackgroundName': comic-fill
                    # }
                    "UTTypeConformsTo": [
                        "public.data",
                        "public.archive",
                        "com.rarlab.rar-archive",
                    ],
                    # 'UTTypeIconFile': 'cbr',
                    "UTTypeIdentifier": "com.rarlab.rar-comic-archive",
                    "UTTypeDescription": "RAR Comic Archive",
                    "UTTypeTagSpecification": {
                        "public.mime-type": [
                            "application/vnd.comicbook-rar",
                            "application/x-cbr",
                        ],
                        "public.filename-extension": [
                            "cbr",
                        ],
                    },
                },
                {
                    # 'UTTypeIcons': {
                    #     'UTTypeIconText': 'cbz',
                    #     'UTTypeIconBackgroundName': 'comic-fill',
                    # }
                    "UTTypeConformsTo": [
                        "public.data",
                        "public.archive",
                        "public.zip-archive",
                    ],
                    # 'UTTypeIconFile': cbz,
                    "UTTypeIdentifier": "public.zip-comic-archive",
                    "UTTypeDescription": "ZIP Comic Archive",
                    "UTTypeTagSpecification": {
                        "public.filename-extension": [
                            "cbz",
                        ],
                    },
                },
                {
                    # 'UTTypeIcons': {
                    #     'UTTypeIconText': 'cb7',
                    #     'UTTypeIconBackgroundName': comic-fill
                    # }
                    "UTTypeConformsTo": [
                        "public.data",
                        "public.archive",
                        "org.7-zip.7-zip-archive",
                    ],
                    # 'UTTypeIconFile': cb7
                    "UTTypeIdentifier": "org.7-zip.7-zip-comic-archive",
                    "UTTypeDescription": "7-Zip Comic Archive",
                    "UTTypeTagSpecification": {
                        "public.mime-type": [
                            "application/vnd.comicbook+7-zip",
                            "application/x-cb7-compressed",
                        ],
                        "public.filename-extension": [
                            "cb7",
                        ],
                    },
                },
            ],
        },
        bundle_identifier=None,
    )
