#!/usr/bin/env bash
# Alle Tests auf einmal – vor jedem Hochladen ausführen (läuft auch auf GitHub).
#
#   tests/run_all.sh          Kern + Oberfläche
#   tests/run_all.sh --perf   zusätzlich Leistungstest mit 1.000 Alben
#
# Braucht ffmpeg. Arbeitet nur in einem Temp-Ordner, fasst nichts anderes an.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && [ -z "${PYTHON:-}" ] && PY=.venv/bin/python

WORK="$(mktemp -d -t bub3tests.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
export XDG_CONFIG_HOME="$WORK/config" XDG_CACHE_HOME="$WORK/cache"
export QT_QPA_PLATFORM=offscreen
SHOTS="${SHOTS:-$WORK/shots}"

echo "== 1/4 Kern: alle Formate lesen/schreiben + Werkzeuge =="
"$PY" tests/test_core.py
"$PY" tests/test_tools.py

echo
echo "== 2/4 Test-Sammlung erzeugen =="
"$PY" tests/make_testfiles.py "$WORK/data" --collection 60

echo
echo "== 3/4 Oberfläche durchklicken =="
"$PY" tests/ui_smoke.py "$WORK/data/Musik" "$SHOTS" 2>&1 | grep -v propagateSizeHints
[ "${PIPESTATUS[0]}" -eq 0 ]

echo
echo "== 4/4 Werkzeuge bedienen (frische Sammlung) =="
"$PY" tests/make_testfiles.py "$WORK/tools" --collection 12 >/dev/null
"$PY" tests/ui_tools.py "$WORK/tools/Musik" "$SHOTS" 2>&1 | grep -v propagateSizeHints
[ "${PIPESTATUS[0]}" -eq 0 ]

if [ "${1:-}" = "--perf" ]; then
  echo
  echo "== Leistung: 1.000 Alben =="
  "$PY" tests/make_testfiles.py "$WORK/big" --collection 1000 --untagged >/dev/null
  "$PY" tests/perf.py "$WORK/big/Musik" 2>&1 | grep -v propagateSizeHints
fi

echo
echo "Screenshots: $SHOTS"
echo "ALLE TESTS OK"
