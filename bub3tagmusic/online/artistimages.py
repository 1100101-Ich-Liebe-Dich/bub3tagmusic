"""Künstlerbilder – gespeichert als folder.jpg im Künstler-Ordner.

Quellen: Deezer (ohne Key) und TheAudioDB (öffentlicher Test-Key).
"""

from __future__ import annotations

from .base import CoverCandidate, OnlineError, RateLimiter, similarity
from .http import get_json

SOURCES = ("Deezer", "TheAudioDB")
DEEZER = "https://api.deezer.com/search/artist"
AUDIODB = "https://www.theaudiodb.com/api/v1/json/123/search.php"

DEEZER_LIMITER = RateLimiter(per_second=4)
AUDIODB_LIMITER = RateLimiter(per_second=0.5)      # Test-Key: höchstens 30 Anfragen/Minute


def from_deezer(artist: str) -> list[CoverCandidate]:
    data = get_json(DEEZER, {"q": artist, "limit": 8}, limiter=DEEZER_LIMITER)
    out = []
    for r in data.get("data", []):
        xl = r.get("picture_xl")
        # Deezer liefert für Künstler ohne Foto ein graues Platzhalterbild ("/artist//")
        if not xl or "/artist//" in xl:
            continue
        name = r.get("name", "")
        fans = r.get("nb_fan") or 0
        out.append(CoverCandidate("Deezer", xl, r.get("picture_medium") or xl, 1000, 1000,
                                  description=f"{name} · {fans:,} Fans".replace(",", "."),
                                  score=similarity(artist, name)))
    return out


def from_audiodb(artist: str) -> list[CoverCandidate]:
    data = get_json(AUDIODB, {"s": artist}, limiter=AUDIODB_LIMITER)
    out = []
    for a in data.get("artists") or []:
        name = a.get("strArtist", "")
        score = similarity(artist, name)
        for key, label in (("strArtistThumb", "Porträt"), ("strArtistFanart", "Fanart"),
                           ("strArtistFanart2", "Fanart"), ("strArtistWideThumb", "Breitbild")):
            url = a.get(key)
            if url:
                out.append(CoverCandidate("TheAudioDB", url, url + "/preview",
                                          description=f"{name} · {label}", score=score - (0 if key == "strArtistThumb" else 0.05)))
    return out


def search_artist_images(artist: str, sources=SOURCES, progress=lambda s, f, e: None) -> list[CoverCandidate]:
    funcs = {"Deezer": from_deezer, "TheAudioDB": from_audiodb}
    out: list[CoverCandidate] = []
    for src in sources:
        try:
            found = funcs[src](artist)
            out += found
            progress(src, found, "")
        except OnlineError as exc:
            progress(src, [], str(exc))
    out.sort(key=lambda c: -c.score)
    return out
