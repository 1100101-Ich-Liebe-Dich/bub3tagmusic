"""Cover-Suche über Cover Art Archive, iTunes und Deezer.

search_covers() liefert Kandidaten fürs Bildergitter (nur Vorschau-URLs).
Heruntergeladen wird das große Bild erst, wenn der Nutzer eins auswählt (download()).
Fällt eine Quelle aus, liefern die anderen trotzdem.
"""

from __future__ import annotations

from . import deezer
from .base import CoverCandidate, OnlineError, RateLimiter, match_score
from .http import get_image, get_json

SOURCES = ("Cover Art Archive", "iTunes", "Deezer")

CAA = "https://coverartarchive.org/"
ITUNES = "https://itunes.apple.com/search"
DEEZER = "https://api.deezer.com/search/album"

CAA_LIMITER = RateLimiter(per_second=2)
ITUNES_LIMITER = RateLimiter(per_second=1)       # iTunes erlaubt ca. 20 Anfragen/Minute
DEEZER_LIMITER = deezer.LIMITER           # eine gemeinsame Bremse für alle Deezer-Abrufe


def from_caa_release_group(rg_id: str, description: str = "", score: float = 0.0) -> list[CoverCandidate]:
    data = get_json(CAA + f"release-group/{rg_id}", limiter=CAA_LIMITER)
    out = []
    for img in data.get("images", []):
        if not img.get("front") and "Front" not in (img.get("types") or []):
            continue
        thumbs = img.get("thumbnails") or {}
        url = img.get("image", "")
        if url.startswith("http://"):
            url = "https://" + url[7:]
        thumb = thumbs.get("500") or thumbs.get("large") or thumbs.get("250") or url
        if thumb.startswith("http://"):
            thumb = "https://" + thumb[7:]
        out.append(CoverCandidate("Cover Art Archive", url, thumb, description=description, score=score,
                                  size_hint="Original"))
    return out


def from_caa(artist: str, album: str, contact: str = "") -> list[CoverCandidate]:
    from .musicbrainz import search_release_groups
    groups = [g for g in search_release_groups(artist, album, contact) if g["score"] >= 70][:2]
    out = []
    for g in groups:
        try:
            score = match_score(artist, album, g["artist"], g["title"])
            out += from_caa_release_group(g["id"], f"{g['title']} – {g['artist']}", score)
        except OnlineError:
            continue          # 404: zu dieser Release-Group gibt es kein Cover
    return out


def from_itunes(artist: str, album: str, country: str = "DE") -> list[CoverCandidate]:
    term = f"{artist} {album}".strip()
    data = get_json(ITUNES, {"term": term, "entity": "album", "media": "music", "limit": 12, "country": country},
                    limiter=ITUNES_LIMITER)
    out = []
    for r in data.get("results", []):
        art = r.get("artworkUrl100") or ""
        if "100x100" not in art:
            continue
        name, who = r.get("collectionName", ""), r.get("artistName", "")
        out.append(CoverCandidate(
            "iTunes", art.replace("100x100bb", "3000x3000bb"), art.replace("100x100bb", "400x400bb"),
            description=f"{name} – {who}", score=match_score(artist, album, who, name), size_hint="bis 3000 px"))
    return out


def from_deezer(artist: str, album: str) -> list[CoverCandidate]:
    q = f'artist:"{artist}" album:"{album}"' if artist.strip() else album
    data = get_json(DEEZER, {"q": q, "limit": 12}, limiter=DEEZER_LIMITER)
    if not data.get("data") and artist.strip():        # strenge Suche ohne Treffer → locker suchen
        data = get_json(DEEZER, {"q": f"{artist} {album}", "limit": 12}, limiter=DEEZER_LIMITER)
    out = []
    for r in data.get("data", []):
        xl = r.get("cover_xl") or r.get("cover_big")
        if not xl:
            continue
        name, who = r.get("title", ""), (r.get("artist") or {}).get("name", "")
        out.append(CoverCandidate("Deezer", xl, r.get("cover_medium") or r.get("cover_big") or xl,
                                  width=1000 if r.get("cover_xl") else 500,
                                  height=1000 if r.get("cover_xl") else 500,
                                  description=f"{name} – {who}", score=match_score(artist, album, who, name)))
    return out


def search_covers(artist: str, album: str, sources=SOURCES, *, contact: str = "", country: str = "DE",
                  progress=lambda source, found, error: None) -> list[CoverCandidate]:
    """Alle Quellen nacheinander; Fehler einer Quelle werden gemeldet, aber nicht geworfen."""
    funcs = {"Cover Art Archive": lambda: from_caa(artist, album, contact),
             "iTunes": lambda: from_itunes(artist, album, country),
             "Deezer": lambda: from_deezer(artist, album)}
    out: list[CoverCandidate] = []
    for src in sources:
        try:
            found = funcs[src]()
            out += found
            progress(src, found, "")
        except OnlineError as exc:
            progress(src, [], str(exc))
    out.sort(key=lambda c: -c.score)
    return out


def download(candidate: CoverCandidate) -> bytes:
    try:
        return get_image(candidate.url)
    except OnlineError:
        if candidate.source == "iTunes":          # 3000 px gibt es nicht immer → kleinere Größe
            return get_image(candidate.url.replace("3000x3000bb", "1400x1400bb"))
        raise


def thumbnail(candidate: CoverCandidate) -> bytes:
    return get_image(candidate.thumb_url or candidate.url)
