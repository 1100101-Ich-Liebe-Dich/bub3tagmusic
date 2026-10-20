"""Künstlerbilder – gespeichert als folder.jpg im Künstler-Ordner.

Quellen (1.1.3):
  * TheAudioDB  – Porträt, Fanart, Breitbild (öffentlicher Test-Key)
  * Bandcamp    – Band-Fotos, oft auch von kleinen, unbekannten Künstlern
  * Discogs     – riesiges Archiv, auch Raritäten (braucht den Discogs-Token, sonst übersprungen)
  * Wikipedia   – freie Bilder von Wikimedia Commons, über MusicBrainz → Wikidata
Deezer liefert keine Bilder mehr (Wunsch: nur Tags von Deezer).
"""

from __future__ import annotations

import urllib.parse

from . import bandcamp
from .base import CoverCandidate, OnlineError, RateLimiter, similarity
from .http import get_json

SOURCES = ("TheAudioDB", "Bandcamp", "Discogs", "Wikipedia")
AUDIODB = "https://www.theaudiodb.com/api/v1/json/123/search.php"
WIKIDATA = "https://www.wikidata.org/wiki/Special:EntityData/"
COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/"

AUDIODB_LIMITER = RateLimiter(per_second=0.5)      # Test-Key: höchstens 30 Anfragen/Minute
WIKI_LIMITER = RateLimiter(per_second=2)

MIN_SCORE = 0.6           # Bandcamp/Discogs finden sonst viele fremde Künstler mit ähnlichem Namen


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
                out.append(CoverCandidate("TheAudioDB", url, url + "/preview", description=f"{name} · {label}",
                                          score=score - (0 if key == "strArtistThumb" else 0.05),
                                          size_hint="Original"))
    return out


def parse_bandcamp(results: list[dict], artist: str) -> list[CoverCandidate]:
    out = []
    for r in results:
        if r.get("type") != "b":
            continue
        img = bandcamp.image_id(r)
        name = r.get("name") or ""
        score = similarity(artist, name)
        if not img or score < MIN_SCORE:
            continue
        where = r.get("location") or ""
        out.append(CoverCandidate("Bandcamp", bandcamp.image_url(img, 0), bandcamp.image_url(img, 2),
                                  description=f"{name}" + (f" · {where}" if where else ""), score=score,
                                  size_hint="Original"))
    return out


def from_bandcamp(artist: str) -> list[CoverCandidate]:
    return parse_bandcamp(bandcamp.search(artist, bandcamp.BANDS), artist)


def from_discogs(artist: str, token: str) -> list[CoverCandidate]:
    """Suche nach dem Künstler; für den besten Treffer alle Fotos (eine zweite Anfrage)."""
    from . import discogs
    if not token:
        return []
    headers = {"Authorization": f"Discogs token={token}"}
    data = get_json(discogs.API + "database/search", {"type": "artist", "q": artist, "per_page": 8},
                    headers=headers, limiter=discogs.LIMITER)
    hits = []
    for r in data.get("results") or []:
        name = discogs._clean_name(r.get("title", ""))
        score = similarity(artist, name)
        if score >= MIN_SCORE:
            hits.append((score, name, r))
    hits.sort(key=lambda h: -h[0])
    out = []
    for i, (score, name, r) in enumerate(hits[:3]):
        images = []
        if i == 0 and r.get("id"):
            try:
                full = get_json(discogs.API + f"artists/{r['id']}", headers=headers, limiter=discogs.LIMITER)
                images = [(img.get("uri"), img.get("uri150") or img.get("uri"), img.get("width"), img.get("height"))
                          for img in full.get("images") or [] if img.get("uri")]
            except OnlineError:
                images = []
        if not images and r.get("cover_image") and "spacer.gif" not in r["cover_image"]:
            images = [(r["cover_image"], r.get("thumb") or r["cover_image"], 0, 0)]
        for n, (url, thumb, w, h) in enumerate(images[:6]):
            out.append(CoverCandidate("Discogs", url, thumb, int(w or 0), int(h or 0),
                                      description=name, score=score - 0.01 * n,
                                      size_hint="" if w else "Original"))
    return out


def commons_url(filename: str, width: int = 0) -> str:
    url = COMMONS + urllib.parse.quote(filename.replace(" ", "_"))
    return url + (f"?width={width}" if width else "")


def from_wikipedia(artist: str, contact: str = "") -> list[CoverCandidate]:
    """MusicBrainz (Künstler + Verweis auf Wikidata) → Wikidata (Bild, P18) → Wikimedia Commons."""
    from . import musicbrainz as mb
    data = get_json(mb.API + "artist/", {"query": f'artist:"{mb._escape(artist)}"', "fmt": "json", "limit": 3},
                    limiter=mb.LIMITER, contact=contact)
    out = []
    for a in [a for a in data.get("artists") or [] if int(a.get("score") or 0) >= 90][:2]:
        name = a.get("name", "")
        score = similarity(artist, name)
        if score < MIN_SCORE:
            continue
        info = get_json(mb.API + f"artist/{a['id']}", {"inc": "url-rels", "fmt": "json"},
                        limiter=mb.LIMITER, contact=contact)
        qids = [r["url"]["resource"].rstrip("/").rsplit("/", 1)[-1] for r in info.get("relations") or []
                if r.get("type") == "wikidata" and (r.get("url") or {}).get("resource")]
        for qid in qids[:1]:
            entity = get_json(WIKIDATA + f"{qid}.json", limiter=WIKI_LIMITER)
            claims = ((entity.get("entities") or {}).get(qid) or {}).get("claims") or {}
            for n, c in enumerate(claims.get("P18") or []):
                filename = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if not filename:
                    continue
                extra = f" ({a['disambiguation']})" if a.get("disambiguation") else ""
                out.append(CoverCandidate("Wikipedia", commons_url(filename, 1600), commons_url(filename, 330),
                                          description=f"{name}{extra} · freies Bild (Wikimedia Commons)",
                                          score=score - 0.01 * n, size_hint="bis 1600 px"))
    return out


def search_artist_images(artist: str, sources=SOURCES, progress=lambda s, f, e: None, *,
                         discogs_token: str = "", contact: str = "") -> list[CoverCandidate]:
    funcs = {"TheAudioDB": lambda: from_audiodb(artist), "Bandcamp": lambda: from_bandcamp(artist),
             "Discogs": lambda: from_discogs(artist, discogs_token),
             "Wikipedia": lambda: from_wikipedia(artist, contact)}
    out: list[CoverCandidate] = []
    for src in sources:
        if src not in funcs:                       # z. B. „Deezer“ aus alten Einstellungen
            continue
        if src == "Discogs" and not discogs_token:  # ohne Token einfach überspringen
            continue
        try:
            found = funcs[src]()
            out += found
            progress(src, found, "")
        except OnlineError as exc:
            progress(src, [], str(exc))
    out.sort(key=lambda c: -c.score)
    return out
