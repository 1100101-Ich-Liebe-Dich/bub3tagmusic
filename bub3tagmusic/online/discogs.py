"""Discogs – zweite Quelle für Album-Daten.

Die Suche braucht einen persönlichen Token (Einstellungen → Online → Discogs-Token).
Mit Token sind 60 Anfragen pro Minute erlaubt.
"""

from __future__ import annotations

import re

from .base import AlbumMatch, OnlineError, RateLimiter, TrackMatch, match_score, seconds
from .http import get_json

API = "https://api.discogs.com/"
LIMITER = RateLimiter(per_second=0.9)

_NUMBER_SUFFIX = re.compile(r"\s+\(\d+\)$")          # "Nirvana (2)" → "Nirvana"
_DISC_POS = re.compile(r"^(?:CD|DVD|Disc|Disk)?\s*(\d+)\s*[-.]\s*(\d+)[a-z]?$", re.IGNORECASE)
_SIDE_POS = re.compile(r"^([A-Z])(\d*)$")


def _clean_name(name: str) -> str:
    return _NUMBER_SUFFIX.sub("", (name or "").strip()).rstrip("*").strip()


def artists_text(artists: list | None) -> str:
    out = ""
    for a in artists or []:
        out += _clean_name(a.get("anv") or a.get("name", ""))
        join = (a.get("join") or "").strip()
        out += f" {join} " if join and join != "," else (", " if join == "," else "")
    return " ".join(out.split()).strip(" ,")


def _headers(token: str) -> dict:
    if not token:
        raise OnlineError("Für Discogs wird ein Token gebraucht – Einstellungen → Online → Discogs-Token")
    return {"Authorization": f"Discogs token={token}"}


def search_albums(artist: str, album: str, token: str, limit: int = 15) -> list[AlbumMatch]:
    params = {"type": "release", "release_title": album, "per_page": limit}
    if artist.strip():
        params["artist"] = artist
    data = get_json(API + "database/search", params, headers=_headers(token), limiter=LIMITER)
    out = []
    for r in data.get("results", []):
        title = r.get("title", "")
        a, _, t = title.partition(" - ")
        if not t:
            a, t = "", title
        labels = r.get("label") or []
        formats = r.get("format") or []
        m = AlbumMatch(
            source="Discogs", source_id=str(r.get("id", "")), album=t.strip(), albumartist=_clean_name(a),
            year=str(r.get("year") or ""), label=labels[0] if labels else "", country=r.get("country", "") or "",
            formats=", ".join(formats[:2]), cover_url=r.get("thumb") or "", cover_full_url=r.get("cover_image") or "",
            extra={"master": r.get("master_id")})
        m.score = int(100 * match_score(artist, album, m.albumartist, m.album))
        out.append(m)
    out.sort(key=lambda m: -m.score)
    return out


def parse_tracklist(tracklist: list | None, album_artist: str) -> list[TrackMatch]:
    """Discogs-Positionen ('1', 'A1', '2-05', 'CD1.3', …) → Disc + fortlaufende Nummer."""
    flat = []
    for t in tracklist or []:
        kind = t.get("type_", "track")
        if kind == "heading":
            continue
        if kind == "index":
            flat.extend(st for st in (t.get("sub_tracks") or []) if st.get("type_", "track") == "track")
            continue
        flat.append(t)
    tracks: list[TrackMatch] = []
    counters: dict[int, int] = {}
    for t in flat:
        pos = (t.get("position") or "").strip()
        disc = 1
        m = _DISC_POS.match(pos)
        if m:
            disc = int(m.group(1))
        counters[disc] = counters.get(disc, 0) + 1
        tracks.append(TrackMatch(position=counters[disc], title=(t.get("title") or "").strip(),
                                 artist=artists_text(t.get("artists")) or album_artist,
                                 length=seconds(t.get("duration") or ""), disc=disc))
    # Discs neu durchnummerieren (1, 2, …) falls Discogs z. B. nur „2-“ benutzt
    order = sorted(counters)
    remap = {d: i for i, d in enumerate(order, 1)}
    for t in tracks:
        t.disc = remap[t.disc]
        t.track_total = counters[order[t.disc - 1]]
    return tracks


def get_album(release_id: str, token: str = "") -> AlbumMatch:
    headers = {"Authorization": f"Discogs token={token}"} if token else {}
    data = get_json(API + f"releases/{release_id}", headers=headers, limiter=LIMITER)
    albumartist = artists_text(data.get("artists"))
    tracks = parse_tracklist(data.get("tracklist"), albumartist)
    images = data.get("images") or []
    primary = next((i for i in images if i.get("type") == "primary"), images[0] if images else {})
    labels = data.get("labels") or []
    genres = list(data.get("genres") or [])
    formats = data.get("formats") or []
    fmt = ", ".join(f"{f.get('qty', '1')}×{f.get('name', '')}" if str(f.get("qty", "1")) != "1"
                    else f.get("name", "") for f in formats)
    return AlbumMatch(
        source="Discogs", source_id=str(release_id), album=(data.get("title") or "").strip(),
        albumartist=albumartist, year=str(data.get("year") or "") if data.get("year") else
        (data.get("released") or "")[:4], label=_clean_name(labels[0].get("name", "")) if labels else "",
        country=data.get("country", "") or "", genre=genres[0] if genres else "", tracks=tracks,
        track_total=len(tracks), disc_total=max([t.disc for t in tracks] or [1]), formats=fmt,
        cover_url=primary.get("uri150") or "", cover_full_url=primary.get("uri") or "",
        extra={"styles": data.get("styles") or []},
    )
