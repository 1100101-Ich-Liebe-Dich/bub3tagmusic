#!/usr/bin/env bash
# BuB3TAGMUSIC starten. Optional einen Ordner mitgeben: ./start.sh ~/Musik
cd "$(dirname "$(readlink -f "$0")")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m bub3tagmusic "$@"
fi
echo "Noch nicht installiert – bitte zuerst ./install.sh ausführen." >&2
exit 1
