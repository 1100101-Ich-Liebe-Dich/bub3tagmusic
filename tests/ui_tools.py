"""Oberflächen-Test der Werkzeuge (Phase 2): jedes Werkzeug öffnen, bedienen, Ergebnis prüfen.

Aufruf: QT_QPA_PLATFORM=offscreen python3 tests/ui_tools.py SAMMLUNG AUSGABEORDNER
Achtung: verändert Dateien in SAMMLUNG (run_all.sh nimmt eine frische Test-Sammlung).
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())
os.environ.setdefault("XDG_CACHE_HOME", tempfile.mkdtemp())

from PySide6.QtWidgets import QApplication  # noqa: E402

from bub3tagmusic.core.settings import Settings  # noqa: E402
from bub3tagmusic.core.tags import read_file  # noqa: E402
from bub3tagmusic.ui import theme  # noqa: E402

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


def pump(app, sec=0.25):
    t0 = time.time()
    while time.time() - t0 < sec:
        app.processEvents()
        time.sleep(0.01)


def main():
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    app = QApplication(sys.argv[:1])
    from bub3tagmusic.app import prepare_app
    prepare_app(app)
    theme.apply(app, "dark")
    from bub3tagmusic.ui import tools as T
    from bub3tagmusic.ui.mainwindow import MainWindow

    win = MainWindow(Settings())
    win.resize(1366, 768)
    win.show()
    win.tree.set_root(root, [])
    check(wait(app, lambda: win.tree.root_node is not None), "Sammlung gescannt")
    # ein kaum getaggtes Album nehmen (nur Titel = Dateiname) → ideal für "Tags aus Dateiname"
    album = next(a for a in win.tree._albums
                 if not read_file(os.path.join(a, sorted(f for f in os.listdir(a) if f[0].isdigit())[0]))
                 ["tags"]["artist"])
    win.tree.select_paths([album])
    check(wait(app, lambda: len(win.session.items) > 0), f"Album geladen: {os.path.basename(album)}")
    pump(app, 0.3)
    n = len(win.session.items)

    def dialog(fid):
        items, scope = win.tool_items()
        d = T.TOOL_DIALOGS[fid](win, items, scope)
        d.show()
        pump(app, 0.3)
        return d

    def shot(d, name):
        d.refresh()
        pump(app, 0.2)
        d.grab().save(os.path.join(out, name))

    # --- #1 Tags aus Dateiname --------------------------------------------------------
    d = dialog("tags_from_filename")
    d.pattern.combo.setEditText("%artist%/%year% - %album%/%track% - %title%")
    pump(app, 0.5)
    check(d.model.preview.apply_count == n, f"#1 Vorschau: alle {n} Dateien passen ({d.model.preview.summary})")
    shot(d, "t1_tags_from_filename.png")
    d.pattern.combo.setEditText("%track% - %titel%")
    pump(app, 0.5)
    check("meintest du %title%" in d.message.text(), "#1 Tippfehler im Muster wird erkannt")
    d.pattern.combo.setEditText("%artist%/%year% - %album%/%track% - %title%")
    pump(app, 0.5)
    d._apply()
    it = win.session.items[0]
    check(it.tags["artist"] == os.path.basename(os.path.dirname(album)), f"#1 Interpret gesetzt: {it.tags['artist']}")
    check(it.tags["track"] == "1" and it.tags["title"] == "Song 1", f"#1 Track/Titel: {it.tags['track']} / {it.tags['title']}")
    check(win.session.modified_count() == n, "#1 alles gelb (ungespeichert)")
    win.undo()
    pump(app)
    check(win.session.modified_count() == 0, "#1 Strg+Z nimmt das ganze Werkzeug in einem Schritt zurück")
    d = dialog("tags_from_filename")
    check(d.pattern.text() == "%artist%/%year% - %album%/%track% - %title%", "#1 Muster wird gemerkt")
    d._apply()
    win.save()
    check(wait(app, lambda: win._save_worker is None and win.session.modified_count() == 0), "#1 gespeichert")

    # --- #3 Nummerieren ------------------------------------------------------------------
    win.table.selectAll()
    pump(app)
    d = dialog("autonumber")
    d.findChildren(type(d.show_same))  # nur damit der Typ geladen ist
    for cb in d.findChildren(type(d.show_same)):
        if cb.text().startswith("Mit führender Null"):
            cb.setChecked(True)
    pump(app, 0.4)
    first = d.model.rows[0].cells[0][0] if d.model.rows else ""
    check(first == f"01/{n:02d}", f"#3 Vorschau 01/{n:02d}: {first}")
    shot(d, "t3_autonumber.png")
    d._apply()
    check(win.session.items[-1].tags["track"] == f"{n:02d}/{n:02d}", "#3 letzte Datei richtig nummeriert")

    # --- #4 Schreibweise -----------------------------------------------------------------
    win.session.apply_fields(win.session.items, {"album": "KURS NORD UND SÜD"})
    d = dialog("case")
    pump(app, 0.4)
    check(d.model.preview.apply_count == n, f"#4 Vorschau: {d.model.preview.summary}")
    shot(d, "t4_case.png")
    d._apply()
    check(win.session.items[0].tags["album"] == "Kurs Nord und Süd", f"#4 Album: {win.session.items[0].tags['album']}")

    # --- #5 Suchen & Ersetzen -------------------------------------------------------------
    d = dialog("replace")
    d.find.setText("Song (\\d+)")
    for cb in d.findChildren(type(d.show_same)):
        if cb.text() == "Regulärer Ausdruck":
            cb.setChecked(True)
    d.repl.setText("Lied Nr. $1")
    pump(app, 0.5)
    check(d.model.preview.apply_count == n and "Treffer" in d.model.preview.summary,
          f"#5 Vorschau: {d.model.preview.summary}")
    shot(d, "t5_replace.png")
    d.find.setText("Song (")
    pump(app, 0.5)
    check("Ungültiger Ausdruck" in d.message.text() and not d.apply_btn.isEnabled(), "#5 kaputter Ausdruck gemeldet")
    d.find.setText("Song (\\d+)")
    pump(app, 0.5)
    d._apply()
    check(win.session.items[0].tags["title"] == "Lied Nr. 1", f"#5 Titel: {win.session.items[0].tags['title']}")

    # --- #6 Aufräumen ---------------------------------------------------------------------
    win.session.apply_fields(win.session.items[:2], {"comment": "  doppelt  __leer ( ) "})
    d = dialog("cleanup")
    pump(app, 0.4)
    check(d.model.preview.apply_count == 2, f"#6 Vorschau: {d.model.preview.summary}")
    shot(d, "t6_cleanup.png")
    d._apply()
    check(win.session.items[0].tags["comment"] == "doppelt leer", f"#6 Kommentar: {win.session.items[0].tags['comment']!r}")
    win.save()
    check(wait(app, lambda: win._save_worker is None and win.session.modified_count() == 0), "#3–#6 gespeichert")

    # --- #2 Umbenennen (+ Rückgängig) -------------------------------------------------------
    win.table.selectAll()
    pump(app)
    before = sorted(os.listdir(album))
    d = dialog("filename_from_tags")
    d.pattern.combo.setEditText("%track% - %artist% - %title%")
    pump(app, 0.5)
    check(d.model.preview.apply_count == n, f"#2 Vorschau: {d.model.preview.summary}")
    shot(d, "t2_rename.png")
    d._apply()
    check(wait(app, lambda: win._save_worker is None), "#2 Umbenennen fertig")
    after = sorted(f for f in os.listdir(album) if not f.endswith(".jpg"))
    want = f"01 - {win.session.items[0].tags['artist']} - Lied Nr. 1"
    check(any(f.startswith(want) for f in after), f"#2 neuer Name: {after[0]}")
    check(all(os.path.exists(it.path) for it in win.session.items), "#2 Liste kennt die neuen Pfade")
    step = win.session.undo.peek()
    check(step.__class__.__name__ == "RenameStep", "#2 Umbenennen liegt im Rückgängig-Verlauf")
    win.session.undo.pop()
    win.run_rename([(new, old) for old, new in reversed(step.pairs)], step.label, record_undo=False)
    check(wait(app, lambda: win._save_worker is None), "#2 Zurückbenennen fertig")
    check(sorted(os.listdir(album)) == before, "#2 alte Namen wieder da")
    # Nach dem Zurückbenennen: Cache korrekt? Ordner neu laden und Tags prüfen
    win._load([album], force=True)
    check(wait(app, lambda: len(win.session.items) == n), "neu geladen")
    check(win.session.items[0].tags["title"] == "Lied Nr. 1" and win.session.items[0].path.endswith(before[0]),
          "Cache + Pfade nach Umbenennen stimmen")

    # Rechtsklick-Menü baut sich ohne Fehler
    win.table.selectAll()
    pump(app)
    check(len(win.table.selected_items()) == n, "Auswahl für Rechtsklick")

    # Helles Theme
    win.apply_theme("light")
    d = dialog("replace")
    d.find.setText("Lied")
    pump(app, 0.4)
    shot(d, "t7_light.png")
    d.reject()
    win.apply_theme("dark")
    win.grab().save(os.path.join(out, "t0_window.png"))
    win.session.revert()
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    app.quit()
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
