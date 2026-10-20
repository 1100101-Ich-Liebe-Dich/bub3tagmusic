"""Cover-Suche über Cover Art Archive, iTunes, TheAudioDB und Bandcamp.

Deezer liefert bewusst keine Cover mehr (nur noch Album-Daten) – deren Bilder sind nicht zum
Weiterverwenden gedacht.

search_covers() liefert Kandidaten fürs Bildergitter (nur Vorschau-URLs).
Heruntergeladen wird das große Bild erst, wenn der Nutzer eins auswählt (download()).
Fällt eine Quelle aus, liefern die anderen trotzdem.
"""

from __future__ import annotations

import html
import re

from . import itunes
from .artistimages import AUDIODB_LIMITER
from .base import CoverCandidate, OnlineError, RateLimiter, match_score
from .http import fetch, get_image, get_json

SOURCES = ("Cover Art Archive", "iTunes", "TheAudioDB", "Bandcamp")

CAA = "https://coverartarchive.org/"
ITUNES = itunes.SEARCH
AUDIODB_ALBUM = "https://www.theaudiodb.com/api/v1/json/123/searchalbum.php"
BANDCAMP = "https://bandcamp.com/search"

CAA_LIMITER = RateLimiter(per_second=2)
ITUNES_LIMITER = itunes.LIMITER            # iTunes erlaubt ca. 20 Anfragen/Minute – Album- und Cover-Suche teilen
BANDCAMP_LIMITER = RateLimiter(per_second=0.5)


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


def from_audiodb(artist: str, album: str) -> list[CoverCandidate]:
    if not artist.strip():
        return []                                   # TheAudioDB sucht Alben nur zusammen mit dem Interpreten
    data = get_json(AUDIODB_ALBUM, {"s": artist, "a": album}, limiter=AUDIODB_LIMITER)
    out = []
    for a in data.get("album") or []:
        name, who = a.get("strAlbum", ""), a.get("strArtist", "")
        url = a.get("strAlbumThumbHQ") or a.get("strAlbumThumb")
        if not url:
            continue
        year = a.get("intYearReleased") or ""
        out.append(CoverCandidate("TheAudioDB", url, url + "/preview",
                                  description=f"{name} – {who}" + (f" ({year})" if year else ""),
                                  score=match_score(artist, album, who, name), size_hint="Original"))
    return out


# Bandcamp hat keine offizielle Schnittstelle: die normale Suchseite wird gelesen. Ändert Bandcamp die Seite,
# liefert diese Quelle nichts mehr – die anderen laufen weiter.
_BC_ITEM = re.compile(r'<li class="searchresult[^"]*"(.*?)</li>', re.DOTALL)
_BC_IMG = re.compile(r'<img src="(https://f4\.bcbits\.com/img/a(\d+)_\d+\.jpg)"')
_BC_HEAD = re.compile(r'<div class="heading">\s*<a[^>]*>(.*?)</a>', re.DOTALL)
_BC_SUB = re.compile(r'<div class="subhead">(.*?)</div>', re.DOTALL)
_BC_TYPE = re.compile(r'<div class="itemtype">\s*(\w+)', re.DOTALL)


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def parse_bandcamp(page: str, artist: str, album: str) -> list[CoverCandidate]:
    out = []
    for block in _BC_ITEM.findall(page):
        kind = _BC_TYPE.search(block)
        if kind and kind.group(1).upper() not in ("ALBUM", "TRACK"):
            continue
        img = _BC_IMG.search(block)
        head = _BC_HEAD.search(block)
        if not img or not head:
            continue
        name = _text(head.group(1))
        sub = _text(_BC_SUB.search(block).group(1)) if _BC_SUB.search(block) else ""
        who = sub[3:].strip() if sub.lower().startswith("by ") else sub
        art = img.group(2)
        out.append(CoverCandidate("Bandcamp", f"https://f4.bcbits.com/img/a{art}_10.jpg",
                                  f"https://f4.bcbits.com/img/a{art}_2.jpg", description=f"{name} – {who}",
                                  score=match_score(artist, album, who, name), size_hint="bis 1200 px"))
    return out


def from_bandcamp(artist: str, album: str) -> list[CoverCandidate]:
    term = f"{artist} {album}".strip()
    page = fetch(BANDCAMP, {"q": term, "item_type": "a"}, limiter=BANDCAMP_LIMITER,
                 headers={"Accept": "text/html"}).decode("utf-8", "replace")
    return parse_bandcamp(page, artist, album)


def search_covers(artist: str, album: str, sources=SOURCES, *, contact: str = "", country: str = "DE",
                  progress=lambda source, found, error: None) -> list[CoverCandidate]:
    """Alle Quellen nacheinander; Fehler einer Quelle werden gemeldet, aber nicht geworfen."""
    funcs = {"Cover Art Archive": lambda: from_caa(artist, album, contact),
             "iTunes": lambda: from_itunes(artist, album, country),
             "TheAudioDB": lambda: from_audiodb(artist, album),
             "Bandcamp": lambda: from_bandcamp(artist, album)}
    out: list[CoverCandidate] = []
    for src in sources:
        if src not in funcs:                        # z. B. „Deezer“ aus alten Einstellungen
            continue
        try:
            found = funcs[src]()
            out += found
            progress(src, found, "")
        except OnlineError as exc:
            progress(src, [], str(exc))
    out.sort(key=lambda c: -c.score)
    return out


def download_url(url: str) -> bytes:
    """Großes Bild laden – bei iTunes notfalls kleiner (3000 px gibt es nicht immer)."""
    try:
        return get_image(url)
    except OnlineError:
        if "3000x3000bb" in url:
            return get_image(url.replace("3000x3000bb", "1400x1400bb"))
        raise


def download(candidate: CoverCandidate) -> bytes:
    return download_url(candidate.url)


def thumbnail(candidate: CoverCandidate) -> bytes:
    return get_image(candidate.thumb_url or candidate.url)
