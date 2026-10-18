"""Echte Antworten der Online-Dienste aufzeichnen → tests/fixtures/online/.

Läuft auf GitHub (Workflow „Testdaten aufzeichnen“), weil die Entwicklungsumgebung
keinen Zugang zu den Musikdiensten hat. Die Tests spielen die Aufnahmen später ab.

Gibt außerdem eine Zusammenfassung als GitHub-Hinweise (::notice::) aus.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from online_fixtures import ALBUMS, ARTISTS, DISCOGS_RELEASES, FIXTURES  # noqa: E402

from bub3tagmusic.online import artistimages, coversearch, discogs, http, musicbrainz  # noqa: E402
from bub3tagmusic.online.base import OnlineError  # noqa: E402

index: dict[str, str] = {}
notes: list[str] = []


def recorder(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=http._context()) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    if status == 200:
        ext = ".json" if body[:1] in (b"{", b"[") else ".bin"
        name = hashlib.sha1(url.encode()).hexdigest()[:16] + ext
        with open(os.path.join(FIXTURES, name), "wb") as fh:
            fh.write(body)
        index[url] = name
    return status, body


def note(text: str):
    notes.append(text)
    print(text)


def main():
    os.makedirs(FIXTURES, exist_ok=True)
    http.set_transport(recorder)

    for artist, album in ALBUMS:
        try:
            res = musicbrainz.search_albums(artist, album)
            note(f"MB Suche {artist} – {album}: {len(res)} Treffer; erster: {res[0].album} / {res[0].albumartist} "
                 f"/ {res[0].details} / Score {res[0].score}" if res else f"MB Suche {artist} – {album}: 0")
            if res:
                full = musicbrainz.get_album(res[0].source_id)
                note(f"MB Album {full.album}: {len(full.tracks)} Tracks, {full.disc_total} Disc(s), Genre "
                     f"'{full.genre}', Cover {'ja' if full.cover_full_url else 'nein'}, Track1 "
                     f"'{full.tracks[0].title}' {full.tracks[0].length:.0f}s" if full.tracks else "keine Tracks")
                if full.cover_url:
                    try:
                        http.get_image(full.cover_url)
                        note("CAA Vorschaubild geladen")
                    except OnlineError as exc:
                        note(f"CAA Vorschaubild: {exc}")
        except OnlineError as exc:
            note(f"MB Fehler {artist} – {album}: {exc}")

        def progress(src, found, err, a=artist, b=album):
            note(f"Cover {src} für {a} – {b}: {len(found)} Treffer {err}")
        covers = coversearch.search_covers(artist, album, progress=progress)
        for c in covers[:1]:
            try:
                coversearch.thumbnail(c)
                note(f"Cover-Vorschau {c.source} geladen")
            except OnlineError as exc:
                note(f"Cover-Vorschau {c.source}: {exc}")

    for artist in ARTISTS:
        imgs = artistimages.search_artist_images(
            artist, progress=lambda s, f, e, a=artist: note(f"Künstlerbild {s} für {a}: {len(f)} {e}"))
        for c in imgs[:1]:
            try:
                http.get_image(c.thumb_url)
                note(f"Künstlerbild-Vorschau {c.source} geladen")
            except OnlineError as exc:
                note(f"Künstlerbild-Vorschau {c.source}: {exc}")

    for rid in DISCOGS_RELEASES:
        try:
            a = discogs.get_album(rid)
            note(f"Discogs {rid}: {a.albumartist} – {a.album} ({a.year}), {len(a.tracks)} Tracks, "
                 f"{a.disc_total} Disc(s), Positionen {[t.position for t in a.tracks][:8]}")
        except OnlineError as exc:
            note(f"Discogs {rid}: {exc}")

    with open(os.path.join(FIXTURES, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1, ensure_ascii=False, sort_keys=True)
    with open(os.path.join(FIXTURES, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(notes) + "\n")
    # Für GitHub: Zusammenfassung als Hinweise (höchstens 10 pro Schritt werden angezeigt)
    chunk = []
    for line in notes:
        chunk.append(line)
    for i in range(0, len(chunk), 8):
        msg = " | ".join(chunk[i:i + 8]).replace("\n", " ")
        print(f"::notice title=Aufnahme {i // 8 + 1}::{msg}")
    print(f"{len(index)} Antworten aufgezeichnet")


if __name__ == "__main__":
    main()
