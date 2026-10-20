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

from bub3tagmusic.online import (acoustid, artistimages, coversearch, deezer, discogs, http, matching,  # noqa: E402
                                 musicbrainz)
from bub3tagmusic.online.base import OnlineError, seconds, similarity, strip_edition  # noqa: E402

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
    eq(full.original_year, "1979", "Original-Jahr aus der Release-Group")
    eq(bool(full.label), True, f"Label aus MusicBrainz ({full.label})")
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
    eq(set(found), {"Cover Art Archive", "iTunes", "TheAudioDB", "Bandcamp"}, "vier Cover-Quellen, kein Deezer mehr")
    eq(found["Cover Art Archive"][0] > 0 and found["iTunes"][0] > 0, True, f"CAA + iTunes liefern ({found})")
    for src, host in (("TheAudioDB", "searchalbum.php"), ("Bandcamp", "bandcamp.com/search")):
        if recorded(host):
            eq(found[src][0] > 0, True, f"{src} liefert ({found[src]})")
        else:
            print(f"   ({src} noch nicht aufgezeichnet – übersprungen)")
    eq(coversearch.search_covers("AC/DC", "Back in Black", ("Deezer",)), [], "alte Einstellung „Deezer“ wird ignoriert")
    it = next(c for c in covers if c.source == "iTunes")
    eq(("3000x3000" in it.url, it.size_text), (True, "bis 3000 px"), "iTunes in groß")
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

    # --- AcoustID (echte Antworten, Key in der Aufnahme = TESTKEY) ---------------------
    import json
    fx_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    info_path = os.path.join(fx_dir, "online", "acoustid.json")
    if os.path.exists(info_path):
        info = json.load(open(info_path))
        if info.get("trackid"):
            res = acoustid.lookup_track(info["trackid"], "TESTKEY", "Back in Black")
            m = res[0]
            eq((m.title, m.artist), ("Hells Bells", "AC/DC"), "AcoustID: Titel + Interpret")
            eq(bool(m.album and m.year and m.track and m.track_total), True,
               f"AcoustID: Album/Jahr/Track ({m.album}, {m.year}, {m.track}/{m.track_total}, {m.kind})")
            t = m.tags()
            eq(t["track"], f"{m.track}/{m.track_total}", "AcoustID: Track mit Gesamtzahl")
            eq(m.others >= 1, True, f"AcoustID: weitere Veröffentlichungen ({m.others})")
        fp = json.load(open(os.path.join(fx_dir, "fingerprint.json")))
        if info.get("fingerprint_lookup") == "ok":
            eq(acoustid.lookup(fp["compressed"], fp["duration"], "TESTKEY"), [],
               "AcoustID: echter Fingerabdruck-Lookup angenommen (Testklang → keine Treffer)")
        err_path = os.path.join(fx_dir, "online", "acoustid_error.json")
        if os.path.exists(err_path):
            body = open(err_path, "rb").read()
            http.set_transport(lambda url, headers: (400, body))
            try:
                acoustid.lookup(fp["compressed"], fp["duration"], "falsch")
                FAILS.append("falscher Key nicht erkannt")
            except OnlineError as exc:
                eq(str(exc), "AcoustID-Key ungültig – in Einstellungen → Online prüfen", "AcoustID: falscher Key")
            use_fixtures(misses)
        try:
            acoustid.lookup("x", 10, "")
            FAILS.append("fehlender Key nicht erkannt")
        except OnlineError as exc:
            eq(str(exc).startswith("AcoustID-Key fehlt"), True, "AcoustID: Key fehlt")
    # Aufbau der Antwort (falls die Aufnahme keinen Treffer hatte): Beispiel nach echter Struktur
    sample = {"status": "ok", "results": [{"score": 0.93, "id": "t", "recordings": [{
        "id": "r", "title": "Westerland", "artists": [{"name": "Die Ärzte"}],
        "releasegroups": [
            {"title": "Das ist nicht die ganze Wahrheit…", "type": "Album", "secondarytypes": [], "artists": [
                {"name": "Die Ärzte"}], "releases": [{"id": "a", "title": "Das ist nicht die ganze Wahrheit…",
                                                     "date": {"year": 1988}, "medium_count": 1, "mediums": [
                                                         {"position": 1, "track_count": 14,
                                                          "tracks": [{"position": 5}]}]}]},
            {"title": "Westerland", "type": "Single", "releases": [{"id": "b", "date": {"year": 1988},
                                                                   "medium_count": 1, "mediums": [
                                                                       {"position": 1, "track_count": 2,
                                                                        "tracks": [{"position": 1}]}]}]},
            {"title": "Ein Schritt", "type": "Album", "secondarytypes": ["Compilation"], "releases": [
                {"id": "c", "date": {"year": 2001}, "medium_count": 2, "mediums": [
                    {"position": 2, "track_count": 10, "tracks": [{"position": 3}]}]}]},
        ]}]}]}
    m = acoustid.parse(sample)[0]
    eq((m.album, m.year, m.track, m.track_total, m.kind), ("Das ist nicht die ganze Wahrheit…", "1988", 5, 14, "Album"),
       "AcoustID: reguläres Studioalbum vor Single/Sampler")
    m = acoustid.parse(sample, current_album="Ein Schritt")[0]
    eq((m.album, m.tags().get("disc")), ("Ein Schritt", "2/2"), "AcoustID: Album aus den Tags hat Vorrang (mit Disc)")

    test_deezer_structure()
    test_new_sources_structure()
    use_fixtures(misses)
    test_deezer_recorded()
    test_new_sources_recorded()

    def offline(url, headers):
        raise urllib.error.URLError("Name or service not known")
    http.set_transport(offline)
    try:
        musicbrainz.search_albums("a", "b")
        FAILS.append("Offline nicht erkannt")
    except OnlineError as exc:
        eq("Keine Verbindung zu MusicBrainz" in str(exc), True, "ohne Internet: verständliche Meldung")
    eq(seconds("1:02:03"), 3723.0, "Zeit 1:02:03")

    # Neue Quellen, die noch nie aufgezeichnet wurden, zählen nicht
    pending = [e for e in ("searchalbum.php", "bandcamp.com/search", "itunes.apple.com/lookup", "audioscrobbler")
               if not recorded(e)]
    unexpected = [u for u in misses if "front-250" not in u and "gibtsnicht" not in u
                  and not any(e in u for e in pending)]
    eq(unexpected, [], "keine unerwarteten Anfragen (alles aus der Aufnahme)")
    http.set_transport(None)
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    return 1 if FAILS else 0


def test_deezer_structure():
    """Deezer-Antworten nach echter Struktur (ohne Aufnahme): Suche, Album, Trackliste, Fehler."""
    import json
    search = {"data": [
        {"id": 1, "title": "Abbey Road (Remastered)", "nb_tracks": 17, "record_type": "album",
         "cover_medium": "https://cdn/x/250x250.jpg", "cover_xl": "https://cdn/x/1000x1000.jpg",
         "artist": {"name": "The Beatles"}},
        {"id": 2, "title": "Abbey Road Medley", "nb_tracks": 1, "record_type": "single", "artist": {"name": "Tribute"}},
    ], "total": 2}
    album = {"id": 1, "title": "Abbey Road (Remastered)", "label": "EMI Catalogue", "release_date": "2015-12-24",
             "record_type": "album", "genres": {"data": [{"id": 152, "name": "Rock"}]},
             "artist": {"name": "The Beatles"}, "cover_medium": "https://cdn/x/250x250.jpg",
             "cover_xl": "https://cdn/x/1000x1000.jpg",
             "tracks": {"data": [{"title": "Come Together (Remastered 2009)", "duration": 259,
                                  "artist": {"name": "The Beatles"}}]}}
    tracks = {"data": [
        {"title": "Come Together (Remastered 2009)", "duration": 259, "track_position": 1, "disk_number": 1,
         "artist": {"name": "The Beatles"}},
        {"title": "Something - Remastered 2009", "duration": 182, "track_position": 2, "disk_number": 1,
         "artist": {"name": "The Beatles"}},
        {"title": "Bonus Take", "duration": 100, "track_position": 1, "disk_number": 3, "artist": {"name": ""}},
    ], "total": 3}
    calls = []

    def fake(url, headers):
        calls.append(url)
        if "/search/album" in url:
            return 200, json.dumps(search).encode()
        if url.startswith("https://api.deezer.com/album/1/tracks"):
            return 200, json.dumps(tracks).encode()
        if url.startswith("https://api.deezer.com/album/1"):
            return 200, json.dumps(album).encode()
        if url.startswith("https://api.deezer.com/album/9"):
            return 200, json.dumps({"error": {"type": "DataException", "message": "no data", "code": 800}}).encode()
        return 404, b""
    http.clear_cache()
    http.set_transport(fake)
    res = deezer.search_albums("The Beatles", "Abbey Road")
    eq([m.source_id for m in res], ["1", "2"], "Deezer-Suche: Album vor Single")
    eq((res[0].track_total, res[0].formats, res[0].cover_url, res[0].cover_full_url), (17, "Album", "", ""),
       "Deezer-Suche: Trackzahl, Art – und keine Cover")
    a = deezer.get_album("1")
    eq((a.year, a.label, a.genre, a.original_year), ("2015", "EMI Catalogue", "Rock", ""), "Deezer-Album: Jahr/Label/Genre")
    eq([(t.disc, t.position, t.track_total) for t in a.tracks], [(1, 1, 2), (1, 2, 2), (2, 1, 1)],
       "Deezer: Discs lückenlos (3 → 2), Tracks je Disc")
    eq(a.tracks[2].artist, "The Beatles", "Deezer: Track ohne Interpret → Albuminterpret")
    eq(len(calls), 3, "Deezer: eine Suche + Album + Trackliste")
    t = matching.tags_for(a, 1, {"title", "album", "label", "originalyear", "year"}, clean=True)
    eq((t["title"], t["album"], t["label"], "originalyear" in t), ("Something", "Abbey Road", "EMI Catalogue", False),
       "Zusätze entfernt, Label übernommen, kein leeres Original-Jahr")
    t = matching.tags_for(a, 0, {"title"})
    eq(t["title"], "Come Together (Remastered 2009)", "ohne „clean“ bleibt der Titel")
    try:
        deezer.get_album("9")
        FAILS.append("Deezer-Fehler nicht erkannt")
    except OnlineError as exc:
        eq(str(exc), "Deezer kennt dieses Album nicht (mehr)", "Deezer-Fehler (Status 200 + error)")
    for raw, want in (("Wish You Were Here (2011 Remaster)", "Wish You Were Here"),
                      ("Money - 2011 Remastered Version", "Money"), ("Song (Live at Wembley)", "Song (Live at Wembley)"),
                      ("Shine On (Pts. 1-5) - 2011 Remaster", "Shine On (Pts. 1-5)"), ("Bonus (Remix)", "Bonus (Remix)"),
                      ("Album (Deluxe Edition) [Remastered]", "Album"), ("Come Together (2019 Mix)", "Come Together"),
                      ("Song (Club Mix)", "Song (Club Mix)"), ("Abbey Road (Super Deluxe Edition)", "Abbey Road")):
        eq(strip_edition(raw), want, f"Zusatz: {raw}")
    http.clear_cache()


def recorded(fragment: str) -> bool:
    from online_fixtures import load_index
    return any(fragment in u for u in load_index())


def test_new_sources_structure():
    """iTunes, Last.fm, TheAudioDB, Bandcamp – Antworten nach echter Struktur (ohne Aufnahme)."""
    import json

    from bub3tagmusic.online import itunes, lastfm
    search = {"resultCount": 2, "results": [
        {"wrapperType": "collection", "collectionId": 5, "collectionName": "Back in Black", "artistName": "AC/DC",
         "artworkUrl100": "https://is1.mzstatic.com/x/100x100bb.jpg", "trackCount": 10,
         "releaseDate": "1980-07-25T07:00:00Z", "primaryGenreName": "Hard Rock", "country": "DEU"},
        {"wrapperType": "collection", "collectionId": 6, "collectionName": "Back in Black (Tribute)",
         "artistName": "Somebody", "artworkUrl100": "", "trackCount": 10}]}
    lookup = {"resultCount": 3, "results": [
        search["results"][0],
        {"wrapperType": "track", "kind": "song", "trackName": "Shoot to Thrill", "artistName": "AC/DC",
         "trackNumber": 2, "trackCount": 10, "discNumber": 1, "trackTimeMillis": 317000},
        {"wrapperType": "track", "kind": "song", "trackName": "Hells Bells (Remastered)", "artistName": "AC/DC",
         "trackNumber": 1, "trackCount": 10, "discNumber": 1, "trackTimeMillis": 312000}]}
    lf_search = {"results": {"albummatches": {"album": [
        {"name": "Back in Black", "artist": "AC/DC", "mbid": "x"},
        {"name": "(null)", "artist": "AC/DC"}]}}}
    lf_info = {"album": {"name": "Back in Black", "artist": "AC/DC", "tags": {"tag": [
        {"name": "seen live"}, {"name": "1980"}, {"name": "hard rock"}]},
        "tracks": {"track": [{"name": "Hells Bells", "duration": 312, "@attr": {"rank": 1},
                              "artist": {"name": "AC/DC"}},
                             {"name": "Shoot to Thrill", "duration": None, "@attr": {"rank": 2},
                              "artist": {"name": "AC/DC"}}]}}}
    lf_one = {"album": {"name": "Single", "artist": "X", "tracks": {"track": {"name": "Nur eins", "duration": 200,
                                                                         "@attr": {"rank": 1}}}}}
    adb = {"album": [{"strAlbum": "Back in Black", "strArtist": "AC/DC", "intYearReleased": "1980",
                      "strAlbumThumb": "https://r2.theaudiodb.com/images/media/album/thumb/bib.jpg"}]}
    bc = ('<ul><li class="searchresult data-search" data-search="{}"><a class="artcont" href="x">'
          '<div class="art"><img src="https://f4.bcbits.com/img/a1234567890_7.jpg"></div></a>'
          '<div class="result-info"><div class="itemtype">ALBUM</div><div class="heading"><a href="x">'
          ' Back in Black &amp; Blue </a></div><div class="subhead">by Kiel Band</div></div></li>'
          '<li class="searchresult data-search"><div class="art"><img src="https://f4.bcbits.com/img/a1_7.jpg">'
          '</div><div class="itemtype">ARTIST</div><div class="heading"><a>Nur Künstler</a></div></li></ul>')
    calls = []

    def fake(url, headers):
        calls.append(url)
        if "itunes.apple.com/search" in url:
            return 200, json.dumps(search).encode()
        if "itunes.apple.com/lookup" in url:
            return 200, json.dumps(lookup).encode()
        if "audioscrobbler" in url:
            if "api_key=falsch" in url:
                return 403, json.dumps({"error": 10, "message": "Invalid API key"}).encode()
            if "album.search" in url:
                return 200, json.dumps(lf_search).encode()
            if "album=Single" in url:
                return 200, json.dumps(lf_one).encode()
            if "album=Gibtsnicht" in url:
                return 200, json.dumps({"error": 6, "message": "Album not found"}).encode()
            return 200, json.dumps(lf_info).encode()
        if "searchalbum.php" in url:
            return 200, json.dumps(adb).encode()
        if "bandcamp.com/search" in url:
            return 200, bc.encode()
        return 404, b""
    http.clear_cache()
    http.set_transport(fake)
    res = itunes.search_albums("AC/DC", "Back in Black")
    eq((res[0].source_id, res[0].year, res[0].genre), ("5", "1980", "Hard Rock"), "iTunes-Suche: Jahr, Genre")
    eq(res[0].cover_full_url.endswith("3000x3000bb.jpg") and res[0].cover_url.endswith("250x250bb.jpg"), True,
       "iTunes: Cover 3000 px, Vorschau 250 px")
    a = itunes.get_album("5")
    eq([(t.position, t.title, round(t.length)) for t in a.tracks],
       [(1, "Hells Bells (Remastered)", 312), (2, "Shoot to Thrill", 317)], "iTunes: Tracks sortiert, Längen")
    eq(matching.tags_for(a, 0, {"title"}, clean=True)["title"], "Hells Bells", "iTunes: Remaster-Zusatz weg")
    try:
        lastfm.search_albums("AC/DC", "Back in Black", "")
        FAILS.append("Last.fm ohne Key nicht abgefangen")
    except OnlineError as exc:
        eq("API-Key" in str(exc), True, "Last.fm ohne Key: klare Meldung")
    res = lastfm.search_albums("AC/DC", "Back in Black", "k")
    eq([m.album for m in res], ["Back in Black"], "Last.fm-Suche ohne „(null)“")
    a = lastfm.get_album(res[0].source_id, "k")
    eq((a.genre, a.year, len(a.tracks), a.tracks[1].length, a.cover_full_url), ("Hard Rock", "", 2, 0.0, ""),
       "Last.fm: Genre aus Tags (ohne „seen live“/„1980“), kein Jahr, kein Cover")
    one = lastfm.get_album(f"X{lastfm.SEP}Single", "k")
    eq([t.title for t in one.tracks], ["Nur eins"], "Last.fm: einzelner Track (Objekt statt Liste)")
    try:
        lastfm.get_album(f"X{lastfm.SEP}Gibtsnicht", "k")
        FAILS.append("Last.fm: unbekanntes Album nicht gemeldet")
    except OnlineError as exc:
        eq("kennt dieses Album nicht" in str(exc), True, "Last.fm: unbekanntes Album")
    try:
        lastfm.search_albums("AC/DC", "Back in Black", "falsch")
        FAILS.append("Last.fm: falscher Key nicht gemeldet")
    except OnlineError as exc:
        eq(str(exc), "Last.fm-API-Key ungültig – in Einstellungen → Online prüfen", "Last.fm: falscher Key (403)")
    c = coversearch.from_audiodb("AC/DC", "Back in Black")
    eq((c[0].url.endswith("bib.jpg"), c[0].thumb_url.endswith("/preview"), "(1980)" in c[0].description),
       (True, True, True), "TheAudioDB: Cover + Vorschau")
    eq(coversearch.from_audiodb("", "Back in Black"), [], "TheAudioDB braucht den Interpreten")
    c = coversearch.from_bandcamp("AC/DC", "Back in Black")
    eq([(x.description, x.url, x.thumb_url) for x in c],
       [("Back in Black & Blue – Kiel Band", "https://f4.bcbits.com/img/a1234567890_10.jpg",
         "https://f4.bcbits.com/img/a1234567890_2.jpg")], "Bandcamp: nur Alben, 1200 px, Text ohne HTML")
    http.clear_cache()


def test_new_sources_recorded():
    """Echte Antworten von iTunes, Last.fm, TheAudioDB, Bandcamp – nur, was schon aufgezeichnet ist."""
    from bub3tagmusic.online import itunes, lastfm
    if recorded("itunes.apple.com/lookup"):
        res = itunes.search_albums("AC/DC", "Back in Black")
        eq((res[0].albumartist, "Back in Black" in res[0].album), ("AC/DC", True), f"iTunes: {res[0].album}")
        a = itunes.get_album(res[0].source_id)
        eq((len(a.tracks), a.tracks[0].position, a.year), (10, 1, "1980"), f"iTunes: Back in Black ({a.tracks[0].title})")
        wall = itunes.get_album(itunes.search_albums("Pink Floyd", "The Wall")[0].source_id)
        eq((wall.disc_total, len(wall.tracks)), (2, 26), "iTunes: The Wall mit 2 Discs")
    else:
        print("   (iTunes-Alben noch nicht aufgezeichnet – übersprungen)")
    if recorded("album.getinfo"):
        res = lastfm.search_albums("AC/DC", "Back in Black", "TESTKEY")
        a = lastfm.get_album(res[0].source_id, "TESTKEY")
        eq((a.albumartist, len(a.tracks) >= 10, bool(a.genre)), ("AC/DC", True, True),
           f"Last.fm: {a.album}, {len(a.tracks)} Tracks, Genre {a.genre!r}")
    else:
        print("   (Last.fm noch nicht aufgezeichnet – übersprungen; braucht das GitHub-Secret LASTFM_KEY)")


def test_deezer_recorded():
    """Echte Deezer-Antworten – nur wenn sie schon aufgezeichnet sind."""
    from online_fixtures import DEEZER_ALBUMS, load_index
    if not any("api.deezer.com/album/" in u for u in load_index()):
        print("   (Deezer-Alben noch nicht aufgezeichnet – übersprungen)")
        return
    res = deezer.search_albums("AC/DC", "Back in Black")
    eq((res[0].album, res[0].albumartist, res[0].formats), ("Back In Black", "AC/DC", "Album"),
       "Deezer: Original-Album vor Coverversionen")
    a = deezer.get_album(res[0].source_id)
    eq((len(a.tracks), a.tracks[0].title, a.tracks[0].position, a.tracks[0].track_total, a.label),
       (10, "Hells Bells", 1, 10, "Columbia"), f"Deezer: Back in Black ({a.year})")
    eq(a.tracks[0].length > 300, True, "Deezer: Längen in Sekunden")
    wall = deezer.get_album(deezer.search_albums("Pink Floyd", "The Wall")[0].source_id)
    eq((len(wall.tracks), wall.disc_total, wall.tracks[13].disc, wall.tracks[13].position), (26, 2, 2, 1),
       "Deezer: The Wall mit 2 Discs")
    for artist, album in DEEZER_ALBUMS:
        res = deezer.search_albums(artist, album)
        full = deezer.get_album(res[0].source_id)
        t = matching.tags_for(full, 0, {"title", "album"}, clean=True)
        eq((t["album"], t["title"]), ("Abbey Road", "Come Together"), f"Deezer: {full.album} – Zusätze gekürzt")
    aerzte = deezer.get_album(deezer.search_albums("Die Ärzte", "Die Bestie in Menschengestalt")[0].source_id)
    eq((aerzte.albumartist, len(aerzte.tracks), aerzte.label, aerzte.year), ("Die Ärzte", 19, "Hot Action Records", "1993"),
       "Deezer: Die Ärzte (Umlaute, Label, Jahr)")


if __name__ == "__main__":
    sys.exit(main())
