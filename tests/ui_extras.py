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
    theme.apply(app, "dark")
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
    test_export(app, win, work, out)
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
