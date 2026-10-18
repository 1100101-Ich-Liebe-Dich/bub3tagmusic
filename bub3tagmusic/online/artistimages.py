"""Künstlerbilder (Phase 3) – gespeichert als folder.jpg im Künstler-Ordner.

Quellen: Deezer (ohne Key), optional TheAudioDB / fanart.tv.
"""

from __future__ import annotations

from .base import CoverCandidate


def search_artist_images(artist: str) -> list[CoverCandidate]:
    raise NotImplementedError("Kommt in Phase 3")
