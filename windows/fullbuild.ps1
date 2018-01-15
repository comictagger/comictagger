# Script to be run inside appveyor for a full build
$env:PATH="C:\tools\mingw64\bin;C:\Miniconda-x64;C:\Miniconda-x64\Scripts;$env:path"
choco install -y mingw
C:\Miniconda-x64\Scripts\conda create -y --name comictagger python=2
C:\Miniconda-x64\Scripts\activate comictagger
C:\Miniconda-x64\Scripts\conda install -y pyqt=4
C:\Miniconda-x64\Scripts\pip install -r .\requirements.txt
mingw32-make dist
objdump -af unrar/libunrar.so
