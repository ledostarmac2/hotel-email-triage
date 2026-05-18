#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-server.txt
python -m pip install -e .
python run_desktop.py
