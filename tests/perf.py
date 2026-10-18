"""Leistungstest: großer Ordnerbaum, Einlesen mit/ohne Cache, Liste mit 50.000 Einträgen.

Aufruf: QT_QPA_PLATFORM=offscreen python3 tests/perf.py SAMMLUNG
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())
os.environ.setdefault("XDG_CACHE_HOME", tempfile.mkdtemp())

from bub3tagmusic.core.cache import Cache  # noqa: E402
from bub3tagmusic.core.scanner import list_audio, load_records, scan_tree  # noqa: E402


def t(label, fn):
    t0 = time.perf_counter()
    r = fn()
    print(f"  {label:<44} {time.perf_counter() - t0:6.2f} s")
    return r


def main():
    root = sys.argv[1]
    cache = Cache(os.path.join(tempfile.mkdtemp(), "c.sqlite"))
    node = t("Ordnerbaum zählen", lambda: scan_tree(root))
    print(f"  → {sum(1 for n in node.walk() if n.audio_count)} Alben, {node.total_count} Dateien")
    paths = t("Dateien auflisten (rekursiv)", lambda: list_audio([root], True))
    t("Tags lesen – erstes Mal (alle Kerne)", lambda: load_records(paths, cache))
    t("Tags lesen – aus dem Cache", lambda: load_records(paths, cache))
    t("Tags lesen – erstes Mal (nur 1 Kern)", lambda: load_records(paths, None, workers=1))

    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from bub3tagmusic.app import prepare_app
    prepare_app(app)
    from bub3tagmusic.core.settings import Settings
    from bub3tagmusic.ui import theme
    theme.apply(app, "dark")
    from bub3tagmusic.ui.mainwindow import MainWindow
    from bub3tagmusic.ui.filetable import COLUMN_INDEX
    win = MainWindow(Settings())
    win.show()
    recs = load_records(paths, cache)
    big = []
    while len(big) < 50000:
        for r in recs:
            r2 = dict(r, path=f"{r['path']}#{len(big)}", tags=dict(r["tags"]))
            big.append(r2)
            if len(big) >= 50000:
                break
    t("Liste mit 50.000 Einträgen füllen", lambda: (win.session.set_records(big), app.processEvents()))
    t("Nach Titel sortieren (50.000)", lambda: (win.table._header_clicked(COLUMN_INDEX["title"]), app.processEvents()))
    t("Filtern (50.000)", lambda: (win.table.model_.set_filter("Song 1"), app.processEvents()))
    win.table.model_.set_filter("")
    t("Alle auswählen + Bearbeitungsfeld (50.000)", lambda: (win.table.selectAll(), win._on_table_selection(),
                                                             app.processEvents()))
    t("Genre für 50.000 setzen", lambda: (win.session.apply_fields(win.panel.items, {"genre": "Rock"}),
                                          app.processEvents()))
    t("Rückgängig (50.000)", lambda: (win.undo(), app.processEvents()))
    win.session.revert()


if __name__ == "__main__":
    main()
