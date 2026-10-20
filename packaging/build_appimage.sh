#!/usr/bin/env bash
# Baut BuB3TAGMUSIC als AppImage: eine einzige ausführbare Datei.
#
#   packaging/build_appimage.sh        (oder einfach: make)
#
# Braucht nur: bash, tar, ldd und curl ODER wget – alles andere (uv, Python, appimagetool)
# wird beim ersten Mal nach build/tools geladen. Ergebnis: dist/BuB3TAGMUSIC-<version>-x86_64.AppImage
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
ROOT="$(pwd)"
BUILD="$ROOT/build"
TOOLS="$BUILD/tools"
APPDIR="$BUILD/AppDir"
DIST="$ROOT/dist"
PYVER="${PYVER:-3.12}"
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' bub3tagmusic/__init__.py)"
OUT="$DIST/BuB3TAGMUSIC-$VERSION-x86_64.AppImage"

say() { printf '\n== %s\n' "$*"; }

if [ "$(uname -m)" != "x86_64" ]; then
  echo "Nur x86_64 (64-Bit-PC) wird unterstützt – Qt 6 gibt es nicht für 32 Bit." >&2
  exit 1
fi
for cmd in tar ldd; do
  command -v "$cmd" >/dev/null || { echo "Es fehlt das Programm '$cmd'." >&2; exit 1; }
done
# Herunterladen mit curl, sonst wget (Ubuntu hat oft nur wget)
if command -v curl >/dev/null && [ -z "${BUB3_USE_WGET:-}" ]; then
  fetch() { curl -fsSL -o "$1" "$2"; }
elif command -v wget >/dev/null; then
  fetch() { wget -q -O "$1" "$2"; }
else
  echo "Zum Herunterladen fehlt curl oder wget:  sudo apt install curl" >&2
  exit 1
fi
mkdir -p "$TOOLS" "$DIST"

# --- Werkzeuge ------------------------------------------------------------------
say "Werkzeuge"
if command -v uv >/dev/null; then
  UV="$(command -v uv)"
else
  UV="$TOOLS/uv"
  if [ ! -x "$UV" ]; then
    echo "Lade uv (Python-Paketwerkzeug) …"
    fetch "$TOOLS/uv.tar.gz" https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz
    tar -xzf "$TOOLS/uv.tar.gz" -C "$TOOLS" --strip-components=1
    rm -f "$TOOLS/uv.tar.gz"
  fi
fi
APPIMAGETOOL="$TOOLS/appimagetool-x86_64.AppImage"
RUNTIME="$TOOLS/runtime-x86_64"
if [ ! -x "$APPIMAGETOOL" ]; then
  echo "Lade appimagetool …"
  fetch "$APPIMAGETOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$APPIMAGETOOL"
fi
if [ ! -f "$RUNTIME" ]; then
  echo "Lade AppImage-Laufzeit …"
  fetch "$RUNTIME" https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64
fi
echo "uv: $("$UV" --version)"

# --- Python ---------------------------------------------------------------------
say "Eigenes Python $PYVER (läuft ab glibc 2.17)"
export UV_PYTHON_INSTALL_DIR="$TOOLS/python"
"$UV" python install "$PYVER" >/dev/null
PYSRC="$(ls -d "$UV_PYTHON_INSTALL_DIR"/cpython-"$PYVER".*-linux-x86_64-gnu | sort -V | tail -1)"
echo "$(basename "$PYSRC")"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/fallback"
cp -a "$PYSRC" "$APPDIR/usr/python"
PY="$APPDIR/usr/python/bin/python3"
SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"

# --- Bibliotheken + Programm --------------------------------------------------------
say "Bibliotheken (Qt, mutagen, Pillow, Icons)"
"$UV" pip install --quiet --python "$PY" --break-system-packages --link-mode copy -r packaging/requirements-appimage.txt
"$PY" - "$SITE" <<'PYEOF'
import shutil, sys, os
dst = os.path.join(sys.argv[1], "bub3tagmusic")
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree("bub3tagmusic", dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
PYEOF
cp packaging/libs/*.so.* "$APPDIR/usr/lib/fallback/"
mkdir -p "$APPDIR/usr/share/doc/bub3tagmusic"
cp -r packaging/libs/copyright "$APPDIR/usr/share/doc/bub3tagmusic/xcb-libs"
cp bub3tagmusic/resources/fonts/OFL-*.txt "$APPDIR/usr/share/doc/bub3tagmusic/"
cp LICENSE "$APPDIR/usr/share/doc/bub3tagmusic/LICENSE-GPL-3.0.txt"

# --- Hilfsprogramme ---------------------------------------------------------------------
# fpcalc (Fingerabdruck: Erkennen, Duplikate) und rsgain (ReplayGain) – beide als fertige,
# eigenständige Programme der Hersteller. Prüfsumme muss stimmen. Ohne Internet oder mit
# BUB3_NO_HELPERS=1 geht es ohne weiter; dann nutzt BuB3TAGMUSIC die Programme des Systems.
say "Hilfsprogramme (fpcalc, rsgain)"
mkdir -p "$APPDIR/usr/bin" "$TOOLS/helpers"
helper() {  # name url sha256
  local name="$1" url="$2" sha="$3" file tmp bin
  file="$TOOLS/helpers/$(basename "$url")"
  if [ ! -f "$file" ] || ! echo "$sha  $file" | sha256sum -c --status 2>/dev/null; then
    fetch "$file" "$url" || { echo "$name: nicht geladen – geht ohne weiter"; rm -f "$file"; return 0; }
  fi
  if ! echo "$sha  $file" | sha256sum -c --status 2>/dev/null; then
    echo "$name: Prüfsumme stimmt nicht – lasse es weg"; rm -f "$file"; return 0
  fi
  tmp="$(mktemp -d)"
  tar -xf "$file" -C "$tmp"
  bin="$(find "$tmp" -type f -name "$name" | head -1)"
  install -m 755 "$bin" "$APPDIR/usr/bin/$name"
  rm -rf "$tmp"
  echo "$name: $(du -h "$APPDIR/usr/bin/$name" | cut -f1)"
}
if [ -z "${BUB3_NO_HELPERS:-}" ] && command -v sha256sum >/dev/null; then
  helper fpcalc \
    https://github.com/acoustid/chromaprint/releases/download/v1.5.1/chromaprint-fpcalc-1.5.1-linux-x86_64.tar.gz \
    4d7433a7f778e5946d7225230681cbcd634e153316ecac87c538c33ac32387a5
  helper rsgain \
    https://github.com/complexlogic/rsgain/releases/download/v3.8/rsgain-3.8-Linux.tar.xz \
    4939de3b2022a50edc0751343b10a791ea8c1c9ca6505012f21413bf8de365a0
  cat > "$APPDIR/usr/share/doc/bub3tagmusic/HILFSPROGRAMME.txt" <<'TXT'
Mitgelieferte Hilfsprogramme (unverändert, wie von den Herstellern veröffentlicht):

fpcalc 1.5.1 – Chromaprint, https://acoustid.org/chromaprint
  Lizenz: LGPL 2.1 (enthält FFmpeg, LGPL). Quelltext: https://github.com/acoustid/chromaprint

rsgain 3.8 – https://github.com/complexlogic/rsgain
  Lizenz: BSD 2-Clause (enthält FFmpeg, libebur128, TagLib). Quelltext: siehe Link.
TXT
fi

# --- Verschlanken + vorkompilieren ---------------------------------------------------
say "Verschlanken"
"$PY" packaging/prune.py "$APPDIR"
# Vorkompilieren: das AppImage ist schreibgeschützt, Python könnte .pyc sonst nie ablegen
"$PY" -m compileall -q -j 0 "$APPDIR/usr/python/lib" >/dev/null || true

# --- AppImage-Rahmen ---------------------------------------------------------------
say "AppImage zusammensetzen"
install -m 755 packaging/AppRun "$APPDIR/AppRun"
cp packaging/bub3tagmusic.desktop "$APPDIR/"
cp bub3tagmusic/resources/bub3tagmusic.svg "$APPDIR/bub3tagmusic.svg"
cp bub3tagmusic/resources/bub3tagmusic.svg "$APPDIR/.DirIcon"
mkdir -p "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp packaging/bub3tagmusic.desktop "$APPDIR/usr/share/applications/"
cp bub3tagmusic/resources/bub3tagmusic.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
echo "$(du -sh "$APPDIR" | cut -f1) entpackt"

rm -f "$OUT"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --no-appstream --runtime-file "$RUNTIME" \
  --comp zstd "$APPDIR" "$OUT" >"$BUILD/appimagetool.log" 2>&1 || { cat "$BUILD/appimagetool.log"; exit 1; }
chmod +x "$OUT"

say "Fertig"
echo "$OUT ($(du -h "$OUT" | cut -f1))"
echo "Starten: Doppelklick oder  $OUT  [MUSIKORDNER]"
