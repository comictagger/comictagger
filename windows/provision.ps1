# This script should be run into an admin PowerShell to install all required
# packages needed for building comictagger on windows
#
# NOTE: this script has not been fully tested on a fresh windows VM.
#
# install chocolatey
Set-ExecutionPolicy Bypass -Scope Process -Force; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
choco install -y git mingw miniconda
$env:PATH+=";C:\ProgramData\Miniconda2\Scripts;C:\ProgramData\Miniconda2"
$env:PATH+=";C:\tools\mingw64\bin"
conda create -y --name comictagger python=2