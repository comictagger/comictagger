# Script to be run inside appveyor for a full build
$env:PATH="C:\Python36-x64;$env:path"
choco install -y mingw
C:\Miniconda-x64\Scripts\pip install -r .\requirements.txt
mingw32-make dist
