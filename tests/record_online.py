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

from online_fixtures import ALBUMS, ARTISTS, DEEZER_ALBUMS, DISCOGS_RELEASES, FIXTURES  # noqa: E402

from bub3tagmusic.online import acoustid, artistimages, coversearch, deezer, discogs, http, musicbrainz  # noqa: E402
from bub3tagmusic.online.base import OnlineError  # noqa: E402

index: dict[str, str] = {}
notes: list[str] = []


# AcoustID braucht einen Key: GitHub-Secret ACOUSTID_KEY, sonst der Beispiel-Key aus der Doku.
# In den Aufnahmen steht immer „TESTKEY“ – ein echter Key landet so nie im Repository.
ACOUSTID_KEY = os.environ.get("ACOUSTID_KEY") or "zYspohqt0AM"
TEST_KEY = "TESTKEY"


def recorder(url, headers):
    import time
    req = urllib.request.Request(url, headers=headers)
    try:
        for attempt in range(4):              # MusicBrainz antwortet nach vielen Anfragen kurz mit 503
            try:
                with urllib.request.urlopen(req, timeout=30, context=http._context()) as resp:
                    status, body = resp.status, resp.read()
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 503 or attempt == 3:
                    raise
                note(f"503 von {url[:60]} … warte {5 * (attempt + 1)} s")
                time.sleep(5 * (attempt + 1))
    except urllib.error.HTTPError as exc:
        body = exc.read() if "acoustid" in url else b""
        if body:
            note(f"AcoustID {exc.code}: {body[:200].decode('utf-8', 'replace')}")
            with open(os.path.join(FIXTURES, "acoustid_error.json"), "wb") as fh:
                fh.write(body)
        return exc.code, body
    if status == 200:
        stored = url.replace(f"client={ACOUSTID_KEY}", f"client={TEST_KEY}")
        ext = ".json" if body[:1] in (b"{", b"[") else ".bin"
        name = hashlib.sha1(stored.encode()).hexdigest()[:16] + ext
        with open(os.path.join(FIXTURES, name), "wb") as fh:
            fh.write(body)
        index[stored] = name
    return status, body


def record_acoustid():
    """Hells Bells (AC/DC): MusicBrainz-Aufnahme → AcoustID-Track → Lookup mit allen Metadaten.
    Dazu ein Lookup mit einem echten Fingerabdruck (Testklang → erwartet: keine Treffer)."""
    import time
    info = {}
    try:
        data = {}
        for attempt in range(4):                 # MusicBrainz ist nach vielen Anfragen kurz zugeknöpft
            time.sleep(5 * (attempt + 1))
            try:
                data = http.get_json(musicbrainz.API + "recording",
                                     {"query": 'recording:"Hells Bells" AND artist:"AC/DC"', "fmt": "json",
                                      "limit": 5}, limiter=musicbrainz.LIMITER, use_cache=False)
                break
            except OnlineError as exc:
                note(f"MB Aufnahmen-Suche Versuch {attempt + 1}: {exc}")
        mbids = [r["id"] for r in data.get("recordings", [])]
        note(f"MB Aufnahmen Hells Bells: {len(mbids)}")
        for mbid in mbids:
            lst = http.get_json("https://api.acoustid.org/v2/track/list_by_mbid",
                                {"client": ACOUSTID_KEY, "mbid": mbid}, limiter=acoustid.LIMITER)
            tracks = lst.get("tracks") or []
            if tracks:
                info = {"mbid": mbid, "trackid": tracks[0]["id"]}
                break
        note(f"AcoustID Track: {info or 'keiner gefunden'}")
        if info:
            res = acoustid.lookup_track(info["trackid"], ACOUSTID_KEY, "Back in Black")
            info["matches"] = len(res)
            if res:
                m = res[0]
                note(f"AcoustID Lookup: {len(res)} Aufnahme(n); erste: {m.title} / {m.artist} / {m.album} / "
                     f"{m.year} / Track {m.track}/{m.track_total} / {m.kind} / weitere {m.others}")
    except OnlineError as exc:
        note(f"AcoustID Fehler: {exc}")
    try:
        fx = json.load(open(os.path.join(HERE, "fixtures", "fingerprint.json")))
        res = acoustid.lookup(fx["compressed"], fx["duration"], ACOUSTID_KEY)
        note(f"AcoustID Fingerabdruck-Lookup (Testklang): {len(res)} Treffer")
        info["fingerprint_lookup"] = "ok"
    except OnlineError as exc:
        note(f"AcoustID Fingerabdruck-Lookup Fehler: {exc}")
    try:
        acoustid.lookup_track(info.get("trackid") or "9ff43b6a-4f16-427c-93c2-92307ca505e0", "falscher-key")
    except OnlineError as exc:
        note(f"AcoustID falscher Key → {exc}")
        info["bad_key_message"] = str(exc)
    path = os.path.join(FIXTURES, "acoustid.json")
    if "matches" not in info and os.path.exists(path) and "matches" in json.load(open(path, encoding="utf-8")):
        note("AcoustID diesmal ohne Treffer – die letzte gute Aufnahme bleibt")
        return
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1, ensure_ascii=False)


def record_deezer(artist: str, album: str):
    try:
        res = deezer.search_albums(artist, album)
        note(f"Deezer Suche {artist} – {album}: {len(res)} Treffer; erste: "
             + "; ".join(f"{m.album} / {m.albumartist} / {m.formats} / {m.track_total} / Score {m.score}"
                         for m in res[:3]))
        if not res:
            return
        full = deezer.get_album(res[0].source_id)
        t0 = full.tracks[0] if full.tracks else None
        note(f"Deezer Album {full.album} ({full.source_id}): {len(full.tracks)} Tracks, {full.disc_total} Disc(s), "
             f"Jahr {full.year}, Label '{full.label}', Genre '{full.genre}', Cover {'ja' if full.cover_full_url else 'nein'}"
             + (f", Track1 '{t0.title}' {t0.position}/{t0.track_total} Disc {t0.disc} {t0.length:.0f}s" if t0 else ""))
        if full.cover_url:
            try:
                http.get_image(full.cover_url)
            except OnlineError as exc:
                note(f"Deezer Vorschaubild: {exc}")
    except OnlineError as exc:
        note(f"Deezer Fehler {artist} – {album}: {exc}")


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

    for artist, album in ALBUMS + DEEZER_ALBUMS:
        record_deezer(artist, album)

    record_acoustid()

    # Was diesmal nicht geklappt hat (z. B. MusicBrainz 503), aus der letzten Aufnahme behalten
    old_path = os.path.join(FIXTURES, "index.json")
    if os.path.exists(old_path):
        kept = 0
        for url, name in json.load(open(old_path, encoding="utf-8")).items():
            if url not in index and os.path.exists(os.path.join(FIXTURES, name)):
                index[url] = name
                kept += 1
        if kept:
            note(f"{kept} Antworten aus der letzten Aufnahme behalten")
    with open(old_path, "w", encoding="utf-8") as fh:
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
