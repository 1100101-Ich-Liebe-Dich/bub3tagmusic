"""Online-Tests mit aufgezeichneten echten Antworten (ohne Internet).

Aufruf: python3 tests/test_online.py
Die Aufnahmen erzeugt der GitHub-Workflow „Testdaten aufzeichnen“ (tests/record_online.py).
"""

from __future__ import annotations

import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from online_fixtures import available, use_fixtures  # noqa: E402

from bub3tagmusic.online import artistimages, coversearch, discogs, http, matching, musicbrainz  # noqa: E402
from bub3tagmusic.online.base import OnlineError, seconds, similarity  # noqa: E402

FAILS = []


def eq(got, want, msg):
    if got != want:
        FAILS.append(msg)
        print(f"   FEHLER: {msg}\n      bekommen: {got!r}\n      erwartet: {want!r}")
    else:
        print(f"  ok   {msg}")


def main():
    if not available():
        print("Keine aufgezeichneten Online-Daten – übersprungen")
        return 0
    misses: list[str] = []
    use_fixtures(misses)

    # --- MusicBrainz ---------------------------------------------------------------
    res = musicbrainz.search_albums("AC/DC", "Back in Black")
    eq(len(res) > 5, True, f"MB-Suche AC/DC: {len(res)} Treffer")
    eq((res[0].album, res[0].albumartist, res[0].year), ("Back in Black", "AC/DC", "1980"), "erster Treffer")
    eq(all(r.score <= 100 for r in res) and res[0].score >= res[-1].score, True, "nach Passgenauigkeit sortiert")
    wall = musicbrainz.search_albums("Pink Floyd", "The Wall")
    full = musicbrainz.get_album(wall[0].source_id)
    eq((len(full.tracks), full.disc_total), (26, 2), "The Wall: 26 Tracks auf 2 Discs")
    eq([t.disc for t in full.tracks].count(2), 13, "Disc 2 hat 13 Tracks")
    eq((full.tracks[13].disc, full.tracks[13].position, full.tracks[13].track_total), (2, 1, 13),
       "erster Track von Disc 2 = 2/1, 13 auf der Disc")
    eq(full.genre, "Progressive Rock", "Genre aus MusicBrainz")
    eq(full.tracks[0].length > 100, True, f"Länge in Sekunden ({full.tracks[0].length:.0f})")
    eq(bool(full.cover_full_url), True, "Cover vorhanden")
    aerzte = musicbrainz.search_albums("Die Ärzte", "Die Bestie in Menschengestalt")
    a = musicbrainz.get_album(aerzte[0].source_id)
    eq((a.albumartist, len(a.tracks)), ("Die Ärzte", 19), "Umlaute: Die Ärzte, 19 Tracks")

    # --- Zuordnung ----------------------------------------------------------------------
    files = [matching.FileInfo(track=str(t.position), disc=str(t.disc), length=t.length + 1.5) for t in full.tracks]
    got, mode = matching.assign(files, full)
    eq((mode, [g.track_index for g in got]), ("number", list(range(26))), "Zuordnung nach Disc + Track")
    files_no_disc = [matching.FileInfo(track="", length=t.length) for t in full.tracks]
    got, mode = matching.assign(files_no_disc, full)
    eq(mode, "order", "ohne Tracknummern: nach Reihenfolge")
    shuffled = list(reversed(files))
    got, _ = matching.assign([matching.FileInfo(length=f.length - 1.5) for f in shuffled], full, "length")
    eq([g.track_index for g in got], list(range(25, -1, -1)), "nach Länge (ganzes Album, umgedrehte Reihenfolge)")
    eq(all(g.length_ok for g in got), True, "Längen passen")
    tags = matching.tags_for(full, 13, {"title", "artist", "album", "year", "track", "genre"})
    eq((tags["track"], tags["disc"], tags["albumartist"], tags["year"]), ("1/13", "2/2", "Pink Floyd", "1979"),
       "Tags für Disc 2, Track 1")
    one = matching.tags_for(a, 0, {"track"})
    eq(("disc" in one, one["track"]), (False, "1/19"), "Einzel-CD: keine Disc-Nummer")
    ranked = matching.rank_for_files(res, 10)
    eq(ranked[0].track_total, 10, "Treffer mit passender Trackzahl nach oben")

    # --- Cover ------------------------------------------------------------------------------
    found = {}
    covers = coversearch.search_covers("AC/DC", "Back in Black",
                                       progress=lambda s, f, e: found.__setitem__(s, (len(f), e)))
    eq({s: n > 0 for s, (n, _e) in found.items()}, {"Cover Art Archive": True, "iTunes": True, "Deezer": True},
       f"alle drei Quellen liefern ({found})")
    it = next(c for c in covers if c.source == "iTunes")
    eq(("3000x3000" in it.url, it.size_text), (True, "bis 3000 px"), "iTunes in groß")
    dz = next(c for c in covers if c.source == "Deezer")
    eq(dz.size_text, "1000 × 1000", "Deezer 1000 px")
    caa = next(c for c in covers if c.source == "Cover Art Archive")
    eq(caa.thumb_url.startswith("https://"), True, "CAA über https")
    eq(len(coversearch.thumbnail(caa)) > 1000, True, "Vorschaubild geladen")
    eq(covers[0].score >= covers[-1].score, True, "Cover nach Ähnlichkeit sortiert")

    # --- Künstlerbilder ---------------------------------------------------------------------
    imgs = artistimages.search_artist_images("AC/DC")
    eq({c.source for c in imgs} >= {"Deezer", "TheAudioDB"}, True, f"Künstlerbilder aus beiden Quellen ({len(imgs)})")
    eq(all("/artist//" not in c.url for c in imgs), True, "Deezer-Platzhalter ausgefiltert")
    eq(similarity("AC/DC", imgs[0].description.split(" · ")[0]) > 0.8, True, "bester Treffer ist AC/DC")

    # --- Discogs -------------------------------------------------------------------------------
    p = discogs.get_album("1")
    eq((p.albumartist, p.album, len(p.tracks)), ("The Persuader", "Stockholm", 6), "Discogs Release 1")
    eq([t.position for t in p.tracks], [1, 2, 3, 4, 5, 6], "Vinyl-Seiten A/B → fortlaufend")
    eq(all(t.length > 0 for t in p.tracks), True, "Längen aus Discogs")
    try:
        discogs.search_albums("x", "y", token="")
        FAILS.append("Discogs ohne Token nicht abgefangen")
    except OnlineError as exc:
        eq("Token" in str(exc), True, "Discogs ohne Token: klare Meldung")
    tl = discogs.parse_tracklist([
        {"position": "", "type_": "heading", "title": "CD 1"},
        {"position": "1-1", "title": "a", "duration": "3:00"}, {"position": "1-2", "title": "b"},
        {"position": "2-1", "title": "c"},
        {"position": "", "type_": "index", "title": "Suite", "sub_tracks": [{"position": "2-2a", "title": "d"}]},
    ], "X")
    eq([(t.disc, t.position, t.track_total) for t in tl], [(1, 1, 2), (1, 2, 2), (2, 1, 2), (2, 2, 2)],
       "Discogs Disc-Positionen (inkl. Teilstück 2-2a)")
    eq(tl[0].length, 180.0, "Dauer 3:00")

    # --- HTTP -------------------------------------------------------------------------------------
    try:
        http.get_json("https://musicbrainz.org/ws/2/gibtsnicht")
        FAILS.append("404 nicht erkannt")
    except http.NotFound:
        eq(True, True, "404 → NotFound")

    def offline(url, headers):
        raise urllib.error.URLError("Name or service not known")
    http.set_transport(offline)
    try:
        musicbrainz.search_albums("a", "b")
        FAILS.append("Offline nicht erkannt")
    except OnlineError as exc:
        eq("Keine Verbindung zu MusicBrainz" in str(exc), True, "ohne Internet: verständliche Meldung")
    eq(seconds("1:02:03"), 3723.0, "Zeit 1:02:03")

    unexpected = [u for u in misses if "front-250" not in u and "gibtsnicht" not in u]
    eq(unexpected, [], "keine unerwarteten Anfragen (alles aus der Aufnahme)")
    http.set_transport(None)
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
