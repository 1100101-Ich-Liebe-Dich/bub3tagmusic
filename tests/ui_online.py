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
    check(srcs == {"Cover Art Archive", "iTunes", "Deezer"}, f"alle drei Quellen: {sorted(srcs)}")
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
    check(wait(app, lambda: d.grid.count() > 0), f"Künstlerbilder: {d.grid.count()}")
    wait(app, lambda: len(d._thumbs) >= 1, 8)
    pump(app, 0.4)
    d.grab().save(os.path.join(out, "o3_artist.png"))
    d._apply()
    check(wait(app, lambda: not d.isVisible()), "Künstlerbild übernommen")
    check(os.path.exists(os.path.join(os.path.dirname(album_dir), "folder.jpg")), "folder.jpg im Künstler-Ordner")

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
