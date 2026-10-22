#!/usr/bin/env bash
# Systempakete auf GitHubs Rechnern installieren – robust gegen hängende Spiegel und langsame Trigger.
# Aufruf: .github/apt-install.sh paket1 paket2 …
# Im Fehlerfall stehen die letzten Zeilen von apt als Hinweis (::error::) im Lauf – die Logs selbst sind
# von der Arbeitsumgebung aus nicht lesbar, die Hinweise schon.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
APT=(-o Acquire::Retries=3 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20
     -o DPkg::Lock::Timeout=60 -o Dpkg::Use-Pty=0)
LOG=/tmp/apt-install.log

# Bekannte Bremse auf ubuntu-24.04: „Processing triggers for man-db“ dauert Minuten
sudo rm -f /var/lib/man-db/auto-update 2>/dev/null || true

step() {   # step SEKUNDEN befehl… – mit Zeitangabe ins Protokoll
  local t0=$SECONDS
  sudo --preserve-env=DEBIAN_FRONTEND timeout "$1" "${@:2}" >>"$LOG" 2>&1
  local rc=$?
  echo "== $(( SECONDS - t0 )) s, Rückgabe $rc: ${*:2:3}" >>"$LOG"
  return $rc
}

install() {
  step 150 apt-get "${APT[@]}" update -qq && step 360 apt-get "${APT[@]}" install -y -qq --no-install-recommends "$@"
}

report() {
  echo "::error title=apt ($1)::$(grep -v '^$' "$LOG" | tail -n 12 | cut -c1-160 | tr '\n' '|')"
}

: >"$LOG"
install "$@" && { echo "Systempakete installiert ($SECONDS s)"; exit 0; }
report "erster Versuch"
echo "::warning::Paket-Spiegel von GitHub hängt – zweiter Versuch über archive.ubuntu.com"
for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do
  [ -f "$f" ] && sudo sed -i -E 's#https?://[a-z.]*azure\.archive\.ubuntu\.com#http://archive.ubuntu.com#g' "$f"
done
install "$@" && exit 0
report "zweiter Versuch"
exit 1
