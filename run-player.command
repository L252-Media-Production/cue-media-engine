#!/usr/bin/env bash
# Cue Media Engine launcher for macOS. Double-click it in Finder, or run ./run-player.command
# Runs player.py from this folder. Creates the virtual environment if needed and installs
# requirements.txt only when that file changed since the last good install.
cd "$(dirname "$0")" || exit 1

pause() { if [ -t 0 ]; then echo; read -r -p "Press Enter to close..." _; fi; }
fail()  { echo; echo "$*"; pause; exit 1; }

PY=$(command -v python3) || fail "Python 3 was not found. Install it from https://www.python.org/downloads/ or with Homebrew: brew install python"
echo "Using: $PY ($("$PY" --version 2>&1))"

# --- virtual environment in .venv (inside this folder) ---
if [ ! -x ".venv/bin/python" ]; then
  echo "Creating the virtual environment..."
  "$PY" -m venv .venv || fail "Could not create the virtual environment."
fi

# --- requirements: only when requirements.txt changed since the last good install ---
if ! cmp -s requirements.txt .venv/requirements.installed; then
  echo "Installing / updating requirements..."
  if .venv/bin/python -m pip install --disable-pip-version-check --upgrade -r requirements.txt; then
    cp requirements.txt .venv/requirements.installed
  elif [ -f .venv/requirements.installed ]; then
    echo "WARNING: could not update the requirements. Starting with the packages already installed."
  else
    fail "Installing the requirements failed. Check the internet connection and try again."
  fi
fi

# --- the code lives in cpl/ and the web pages in static/; both must be deployed together with player.py ---
[ -f cpl/__init__.py ] || fail "The cpl folder is missing. Copy player.py, cpl and static together into this folder."
[ -f static/help.html ] || fail "The static folder is missing. Copy player.py, cpl and static together into this folder."

# --- run the player (caffeinate keeps the Mac from idle-sleeping while it runs) ---
echo
echo "Starting Cue Media Engine. Press Ctrl+C or close this window to stop it."
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -i .venv/bin/python player.py "$@"
else
  .venv/bin/python player.py "$@"
fi
rc=$?
echo
echo "The player stopped (exit code $rc)."
pause
exit $rc