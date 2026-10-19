"""Extras der Phase 4 bedienen: Schnellfilter, Export, Duplikate, Aktionen, ReplayGain, Erkennen.

Aufruf: QT_QPA_PLATFORM=offscreen python3 tests/ui_extras.py ARBEITSORDNER SCREENSHOTS
Erzeugt eine kleine eigene Sammlung mit „echter“ Musik (Melodien statt Sinuston – sonst gibt es
keinen Fingerabdruck). fpcalc/rsgain-Teile laufen nur, wenn die Programme installiert sind.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())
os.environ.setdefault("XDG_CACHE_HOME", tempfile.mkdtemp())
os.environ.setdefault("XDG_DATA_HOME", tempfile.mkdtemp())       # Papierkorb landet hier

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from bub3tagmusic.core.settings import Settings  # noqa: E402
from bub3tagmusic.core.tags import write_file  # noqa: E402
from bub3tagmusic.core.tools_external import find_tool  # noqa: E402
from bub3tagmusic.ui import theme  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FEHLER ") + msg)
    if not cond:
        FAILS.append(msg)


def wait(app, cond, timeout=60.0):
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


# ----------------------------------------------------------------------
# Kleine Sammlung mit unterscheidbaren Melodien
# ----------------------------------------------------------------------
def melody(path: str, seed: int, seconds: int = 24, codec=("-c:a", "flac")):
    expr = (f"0.3*sin(2*PI*(220+110*mod(floor(t*{seed + 1}),5))*t)"
            f"+0.2*sin(2*PI*(330+55*mod(floor(t*{seed * 2 + 1}),7))*t)")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':d={seconds}",
                    "-ac", "2", *codec, "-map_metadata", "-1", path], check=True)


def cover_jpeg(size: int) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (30, 90, 120)).save(buf, "JPEG")
    return buf.getvalue()


def make_collection(base: str) -> dict[str, str]:
    from bub3tagmusic.core.covers import CoverData
    m = os.path.join(base, "Musik")
    mp3 = ("-c:a", "libmp3lame", "-b:a", "128k")
    p = {
        "eins": os.path.join(m, "Kielwasser", "2001 - Hochsee", "01 - Am Kai.flac"),
        "zwei": os.path.join(m, "Kielwasser", "2001 - Hochsee", "02 - Nebelhorn.mp3"),
        "drei": os.path.join(m, "Kielwasser", "2001 - Hochsee", "03 - Tiefgang.mp3"),
        "best": os.path.join(m, "Kielwasser", "2005 - Best Of", "07 - Am Kai.mp3"),
        "unbekannt": os.path.join(m, "Unsortiert", "track07.mp3"),
        "kaputt": os.path.join(m, "Unsortiert", "kaputt.mp3"),
    }
    melody(p["eins"], 3)
    melody(p["zwei"], 5, codec=mp3)
    melody(p["drei"], 8, codec=mp3)
    melody(p["best"], 3, codec=mp3)                 # gleiche Aufnahme wie „eins“, andere Kodierung
    melody(p["unbekannt"], 5, codec=("-c:a", "libmp3lame", "-b:a", "96k"))   # = „zwei“, ohne Tags
    with open(p["kaputt"], "wb") as fh:
        fh.write(b"das ist keine mp3" * 50)
    album = dict(artist="Kielwasser", albumartist="Kielwasser", album="Hochsee", year="2001", genre="Folk")
    write_file(p["eins"], dict(album, title="Am Kai", track="1/3"), CoverData(cover_jpeg(800), "image/jpeg"))
    write_file(p["zwei"], dict(album, title="Nebelhorn", track="2/3", year=""))
    write_file(p["drei"], dict(album, title="TIEFGANG", track="3/3"), CoverData(cover_jpeg(300), "image/jpeg"))
    write_file(p["best"], dict(artist="Kielwasser", album="Best Of", year="2005", title="am kai!", track="7"))
    return p


# ----------------------------------------------------------------------
def main():
    work, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    files = make_collection(work)
    root = os.path.join(work, "Musik")
    app = QApplication(sys.argv[:1])
    from bub3tagmusic.app import prepare_app
    prepare_app(app)
    theme.apply(app, "bub")
    from bub3tagmusic.ui.mainwindow import MainWindow

    # Rückfragen automatisch bestätigen
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)

    s = Settings()
    s.recursive = True
    win = MainWindow(s)
    win.resize(1366, 768)
    win.show()
    win.tree.set_root(root, [])
    check(wait(app, lambda: win.tree.root_node is not None), "Sammlung gescannt")
    win.tree.select_paths([os.path.join(root, "Kielwasser")])
    check(wait(app, lambda: len(win.session.items) == 4), f"Künstler geladen ({len(win.session.items)} Dateien)")
    pump(app, 0.6)

    test_filters(app, win, root, out)
    test_new_fields(app, win, root, out)
    test_choices(app, win, root, out)
    test_artist_folder(app, win, root, out)
    test_export(app, win, work, out)
    test_actions(app, win, root, files, out)
    test_replaygain(app, win, out)
    test_acoustid(app, win, root, out)
    test_duplicates(app, win, root, files, out)

    win.session.revert()
    win.close()
    print()
    print("ALLE EXTRAS OK" if not FAILS else f"{len(FAILS)} FEHLER")
    return 1 if FAILS else 0


def test_filters(app, win, root, out):
    print("Schnellfilter")
    bar = win.filterbar
    check(bar.isVisible(), "Filterleiste sichtbar")
    check(bar.chips["no_cover"].text().endswith("2"), f"Zähler am Chip: {bar.chips['no_cover'].text()}")
    bar.chips["no_cover"].setChecked(True)
    pump(app)
    names = [it.name for it in win.table.model_.visible_items()]
    check(names == ["02 - Nebelhorn.mp3", "07 - Am Kai.mp3"], f"ohne Cover: {names}")
    check("2 von 4 Dateien" in win.lbl_count.text(), f"Statusleiste: {win.lbl_count.text()}")
    win.grab().save(os.path.join(out, "x1_filter.png"))
    bar.chips["no_year"].setChecked(True)
    pump(app)
    check([it.name for it in win.table.model_.visible_items()] == ["02 - Nebelhorn.mp3"], "kombiniert: ohne Cover + Jahr")
    bar.clear()
    bar.chips["small_cover"].setChecked(True)
    pump(app)
    check([it.name for it in win.table.model_.visible_items()] == ["03 - Tiefgang.mp3"], "Cover < 500 px")
    # Ungespeichert
    bar.clear()
    win.session.apply_fields([win.session.items[0]], {"comment": "x"})
    bar.chips["modified"].setChecked(True)
    pump(app)
    check(len(win.table.model_.visible_items()) == 1, "ungespeichert")
    win.undo()
    bar.clear()
    # Ganze Sammlung: Lesefehler + ohne Cover
    bar.chips["error"].setChecked(True)
    pump(app)
    win.search_collection()
    check(wait(app, lambda: win._load_worker is None and win._search is not None), "Suche in der ganzen Sammlung")
    pump(app, 0.4)
    check([it.name for it in win.session.items] == ["kaputt.mp3"], f"Treffer: {[it.name for it in win.session.items]}")
    check("Sammlung" in win.windowTitle(), f"Fenstertitel: {win.windowTitle()}")
    bar.clear()
    bar.chips["no_cover"].setChecked(True)
    win.search_collection()
    check(wait(app, lambda: win._load_worker is None), "zweite Suche fertig")
    pump(app, 0.4)
    check(len(win.session.items) == 3, f"ohne Cover in der Sammlung: {[it.name for it in win.session.items]}")
    win.grab().save(os.path.join(out, "x2_filter_sammlung.png"))
    bar.clear()
    win.toggle_filter_bar()
    check(not bar.isVisible() and not win.settings.show_filter_bar, "Leiste ausblenden (Extras → Erweiterte Filter)")
    win.toggle_filter_bar()
    win.tree.select_paths([os.path.join(root, "Kielwasser")])
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 4 and win._search is None),
          "Ordner wählen beendet die Suche")
    pump(app, 0.4)


def test_new_fields(app, win, root, out):
    print("Label, Original-Jahr, Songtext (1.1)")
    from bub3tagmusic.core.tags import read_file
    from bub3tagmusic.ui import lyrics as ui_lyrics
    from bub3tagmusic.ui.filetable import COLUMN_INDEX
    album = os.path.join(root, "Kielwasser", "2001 - Hochsee")
    win.tree.select_paths([album])
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 3), "Album geladen")
    pump(app, 0.3)
    panel = win.panel
    # Label + Original-Jahr für alle drei
    win.table.selectAll()
    pump(app, 0.2)
    for key, value in (("label", "Harvest"), ("originalyear", "1975")):
        fe = panel.fields[key]
        fe.setText(value)
        fe.textEdited.emit(value)
        fe.editingFinished.emit()
        pump(app, 0.1)
    check(all(it.tags["label"] == "Harvest" and it.tags["originalyear"] == "1975" for it in win.session.items),
          "Label + Original-Jahr für alle gesetzt")
    check(panel.lyrics.text().startswith("Kein Songtext"), f"Songtext-Zeile leer: {panel.lyrics.text()!r}")

    # Begleitdatei neben „01 - Am Kai.flac“
    lrc = os.path.join(album, "01 - Am Kai.lrc")
    with open(lrc, "w", encoding="utf-8") as fh:
        fh.write("[ar:Kielwasser]\n[ti:Am Kai]\n[00:01.00]Das Schiff liegt still\n[00:04.50]am Kai im Nebel\n"
                 "\n[00:09.00]Möwen über'm Deck\n")
    first = next(it for it in win.session.items if it.name.startswith("01"))
    row = win.table.model_.row_of(first)
    win.table.selectRow(row)
    pump(app, 0.2)

    def run_dialog(actions):
        orig = ui_lyrics.LyricsDialog.exec

        def fake(dlg):
            dlg.show()
            pump(app, 0.2)
            r = actions(dlg)
            return dlg.result() if r is None else r
        ui_lyrics.LyricsDialog.exec = fake
        try:
            panel.lyrics.click()
            pump(app, 0.2)
        finally:
            ui_lyrics.LyricsDialog.exec = orig

    def from_lrc(dlg):
        check(hasattr(dlg, "btn_found") and "01 - Am Kai.lrc" in dlg.btn_found.text(),
              f"Begleitdatei erkannt: {getattr(dlg, 'btn_found', None) and dlg.btn_found.text()}")
        dlg.btn_found.click()
        check(dlg.edit.toPlainText() == "Das Schiff liegt still\nam Kai im Nebel\n\nMöwen über'm Deck",
              f"Zeitmarken entfernt: {dlg.edit.toPlainText()!r}")
        dlg.grab().save(os.path.join(out, "x0_songtext.png"))
        dlg.ok.click()
    run_dialog(from_lrc)
    check(first.tags["lyrics"].startswith("Das Schiff"), "Songtext übernommen (gelb)")
    check(panel.lyrics.text().startswith("3 Zeilen"), f"Songtext-Zeile: {panel.lyrics.text()!r}")
    check(win.table.model_.index(row, COLUMN_INDEX["lyrics"]).data() == "3 Zeilen", "Spalte Songtext")
    win.grab().save(os.path.join(out, "x0_felder.png"))

    # Abbrechen ändert nichts
    run_dialog(lambda dlg: (dlg.edit.setPlainText("anders"), dlg.reject()) and None)
    check(first.tags["lyrics"].startswith("Das Schiff"), "Abbrechen lässt den Songtext")

    # Mehrere Dateien mit verschiedenen Songtexten: festlegen für alle
    win.table.selectAll()
    pump(app, 0.2)
    check(panel.lyrics.mixed, "Auswahl: verschiedene Songtexte")

    def for_all(dlg):
        check(dlg.edit.toPlainText() == "", "verschieden → leeres Feld")
        check("1 von 3" in dlg.btn_found.text(), f"Begleitdateien zählen: {dlg.btn_found.text()}")
        dlg.edit.setPlainText("Instrumental\r\n")
        dlg.ok.click()
    run_dialog(for_all)
    check(all(it.tags["lyrics"] == "Instrumental" for it in win.session.items), "Songtext für alle (bereinigt)")
    win.undo()
    pump(app, 0.2)
    check(first.tags["lyrics"].startswith("Das Schiff") and win.session.items[1].tags["lyrics"] == "",
          "Strg+Z: jeder wieder mit seinem Songtext")

    # Suchen & Ersetzen kennt die neuen Felder, der Dateiname-Platzhalter %lyrics% nicht
    from bub3tagmusic.ui.tools import TOOL_DIALOGS
    d = TOOL_DIALOGS["replace"](win, win.session.items, "Test")
    check("lyrics" in d.fields._chips and "label" in d.fields._chips, "Ersetzen: Songtext + Label wählbar")
    d.close()

    # Speichern und von der Platte lesen
    win.save()
    check(wait(app, lambda: win._save_worker is None and win.session.modified_count() == 0), "gespeichert")
    rec = read_file(first.path)["tags"]
    check(rec["label"] == "Harvest" and rec["originalyear"] == "1975" and rec["lyrics"].endswith("über'm Deck"),
          f"auf der Platte: {rec['label']!r} {rec['originalyear']!r} {rec['lyrics'][:20]!r}")
    mp3 = read_file(os.path.join(album, "02 - Nebelhorn.mp3"))["tags"]
    check(mp3["label"] == "Harvest" and mp3["originalyear"] == "1975", "MP3 (ID3v2.3): Label + Original-Jahr")
    os.remove(lrc)
    win.tree.select_paths([os.path.join(root, "Kielwasser")])
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 4), "zurück zum Künstler")
    pump(app, 0.3)


def test_choices(app, win, root, out):
    print("‹verschieden› – aus vorhandenen Werten wählen (1.1.1)")
    win.table.selectAll()
    pump(app, 0.3)
    panel = win.panel
    album = panel.fields["album"]
    check(album.mixed and album._pick.isVisible(), "Pfeil bei ‹verschieden› sichtbar")
    check(not panel.fields["title"]._pick.isVisible() or panel.fields["title"].mixed, "Pfeil nur bei ‹verschieden›")
    check(not panel.fields["track"]._pick.isVisible(), "kein Pfeil bei Track")
    check(panel.fields["genre"]._pick.isVisible() is False or panel.fields["genre"].mixed, "Genre wie die anderen")
    menu = panel.choice_menu(album)
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    check(texts[1:3] == ["Hochsee\t3×", "Best Of\t1×"], f"Werte nach Häufigkeit: {texts}")
    aa = panel.choice_menu(panel.fields["albumartist"])
    check(any("ohne Wert" in a.text() for a in aa.actions()), "Hinweis auf Dateien ohne Wert")
    before = [it.tags["album"] for it in win.session.items]
    menu.close()                                          # nichts gewählt → nichts passiert
    pump(app, 0.1)
    check([it.tags["album"] for it in win.session.items] == before and win.session.modified_count() == 0,
          "Menü schließen ändert nichts")
    pick = next(a for a in menu.actions() if a.text().startswith("Hochsee"))
    pick.trigger()
    pump(app, 0.2)
    check(all(it.tags["album"] == "Hochsee" for it in win.session.items), "Hochsee für alle 4 gesetzt")
    check(not album.mixed and album.text() == "Hochsee" and not album._pick.isVisible(), "Feld zeigt den Wert")
    check(win.session.modified_count() == 1, f"nur die eine Datei wird gelb ({win.session.modified_count()})")
    win.undo()
    pump(app, 0.2)
    check([it.tags["album"] for it in win.session.items] == before and album.mixed, "Strg+Z stellt alles wieder her")
    win.grab().save(os.path.join(out, "x0_auswahl.png"))
    # Alt+↓ öffnet das Menü (hier abgefangen, damit der Test nicht wartet)
    shown = []
    orig = panel._show_choices
    panel._show_choices = lambda fe: shown.append(fe.key)
    album.choicesRequested.disconnect()
    album.choicesRequested.connect(panel._show_choices)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent          # (QtTest fehlt im AppImage)
    album.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier))
    check(shown == ["album"], "Alt+↓ öffnet die Auswahl")
    album.choicesRequested.disconnect()
    panel._show_choices = orig
    album.choicesRequested.connect(panel._show_choices)


def test_artist_folder(app, win, root, out):
    print("Künstler-Ordner (folder.jpg)")
    artist = os.path.join(root, "Kielwasser")
    win.btn_recursive.setChecked(False)
    check(wait(app, lambda: win._load_worker is None), "ohne Unterordner neu geladen")
    pump(app, 0.3)
    check(win.session.items == [] and win.right.currentWidget() is win.artist_panel,
          "Künstler-Ordner ohne Musik → rechts das Künstler-Feld")
    ap = win.artist_panel
    check(ap.title.text() == "Kielwasser" and ap.artist_name() == "Kielwasser", "Ordnername = Künstlername")
    check(ap.albums.count() == 2 and "0 von 2" in ap.albums_head.text(), f"Alben: {ap.albums_head.text()}")
    check(not ap.existing_image() and not ap.btn_remove.isEnabled(), "noch kein folder.jpg")
    win.grab().save(os.path.join(out, "x9_kuenstler_leer.png"))
    ok = ap.set_image_bytes(cover_jpeg(600))
    target = os.path.join(artist, "folder.jpg")
    check(ok and os.path.exists(target), "folder.jpg direkt im Künstler-Ordner gespeichert")
    check("600 × 600" in ap.image_info.text(), ap.image_info.text())
    ap.set_image_bytes(cover_jpeg(800))                 # ersetzen (Rückfrage wird bejaht)
    from PIL import Image
    check(Image.open(target).size == (800, 800), "ersetzt – altes Bild im Papierkorb")
    trash = os.path.join(os.environ["XDG_DATA_HOME"], "Trash", "files")
    check(os.path.isdir(trash) and any(f.startswith("folder") for f in os.listdir(trash)), "alt liegt im Papierkorb")
    win.grab().save(os.path.join(out, "x9_kuenstler.png"))
    # Online-Suche: Künstlername aus dem (änderbaren) Feld, Ziel = dieser Ordner
    ap.artist.setText("Kielwasser Band")
    from bub3tagmusic.ui.online import ArtistImageDialog
    d = ArtistImageDialog(win, [], "", folder=artist, artist=ap.artist_name())
    check(d.target_dir == artist and d.artist.text() == "Kielwasser Band", "Online-Suche mit Ordner + Namen")
    d.reject()
    # Strg+J öffnet die Suche für den Ordner (ohne geladene Dateien)
    opened = []
    win.search_artist_image = lambda folder="": opened.append(folder or win.artist_folder())
    win.open_online("artist_image")
    check(opened == [artist], f"Strg+J im Künstler-Ordner: {opened}")
    # Rechtsklick im Baum: auch für jeden anderen Ordner
    win.tree.artistImageRequested.emit(os.path.join(artist, "2001 - Hochsee"))
    check(opened[-1] == os.path.join(artist, "2001 - Hochsee"), "Baum-Menü: Künstlerbild für diesen Ordner")
    del win.search_artist_image
    # „Alle Alben laden“ → Unterordner an, normale Bearbeitung
    ap.loadAlbumsRequested.emit(artist)
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 4), "alle Alben geladen")
    pump(app, 0.3)
    check(win.right.currentWidget() is win.panel and win.btn_recursive.isChecked(), "zurück im Bearbeitungsfeld")
    os.remove(target)


def test_export(app, win, work, out):
    print("Export")
    from bub3tagmusic.ui.export import ExportDialog
    d = ExportDialog(win)
    d.open_after.setChecked(False)
    d.rb_csv.setChecked(True)
    path = os.path.join(work, "liste.csv")
    d.export(path)
    check(wait(app, lambda: os.path.exists(path) and d.result_path), "CSV geschrieben")
    rows = list(csv.reader(open(path, encoding="utf-8-sig"), delimiter=";"))
    check(rows[0][:3] == ["Dateiname", "Titel", "Interpret"] and len(rows) == 5, f"CSV-Kopf + 4 Zeilen: {rows[0]}")
    # Spaltenreihenfolge wie auf dem Bildschirm
    hh = win.table.horizontalHeader()
    from bub3tagmusic.ui.filetable import COLUMN_INDEX
    hh.moveSection(hh.visualIndex(COLUMN_INDEX["title"]), 1)
    d = ExportDialog(win)
    d.open_after.setChecked(False)
    d.rb_html.setChecked(True)
    d.show()
    pump(app)
    d.grab().save(os.path.join(out, "x3_export.png"))
    path = os.path.join(work, "liste.html")
    d.export(path)
    check(wait(app, lambda: os.path.exists(path) and d.result_path), "HTML geschrieben")
    page = open(path, encoding="utf-8").read()
    check(page.index(">Titel<") < page.index(">Dateiname<"), "HTML: verschobene Spalte steht vorn")
    check("Kielwasser" in page and "präsentiert von" in page, "HTML: Inhalt + präsentiert von")
    hh.moveSection(hh.visualIndex(COLUMN_INDEX["title"]), COLUMN_INDEX["title"])
    # nur Auswahl
    win.table.selectRow(0)
    pump(app)
    d = ExportDialog(win)
    d.open_after.setChecked(False)
    d.rb_csv.setChecked(True)
    d.rb_sel.setChecked(True)
    path = os.path.join(work, "auswahl.csv")
    d.export(path)
    check(wait(app, lambda: os.path.exists(path) and d.result_path), "Auswahl exportiert")
    check(len(list(csv.reader(open(path, encoding="utf-8-sig"), delimiter=";"))) == 2, "nur 1 Zeile")


def test_actions(app, win, root, files, out):
    print("Aktionen")
    from bub3tagmusic.core.undo import ChainStep
    from bub3tagmusic.ui.extras import EXTRA_DIALOGS
    win.table.selectAll()
    pump(app)
    items, scope = win.tool_items()
    d = EXTRA_DIALOGS["actions"](win, items, scope)
    d.show()
    pump(app, 0.5)
    names = [d.combo.itemText(i) for i in range(d.combo.count())]
    check("Album fertig machen" in names, f"Beispiel-Aktionen da: {names}")
    check(os.path.exists(d.path), "actions.json angelegt")
    d.combo.setCurrentIndex(names.index("Album fertig machen"))
    pump(app, 0.8)
    p = d.model.preview
    check("Neuer Name" in p.columns and "Titel" in p.columns, f"Vorschau-Spalten: {p.columns}")
    check(p.apply_count == 2, f"2 Dateien betroffen: {p.summary}")
    d.grab().save(os.path.join(out, "x5_aktionen.png"))
    best_dir = os.path.dirname(files["best"])
    d._apply()
    check(wait(app, lambda: win._save_worker is None), "Aktion ausgeführt")
    pump(app, 0.3)
    check(os.path.exists(os.path.join(best_dir, "07 - Am Kai!.mp3")), "umbenannt mit neuen Tags (Am Kai!)")
    it = next(i for i in win.session.items if i.name == "07 - Am Kai!.mp3")
    check(it.tags["albumartist"] == "Kielwasser" and it.tags["title"] == "Am Kai!", f"Tags: {it.tags['title']}")
    tief = next(i for i in win.session.items if i.name == "03 - Tiefgang.mp3")
    check(tief.tags["title"] == "Tiefgang", "Schreibweise: TIEFGANG → Tiefgang")
    check(isinstance(win.session.undo.peek(), ChainStep), "ein einziger Rückgängig-Schritt (Tags + Umbenennen)")
    win.undo()
    check(wait(app, lambda: win._save_worker is None and os.path.exists(files["best"])), "Strg+Z benennt zurück")
    pump(app, 0.3)
    check(win.session.modified_count() == 0, "… und nimmt die Tag-Änderungen zurück")
    # eigene Aktion anlegen
    d = EXTRA_DIALOGS["actions"](win, win.session.items, "alle")
    d.new_action("Kommentar weg")
    d.add_step("set_field", edit=False)
    d.action.steps[0]["opts"].update(field="comment", value="Gerippt von BuB3", only_empty=False)
    d._changed(0)
    d.add_step("rename", edit=False)
    d.add_step("cleanup", edit=False)
    check([s["type"] for s in d.action.steps] == ["set_field", "cleanup", "rename"], "Umbenennen bleibt am Ende")
    d.refresh()
    check(d.model.preview.apply_count == 4, f"eigene Aktion: {d.model.preview.summary}")
    from bub3tagmusic.core import actions as A
    check(any(a.name == "Kommentar weg" for a in A.load_actions(d.path)), "eigene Aktion gespeichert")
    d.reject()


def test_replaygain(app, win, out):
    print("ReplayGain")
    from bub3tagmusic.ui.extras import EXTRA_DIALOGS
    from bub3tagmusic.ui.filetable import COLUMN_INDEX
    win.table.selectAll()
    pump(app)
    items, scope = win.tool_items()
    d = EXTRA_DIALOGS["replaygain"](win, items, scope)
    d.show()
    pump(app)
    check(d.tree.topLevelItemCount() == 2, "zwei Alben (Ordner)")
    if not find_tool("rsgain"):
        check(not d.start_btn.isEnabled() and "rsgain" in d.message.text(), "ohne rsgain: Hinweis statt Start")
        d.grab().save(os.path.join(out, "x6_replaygain_fehlt.png"))
        d.reject()
        return
    from bub3tagmusic.core import replaygain as rg
    check(d._mode() == rg.MODE_SCAN and d.start_btn.text() == "Messen", "Start ist immer „Nur messen“")
    check(not d.message.isVisible() or not d.message.text(), "beim Messen keine Warnung")
    mtimes = [os.stat(it.path).st_mtime_ns for it in items]
    d.start()
    check(wait(app, lambda: d.task is not None and not d.task.isRunning() and d.results, 120), "gemessen")
    pump(app, 0.3)
    check(all(r.gain for r in d.results), f"Messwerte da: {[r.gain for r in d.results]}")
    check([os.stat(it.path).st_mtime_ns for it in items] == mtimes and not any(it.rec.get("rg") for it in items),
          "Nur messen: keine Datei verändert")
    check("nichts geändert" in d.message.text(), d.message.text())
    # Schreiben: Warnung im Fenster + Rückfrage; Abbrechen = nichts passiert
    d.modes.buttons()[1].setChecked(True)
    pump(app)
    check("NICHT mit Strg+Z" in d.message.text() and d.message.isVisible(), "Warnung sichtbar beim Schreiben")
    asked = []
    d.confirm_write = lambda mode, n: (asked.append((mode, n)), False)[1]
    d.start()
    pump(app, 0.3)
    check(asked == [(rg.MODE_ALBUM, 4)] and (d.task is None or not d.task.isRunning()), "Rückfrage kommt, Nein = nichts")
    check([os.stat(it.path).st_mtime_ns for it in items] == mtimes, "nach Nein: Dateien unverändert")
    d.confirm_write = lambda mode, n: (asked.append((mode, n)), True)[1]
    # ungespeicherte Änderung → erst speichern (Rückfrage wird automatisch bejaht)
    win.session.apply_fields([items[0]], {"comment": "vor ReplayGain"})
    d.results.clear()
    d.start()
    check(wait(app, lambda: d.task is not None and not d.task.isRunning() and d.results, 120), "ReplayGain geschrieben")
    pump(app, 0.3)
    check(win.session.modified_count() == 0, "vorher gespeichert")
    check(items[0].tags["comment"] == "vor ReplayGain", "gespeicherte Änderung bleibt erhalten")
    check(all(r.gain for r in d.results) and all(not r.error for r in d.results),
          f"Album-Gain je Ordner: {[r.gain for r in d.results]}")
    rgs = [(it.rec.get("rg") or {}) for it in win.session.items]
    check(all(r.get("track") and r.get("album") for r in rgs), f"Liste kennt die neuen Werte: {rgs[:1]}")
    win.table.horizontalHeader().setSectionHidden(COLUMN_INDEX["rg_album"], False)
    win.table.horizontalHeader().setSectionHidden(COLUMN_INDEX["rg_track"], False)
    d.grab().save(os.path.join(out, "x6_replaygain.png"))
    d.reject()
    pump(app)
    win.grab().save(os.path.join(out, "x7_replaygain_liste.png"))
    fe = win.panel.fields["title"]
    pos = fe.mapTo(win, fe.rect().topLeft())
    border = win.grab().toImage().pixelColor(pos.x() + 40, pos.y()).name()
    check(border != theme.tok("modified").lower(), f"kein gelber Rahmen mehr nach Rückgängig/Speichern ({border})")
    # entfernen
    d = EXTRA_DIALOGS["replaygain"](win, items, scope)
    d.modes.buttons()[3].setChecked(True)
    d.confirm_write = lambda mode, n: True
    d.start()
    check(wait(app, lambda: d.task is not None and not d.task.isRunning(), 120), "ReplayGain entfernt")
    pump(app, 0.3)
    check(not any(it.rec.get("rg") for it in win.session.items), "keine ReplayGain-Werte mehr")
    d.reject()


def test_acoustid(app, win, root, out):
    print("Erkennen (AcoustID)")
    import dataclasses
    import json
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from online_fixtures import FIXTURES, use_fixtures
    from bub3tagmusic.online import acoustid
    from bub3tagmusic.ui.extras import EXTRA_DIALOGS
    use_fixtures()
    info_path = os.path.join(FIXTURES, "acoustid.json")
    info = json.load(open(info_path)) if os.path.exists(info_path) else {}
    calls = []

    def fake_lookup(fp, duration, key, album=""):
        calls.append((len(fp), round(duration), key))
        if info.get("trackid"):
            return [dataclasses.replace(m, score=0.95) for m in acoustid.lookup_track(info["trackid"], "TESTKEY")]
        return [acoustid.AcoustMatch(0.95, "r", "Hells Bells", "AC/DC", "Back in Black", "AC/DC", "1980", 1, 10)]
    real = acoustid.lookup
    acoustid.lookup = fake_lookup
    win.tree.select_paths([os.path.join(root, "Unsortiert")])
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 2), "Ordner ohne Tags geladen")
    pump(app, 0.3)
    win.table.selectAll()
    pump(app)
    items, scope = win.tool_items()
    win.settings.acoustid_key = ""
    d = EXTRA_DIALOGS["acoustid"](win, items, scope)
    d.show()
    pump(app, 0.4)
    check(len(d.targets()) == 1, "nur die Datei ohne Titel (kaputte Datei zählt nicht)")
    if not find_tool("fpcalc"):
        check(not d.start_btn.isEnabled(), "ohne fpcalc: Start gesperrt, Hinweis da")
        d.reject()
        acoustid.lookup = real
        return
    d.start()
    check("Key" in d.message.text(), f"ohne Key: Hinweis ({d.message.text()})")
    d.key.setText("TESTKEY")
    d._store_key()
    check(win.settings.acoustid_key == "TESTKEY", "Key wird in den Einstellungen gemerkt")
    d.start()
    check(wait(app, lambda: d.task is not None and not d.task.isRunning(), 60), "Erkennen fertig")
    pump(app, 0.5)
    check(calls and calls[0][2] == "TESTKEY" and calls[0][0] > 100, f"Fingerabdruck + Key an AcoustID: {calls[:1]}")
    p = d.model.preview
    check(p.apply_count == 1 and "erkannt (95 %)" in p.rows[0].status, f"Vorschau: {p.summary} / {p.rows[0].status}")
    d.grab().save(os.path.join(out, "x8_erkennen.png"))
    d._apply()
    it = next(i for i in win.session.items if i.name == "track07.mp3")
    check(it.tags["title"] == "Hells Bells" and it.tags["artist"] == "AC/DC", f"übernommen: {it.tags['title']}")
    check(win.session.modified_count() == 1, "gelb markiert, noch nicht gespeichert")
    win.undo()
    check(win.session.modified_count() == 0, "Strg+Z nimmt es zurück")
    # zweiter Durchlauf: Fingerabdruck kommt aus dem Zwischenspeicher
    d = EXTRA_DIALOGS["acoustid"](win, items, scope)
    import bub3tagmusic.ui.acoustid as UA
    real_fp = UA.fingerprint
    UA.fingerprint = lambda *a, **k: (_ for _ in ()).throw(AssertionError("fpcalc sollte nicht laufen"))
    d.start()
    check(wait(app, lambda: d.task is not None and not d.task.isRunning(), 60), "zweites Mal fertig")
    pump(app, 0.3)
    check(d.model.preview.apply_count == 1, "Fingerabdruck aus dem Zwischenspeicher")
    UA.fingerprint = real_fp
    d.reject()
    acoustid.lookup = real
    from bub3tagmusic.online import http
    http.set_transport(None)
    win.tree.select_paths([os.path.join(root, "Kielwasser")])
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 4), "zurück zum Künstler")
    pump(app, 0.3)


def test_duplicates(app, win, root, files, out):
    print("Duplikate")
    from bub3tagmusic.ui.extras import DuplicatesDialog
    win.table.selectAll()
    items, scope = win.tool_items()
    d = DuplicatesDialog(win, items, scope)
    d.show()
    d.rb_list.setChecked(True)
    d.cb_sound.setChecked(False)
    d.search()
    check(wait(app, lambda: d.task is not None and not d.task.isRunning() and d.groups is not None
               and d.summary.text() != "Noch nicht gesucht"), "Suche nach Tags fertig")
    pump(app, 0.2)
    titles = [g.title for g in d.groups]
    check(len(d.groups) == 1 and len(d.groups[0].members) == 2, f"Am Kai doppelt (FLAC + MP3): {titles}")
    if d.groups:
        best = d.entries[d.groups[0].best]
        check(best.path == files["eins"], "beste Qualität = FLAC")
    if not find_tool("fpcalc"):
        print("  (fpcalc fehlt – Klang-Vergleich übersprungen)")
        d.close()
        return
    d.rb_all.setChecked(True)
    d.cb_sound.setChecked(True)
    d.search()
    check(wait(app, lambda: not d.task.isRunning(), 120), "Suche nach Klang in der ganzen Sammlung fertig")
    pump(app, 0.3)
    groups = sorted(sorted(os.path.basename(d.entries[i].path) for i in g.members) for g in d.groups)
    check(groups == [["01 - Am Kai.flac", "07 - Am Kai.mp3"], ["02 - Nebelhorn.mp3", "track07.mp3"]],
          f"Klang findet auch die Datei ohne Tags: {groups}")
    check("1 Datei ohne Interpret oder Titel konnte" in d.message.text(), f"Hinweis: {d.message.text()}")
    d.grab().save(os.path.join(out, "x4_duplikate.png"))
    # Papierkorb: die Datei ohne Tags
    for t in range(d.tree.topLevelItemCount()):
        top = d.tree.topLevelItem(t)
        for c in range(top.childCount()):
            if top.child(c).text(0) == "track07.mp3":
                top.child(c).setCheckState(0, Qt.CheckState.Checked)
    pump(app)
    check(d.btn_trash.text() == "In den Papierkorb (1)", d.btn_trash.text())
    d.trash()
    pump(app, 0.3)
    check(not os.path.exists(files["unbekannt"]), "Datei liegt im Papierkorb")
    check(len(d.groups) == 1, "Gruppe mit nur noch einer Datei verschwindet")
    # in der Liste zeigen
    d.show_in_list()
    check(wait(app, lambda: win._load_worker is None and len(win.session.items) == 2), "Duplikate in der Liste")
    check(win._result_label == "Duplikate" and "Duplikate" in win.lbl_count.text(), win.lbl_count.text())


if __name__ == "__main__":
    sys.exit(main())
