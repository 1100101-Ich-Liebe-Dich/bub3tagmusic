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

install() {   # $1 = Sekunden fürs Installieren, dann die Pakete
  local t=$1; shift
  step 150 apt-get "${APT[@]}" update -qq && step "$t" apt-get "${APT[@]}" install -y --no-install-recommends -o Dpkg::Progress-Fancy=0 "$@"
}

use_ubuntu_server() {
  # GitHubs Rechner holen Pakete über /etc/apt/apt-mirrors.txt (zuerst azure.archive.ubuntu.com).
  # Ist dieser Spiegel lahm, nur noch den offiziellen Ubuntu-Server benutzen.
  if [ -f /etc/apt/apt-mirrors.txt ]; then
    echo "http://archive.ubuntu.com/ubuntu/" | sudo tee /etc/apt/apt-mirrors.txt >/dev/null
  fi
  for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do
    [ -f "$f" ] && sudo sed -i -E 's#https?://[a-z.]*azure\.archive\.ubuntu\.com#http://archive.ubuntu.com#g' "$f"
  done
}

report() {   # report error|warning TEXT
  echo "::$1 title=apt ($2)::$(grep -v '^$' "$LOG" | tail -n 14 | cut -c1-140 | tr '\n' '|')"
}

: >"$LOG"
# Normal dauert das unter einer Minute – nach 3 Minuten lieber den Server wechseln
install 180 "$@" && { echo "Systempakete installiert ($SECONDS s)"; exit 0; }
report warning "erster Versuch"
echo "::warning::Paket-Spiegel von GitHub ist lahm – zweiter Versuch nur über archive.ubuntu.com"
use_ubuntu_server
install 420 "$@" && exit 0
report error "zweiter Versuch"
exit 1
