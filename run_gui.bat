@echo off
rem Launches Test_ODW.py without the xdw virtual environment (its python.exe points
rem to a Python 3.12 install that is not present). The library folders are restored
rem from git into %LOCALAPPDATA%\IQ_Streaming_ODW\lib the first time, then reused.
setlocal

cd /d "%~dp0"
set "LIB=%LOCALAPPDATA%\IQ_Streaming_ODW\lib"
set "ODW=%LIB%\xdw\Lib\site-packages\rsxdwstreaming\odw.py"

rem Make sure an activated venv does not override the system Python.
set "VIRTUAL_ENV="

set "NEEDS=1"
if exist "%ODW%" for %%A in ("%ODW%") do if %%~zA GTR 100 set "NEEDS="

if defined NEEDS (
  echo Restoring library files from git into %LIB% ...
  if not exist "%LIB%" mkdir "%LIB%"
  git archive --format=tar -o "%LIB%\lib.tar" HEAD -- xdw/Lib/site-packages/rsxdwstreaming xdw/Lib/site-packages/bitstring xdw/Lib/site-packages/pyqtgraph xdw/Lib/site-packages/colorama
  tar -xf "%LIB%\lib.tar" -C "%LIB%"
)

if not exist "%ODW%" (
  echo Could not restore the library files. Run this from a clone of the repo with git installed.
  exit /b 1
)

set "PYTHONPATH=%LIB%\xdw\Lib\site-packages"
py -3 Test_ODW.py
