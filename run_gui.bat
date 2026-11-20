@echo off
rem Launches Test_ODW.py with the system Python. The libraries ship in this repo under
rem xdw\Lib\site-packages, so a fresh clone runs with no extra download.
setlocal
cd /d "%~dp0"

rem Ignore an activated virtual environment so "py -3" is the system Python.
set "VIRTUAL_ENV="

set "SITE=xdw\Lib\site-packages"
set "ODW=%SITE%\rsxdwstreaming\odw.py"

set "NEEDS=1"
if exist "%ODW%" for %%A in ("%ODW%") do if %%~zA GTR 100 set "NEEDS="

if defined NEEDS (
  echo Library files are missing or empty. Restoring them from git...
  git rev-parse --is-inside-work-tree >nul 2>&1
  if errorlevel 1 (
    echo This folder is not a git checkout, and the bundled libraries are missing.
    echo Clone the repo again, then run run_gui.bat from that folder.
    exit /b 1
  )
  git checkout HEAD -- xdw/Lib/site-packages/rsxdwstreaming xdw/Lib/site-packages/bitstring xdw/Lib/site-packages/pyqtgraph xdw/Lib/site-packages/colorama
  if errorlevel 1 (
    echo Could not restore the library files from git.
    exit /b 1
  )
)

if not exist "%ODW%" (
  echo Could not find %ODW%. Clone the repo again and run run_gui.bat.
  exit /b 1
)

set "PYTHONPATH=%CD%\%SITE%"
py -3 Test_ODW.py
