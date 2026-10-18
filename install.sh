#!/usr/bin/env bash
# BuB3TAGMUSIC installieren – präsentiert von www.BAUENUNDBOOTEN.de
#
# Legt eine eigene Python-Umgebung im Programmordner an (.venv),
# installiert die Bibliotheken und trägt das Programm ins Startmenü ein.
# Es wird nichts systemweit verändert.
set -e
cd "$(dirname "$(readlink -f "$0")")"
APP_DIR="$(pwd)"

echo "== BuB3TAGMUSIC – Installation =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 fehlt. Bitte installieren, z. B.:"
  echo "  Debian/Ubuntu/Mint:  sudo apt install python3 python3-venv python3-pip"
  echo "  Fedora:              sudo dnf install python3"
  echo "  Arch/Manjaro:        sudo pacman -S python"
  exit 1
fi

PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Python $PYV ist zu alt – mindestens 3.10 wird gebraucht."
  exit 1
fi
echo "Python $PYV gefunden."

if [ ! -d .venv ]; then
  echo "Lege Programm-Umgebung an (.venv) …"
  if ! python3 -m venv .venv 2>/dev/null; then
    echo "Das Modul 'venv' fehlt. Debian/Ubuntu/Mint:  sudo apt install python3-venv"
    exit 1
  fi
fi

echo "Installiere Bibliotheken (Qt, mutagen, Pillow, Icons) – das kann ein paar Minuten dauern …"
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt

chmod +x start.sh

# Startmenü-Eintrag
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/bub3tagmusic.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=BuB3TAGMUSIC
GenericName=Musik-Tagger
Comment=Musik-Tags und Cover bearbeiten – präsentiert von www.BAUENUNDBOOTEN.de
Exec="$APP_DIR/start.sh" %f
Icon=$APP_DIR/bub3tagmusic/resources/bub3tagmusic.svg
Terminal=false
Categories=AudioVideo;Audio;Qt;
Keywords=tag;tagger;mp3;flac;cover;id3;musik;
MimeType=inode/directory;
StartupWMClass=bub3tagmusic
EOF
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true

# Qt braucht unter X11 libxcb-cursor0 – nur Hinweis, keine Installation
if [ "${XDG_SESSION_TYPE:-}" = "x11" ] && command -v ldconfig >/dev/null 2>&1; then
  if ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor.so.0; then
    echo
    echo "Hinweis: Für Qt unter X11 fehlt evtl. libxcb-cursor0."
    echo "  Debian/Ubuntu/Mint:  sudo apt install libxcb-cursor0"
    echo "  Fedora:              sudo dnf install xcb-util-cursor"
  fi
fi

echo
echo "Fertig! Starten über das Startmenü (BuB3TAGMUSIC) oder mit:"
echo "  $APP_DIR/start.sh"
