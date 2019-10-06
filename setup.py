# Setup file for comictagger python source  (no wheels yet)
#
# An entry point script called "comictagger" will be created
#
# Currently commented out, an experiment at desktop integration.
# It seems that post installation tweaks are broken by wheel files.
# Kept here for further research

from __future__ import print_function
from setuptools import setup
from setuptools import dist
from setuptools import Command
import setuptools.command.build_py 
import setuptools.command.install
import subprocess
import os
import sys
import shutil
import platform
import tempfile

python_requires='>=3',

with open('requirements.txt') as f:
    required = f.read().splitlines()

with open('README.md') as f:
    long_description = f.read()

platform_data_files = []

"""
if platform.system() in [ "Windows" ]:
    required.append("winshell")

# Some files to install on different platforms

if platform.system() == "Linux":
    linux_desktop_shortcut = "/usr/local/share/applications/ComicTagger.desktop"
    platform_data_files = [("/usr/local/share/applications",
                                ["desktop-integration/linux/ComicTagger.desktop"]),
                           ("/usr/local/share/comictagger",
                                ["comictaggerlib/graphics/app.png"]),
                          ]
    
if platform.system() == "Windows":
    win_desktop_folder = os.path.join(os.environ["USERPROFILE"], "Desktop")
    win_appdata_folder = os.path.join(os.environ["APPDATA"], "comictagger")
    win_desktop_shortcut = os.path.join(win_desktop_folder, "ComicTagger-pip.lnk")
    platform_data_files = [(win_desktop_folder,
                                ["desktop-integration/windows/ComicTagger-pip.lnk"]),
                           (win_appdata_folder,
                                ["windows/app.ico"]),
                          ]    

if platform.system() == "Darwin":
    mac_app_folder = "/Applications"
    ct_app_name = "ComicTagger-pip.app"
    mac_app_infoplist = os.path.join(mac_app_folder, ct_app_name, "Contents", "Info.plist")
    mac_app_main = os.path.join(mac_app_folder, ct_app_name, "MacOS", "main.sh")
    mac_python_link = os.path.join(mac_app_folder, ct_app_name, "MacOS", "ComicTagger")
    platform_data_files = [(os.path.join(mac_app_folder, ct_app_name, "Contents"),
                                ["desktop-integration/mac/Info.plist"]),
                           (os.path.join(mac_app_folder, ct_app_name, "Contents/Resources"),
                                ["mac/app.icns"]),
                           (os.path.join(mac_app_folder, ct_app_name, "Contents/MacOS"),
                                ["desktop-integration/mac/main.sh",
                                 "desktop-integration/mac/ComicTagger"]),
                           ]   

def fileTokenReplace(filename, token, replacement):
    with open(filename, "rt") as fin:
        fd, tmpfile = tempfile.mkstemp()
        with open(tmpfile, "wt") as fout:
            for line in fin:
                fout.write(line.replace('%%{}%%'.format(token), replacement))
    os.close(fd)
    # fix permissions of temp file
    os.chmod(tmpfile, 420) #Octal 0o644
    os.rename(tmpfile, filename)

def postInstall(scripts_folder):
    entry_point_script = os.path.join(scripts_folder, "comictagger")
    
    if platform.system() == "Windows":
        # doctor the shortcut for this windows system after deployment
        import winshell
        winshell.CreateShortcut(
          Path=os.path.abspath(win_desktop_shortcut),
          Target=entry_point_script + ".exe",
          Icon=(os.path.join(win_appdata_folder, 'app.ico'), 0),
          Description="Launch ComicTagger as installed by PIP"
        )
        
    if platform.system() == "Linux":
        # doctor the script path in the desktop file
        fileTokenReplace(linux_desktop_shortcut,
                    "CTSCRIPT",
                    entry_point_script)
        
    if platform.system() == "Darwin":
        # doctor the plist app version
        fileTokenReplace(mac_app_infoplist,
                    "CTVERSION",
                    comictaggerlib.ctversion.version)
        # doctor the script path in main.sh
        fileTokenReplace(mac_app_main,
                    "CTSCRIPT",    
                    entry_point_script)
        # Make the launcher script executable
        os.chmod(mac_app_main, 509) #Octal 0o775
        
        # Final install step: create a symlink to Python OS X application
        punt = False
        pythonpath,top = os.path.split(os.path.realpath(sys.executable))
        while top:
            if 'Resources' in pythonpath:
                pass
            elif os.path.exists(os.path.join(pythonpath,'Resources')):
                break
            pythonpath,top = os.path.split(pythonpath)
        else:
            print("Failed to find a Resources directory associated with ", str(sys.executable))
            punt = True
        
        if not punt:
            pythonapp = os.path.join(pythonpath, 'Resources','Python.app','Contents','MacOS','Python')
            if not os.path.exists(pythonapp): 
                print("Failed to find a Python app in ", str(pythonapp))
                punt = True
                   
        # remove the placeholder
        os.remove(mac_python_link)
        if not punt:    
            os.symlink(pythonapp, mac_python_link)
        else:
            # We failed, but we can still be functional
            os.symlink(sys.executable, mac_python_link) 
"""

setup(name="comictagger",
      install_requires=required,
      description="A cross-platform GUI/CLI app for writing metadata to comic archives",
      author="ComicTagger team",
      author_email="comictagger@gmail.com",
      url="https://github.com/comictagger/comictagger",      
      packages=["comictaggerlib", "comicapi"],
      package_data={
          'comictaggerlib': ['ui/*', 'graphics/*'],
      },
      entry_points=dict(console_scripts=['comictagger=comictaggerlib.main:ctmain']),
      data_files=platform_data_files,
      setup_requires=[
        "setuptools_scm"
      ],
      use_scm_version={
          'write_to': 'comictaggerlib/ctversion.py'
      },
      classifiers=[
            "Development Status :: 4 - Beta",
            "Environment :: Console",
            "Environment :: Win32 (MS Windows)",
            "Environment :: MacOS X",
            "Environment :: X11 Applications :: Qt",
            "Intended Audience :: End Users/Desktop",
            "License :: OSI Approved :: Apache Software License",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
            "Topic :: Utilities",
            "Topic :: Other/Nonlisted Topic",
            "Topic :: Multimedia :: Graphics"
      ],
      keywords=['comictagger', 'comics', 'comic', 'metadata', 'tagging', 'tagger'],
      license="Apache License 2.0",
      long_description=long_description,
      long_description_content_type="text/markdown"
)
