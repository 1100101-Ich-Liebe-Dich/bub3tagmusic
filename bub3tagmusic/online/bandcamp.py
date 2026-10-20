"""Bandcamp – Suche für Cover (Alben) und Künstlerbilder (Bands).

Bandcamp hat keine offizielle Schnittstelle, und die normale Suchseite sperrt Programme (JavaScript-Prüfung).
Benutzt wird deshalb die Suche, die die Bandcamp-Seite selbst aufruft (JSON per POST). Ändert Bandcamp sie,
liefert nur diese Quelle nichts mehr – die anderen laufen weiter.
"""

from __future__ import annotations

import html
import json
import re

from .base import OnlineError, RateLimiter
from .http import fetch

API = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"
LIMITER = RateLimiter(per_second=0.5)
IMG = "https://f4.bcbits.com/img/"

ALBUMS, BANDS = "a", "b"


def search(term: str, kind: str) -> list[dict]:
    """kind: ALBUMS oder BANDS. Liefert die Treffer, Texte schon ohne HTML-Zeichen (&amp; → &)."""
    body = fetch(API, limiter=LIMITER,
                 post_json={"search_text": term, "search_filter": kind, "full_page": False, "fan_id": None})
    if body[:1] != b"{":
        raise OnlineError("Bandcamp lässt die Suche gerade nicht zu – die anderen Quellen laufen weiter")
    out = []
    for r in ((json.loads(body.decode("utf-8")).get("auto") or {}).get("results") or []):
        r = dict(r)
        for k in ("name", "band_name"):
            if r.get(k):
                r[k] = html.unescape(r[k])
        out.append(r)
    return out


def image_id(r: dict) -> str:
    """Kennung des Bildes: 'a123…' bei Alben (Cover), '0012…' bei Bands (Foto)."""
    m = re.search(r"/img/(a?\d+)_\d+\.jpg", r.get("img") or "")
    if m:
        return m.group(1)
    if r.get("art_id"):
        return f"a{r['art_id']}"
    if r.get("img_id"):
        return f"{int(r['img_id']):010d}"
    return ""


def image_url(img: str, size: int) -> str:
    """Bandcamp-Größen: 0 = Original, 10 = 1200 px, 2 = 350 px (Vorschau)."""
    return f"{IMG}{img}_{size}.jpg"
