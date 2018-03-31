# Setup file for comictagger python source  (no wheels yet)
#
# The install process will attempt to compile the unrar lib from source.
# If it succeeds, the unrar lib binary will be installed with the python
# source.  If it fails, install will just continue.  On most Linux systems it
# should just work.  (Tested on a Mac system with homebrew, as well)
#
# An entry point script called "comictagger" will be created
#
# In addition, the install process will add some platform specfic files for 
# dekstop integration.  These files will reference the entry point script:
#   Linux: a "desktop" file in /usr/local/share/applications
#   Windows: a desktop shortcut on the installing user's desktop
#   Mac: an app bundle is put into /Applications  

from __future__ import print_function
from setuptools import setup
from setuptools import Command
import setuptools.command.build_py 
import setuptools.command.install
import subprocess
import os
import sys
import shutil
import platform
import tempfile

import comictaggerlib.ctversion

python_requires='>=3',

with open('requirements.txt') as f:
    required = f.read().splitlines()

if platform.system() in [ "Windows" ]:
    required.append("winshell")

# Always require PyQt5 on Windows and Mac
if platform.system() in [ "Windows", "Darwin" ]:
    required.append("PyQt5")

# Some files to install on different platforms
platform_data_files = []
if platform.system() == "Linux":
    platform_data_files = [("/usr/local/share/applications",
                                ["desktop-integration/linux/ComicTagger.desktop"]),
                           ("/usr/local/share/comictagger",
                                ["comictaggerlib/graphics/app.png"]),
                          ]
    
if platform.system() == "Windows":
    win_desktop_folder = os.path.join(os.environ["USERPROFILE"], "Desktop")
    win_appdata_folder = os.path.join(os.environ["APPDATA"], "comictagger")
    platform_data_files = [(win_desktop_folder,
                                ["desktop-integration/windows/ComicTagger-pip.lnk"]),
                           (win_appdata_folder,
                                ["windows/app.ico"]),
                          ]    

if platform.system() == "Darwin":
    mac_app_folder = "/Applications"
    ct_app_name = "ComicTagger-pip.app"
    platform_data_files = [(os.path.join(mac_app_folder, ct_app_name, "Contents"),
                                ["desktop-integration/mac/Info.plist"]),
                           (os.path.join(mac_app_folder, ct_app_name, "Contents/Resources"),
                                ["mac/app.icns"]),
                           (os.path.join(mac_app_folder, ct_app_name, "Contents/MacOS"),
                                ["desktop-integration/mac/main.sh",
                                 "desktop-integration/mac/ComicTagger"]),
                           ]   

def fileReplace(filename, token, newstring):
    with open(filename, "rt") as fin:
        fout = tempfile.NamedTemporaryFile(mode="wt")
        for line in fin:
            fout.write(line.replace('%%{}%%'.format(token), newstring))
        os.rename(fout.name, filename)
        # fix permissions of former temp file
        os.chmod(filename, 420) #Octal 0o644
    
class BuildUnrarCommand(Command):
    description = 'build unrar library' 
    user_options = []

    def initialize_options(self):
        pass
    def finalize_options(self):
        pass

    def run(self):
        try: 
            if not os.path.exists("comictaggerlib/libunrar.so"):
                if not os.path.exists("unrar/libunrar.so"):
                   print("Building C++ unrar library....")
                   subprocess.call(['make', '-C', 'unrar', 'lib'])
                print("Copying .so file to comictaggerlib folder")
                shutil.copyfile("unrar/libunrar.so", "comictaggerlib/libunrar.so")
        except Exception as e:
            print(e)
            print("WARNING ----  Unrar library build/deploy failed.  User will have to self-install libunrar.")

           
class BuildPyCommand(setuptools.command.build_py.build_py):
  """Custom build command."""

  def run(self):
    self.run_command('build_unrar')
    setuptools.command.build_py.build_py.run(self)

    # This is after the "build" is complete, but before the install process
    # We can now create/modify some files for desktop integration
    
    if platform.system() == "Windows":
        # doctor the shortcut for this windows system before deployment
        import winshell
        winshell.CreateShortcut(
          Path=os.path.abspath(r"desktop-integration\windows\ComicTagger-pip.lnk"),
          Target=os.path.join(self.distribution._x_script_dir, "comictagger.exe"),
          Icon=(os.path.join(win_appdata_folder, 'app.ico'), 0),
          Description="Launch ComicTagger as installed by PIP"
        )
        
    if platform.system() == "Linux":
        # doctor the script path in the desktop file
        fileReplace("desktop-integration/linux/ComicTagger.desktop",
                    "CTSCRIPT",
                    os.path.join(self.distribution._x_script_dir, "comictagger"))
        
    if platform.system() == "Darwin":
        # doctor the plist app version
        fileReplace("desktop-integration/mac/Info.plist",
                    "CTVERSION",
                    comictaggerlib.ctversion.version)
        # doctor the script path in main.sh
        fileReplace("desktop-integration/mac/main.sh",
                    "CTSCRIPT",
                    os.path.join(self.distribution._x_script_dir, "comictagger"))      
            
class customInstall(setuptools.command.install.install):
  """Custom install command."""

  def run(self):
    # save the install script folder for desktop integration stuff later
    self.distribution._x_script_dir = self.install_scripts
    print ("ATB script install folder = ", self.install_scripts)
    
    setuptools.command.install.install.run(self)
    
    # Final install step:
    if platform.system() == "Darwin":
        # Try to create a symlink to Python OS X app
        # find the python application; must be an OS X app
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
                   
        # create a link to the python app, but named to match the project
        apppath = os.path.abspath(os.path.join(mac_app_folder,ct_app_name))
        newpython =  os.path.join(apppath,"Contents","MacOS","ComicTagger")
        # remove the placeholder
        os.remove(newpython)
        if not punt:    
            os.symlink(pythonapp, newpython)
        else:
            # We failed, but we can still be functional
            os.symlink(sys.executable, newpython)
        
        # Lastly, make the launcher script executable
        launcher_script =  os.path.join(apppath,"Contents","MacOS","main.sh")
        os.chmod(launcher_script, 509) #Octal 0o775

    
setup(name="comictagger",
      install_requires=required,
      cmdclass={
        'build_unrar': BuildUnrarCommand,
        'build_py': BuildPyCommand,
        'install': customInstall,
        },
      version=comictaggerlib.ctversion.version,
      description="A cross-platform GUI/CLI app for writing metadata to comic archives",
      author="ComicTagger team",
      author_email="comictagger@gmail.com",
      url="https://github.com/davide-romanini/comictagger",
      download_url="https://pypi.python.org/packages/source/c/comictagger/comictagger-{0}.zip".format(comictaggerlib.ctversion.version),
      packages=["comictaggerlib", "comicapi"],
      package_data={
          'comictaggerlib': ['ui/*', 'graphics/*', '*.so'],
      },
      entry_points=dict(console_scripts=['comictagger=comictaggerlib.main:ctmain']),
      data_files=platform_data_files,
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
          "Programming Language :: Python",
          "Topic :: Utilities",
          "Topic :: Other/Nonlisted Topic",
          "Topic :: Multimedia :: Graphics"
      ],
      license="Apache License 2.0",

      long_description="""
ComicTagger is a multi-platform app for writing metadata to digital comics, written in Python and PyQt.

Features:

* Runs on Mac OSX, Microsoft Windows, and Linux systems
* Communicates with an online database (Comic Vine) for acquiring metadata
* Uses image processing to automatically match a given archive with the correct issue data
* Batch processing in the GUI for tagging hundreds or more comics at a time
* Reads and writes multiple tagging schemes ( ComicBookLover and ComicRack).
* Reads and writes RAR and Zip archives (external tools needed for writing RAR)
* Command line interface (CLI) on all platforms (including Windows), which supports batch operations, and which can be used in native scripts for complex operations.
* Can run without PyQt5 installed 
"""
      )
