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

echo "== 1/3 Kern: alle Formate lesen/schreiben =="
"$PY" tests/test_core.py

echo
echo "== 2/3 Test-Sammlung erzeugen =="
"$PY" tests/make_testfiles.py "$WORK/data" --collection 60

echo
echo "== 3/3 Oberfläche durchklicken =="
"$PY" tests/ui_smoke.py "$WORK/data/Musik" "$SHOTS" 2>&1 | grep -v propagateSizeHints
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
