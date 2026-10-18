"""MusicBrainz – Album-Suche.

Ablauf (nach Wunsch des Auftraggebers sparsam):
  1. search_albums(artist, album) → EINE Anfrage, Liste von AlbumMatch (ohne Tracks)
  2. Nutzer wählt einen Treffer
  3. get_album(mbid)              → EINE weitere Anfrage mit allen Tracks
Höchstens 1 Anfrage pro Sekunde, eigener User-Agent (MusicBrainz-Regeln).
"""

from __future__ import annotations

import re

from .base import AlbumMatch, RateLimiter, TrackMatch, match_score
from .http import get_json

API = "https://musicbrainz.org/ws/2/"
CAA = "https://coverartarchive.org/"
LIMITER = RateLimiter(per_second=0.9)

_LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')


def _escape(text: str) -> str:
    return _LUCENE_SPECIAL.sub(r"\\\1", text.strip())


def credit(ac: list | None) -> str:
    """artist-credit → 'Künstler feat. Gast'."""
    out = ""
    for c in ac or []:
        name = c.get("name") or (c.get("artist") or {}).get("name", "")
        out += name + (c.get("joinphrase") or "")
    return out.strip()


def _label(info: list | None) -> str:
    for li in info or []:
        name = (li.get("label") or {}).get("name")
        if name:
            return name
    return ""


def _formats(media: list | None) -> str:
    counts: dict[str, int] = {}
    for m in media or []:
        f = m.get("format") or "?"
        counts[f] = counts.get(f, 0) + 1
    parts = [f"{n}×{f}" if n > 1 else f for f, n in counts.items() if f != "?"]
    return ", ".join(parts)


def _query(artist: str, album: str) -> str:
    q = f'release:"{_escape(album)}"'
    if artist.strip():
        q += f' AND artist:"{_escape(artist)}"'
    return q


def search_albums(artist: str, album: str, contact: str = "", limit: int = 15) -> list[AlbumMatch]:
    data = get_json(API + "release/", {"query": _query(artist, album), "fmt": "json", "limit": limit},
                    limiter=LIMITER, contact=contact)
    out = []
    for r in data.get("releases", []):
        rid = r.get("id", "")
        media = r.get("media") or []
        m = AlbumMatch(
            source="MusicBrainz", source_id=rid, album=r.get("title", ""),
            albumartist=credit(r.get("artist-credit")), year=(r.get("date") or "")[:4],
            label=_label(r.get("label-info")), country=r.get("country", "") or "",
            track_total=int(r.get("track-count") or sum(int(x.get("track-count") or 0) for x in media)),
            disc_total=max(1, len(media)), formats=_formats(media), score=int(r.get("score") or 0),
            cover_url=f"{CAA}release/{rid}/front-250",
            extra={"release_group": (r.get("release-group") or {}).get("id", ""),
                   "type": (r.get("release-group") or {}).get("primary-type", ""),
                   "status": r.get("status", "")},
        )
        # MusicBrainz-Score + eigene Ähnlichkeit (Schreibweisen, „The“, Klammern …)
        m.score = int(0.5 * m.score + 50 * match_score(artist, album, m.albumartist, m.album))
        out.append(m)
    out.sort(key=lambda m: (-m.score, m.extra.get("status") != "Official", m.year or "9999"))
    return out


def _genre(data: dict) -> str:
    genres = list(data.get("genres") or []) + list((data.get("release-group") or {}).get("genres") or [])
    if not genres:
        return ""
    best = max(genres, key=lambda g: g.get("count", 0))
    name = best.get("name", "")
    return " ".join(w[:1].upper() + w[1:] for w in name.split()) if name else ""


def get_album(mbid: str, contact: str = "") -> AlbumMatch:
    data = get_json(API + f"release/{mbid}",
                    {"inc": "recordings+artist-credits+labels+release-groups+genres", "fmt": "json"},
                    limiter=LIMITER, contact=contact)
    media = data.get("media") or []
    tracks = []
    for disc_no, medium in enumerate(media, 1):
        disc = int(medium.get("position") or disc_no)
        mtracks = medium.get("tracks") or []
        for i, t in enumerate(mtracks, 1):
            rec = t.get("recording") or {}
            length = t.get("length") or rec.get("length") or 0
            tracks.append(TrackMatch(
                position=int(t.get("position") or i), title=t.get("title") or rec.get("title", ""),
                artist=credit(t.get("artist-credit") or rec.get("artist-credit")) or credit(data.get("artist-credit")),
                length=(length or 0) / 1000.0, disc=disc, track_total=len(mtracks)))
    caa = data.get("cover-art-archive") or {}
    has_front = bool(caa.get("front"))
    return AlbumMatch(
        source="MusicBrainz", source_id=mbid, album=data.get("title", ""),
        albumartist=credit(data.get("artist-credit")), year=(data.get("date") or "")[:4],
        label=_label(data.get("label-info")), country=data.get("country", "") or "",
        genre=_genre(data), track_total=len(tracks), disc_total=max(1, len(media)), tracks=tracks,
        formats=_formats(media),
        cover_url=f"{CAA}release/{mbid}/front-250" if has_front else "",
        cover_full_url=f"{CAA}release/{mbid}/front" if has_front else "",
        extra={"release_group": (data.get("release-group") or {}).get("id", "")},
    )


def search_release_groups(artist: str, album: str, contact: str = "", limit: int = 5) -> list[dict]:
    """Für die Cover-Suche: passende Release-Groups (id, Titel, Künstler, Score)."""
    q = f'releasegroup:"{_escape(album)}"' + (f' AND artist:"{_escape(artist)}"' if artist.strip() else "")
    data = get_json(API + "release-group/", {"query": q, "fmt": "json", "limit": limit},
                    limiter=LIMITER, contact=contact)
    out = []
    for g in data.get("release-groups", []):
        out.append({"id": g.get("id", ""), "title": g.get("title", ""), "artist": credit(g.get("artist-credit")),
                    "score": int(g.get("score") or 0)})
    return out
