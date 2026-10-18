"""Externe Hilfsprogramme (Phase 4): fpcalc (Fingerabdruck) und rsgain (ReplayGain).

Gesucht wird in dieser Reihenfolge:
  1. Umgebungsvariable BUB3_FPCALC / BUB3_RSGAIN (zum Testen oder für eigene Builds)
  2. mitgeliefert im AppImage ($APPDIR/usr/bin)
  3. im System (PATH)

Fehlt ein Programm, gibt install_hint() eine passende Anleitung für die
Distribution zurück.
"""

from __future__ import annotations

import os
import shutil
import subprocess

TOOLS = {
    "fpcalc": {
        "what": "fpcalc (Chromaprint) berechnet den Audio-Fingerabdruck",
        "packages": {
            "debian": "sudo apt install libchromaprint-tools",
            "fedora": "sudo dnf install chromaprint-tools",
            "arch": "sudo pacman -S chromaprint",
            "suse": "sudo zypper install chromaprint-fpcalc",
        },
        "download": "https://acoustid.org/chromaprint",
    },
    "rsgain": {
        "what": "rsgain misst die Lautheit und schreibt ReplayGain-Tags",
        "packages": {
            "debian": "sudo apt install rsgain   (ab Ubuntu 24.04 / Mint 22 / Debian 13)",
            "fedora": "sudo dnf install rsgain",
            "arch": "aus dem AUR: rsgain",
            "suse": "aus dem Packman-Repository: rsgain",
        },
        "download": "https://github.com/complexlogic/rsgain/releases",
    },
}


def find_tool(name: str) -> str:
    env = os.environ.get(f"BUB3_{name.upper()}")
    if env:
        return env if os.access(env, os.X_OK) else ""
    appdir = os.environ.get("APPDIR")
    if appdir:
        cand = os.path.join(appdir, "usr", "bin", name)
        if os.access(cand, os.X_OK):
            return cand
    return shutil.which(name) or ""


def tool_version(name: str) -> str:
    exe = find_tool(name)
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, "-version" if name == "fpcalc" else "--version"], capture_output=True, text=True,
                           timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    import re
    text = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", text)
    return m.group(1) if m else "?"


def distro_family(os_release: str = "/etc/os-release") -> str:
    """debian | fedora | arch | suse | '' (unbekannt)."""
    try:
        text = open(os_release, encoding="utf-8").read().lower()
    except OSError:
        return ""
    ids = []
    for line in text.splitlines():
        if line.startswith(("id=", "id_like=")):
            ids += line.split("=", 1)[1].strip().strip('"').split()
    for fam, keys in (("debian", ("debian", "ubuntu", "linuxmint", "mint", "pop", "elementary", "zorin")),
                      ("fedora", ("fedora", "rhel", "centos", "rocky", "almalinux", "nobara")),
                      ("arch", ("arch", "manjaro", "endeavouros", "garuda", "cachyos")),
                      ("suse", ("suse", "opensuse", "opensuse-leap", "opensuse-tumbleweed"))):
        if any(i in keys for i in ids):
            return fam
    return ""


def install_hint(name: str, family: str | None = None) -> str:
    """Kurze, verständliche Anleitung (mehrzeilig) – passend zur Distribution."""
    info = TOOLS[name]
    family = distro_family() if family is None else family
    lines = [f"{info['what']}, ist aber nicht installiert."]
    if family and family in info["packages"]:
        lines.append(f"Installieren im Terminal:\n    {info['packages'][family]}")
    else:
        lines.append("Installieren über die Paketverwaltung, z. B.:")
        lines += [f"    {cmd}" for cmd in info["packages"].values()]
    lines.append(f"Oder herunterladen: {info['download']}")
    lines.append("Das fertige AppImage (make) bringt es schon mit.")
    return "\n".join(lines)
