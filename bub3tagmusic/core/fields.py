"""Einheitliche Tag-Felder.

Jedes Format (ID3, Vorbis, MP4, APE, ASF) wird auf diese Feldnamen
abgebildet. Neue Felder werden hier ergänzt und in core/tags.py den
Formaten zugeordnet – die Oberfläche übernimmt sie dann automatisch.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    # Platzhalter-Name für Muster wie %artist% (Phase 2)
    pattern: str
    numeric: bool = False
    multiline: bool = False   # Songtext: eigenes Fenster statt Zeile, nicht in Mustern/Dateinamen


FIELDS: tuple[Field, ...] = (
    Field("title", "Titel", "%title%"),
    Field("artist", "Interpret", "%artist%"),
    Field("albumartist", "Albuminterpret", "%albumartist%"),
    Field("album", "Album", "%album%"),
    Field("year", "Jahr", "%year%", numeric=True),
    Field("track", "Track", "%track%", numeric=True),
    Field("disc", "Disc", "%disc%", numeric=True),
    Field("genre", "Genre", "%genre%"),
    Field("composer", "Komponist", "%composer%"),
    Field("comment", "Kommentar", "%comment%"),
    # 1.1
    Field("label", "Label", "%label%"),
    Field("originalyear", "Original-Jahr", "%originalyear%", numeric=True),
    Field("lyrics", "Songtext", "%lyrics%", multiline=True),
)

FIELD_KEYS: tuple[str, ...] = tuple(f.key for f in FIELDS)
FIELD_BY_KEY: dict[str, Field] = {f.key: f for f in FIELDS}
# Felder für Muster (%title% …) – ohne mehrzeilige wie den Songtext
PATTERN_KEYS: tuple[str, ...] = tuple(f.key for f in FIELDS if not f.multiline)

# Häufige Genres für die Auswahlliste im Bearbeitungsfeld
COMMON_GENRES: tuple[str, ...] = (
    "Alternative", "Ambient", "Blues", "Chanson", "Classical", "Country",
    "Dance", "Deutschrock", "Disco", "Drum & Bass", "Electronic", "Folk",
    "Funk", "Hip-Hop", "House", "Indie", "Jazz", "Latin", "Metal", "Pop",
    "Punk", "R&B", "Rap", "Reggae", "Rock", "Schlager", "Soul", "Soundtrack",
    "Techno", "Trance", "Volksmusik", "World",
)


def split_number(value: str) -> tuple[str, str]:
    """'3/12' -> ('3', '12'), '3' -> ('3', '')."""
    value = (value or "").strip()
    if "/" in value:
        a, b = value.split("/", 1)
        return a.strip(), b.strip()
    return value, ""


def join_number(num: str, total: str) -> str:
    num, total = (num or "").strip(), (total or "").strip()
    if num and total:
        return f"{num}/{total}"
    if total:
        return f"/{total}"
    return num


def number_sort_key(value: str) -> tuple[int, str]:
    """Sortiert '2' vor '10' und lässt leere Werte nach hinten fallen."""
    num, _ = split_number(value)
    digits = "".join(ch for ch in num if ch.isdigit())
    if digits:
        return (int(digits), value)
    return (10**9, value)


def one_line(text: str, limit: int = 300) -> str:
    """Mehrzeiligen Text (Songtext) für Tabellen einzeilig zeigen: 'Zeile 1 / Zeile 2 / …'."""
    if not text or "\n" not in text:
        return text
    out = " / ".join(line.strip() for line in text.splitlines() if line.strip())
    return out if len(out) <= limit else out[:limit].rstrip() + " …"
