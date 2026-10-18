"""Cover-Suche über Cover Art Archive, iTunes und Deezer (Phase 3).

Ergebnis: Liste von CoverCandidate für das Bildergitter. Herunterladen
passiert erst, wenn der Nutzer ein Bild auswählt. Gespeichert wird dann
über core.covers (cover.jpg im Album-Ordner und/oder eingebettet).
"""

from __future__ import annotations

from .base import CoverCandidate

SOURCES = ("Cover Art Archive", "iTunes", "Deezer")


def search_covers(artist: str, album: str, sources: tuple[str, ...] = SOURCES) -> list[CoverCandidate]:
    raise NotImplementedError("Kommt in Phase 3")


def download(candidate: CoverCandidate) -> bytes:
    raise NotImplementedError("Kommt in Phase 3")
