"""Muster wie '%track% - %artist% - %title%' (Baustein für Phase 2).

Die Grundfunktionen sind schon da und getestet; die Oberfläche
(Dialog mit Vorschau) kommt in Phase 2.
"""

from __future__ import annotations

import re

from .fields import FIELDS, split_number

PLACEHOLDER_RE = re.compile(r"%([a-z]+)%")
_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def sanitize_filename_part(text: str) -> str:
    """Zeichen ersetzen, die in Dateinamen Ärger machen."""
    text = _FORBIDDEN.sub("_", text)
    return text.strip().rstrip(".") or "_"


def format_from_tags(pattern: str, tags: dict, pad_track: int = 2) -> str:
    """'%track% - %title%' + Tags → '03 - Titel' (Tracknummer aufgefüllt)."""

    def repl(m: re.Match) -> str:
        key = m.group(1)
        value = tags.get(key, "")
        if key in ("track", "disc"):
            num, _ = split_number(value)
            if num.isdigit() and key == "track":
                return num.zfill(pad_track)
            return num
        return sanitize_filename_part(value) if value else ""

    return PLACEHOLDER_RE.sub(repl, pattern)


def parse_with_pattern(pattern: str, text: str) -> dict[str, str] | None:
    """Umkehrung: '03 - Titel' + '%track% - %title%' → {'track': '03', 'title': 'Titel'}.

    Gibt None zurück, wenn der Text nicht zum Muster passt.
    """
    known = {f.key for f in FIELDS}
    regex, names = "", []
    pos = 0
    for m in PLACEHOLDER_RE.finditer(pattern):
        regex += re.escape(pattern[pos:m.start()])
        key = m.group(1)
        if key in known and key not in names:
            regex += f"(?P<{key}>.+?)"
            names.append(key)
        else:
            regex += ".+?"
        pos = m.end()
    regex += re.escape(pattern[pos:])
    match = re.fullmatch(regex, text)
    if not match:
        return None
    return {k: v.strip() for k, v in match.groupdict().items()}
