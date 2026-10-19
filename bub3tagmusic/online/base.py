"""Gemeinsame Datentypen und Hilfen für alle Online-Quellen."""

from __future__ import annotations

import difflib
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field

from .. import APP_NAME, APP_VERSION, PRESENTER_URL


class OnlineError(Exception):
    """Verständliche Fehlermeldung für die Oberfläche."""


def user_agent(contact: str = "") -> str:
    """MusicBrainz verlangt einen aussagekräftigen User-Agent mit Kontakt."""
    return f"{APP_NAME}/{APP_VERSION} ( {contact or PRESENTER_URL} )"


class RateLimiter:
    """Wartet so lange, dass höchstens `per_second` Anfragen pro Sekunde rausgehen."""

    def __init__(self, per_second: float = 1.0):
        self.interval = 1.0 / per_second
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._last + self.interval - now
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


@dataclass
class TrackMatch:
    position: int
    title: str
    artist: str = ""
    length: float = 0.0          # Sekunden – zum Zuordnen der eigenen Dateien
    disc: int = 1
    track_total: int = 0         # Anzahl Tracks auf dieser Disc


@dataclass
class AlbumMatch:
    source: str                  # "MusicBrainz", "Discogs" …
    source_id: str
    album: str
    albumartist: str
    year: str = ""
    original_year: str = ""      # Erstveröffentlichung (MusicBrainz: Release-Group), sonst leer
    label: str = ""
    country: str = ""
    genre: str = ""
    track_total: int = 0
    disc_total: int = 1
    tracks: list[TrackMatch] = field(default_factory=list)
    cover_url: str = ""          # kleines Vorschaubild
    cover_full_url: str = ""     # Cover in voller Größe (zum Übernehmen)
    formats: str = ""            # "CD", "2×CD", "Digital Media", "Vinyl" …
    score: int = 0               # 0–100, wie gut der Treffer passt
    extra: dict = field(default_factory=dict)

    @property
    def details(self) -> str:
        parts = [self.year, self.country, self.label, self.formats,
                 f"{self.track_total} Tracks" if self.track_total else ""]
        return " · ".join(p for p in parts if p)


@dataclass
class CoverCandidate:
    source: str                  # "Cover Art Archive", "iTunes", "Deezer"
    url: str
    thumb_url: str = ""
    width: int = 0
    height: int = 0
    description: str = ""        # z. B. "Kurs Nord – Ankerplatz"
    score: float = 0.0           # Ähnlichkeit zur Suche (0–1)
    size_hint: str = ""          # wenn die Größe vorher unbekannt ist, z. B. "bis 3000 px"

    @property
    def size_text(self) -> str:
        if self.width and self.height:
            return f"{self.width} × {self.height}"
        return self.size_hint


# ----------------------------------------------------------------------
# Ähnlichkeit von Namen (für Sortierung der Treffer)
# ----------------------------------------------------------------------
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)          # (Remastered), [Deluxe]
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"^the\s+", "", text.strip())
    return " ".join(text.split())


# Zusätze von Neuauflagen: „(Remastered 2011)“, „ - 2011 Remaster“, „[Deluxe Edition]“ …
# Bewusst NICHT: Live, Acoustic, Remix, Demo, Single Version – das gehört zum Titel.
_EDITION_WORDS = (r"remaster(?:ed)?|deluxe|expanded|anniversary|bonus\s+tracks?|special\s+edition|"
                  r"collector'?s\s+edition|legacy\s+edition|super\s+deluxe")
_EDITION_BRACKET = re.compile(r"\s*[\(\[][^\(\)\[\]]*\b(?:" + _EDITION_WORDS + r")\b[^\(\)\[\]]*[\)\]]\s*$",
                              re.IGNORECASE)
_EDITION_DASH = re.compile(r"\s+[-–]\s+[^-–]*\b(?:" + _EDITION_WORDS + r")\b[^-–]*$", re.IGNORECASE)


def strip_edition(text: str) -> str:
    """'Come Together - Remastered 2009' → 'Come Together', 'Abbey Road (Super Deluxe Edition)' → 'Abbey Road'."""
    out = (text or "").strip()
    for _ in range(3):                      # „Titel (Deluxe Edition) [Remastered]“
        new = _EDITION_DASH.sub("", _EDITION_BRACKET.sub("", out)).strip()
        if new == out or not new:
            break
        out = new
    return out


def similarity(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_score(want_artist: str, want_album: str, artist: str, album: str) -> float:
    """0–1: wie gut passt ein Treffer zur Suche (Album zählt etwas mehr)."""
    if not want_artist:
        return similarity(want_album, album)
    return 0.45 * similarity(want_artist, artist) + 0.55 * similarity(want_album, album)


def seconds(text: str) -> float:
    """'4:05' → 245, '1:02:03' → 3723, '' → 0."""
    try:
        parts = [int(p) for p in (text or "").strip().split(":")]
    except ValueError:
        return 0.0
    total = 0
    for p in parts:
        total = total * 60 + p
    return float(total) if parts else 0.0
