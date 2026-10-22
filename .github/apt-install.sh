#!/usr/bin/env bash
# Systempakete auf GitHubs Rechnern installieren – robust gegen einen hängenden Paket-Spiegel.
# Aufruf: .github/apt-install.sh paket1 paket2 …
set -uo pipefail
APT=(-o Acquire::Retries=3 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20)

install() {
  sudo timeout 180 apt-get "${APT[@]}" update -qq &&
  sudo timeout 420 apt-get "${APT[@]}" install -y -qq --no-install-recommends "$@"
}

install "$@" && exit 0
echo "::warning::Paket-Spiegel von GitHub hängt – zweiter Versuch über archive.ubuntu.com"
for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list; do
  [ -f "$f" ] && sudo sed -i -E 's#https?://[a-z.]*azure\.archive\.ubuntu\.com#http://archive.ubuntu.com#g' "$f"
done
install "$@"
