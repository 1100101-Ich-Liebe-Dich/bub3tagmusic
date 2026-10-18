"""Externe Hilfsprogramme (Phase 4): fpcalc (Fingerabdruck) und rsgain (ReplayGain).

Gesucht wird in dieser Reihenfolge:
  1. Umgebungsvariable BUB3_FPCALC / BUB3_RSGAIN (zum Testen oder für eigene Builds)
  2. mitgeliefert im AppImage ($BUB3_BIN bzw. $APPDIR/usr/bin) – wenn es dort startet
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
            "debian": "sudo apt install rsgain\n    (gibt es ab Ubuntu 24.04, Mint 22 und Debian 13)",
            "fedora": "sudo dnf install rsgain",
            "arch": "aus dem AUR: rsgain",
            "suse": "aus dem Packman-Repository: rsgain",
        },
        "download": "https://github.com/complexlogic/rsgain/releases",
    },
}


def _runnable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


_works: dict[str, bool] = {}


def _starts(path: str, name: str) -> bool:
    """Mitgeliefertes Programm einmal kurz starten – auf sehr alten Systemen (glibc < 2.30)
    läuft z. B. das mitgelieferte rsgain nicht, dann zählt das vom System."""
    if path not in _works:
        try:
            r = subprocess.run([path, "-version" if name == "fpcalc" else "--version"], capture_output=True,
                               timeout=10, stdin=subprocess.DEVNULL)
            _works[path] = r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _works[path] = False
    return _works[path]


def find_tool(name: str) -> str:
    env = os.environ.get(f"BUB3_{name.upper()}")
    if env:
        return env if _runnable(env) else ""
    for base in (os.environ.get("BUB3_BIN"), os.path.join(os.environ.get("APPDIR") or "/-", "usr", "bin")):
        if base:
            cand = os.path.join(base, name)
            if _runnable(cand) and _starts(cand, name):
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
