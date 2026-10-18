#!/usr/bin/env bash
# Baut BuB3TAGMUSIC als AppImage: eine einzige ausführbare Datei.
#
#   packaging/build_appimage.sh        (oder einfach: make)
#
# Braucht nur: bash, curl, tar, ldd – alles andere (uv, Python, appimagetool)
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
for cmd in curl tar ldd; do
  command -v "$cmd" >/dev/null || { echo "Es fehlt das Programm '$cmd'." >&2; exit 1; }
done
mkdir -p "$TOOLS" "$DIST"

# --- Werkzeuge ------------------------------------------------------------------
say "Werkzeuge"
if command -v uv >/dev/null; then
  UV="$(command -v uv)"
else
  UV="$TOOLS/uv"
  if [ ! -x "$UV" ]; then
    echo "Lade uv (Python-Paketwerkzeug) …"
    curl -fsSL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz \
      | tar -xz -C "$TOOLS" --strip-components=1
  fi
fi
APPIMAGETOOL="$TOOLS/appimagetool-x86_64.AppImage"
RUNTIME="$TOOLS/runtime-x86_64"
if [ ! -x "$APPIMAGETOOL" ]; then
  echo "Lade appimagetool …"
  curl -fsSL -o "$APPIMAGETOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$APPIMAGETOOL"
fi
if [ ! -f "$RUNTIME" ]; then
  echo "Lade AppImage-Laufzeit …"
  curl -fsSL -o "$RUNTIME" https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64
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
