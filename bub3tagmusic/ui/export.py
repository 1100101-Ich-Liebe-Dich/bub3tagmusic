"""Liste exportieren (Phase 4) – kleiner Dialog: Format, Umfang, fertig.

Exportiert wird genau, was die Liste zeigt: sichtbare Spalten in ihrer
aktuellen Reihenfolge, Zeilen in der aktuellen Sortierung und Filterung.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QVBoxLayout)

from ..core import export
from . import icons, theme
from .filetable import COLUMNS, FileTableModel
from .widgets import hint, section
from .workers import Job


def table_snapshot(table, items=None) -> tuple[list[str], list[list[str]], set[int]]:
    """Sichtbare Spalten (in der Reihenfolge auf dem Bildschirm) + Zellentexte."""
    hh = table.horizontalHeader()
    cols = []
    for visual in range(hh.count()):
        logical = hh.logicalIndex(visual)
        if hh.isSectionHidden(logical):
            continue
        col = COLUMNS[logical]
        if col.key == "state":
            continue
        cols.append(col)
    items = items if items is not None else table.model_.visible_items()
    rows = [[FileTableModel._text(it, c) for c in cols] for it in items]
    numeric = {i for i, c in enumerate(cols) if c.align == "right"}
    return [c.label for c in cols], rows, numeric


class ExportDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.settings = win.settings
        self.opts: dict = dict(self.settings.tool_options.get("export", {}))
        self.setWindowTitle("Liste exportieren")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(8)

        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.icon("download-simple", "accent").pixmap(26, 26))
        head.addWidget(ic)
        t = QLabel("Liste exportieren")
        t.setProperty("role", "heading")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)

        self.all_items = win.table.model_.visible_items()
        self.selected = win.table.selected_items()
        headers, _rows, _num = table_snapshot(win.table, [])
        lay.addWidget(hint("Spalten wie in der Liste: " + ", ".join(headers) +
                           ". Andere Spalten per Rechtsklick auf den Spaltenkopf ein- oder ausblenden.", "muted"))

        lay.addSpacing(6)
        lay.addWidget(section("Format"))
        self.fmt = QButtonGroup(self)
        self.rb_html = QRadioButton("HTML – zum Anschauen, Weitergeben und Drucken")
        self.rb_csv = QRadioButton("CSV – für LibreOffice Calc, Excel && Co.")
        for rb in (self.rb_html, self.rb_csv):
            self.fmt.addButton(rb)
            lay.addWidget(rb)
        (self.rb_csv if self.opts.get("format") == "csv" else self.rb_html).setChecked(True)
        row = QHBoxLayout()
        row.setContentsMargins(26, 0, 0, 0)
        row.addWidget(QLabel("Trennzeichen"))
        self.delim = QComboBox()
        for key, (_ch, label) in export.DELIMITERS.items():
            self.delim.addItem(label, key)
        self.delim.setCurrentIndex(max(0, self.delim.findData(self.opts.get("delimiter", "semicolon"))))
        row.addWidget(self.delim, 1)
        lay.addLayout(row)
        self.fmt.buttonToggled.connect(lambda *_: self.delim.setEnabled(self.rb_csv.isChecked()))
        self.delim.setEnabled(self.rb_csv.isChecked())

        lay.addSpacing(6)
        lay.addWidget(section("Umfang"))
        n_all, n_sel = len(self.all_items), len(self.selected)
        self.rb_all = QRadioButton(f"Alle {n_all:,} Dateien der Liste".replace(",", "."))
        self.rb_sel = QRadioButton(f"Nur die {n_sel:,} ausgewählten".replace(",", "."))
        self.rb_sel.setEnabled(0 < n_sel < n_all)
        grp = QButtonGroup(self)
        grp.addButton(self.rb_all)
        grp.addButton(self.rb_sel)
        self.rb_all.setChecked(True)
        lay.addWidget(self.rb_all)
        lay.addWidget(self.rb_sel)
        if win.table.model_.is_filtered:
            lay.addWidget(hint("Die Liste ist gefiltert – exportiert wird nur, was zu sehen ist.", "faint"))

        lay.addSpacing(6)
        self.open_after = QCheckBox("Danach öffnen")
        self.open_after.setChecked(bool(self.opts.get("open_after", True)))
        lay.addWidget(self.open_after)

        lay.addSpacing(8)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self.go = QPushButton("Exportieren …")
        self.go.setProperty("kind", "primary")
        self.go.setDefault(True)
        self.go.setEnabled(n_all > 0)
        self.go.clicked.connect(self.export)
        btns.addWidget(self.go)
        lay.addLayout(btns)
        self.result_path = ""

    # ------------------------------------------------------------------
    def _title(self) -> str:
        win = self.win
        if win._result_files is not None:
            return win._result_label
        if win._search is not None:
            from ..core.filters import describe
            return "Sammlung: " + describe(*win._search)
        dirs = win._loaded_dirs
        if len(dirs) == 1:
            return os.path.basename(dirs[0].rstrip("/")) or dirs[0]
        if dirs:
            return f"{len(dirs)} Ordner"
        return "Liste"

    def export(self, path: str = ""):
        is_csv = self.rb_csv.isChecked()
        ext = "csv" if is_csv else "html"
        title = self._title()
        if not path:
            start = self.opts.get("dir") or os.path.expanduser("~")
            suggestion = os.path.join(start, export.default_name(title, ext))
            filt = "CSV-Datei (*.csv)" if is_csv else "HTML-Seite (*.html)"
            path, _ = QFileDialog.getSaveFileName(self, "Liste exportieren", suggestion, filt)
            if not path:
                return
        if not path.lower().endswith("." + ext):
            path += "." + ext
        items = self.selected if self.rb_sel.isChecked() else self.all_items
        headers, rows, numeric = table_snapshot(self.win.table, items)
        self.opts.update(format=ext, delimiter=self.delim.currentData(), open_after=self.open_after.isChecked(),
                         dir=os.path.dirname(path))
        self.settings.tool_options["export"] = self.opts

        if is_csv:
            delim = export.DELIMITERS[self.delim.currentData()][0]
            fn, args, kw = export.write_csv, (path, headers, rows, delim), {}
        else:
            subtitle = ""
            if self.win.table.model_.is_filtered:
                from ..core.filters import describe
                subtitle = "gefiltert: " + describe(self.win.filterbar.active(), self.win.filter.text())
            fn, args, kw = export.write_html, (path, headers, rows), dict(
                title=title, subtitle=subtitle, numeric=numeric,
                dark=theme.THEMES["dark"], light=theme.THEMES["light"])
        self.go.setEnabled(False)
        self.go.setText("Exportiere …")
        job = Job(lambda: fn(*args, **kw))
        job.done.connect(lambda _r: self._done(path, len(rows)))
        job.failed.connect(self._failed)
        self._job = job
        job.start()

    def _done(self, path: str, n: int):
        self.result_path = path
        self.win.toast.show_message(f"{n:,} Zeilen exportiert: {os.path.basename(path)}".replace(",", "."))
        if self.open_after.isChecked():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.accept()

    def _failed(self, msg: str):
        from PySide6.QtWidgets import QMessageBox
        self.go.setEnabled(True)
        self.go.setText("Exportieren …")
        QMessageBox.warning(self, "Export fehlgeschlagen",
                            f"Die Datei konnte nicht geschrieben werden.\n\n{msg}\n\n"
                            "Bitte einen anderen Ordner wählen (z. B. Dokumente).")

