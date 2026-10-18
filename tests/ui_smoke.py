"""Oberflächen-Test ohne Bildschirm: startet das Fenster, klickt sich durch und macht Screenshots.

Aufruf: QT_QPA_PLATFORM=offscreen python3 tests/ui_smoke.py SAMMLUNG AUSGABEORDNER
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


def pump(app, sec=0.3):
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
    s = Settings()
    theme.apply(app, s.theme)
    from bub3tagmusic.ui.mainwindow import MainWindow
    win = MainWindow(s)
    win.resize(1440, 860)
    win.show()
    win.tree.set_root(root, [])
    win._update_empty_text()
    check(wait(app, lambda: win.tree.root_node is not None), "Ordnerbaum gescannt")
    albums = win.tree._albums
    check(len(albums) > 10, f"{len(albums)} Alben gefunden")
    pump(app)
    win.grab().save(os.path.join(out, "01_start.png"))

    # Album wählen
    win.tree.select_paths([albums[1]])
    check(wait(app, lambda: len(win.session.items) > 0), "Album geladen")
    pump(app, 0.4)
    check(len(win.panel.items) == len(win.session.items), "nach dem Laden alles ausgewählt")
    win.grab().save(os.path.join(out, "02_album.png"))

    # Feld für alle setzen
    fe = win.panel.fields["genre"]
    fe.setFocus()
    fe.setText("Deutschrock")
    fe.textEdited.emit("Deutschrock")
    fe.editingFinished.emit()
    pump(app)
    check(all(it.tags["genre"] == "Deutschrock" for it in win.session.items), "Genre für alle gesetzt")
    check(win.session.modified_count() == len(win.session.items), "alle als geändert markiert")
    # einzelne Datei: Titel ändern
    win.table.selectRow(2)
    pump(app, 0.2)
    t = win.panel.fields["title"]
    t.setText("Neuer Titel")
    t.textEdited.emit("Neuer Titel")
    t.editingFinished.emit()
    pump(app, 0.3)
    win.grab().save(os.path.join(out, "03_modified.png"))

    # Rückgängig der letzten Bearbeitung
    win.undo()
    pump(app)
    check(win.session.items[2].tags["title"] != "Neuer Titel", "Rückgängig (Bearbeitung)")

    # Speichern & weiter
    first_album = win.session.dirs()[0]
    win.save_and_next()
    check(wait(app, lambda: win.tree.is_done(first_album)), "Ordner als fertig markiert")
    check(wait(app, lambda: win.session.items and win.session.dirs()[0] != first_album), "zum nächsten Ordner gesprungen")
    from bub3tagmusic.core.tags import read_file
    rec = read_file(os.path.join(first_album, sorted(os.listdir(first_album))[0]))
    check(rec["tags"]["genre"] == "Deutschrock", "Genre wirklich in Datei gespeichert")
    pump(app, 0.4)

    # Rückgängig des Speicherns (ohne Rückfrage-Dialog testen)
    step = win.session.undo.peek()
    check(step is not None and step.__class__.__name__ == "SaveStep", "Speichern liegt im Rückgängig-Verlauf")
    win.session.undo.pop()
    win._run_save(win.session.undo_jobs(step), step.label, record_undo=False)
    check(wait(app, lambda: win._save_worker is None), "Rückgängig-Speichern beendet")
    rec = read_file(os.path.join(first_album, sorted(os.listdir(first_album))[0]))
    check(rec["tags"]["genre"] != "Deutschrock", f"Speichern rückgängig gemacht (Genre jetzt {rec['tags']['genre']!r})")

    # Cover: neues Bild per "Drag & Drop", speichern, als cover.jpg ablegen, entfernen
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1500, 1500), (20, 140, 160)).save(buf, "PNG")
    win.table.selectAll()
    pump(app, 0.2)
    win.panel._cover_from_bytes(buf.getvalue())
    check(all(it.cover_state()[0] == "new" for it in win.session.items), "Cover für alle vorgemerkt")
    win.grab().save(os.path.join(out, "03b_newcover.png"))
    win.save()
    check(wait(app, lambda: win._save_worker is None and win.session.modified_count() == 0), "Cover gespeichert")
    cur_dir = win.session.dirs()[0]
    rec = read_file(win.session.items[0].path)
    check(rec["cover"] and rec["cover"]["w"] == 600, f"Cover eingebettet und auf 600 px verkleinert ({rec['cover']})")
    target = os.path.join(cur_dir, "cover.jpg")
    if os.path.exists(target):
        os.remove(target)
    win.panel._cover_from_bytes(buf.getvalue())   # nochmal frisch, damit das Original bekannt ist
    win.panel._cover_save_to_folders()
    check(os.path.exists(target), "cover.jpg im Album-Ordner gespeichert")
    check(Image.open(target).size == (1500, 1500), f"cover.jpg in voller Größe ({Image.open(target).size})")
    win.session.revert()
    win.panel._cover_remove()
    win.save()
    check(wait(app, lambda: win._save_worker is None and win.session.modified_count() == 0), "Cover entfernt + gespeichert")
    check(read_file(win.session.items[0].path)["cover"] is None, "Cover wirklich entfernt")
    win.panel._cover_from_folder()
    check(all(it.cover_state()[0] == "new" for it in win.session.items), "Cover aus Ordner (cover.jpg) übernommen")
    win.session.revert()
    pump(app, 0.2)

    # Rekursiv: Künstler-Ordner mit allen Alben
    artist = os.path.dirname(albums[5])
    win.btn_recursive.setChecked(True)
    pump(app, 0.1)
    win.tree.select_paths([artist])
    check(wait(app, lambda: win.session.items and len(win.session.dirs()) > 1), "Künstler mit Unterordnern geladen")
    pump(app, 0.4)
    win.grab().save(os.path.join(out, "04_recursive.png"))

    # Filter
    win.filter.setText("Nebelhorn")
    pump(app, 0.5)
    check(0 < win.table.model_.rowCount() < len(win.session.items), "Filter funktioniert")
    win.filter.setText("")
    pump(app, 0.4)

    # Sortieren nach Track
    from bub3tagmusic.ui.filetable import COLUMN_INDEX
    win.table._header_clicked(COLUMN_INDEX["track"])
    pump(app)
    check(True, "Sortieren ohne Absturz")

    # Hell-Theme + kleiner Bildschirm
    win.apply_theme("bub_light")
    win.resize(1366, 740)
    win.btn_recursive.setChecked(False)
    win.tree.select_paths([albums[3]])
    wait(app, lambda: win.session.items and win.session.dirs()[0] == albums[3])
    pump(app, 0.5)
    win.grab().save(os.path.join(out, "05_light_small.png"))
    for key in theme.THEME_INFO:                   # alle Farb-Themes einmal anwenden
        win.apply_theme(key)
        pump(app, 0.1)
        win.grab().save(os.path.join(out, f"05_theme_{key}.png"))
    win.toggle_theme()
    check(theme.current() == theme.partner("light"), f"Hell/Dunkel umschalten: {theme.current()}")
    win.apply_theme("bub_light")
    pump(app, 0.2)

    # Ganze Sammlung rekursiv (Leistung)
    win.btn_recursive.setChecked(True)
    t0 = time.time()
    win.tree.select_paths([root])
    check(wait(app, lambda: len(win.session.items) > 500, 120), "ganze Sammlung geladen")
    first = time.time() - t0
    pump(app, 0.3)
    win.tree.select_paths([albums[0]])
    wait(app, lambda: len(win.session.items) < 50)
    t0 = time.time()
    win.tree.select_paths([root])
    wait(app, lambda: len(win.session.items) > 500, 60)
    second = time.time() - t0
    print(f"  Sammlung ({len(win.session.items)} Dateien): erstes Laden {first:.2f}s, aus Cache {second:.2f}s")
    t0 = time.time()
    win.table.selectAll()
    pump(app, 0.2)
    print(f"  Alles auswählen + Bearbeitungsfeld: {time.time() - t0:.2f}s")
    win.apply_theme("bub")
    pump(app, 0.3)
    win.grab().save(os.path.join(out, "06_collection.png"))

    win.session.revert()
    win._store_state()
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    app.quit()
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
