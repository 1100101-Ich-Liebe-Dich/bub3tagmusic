"""iTunes / Apple Music – Album-Daten ohne Anmeldung (iTunes Search API).

Ablauf wie bei MusicBrainz:
  1. search_albums(artist, album) → EINE Suche (entity=album)
  2. get_album(collection_id)     → EINE Abfrage mit allen Tracks (lookup … entity=song)
Apple erlaubt grob 20 Anfragen pro Minute – die Bremse teilen sich Album- und Cover-Suche.

Stärken: genaue Trackliste mit Disc-Nummern, Erscheinungsdatum meist das der Erstveröffentlichung,
Cover bis 3000 px. Schwächen: Genre grob („Rock“), Titel tragen gern „(Remastered)“.
"""

from __future__ import annotations

from .base import AlbumMatch, RateLimiter, TrackMatch, match_score
from .http import get_json

SEARCH = "https://itunes.apple.com/search"
LOOKUP = "https://itunes.apple.com/lookup"
LIMITER = RateLimiter(per_second=1)


def artwork(url100: str, size: int) -> str:
    """artworkUrl100 (…/100x100bb.jpg) → gewünschte Größe."""
    return url100.replace("100x100bb", f"{size}x{size}bb") if "100x100bb" in (url100 or "") else (url100 or "")


def _album(r: dict) -> AlbumMatch:
    art = r.get("artworkUrl100") or ""
    explicit = r.get("collectionExplicitness") == "explicit"
    return AlbumMatch(
        source="iTunes", source_id=str(r.get("collectionId", "")), album=(r.get("collectionName") or "").strip(),
        albumartist=(r.get("artistName") or "").strip(), year=(r.get("releaseDate") or "")[:4],
        country=r.get("country", "") or "", genre=r.get("primaryGenreName", "") or "",
        track_total=int(r.get("trackCount") or 0), formats="Digital" + (" · explicit" if explicit else ""),
        cover_url=artwork(art, 250), cover_full_url=artwork(art, 3000),
        extra={"copyright": r.get("copyright", "")})


def search_albums(artist: str, album: str, country: str = "DE", limit: int = 25) -> list[AlbumMatch]:
    term = f"{artist} {album}".strip()
    data = get_json(SEARCH, {"term": term, "entity": "album", "media": "music", "limit": limit, "country": country},
                    limiter=LIMITER)
    out = []
    for r in data.get("results") or []:
        if r.get("wrapperType") not in (None, "collection"):
            continue
        m = _album(r)
        m.score = int(100 * match_score(artist, album, m.albumartist, m.album))
        out.append(m)
    out.sort(key=lambda m: -m.score)
    return out


def get_album(collection_id: str, country: str = "DE") -> AlbumMatch:
    from .base import OnlineError
    data = get_json(LOOKUP, {"id": collection_id, "entity": "song", "limit": 200, "country": country},
                    limiter=LIMITER)
    rows = data.get("results") or []
    coll = next((r for r in rows if r.get("wrapperType") == "collection"), None)
    if coll is None:
        raise OnlineError("iTunes kennt dieses Album nicht (mehr) – in einem anderen Land gibt es es vielleicht")
    m = _album(coll)
    songs = [r for r in rows if r.get("wrapperType") == "track" and r.get("kind") in (None, "song", "music-video")]
    tracks = []
    for r in songs:
        tracks.append(TrackMatch(
            position=int(r.get("trackNumber") or 0), title=(r.get("trackName") or "").strip(),
            artist=(r.get("artistName") or "").strip() or m.albumartist,
            length=(r.get("trackTimeMillis") or 0) / 1000.0, disc=int(r.get("discNumber") or 1),
            track_total=int(r.get("trackCount") or 0)))
    tracks.sort(key=lambda t: (t.disc, t.position))
    m.tracks = tracks
    m.track_total = len(tracks)
    m.disc_total = max([t.disc for t in tracks] or [1])
    return m
