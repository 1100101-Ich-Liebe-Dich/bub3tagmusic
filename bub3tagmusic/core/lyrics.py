"""Songtexte: Begleitdateien (.lrc/.txt) finden und lesen, Zeitmarken entfernen.

Ohne Qt – die Oberfläche (ui/lyrics.py) nutzt nur diese Funktionen.
Eingebettet wird immer der ungetaktete Songtext (ID3 USLT, Vorbis LYRICS …);
die Zeitmarken einer .lrc-Datei ([01:23.45]) werden dabei entfernt.
"""

from __future__ import annotations

import os
import re

COMPANION_EXTS = (".lrc", ".txt")
MAX_BYTES = 256 * 1024            # größere „Songtexte“ sind keine

_TIME = re.compile(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]")
_WORD_TIME = re.compile(r"<\d{1,3}:\d{2}(?:[.:]\d{1,3})?>")
_META = re.compile(r"^\s*\[(?:ar|ti|al|au|by|length|offset|re|ve|tool|#)\s*:[^\]]*\]\s*$", re.IGNORECASE)


def normalize(text: str) -> str:
    """Einheitliche Zeilenenden, keine Leerzeilen am Anfang/Ende, Zeilen ohne Leerzeichen am Ende."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("﻿", "")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def is_lrc(text: str) -> bool:
    return bool(_TIME.search(text or ""))


def strip_lrc(text: str) -> str:
    """LRC → reiner Text: Kopfzeilen ([ar:…]) weg, Zeitmarken weg, Leerzeilen bleiben (Strophen)."""
    out = []
    for line in normalize(text).split("\n"):
        if _META.match(line):
            continue
        line = _WORD_TIME.sub("", _TIME.sub("", line)).strip()
        out.append(line)
    # mehrere Leerzeilen hintereinander → eine
    cleaned: list[str] = []
    for line in out:
        if not line and cleaned and not cleaned[-1]:
            continue
        cleaned.append(line)
    return normalize("\n".join(cleaned))


def read_text(path: str) -> str:
    """Textdatei lesen – UTF-8 (mit/ohne BOM), sonst Windows-1252 (alte Songtext-Dateien)."""
    with open(path, "rb") as fh:
        data = fh.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Die Datei ist zu groß für einen Songtext.")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace")


def load(path: str) -> str:
    """Songtext aus .lrc/.txt – Zeitmarken werden entfernt."""
    text = read_text(path)
    return strip_lrc(text) if is_lrc(text) else normalize(text)


def companion(audio_path: str, listing: list[str] | None = None) -> str:
    """Gleichnamige .lrc/.txt neben der Audiodatei („01 - Titel.lrc“), Groß/klein egal. Sonst ''.

    listing: Dateinamen des Ordners (spart bei vielen Dateien das wiederholte Auflisten).
    """
    folder, name = os.path.split(audio_path)
    stem = os.path.splitext(name)[0].casefold()
    if listing is None:
        try:
            listing = os.listdir(folder)
        except OSError:
            return ""
    by_name = {n.casefold(): n for n in listing}
    for ext in COMPANION_EXTS:
        hit = by_name.get(stem + ext)
        if hit and os.path.isfile(os.path.join(folder, hit)):
            return os.path.join(folder, hit)
    return ""


def companions(paths: list[str]) -> dict[str, str]:
    """{audio_pfad: begleitdatei} für alle Dateien, die eine haben (jeder Ordner nur einmal gelistet)."""
    listings: dict[str, list[str]] = {}
    out = {}
    for p in paths:
        d = os.path.dirname(p)
        if d not in listings:
            try:
                listings[d] = os.listdir(d)
            except OSError:
                listings[d] = []
        c = companion(p, listings[d])
        if c:
            out[p] = c
    return out


def line_count(text: str) -> int:
    return sum(1 for line in (text or "").splitlines() if line.strip())
