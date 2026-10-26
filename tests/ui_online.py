"""Oberflächen-Test der Online-Dialoge mit aufgezeichneten echten Antworten.

Aufruf: QT_QPA_PLATFORM=offscreen python3 tests/ui_online.py ARBEITSORDNER AUSGABEORDNER
Große Bilder (volle Cover) sind nicht aufgezeichnet – dafür liefert der Test ein erzeugtes JPEG.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())
os.environ.setdefault("XDG_CACHE_HOME", tempfile.mkdtemp())

from online_fixtures import FIXTURES, available, load_index  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FEHLER ") + msg)
    if not cond:
        FAILS.append(msg)


def wait(app, cond, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def pump(app, sec=0.3):
    t0 = time.time()
    while time.time() - t0 < sec:
        app.processEvents()
        time.sleep(0.01)


def big_jpeg() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1400, 1400), (200, 40, 40)).save(buf, "JPEG", quality=85)
    return buf.getvalue()


def main():
    if not available():
        print("Keine aufgezeichneten Online-Daten – übersprungen")
        return 0
    work, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    from make_testfiles import make

    from bub3tagmusic.core.tags import read_file, write_file

    # Test-Album: AC/DC – Back in Black (10 Tracks), Ordner wie bei echten Sammlungen
    shutil.rmtree(work, ignore_errors=True)
    tpl = make(os.path.join(work, "tpl"))["mp3"]
    album_dir = os.path.join(work, "Musik", "AC_DC", "1980 - Back in Black")
    os.makedirs(album_dir)
    for n in range(1, 11):
        p = os.path.join(album_dir, f"{n:02d} - Track {n}.mp3")
        shutil.copy(tpl, p)
        write_file(p, {"artist": "AC/DC", "albumartist": "AC/DC", "album": "Back in Black", "track": str(n),
                       "title": f"Track {n}"}, None, {"id3_version": 3})
    second_dir = os.path.join(work, "Musik", "AC_DC", "1981 - For Those About to Rock")   # für „Übernehmen & weiter“
    os.makedirs(second_dir)
    for n in range(1, 3):
        p = os.path.join(second_dir, f"{n:02d} - Lied {n}.mp3")
        shutil.copy(tpl, p)
        write_file(p, {"artist": "AC/DC", "album": "For Those About to Rock", "track": str(n)}, None, {"id3_version": 3})

    # Abspielen der Aufnahmen; fehlende große Bilder → erzeugtes JPEG
    index = load_index()
    big = big_jpeg()
    requested = []

    def transport(url, headers):
        requested.append(url)
        name = index.get(url)
        if name:
            with open(os.path.join(FIXTURES, name), "rb") as fh:
                return 200, fh.read()
        if url.endswith("/front") or "3000x3000" in url or url.endswith(".jpg") or "picture_xl" in url \
                or "/1000x1000" in url or "theaudiodb.com/images" in url:
            return 200, big
        return 404, b""

    from bub3tagmusic.online import http
    http.set_transport(transport)

    app = QApplication(sys.argv[:1])
    from bub3tagmusic.app import prepare_app
    prepare_app(app)
    from bub3tagmusic.core.settings import Settings
    from bub3tagmusic.ui import theme
    theme.apply(app, "bub")
    from bub3tagmusic.ui import online as O
    from bub3tagmusic.ui.mainwindow import MainWindow

    win = MainWindow(Settings())
    win.resize(1366, 768)
    win.show()
    win.tree.set_root(os.path.join(work, "Musik"), [])
    check(wait(app, lambda: win.tree.root_node is not None), "Sammlung gescannt")
    win.tree.select_paths([album_dir])
    check(wait(app, lambda: len(win.session.items) == 10), "Album geladen (10 Dateien)")
    pump(app)
    items, scope = win.tool_items()
    check(O.guess_search(items) == ("AC/DC", "Back in Black"), f"Suchbegriffe erkannt: {O.guess_search(items)}")
    from types import SimpleNamespace as NS
    for folder, want in (("/m/Kielwasser (Band)/Hochsee (2020) [FLAC]", ("Kielwasser", "Hochsee")),
                         ("/m/Kielwasser/2019 - Nebelhorn (EP)", ("Kielwasser", "Nebelhorn"))):
        got = O.guess_search([NS(tags={}, dir=folder)])
        check(got == want, f"ohne Klammern: {folder} → {got}")
    got = O.guess_search([NS(tags={"album": "Hochsee [Deluxe Edition]", "albumartist": "Kielwasser"}, dir="/m/x")])
    check(got == ("Kielwasser", "Hochsee"), f"auch aus den Tags ohne Klammern: {got}")

    # --- Album suchen (MusicBrainz) ------------------------------------------------------------
    d = O.AlbumSearchDialog(win, items, scope)
    d.show()
    check(wait(app, lambda: d.results.count() > 0), f"MusicBrainz-Treffer: {d.results.count()}")
    mb_searches = [u for u in requested if "musicbrainz.org/ws/2/release/?" in u]
    check(len(mb_searches) == 1, f"genau EINE Suchanfrage an MusicBrainz ({len(mb_searches)})")
    recorded = {u.split("/release/")[1].split("?")[0] for u in index if "inc=recordings" in u}
    row = next(i for i in range(d.results.count())
               if d.results.item(i).data(0x0100).source_id in recorded)
    d.results.setCurrentRow(row)
    check(wait(app, lambda: d._current is not None and d.model.preview.apply_count > 0), "Trackliste geladen")
    pump(app, 0.5)
    col = d.model.preview.columns.index("Titel")
    titles = [r.cells[col][0] for r in d.model.rows]
    check(titles[0] == "Hells Bells", f"Track 1 → {titles[0]}")
    check(d.model.preview.apply_count == 10, f"10 Dateien bekommen Daten ({d.status.text()})")
    check("Länge weicht ab" in d.model.rows[0].status, "Längen-Abweichung wird gezeigt (Testdateien sind 1 s lang)")

    # Von Hand zuordnen (1.1.7): Zeile anklicken → Menü mit den Tracks; belegter Track = die beiden tauschen
    menus = []

    def fake_exec(menu, *_a, pick=""):
        acts = [a for a in menu.actions() if a.text()]
        menus.append([a.text() for a in acts])
        if len(menus) == 1:                          # Bild vom echten Menü
            menu.popup(d.mapToGlobal(d.rect().center()))
            pump(app, 0.3)
            menu.grab().save(os.path.join(out, "o1_album_menue.png"))
            menu.close()
        next(a for a in acts if a.text().startswith(pick)).trigger()

    try:
        d._popup = lambda m: fake_exec(m, pick="2. ")
        d._choose_track(d.model.index(0, 0))
        titles = [r.cells[col][0] for r in d.model.rows]
        check(menus[-1][0].startswith("Track für") and any("⇄" in t for t in menus[-1]),
              f"Menü: Tracks, belegte mit ⇄ ({menus[-1][:3]})")
        check(titles[:2] == ["Shoot to Thrill", "Hells Bells"], f"getauscht: {titles[:2]}")
        check(d.model.rows[0].status.startswith("von Hand") and d.model.rows[1].status.startswith("von Hand"),
              f"als „von Hand“ markiert, ohne Warnung: {d.model.rows[0].status}")
        check(d.reset_btn.isVisible() and "2 von Hand" in d.status.text(), f"Zurücksetzen da: {d.status.text()}")
        d._popup = lambda m: fake_exec(m, pick="Keinen Track")
        d._choose_track(d.model.index(2, 0))
        check(d.model.rows[2].kind == O.UNCHANGED and d.model.preview.apply_count == 9,
              f"„Keinen Track“: Datei bleibt, 9 bekommen Daten ({d.model.rows[2].status})")
    finally:
        del d._popup
    pump(app, 0.3)
    d.grab().save(os.path.join(out, "o1_album_von_hand.png"))
    d.mode.setCurrentIndex(d.mode.findData("order"))
    pump(app)
    check(not d._manual and not d.reset_btn.isVisible(), "anderer Zuordnungs-Modus: Wahl von Hand verworfen")
    d.mode.setCurrentIndex(d.mode.findData("auto"))
    d._set_manual(0, 1)
    d._reset_manual()
    titles = [r.cells[col][0] for r in d.model.rows]
    check(titles[0] == "Hells Bells" and d.model.preview.apply_count == 10 and not d.reset_btn.isVisible(),
          "Zurücksetzen: wieder automatisch")
    d.grab().save(os.path.join(out, "o1_album.png"))
    d._apply()
    check(wait(app, lambda: not d.isVisible()), "übernommen")
    it = win.session.items[0]
    check((it.tags["title"], it.tags["track"], it.tags["year"]) == ("Hells Bells", "1/10", "1980"),
          f"Tags: {it.tags['title']} / {it.tags['track']} / {it.tags['year']}")
    check(bool(it.tags["label"]) and it.tags["originalyear"] == "1980",
          f"Label + Original-Jahr von MusicBrainz: {it.tags['label']!r} / {it.tags['originalyear']!r}")
    check(win.session.modified_count() == 10, "alles gelb, noch nicht gespeichert")
    win.undo()
    pump(app)
    check(win.session.items[0].tags["title"] == "Track 1", "Strg+Z nimmt Album-Daten in einem Schritt zurück")
    check(win.session.items[0].tags["label"] == "", "Label wieder leer")

    # --- Album suchen (Deezer, 1.1) ----------------------------------------------------------------
    requested.clear()
    d = O.AlbumSearchDialog(win, items, scope, "Deezer")
    d.show()
    check(wait(app, lambda: d.results.count() > 0), f"Deezer-Treffer: {d.results.count()}")
    check(sum(1 for u in requested if "api.deezer.com/search/album" in u) == 1, "genau EINE Suche bei Deezer")
    check(d.results.item(0).data(0x0100).album == "Back In Black", "bester Treffer = das Original")
    check(wait(app, lambda: d._current is not None and d.model.preview.apply_count > 0), "Deezer-Trackliste geladen")
    pump(app, 0.5)
    cols = d.model.preview.columns
    check("Label" in cols and "Original-Jahr" not in cols, f"Spalten: {cols}")
    row0 = d.model.rows[0].cells
    check(row0[cols.index("Titel")][0] == "Hells Bells" and row0[cols.index("Label")][0] == "Columbia",
          f"Track 1 + Label: {row0[cols.index('Titel')][0]} / {row0[cols.index('Label')][0]}")
    check("Neuauflage" in d.d_details.text(), "Hinweis: Jahr oft von der Neuauflage")
    d.field_chips["year"].setChecked(False)          # Jahr von Deezer lieber nicht (2014 = Remaster)
    pump(app, 0.2)
    check("Jahr" not in d.model.preview.columns, "Jahr abgewählt")
    check(not any("dzcdn" in u or "cover_" in u for u in requested), "keine Bilder von Deezer geladen")
    d.grab().save(os.path.join(out, "o1b_deezer.png"))
    d._apply()
    check(wait(app, lambda: not d.isVisible()), "Deezer übernommen")
    it = win.session.items[0]
    check((it.tags["title"], it.tags["label"], it.tags["year"]) == ("Hells Bells", "Columbia", ""),
          f"Deezer-Tags: {it.tags['title']} / {it.tags['label']} / Jahr {it.tags['year']!r}")
    win.undo()
    pump(app)
    check(win.session.items[0].tags["label"] == "", "Strg+Z nimmt Deezer-Daten zurück")
    d = O.AlbumSearchDialog(win, items, scope, "Deezer")
    check(d.field_chips["year"].isChecked() is False, "Feldauswahl wird gemerkt")
    d.field_chips["year"].setChecked(True)
    d.store_options()
    d.reject()

    # --- iTunes / Last.fm (1.1.2) -------------------------------------------------------------------
    if any("itunes.apple.com/lookup" in u for u in index):
        d = O.AlbumSearchDialog(win, items, scope, "iTunes")
        d.show()
        check(wait(app, lambda: d._current is not None and d.model.preview.apply_count > 0), "iTunes: Trackliste geladen")
        pump(app, 0.3)
        cols = d.model.preview.columns
        check(d.model.rows[0].cells[cols.index("Titel")][0].startswith("Hells Bells"), "iTunes: Track 1 = Hells Bells")
        d.grab().save(os.path.join(out, "o1c_itunes.png"))
        d.reject()
    else:
        print("  (iTunes noch nicht aufgezeichnet)")
    d = O.AlbumSearchDialog(win, items, scope, "Last.fm")
    d.show()
    check(wait(app, lambda: "API-Key" in d.status.text()), f"Last.fm ohne Key: {d.status.text()[:60]}")
    check(list(d.src) == ["MusicBrainz", "Discogs", "Deezer", "iTunes", "Last.fm", O.ALL_SOURCES],
          "fünf Album-Quellen + „Alle Quellen“")
    d.reject()

    # --- Discogs ohne Token ------------------------------------------------------------------------
    d = O.AlbumSearchDialog(win, items, scope, "Discogs")
    d.show()
    check(wait(app, lambda: "Token" in d.status.text()), f"Discogs ohne Token: {d.status.text()[:60]}")
    d.reject()

    # --- Cover suchen ------------------------------------------------------------------------------
    for f in os.listdir(album_dir):
        if f.endswith(".jpg"):
            os.remove(os.path.join(album_dir, f))
    d = O.CoverSearchDialog(win, items, scope)
    d.show()
    check(wait(app, lambda: d.grid.count() > 5), f"Cover gefunden: {d.grid.count()}")
    check(wait(app, lambda: len(d._thumbs) >= 3, 10), f"Vorschaubilder geladen: {len(d._thumbs)}")
    srcs = {c.source for c in d._candidates}
    check({"Cover Art Archive", "iTunes"} <= srcs and "Deezer" not in srcs, f"Quellen ohne Deezer: {sorted(srcs)}")
    check(list(d.src_chips) == ["Cover Art Archive", "iTunes", "TheAudioDB", "Bandcamp", "Discogs"], f"Chips: {list(d.src_chips)}")
    pump(app, 0.4)
    d.grab().save(os.path.join(out, "o2_cover.png"))
    d._apply()
    check(wait(app, lambda: not d.isVisible()), "Cover übernommen")
    check(all(i.cover_state()[0] == "new" for i in win.session.items), "Cover bei allen Dateien vorgemerkt")
    check(os.path.exists(os.path.join(album_dir, "cover.jpg")), "cover.jpg im Album-Ordner")
    from PIL import Image
    check(Image.open(os.path.join(album_dir, "cover.jpg")).size == (1400, 1400), "cover.jpg in voller Größe")
    win.save()
    check(wait(app, lambda: win._save_worker is None and win.session.modified_count() == 0), "gespeichert")
    rec = read_file(win.session.items[0].path)
    check(rec["cover"] and rec["cover"]["w"] == 600, f"eingebettet und verkleinert ({rec['cover']})")

    # --- Künstlerbild -------------------------------------------------------------------------------
    d = O.ArtistImageDialog(win, items, scope)
    d.show()
    check(d.target_dir == os.path.dirname(album_dir), "Ziel = Künstler-Ordner")
    check(list(d.src_chips) == ["TheAudioDB", "Bandcamp", "Discogs", "Wikipedia"], f"Quellen: {list(d.src_chips)}")
    check(not d.src_chips["Discogs"].isEnabled() and "Token" in d.src_chips["Discogs"].toolTip(),
          "Discogs ohne Token: aus, mit Hinweis")
    check(wait(app, lambda: d.grid.count() > 0), f"Künstlerbilder: {d.grid.count()}")
    wait(app, lambda: len(d._thumbs) >= 1, 8)
    pump(app, 0.4)
    d.grab().save(os.path.join(out, "o3_artist.png"))
    d._apply()
    check(wait(app, lambda: not d.isVisible()), "Künstlerbild übernommen")
    check(os.path.exists(os.path.join(os.path.dirname(album_dir), "folder.jpg")), "folder.jpg im Künstler-Ordner")

    # --- Alle Quellen + Übernehmen & weiter (1.1.4) --------------------------------------------------
    win.tree.select_paths([album_dir])
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 10), "wieder Back in Black")
    pump(app, 0.3)
    items, scope = win.tool_items()
    requested.clear()
    d = O.AlbumSearchDialog(win, items, scope, O.ALL_SOURCES)
    d.show()
    check(wait(app, lambda: getattr(d, "_all", {}).get("left", 1) == 0 and d.results.count() > 0, 30),
          f"alle Quellen fertig: {d.status.text()[:90]}")
    rows = [d.results.item(i) for i in range(d.results.count())]
    srcs = {r.data(0x0100).source for r in rows}
    check({"MusicBrainz", "Deezer", "iTunes"} <= srcs, f"Treffer aus mehreren Quellen: {sorted(srcs)}")
    check(all((r.data(0x0101) or "").startswith(r.data(0x0100).source) for r in rows), "jeder Treffer zeigt seine Quelle")
    check(d._all["skipped"] == ["Discogs", "Last.fm"], f"ohne Schlüssel übersprungen: {d._all['skipped']}")
    check(sum(1 for u in requested if "musicbrainz.org/ws/2/release/?" in u) <= 1, "MusicBrainz höchstens EINE Suche")
    pump(app, 0.5)
    d.grab().save(os.path.join(out, "o4_alle_quellen.png"))
    row = next(i for i, r in enumerate(rows) if r.data(0x0100).source == "iTunes")
    d.results.setCurrentRow(row)
    check(wait(app, lambda: d._current is not None and d._current.source == "iTunes" and d.next_btn.isEnabled()),
          "iTunes-Treffer gewählt, „Übernehmen & weiter“ bereit")
    d._apply_next()
    check(wait(app, lambda: d.items and d.items[0].dir == second_dir, 30), "nächster Ordner im selben Fenster")
    check(d.isVisible() and d.album.text() == "For Those About to Rock", f"Suchbegriffe neu: {d.album.text()!r}")
    check("2 ausgewählte" in d.scope_label.text(), f"Bereich neu: {d.scope_label.text()}")
    check(win.tree.is_done(album_dir), "voriger Ordner abgehakt")
    rec = read_file(os.path.join(album_dir, "01 - Track 1.mp3"))
    check(rec["tags"]["title"] == "Hells Bells", "voriger Ordner gespeichert")
    check(not d.next_btn.isEnabled() or d._current is not None, "„Übernehmen & weiter“ erst mit Treffer")
    pump(app, 0.5)
    d.skip_btn.click()                                   # letzter offener Ordner → fertig
    check(wait(app, lambda: "kein offener Ordner mehr" in d.status.text(), 30), f"am Ende: {d.status.text()[:70]}")
    check(win.tree.is_done(second_dir), "letzter Ordner abgehakt")
    d.reject()
    d = O.AlbumSearchDialog(win, items, scope)
    check(d.source == O.ALL_SOURCES and d.src[O.ALL_SOURCES].isChecked(), "Strg+L merkt sich „Alle Quellen“")
    d.reject()

    # Fehlerfall: ohne Netz
    http.set_transport(lambda url, h: (_ for _ in ()).throw(__import__("urllib.error").error.URLError("offline")))
    d = O.CoverSearchDialog(win, items, scope)
    d.show()
    check(wait(app, lambda: d.status.text().startswith("Keine Verbindung")), f"ohne Internet: {d.status.text()[:70]}")
    d.reject()

    with open(os.path.join(out, "online_requests.json"), "w") as fh:
        json.dump(requested, fh, indent=1)
    http.set_transport(None)
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    app.quit()
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
