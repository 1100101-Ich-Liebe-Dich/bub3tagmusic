"""Discogs – zweite Quelle für Album-Daten (Phase 3).

Braucht einen persönlichen Token (Einstellungen → Online → Discogs-Token).
Erlaubt sind 60 Anfragen pro Minute mit Token.
"""

from __future__ import annotations

from .base import AlbumMatch, RateLimiter

API = "https://api.discogs.com/"
LIMITER = RateLimiter(per_second=1.0)


def search_albums(artist: str, album: str, token: str) -> list[AlbumMatch]:
    raise NotImplementedError("Kommt in Phase 3")


def get_album(release_id: str, token: str) -> AlbumMatch:
    raise NotImplementedError("Kommt in Phase 3")
