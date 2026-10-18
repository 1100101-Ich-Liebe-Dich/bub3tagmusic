"""Gemeinsame Datentypen und Hilfen für alle Online-Quellen."""

from __future__ import annotations

import threading
import time
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


@dataclass
class AlbumMatch:
    source: str                  # "MusicBrainz", "Discogs" …
    source_id: str
    album: str
    albumartist: str
    year: str = ""
    label: str = ""
    country: str = ""
    genre: str = ""
    track_total: int = 0
    disc_total: int = 1
    tracks: list[TrackMatch] = field(default_factory=list)
    cover_url: str = ""
    score: int = 0               # 0–100, wie gut der Treffer passt


@dataclass
class CoverCandidate:
    source: str                  # "Cover Art Archive", "iTunes", "Deezer"
    url: str
    thumb_url: str = ""
    width: int = 0
    height: int = 0
    description: str = ""
