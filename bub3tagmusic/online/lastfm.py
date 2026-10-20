"""Last.fm – Album-Daten (braucht einen kostenlosen API-Key: last.fm/api/account/create).

Ablauf:
  1. search_albums(artist, album, key) → EINE Suche (album.search)
  2. get_album(source_id, key)         → EINE Abfrage (album.getInfo) mit Trackliste und Tags

Stärken: Titel, Reihenfolge, Längen und gute Genres (die Tags der Hörer).
Kein Jahr (Last.fm kennt nur das Datum des Wiki-Textes), kein Label, nur eine Disc.
Bilder von Last.fm werden bewusst nicht benutzt.
"""

from __future__ import annotations

import re

from .base import AlbumMatch, OnlineError, RateLimiter, TrackMatch, match_score
from .http import ApiError, get_json

API = "https://ws.audioscrobbler.com/2.0/"
LIMITER = RateLimiter(per_second=2)
SEP = "␟"                       # trennt Interpret und Album in source_id

# Tags, die kein Genre sind
_NOT_GENRE = re.compile(r"^(\d{2,4}s?|seen live|albums i own|favou?rites?|favorite albums?|my .*|"
                        r"best .*|love|awesome|vinyl|cd|owned|under \d+ listeners|.*\bof (the )?\d{4}.*)$",
                        re.IGNORECASE)


def _key(key: str) -> str:
    if not key:
        raise OnlineError("Für Last.fm wird ein API-Key gebraucht – Einstellungen → Online → Last.fm-API-Key "
                          "(kostenlos unter last.fm/api/account/create)")
    return key


def _call(method: str, key: str, **params) -> dict:
    try:
        data = get_json(API, {"method": method, "api_key": _key(key), "format": "json", **params}, limiter=LIMITER)
    except ApiError as exc:                         # Last.fm meldet Fehler meist mit Status 400/403
        data = {"error": exc.code, "message": exc.message}
    err = data.get("error") if isinstance(data, dict) else None
    if err:
        if err in (10, 26):
            raise OnlineError("Last.fm-API-Key ungültig – in Einstellungen → Online prüfen")
        if err == 6:
            return {}
        if err == 29:
            raise OnlineError("Last.fm: zu viele Anfragen – kurz warten und noch einmal versuchen")
        raise OnlineError(f"Last.fm meldet einen Fehler: {data.get('message') or err}")
    return data


def _as_list(value) -> list:
    """Last.fm liefert bei genau einem Eintrag ein Objekt statt einer Liste."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def search_albums(artist: str, album: str, key: str, limit: int = 20) -> list[AlbumMatch]:
    data = _call("album.search", key, album=album, limit=limit)
    found = _as_list(((data.get("results") or {}).get("albummatches") or {}).get("album"))
    out = []
    for r in found:
        who, name = (r.get("artist") or "").strip(), (r.get("name") or "").strip()
        if not who or not name or name == "(null)":
            continue
        m = AlbumMatch(source="Last.fm", source_id=f"{who}{SEP}{name}", album=name, albumartist=who,
                       extra={"mbid": r.get("mbid", "")})
        m.score = int(100 * match_score(artist, album, who, name))
        out.append(m)
    out.sort(key=lambda m: -m.score)
    return out


def genre(tags: list) -> str:
    for t in tags:
        name = (t.get("name") or "").strip()
        if name and not _NOT_GENRE.match(name):
            return " ".join(w[:1].upper() + w[1:] for w in name.split())
    return ""


def get_album(source_id: str, key: str) -> AlbumMatch:
    who, _, name = source_id.partition(SEP)
    data = _call("album.getinfo", key, artist=who, album=name, autocorrect=1)
    a = data.get("album") or {}
    if not a:
        raise OnlineError("Last.fm kennt dieses Album nicht (mehr)")
    albumartist = (a.get("artist") or who).strip() if isinstance(a.get("artist"), str) else who
    tracks = []
    rows = _as_list((a.get("tracks") or {}).get("track"))
    for i, t in enumerate(rows, 1):
        rank = (t.get("@attr") or {}).get("rank") or i
        artist = t.get("artist")
        artist = (artist.get("name") if isinstance(artist, dict) else artist) or albumartist
        try:
            length = float(t.get("duration") or 0)
        except (TypeError, ValueError):
            length = 0.0
        tracks.append(TrackMatch(position=int(rank), title=(t.get("name") or "").strip(), artist=artist,
                                 length=length, disc=1, track_total=len(rows)))
    tracks.sort(key=lambda t: t.position)
    tags = _as_list((a.get("tags") or {}).get("tag"))
    return AlbumMatch(source="Last.fm", source_id=source_id, album=(a.get("name") or name).strip(),
                      albumartist=albumartist, genre=genre(tags), track_total=len(tracks), disc_total=1,
                      tracks=tracks, extra={"mbid": a.get("mbid", ""), "listeners": a.get("listeners", "")})
