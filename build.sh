#!/usr/bin/env sh
# BuB3TAGMUSIC – präsentiert von www.BAUENUNDBOOTEN.de
#
# Baut die ausführbare Datei (AppImage) – für alle, die lieber ein Skript starten als make:
#
#   sh build.sh            bauen  →  dist/BuB3TAGMUSIC-<version>-x86_64.AppImage
#   sh build.sh --install  bauen und ins Startmenü eintragen (~/.local/bin)
#
# Braucht nur bash, tar und curl oder wget. Python, Qt & Co. lädt das Bauskript selbst.
set -e
cd "$(dirname "$0")"
bash packaging/build_appimage.sh
if [ "${1:-}" = "--install" ]; then
  if command -v make >/dev/null 2>&1; then
    make install
  else
    mkdir -p "$HOME/.local/bin"
    cp dist/BuB3TAGMUSIC-*-x86_64.AppImage "$HOME/.local/bin/BuB3TAGMUSIC.AppImage"
    chmod +x "$HOME/.local/bin/BuB3TAGMUSIC.AppImage"
    echo "Kopiert nach ~/.local/bin/BuB3TAGMUSIC.AppImage – im Programm: ⚙ → Ins Startmenü eintragen"
  fi
fi
