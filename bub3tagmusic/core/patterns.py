"""Muster wie '%track% - %artist% - %title%'.

* parse_with_pattern / tags_from_path:  Text bzw. Dateipfad → Tags
  (Ordnerebenen mit '/', z. B. '%artist%/%year% - %album%/%track% - %title%')
* format_from_tags:                     Tags → Dateiname

Platzhalter sind die Feldnamen aus core/fields.py. %dummy% (oder jeder andere
unbekannte Name) steht für einen Teil, der übersprungen wird.
"""

from __future__ import annotations

import os
import re

from .fields import FIELDS, split_number

PLACEHOLDER_RE = re.compile(r"%([a-z]+)%")
KNOWN = {f.key for f in FIELDS if not f.multiline}
SKIP_NAMES = {"dummy", "skip", "egal"}

# Unter Linux sind nur '/' und NUL verboten. Für USB-Sticks, Autoradios (FAT32)
# und Windows-Freigaben sind aber auch diese Zeichen tabu:
_WINDOWS_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_LINUX_FORBIDDEN = re.compile(r"[/\x00]")


def placeholders(pattern: str) -> list[str]:
    return PLACEHOLDER_RE.findall(pattern)


def unknown_placeholders(pattern: str) -> list[str]:
    return [p for p in placeholders(pattern) if p not in KNOWN and p not in SKIP_NAMES]


def sanitize_filename_part(text: str, windows_safe: bool = True, replacement: str = "_") -> str:
    """Zeichen ersetzen, die in Dateinamen Ärger machen."""
    rx = _WINDOWS_FORBIDDEN if windows_safe else _LINUX_FORBIDDEN
    text = rx.sub(replacement, text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().rstrip(".") or ("_" if text else "")


def format_from_tags(pattern: str, tags: dict, pad_track: int = 2, windows_safe: bool = True,
                     replacement: str = "_") -> str:
    """'%track% - %title%' + Tags → '03 - Titel' (Tracknummer aufgefüllt)."""

    def repl(m: re.Match) -> str:
        key = m.group(1)
        value = tags.get(key, "")
        if key in ("track", "disc"):
            num, _ = split_number(value)
            if num.isdigit() and key == "track" and pad_track > 0:
                return num.zfill(pad_track)
            return sanitize_filename_part(num, windows_safe, replacement) if num else ""
        return sanitize_filename_part(value, windows_safe, replacement) if value else ""

    return PLACEHOLDER_RE.sub(repl, pattern)


def _pattern_regex(pattern: str) -> tuple[re.Pattern, list[str]]:
    regex, names, pos = "", [], 0
    for m in PLACEHOLDER_RE.finditer(pattern):
        regex += re.escape(pattern[pos:m.start()])
        key = m.group(1)
        if key in KNOWN and key not in names:
            regex += f"(?P<{key}>[^/]+?)"
            names.append(key)
        else:
            regex += "[^/]+?"
        pos = m.end()
    regex += re.escape(pattern[pos:])
    return re.compile(regex), names


def parse_with_pattern(pattern: str, text: str) -> dict[str, str] | None:
    """'03 - Titel' + '%track% - %title%' → {'track': '03', 'title': 'Titel'}.

    Gibt None zurück, wenn der Text nicht zum Muster passt.
    """
    rx, _ = _pattern_regex(pattern)
    match = rx.fullmatch(text)
    if not match:
        return None
    return {k: v.strip() for k, v in match.groupdict().items()}


def path_subject(path: str, pattern: str) -> str | None:
    """Der Teil des Pfads, auf den das Muster passen soll.

    Ohne '/' im Muster: nur der Dateiname (ohne Endung).
    Mit einem '/': Ordner/Dateiname, mit zwei: Ordner/Ordner/Dateiname usw.
    """
    levels = pattern.strip("/").count("/") + 1
    stem = os.path.splitext(path)[0]
    parts = [p for p in stem.split(os.sep) if p]
    if len(parts) < levels:
        return None
    return "/".join(parts[-levels:])


def tags_from_path(path: str, pattern: str) -> dict[str, str] | None:
    pattern = pattern.strip().strip("/")
    subject = path_subject(path, pattern)
    if subject is None:
        return None
    return parse_with_pattern(pattern, subject)
