@echo off
rem Cue Media Engine launcher for Windows.
rem Runs player.py from this folder. It creates the virtual environment if needed and installs
rem everything in requirements.txt when that file has changed since the last successful install.
rem If the install fails (for example when offline) it carries on with the packages already installed.
setlocal
cd /d "%~dp0"
title Cue Media Engine

rem --- find Python (the "py" launcher first, then python) ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python 3 was not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

echo Using:
%PY% --version

rem --- virtual environment in .venv (kept inside this folder) ---
if not exist ".venv\Scripts\python.exe" (
  echo Creating the virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment.
    pause
    exit /b 1
  )
)

rem --- requirements: only when requirements.txt changed since the last successful install ---
set "STAMP=.venv\requirements.installed"
if exist "%STAMP%" fc /b requirements.txt "%STAMP%" >nul 2>nul && goto deps_ok
echo Installing requirements...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade -r requirements.txt
if not errorlevel 1 (
  copy /y requirements.txt "%STAMP%" >nul
  goto deps_ok
)
rem pip failed (offline?). Carry on if the core packages are already there.
".venv\Scripts\python.exe" -c "import aiohttp, pygame, numpy, pythonosc" >nul 2>nul
if not errorlevel 1 (
  echo.
  echo Could not update the requirements (offline?). Continuing with the packages already installed.
  goto deps_ok
)
echo.
echo Installing the requirements failed. Check the internet connection and try again.
echo If it says a package "failed to build", send the Python version shown above.
pause
exit /b 1
:deps_ok

rem --- the app folders must be deployed together with player.py ---
if not exist "static\help.html" (
  echo The static folder is missing. Copy it next to player.py together with player.py.
  pause
  exit /b 1
)
if not exist "cpl\__init__.py" (
  echo The cpl folder is missing. Copy it next to player.py together with player.py and static.
  pause
  exit /b 1
)

rem --- run the player ---
echo.
echo Starting Cue Media Engine. Close this window or press Ctrl+C to stop it.
".venv\Scripts\python.exe" player.py %*
set "RC=%errorlevel%"
echo.
echo The player stopped (exit code %RC%).
pause
exit /b %RC%
