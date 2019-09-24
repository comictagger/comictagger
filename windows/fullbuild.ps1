# Script to be run inside appveyor for a full build
choco install -y mingw zip
refreshenv
$env:PATH="C:\Python36-x64;$env:path"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r .\requirements.txt
mingw32-make dist
