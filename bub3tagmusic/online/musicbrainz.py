"""MusicBrainz – Album-Suche (Phase 3).

Ablauf (geplant):
  1. search_albums(artist, album)  → EINE Anfrage, Liste von AlbumMatch (ohne Tracks)
  2. Nutzer wählt einen Treffer
  3. get_album(mbid)               → EINE weitere Anfrage mit allen Tracks
  4. Zuordnung zu den eigenen Dateien über Tracknummer bzw. Länge, Vorschau, Übernahme
"""

from __future__ import annotations

from .base import AlbumMatch, RateLimiter

API = "https://musicbrainz.org/ws/2/"
LIMITER = RateLimiter(per_second=1.0)


def search_albums(artist: str, album: str, contact: str = "") -> list[AlbumMatch]:
    raise NotImplementedError("Kommt in Phase 3")


def get_album(mbid: str, contact: str = "") -> AlbumMatch:
    raise NotImplementedError("Kommt in Phase 3")
