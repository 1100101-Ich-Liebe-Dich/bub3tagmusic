"""Songtext im Bearbeitungsfeld: kompakte Zeile + eigenes Fenster zum Lesen und Bearbeiten.

Der Songtext ist mehrzeilig und oft lang – im Bearbeitungsfeld steht daher nur, ob einer da ist
(„24 Zeilen“). Ein Klick öffnet das Fenster. Wie bei allen Feldern gilt: Änderungen landen gelb in
der Liste, Strg+S speichert, Strg+Z nimmt zurück.

Begleitdateien: Liegt neben einem Lied eine gleichnamige .lrc oder .txt („01 - Titel.lrc“), kann das
Fenster die Songtexte aller gewählten Dateien in einem Rutsch daraus übernehmen.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                               QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ..core import lyrics as L
from ..core.model import FileItem
from . import icons
from .widgets import hint

MIXED = "‹verschieden›"


class LyricsField(QToolButton):
    """Sieht aus wie ein Eingabefeld, öffnet aber das Songtext-Fenster."""

    openRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.key = "lyrics"
        self.dirty = False                 # wie FieldEdit: nie „halb getippt“
        self.mixed = False
        self.value = ""
        self.setProperty("kind", "field")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.openRequested.emit)
        self.refresh_icons()

    def refresh_icons(self):
        self.setIcon(icons.icon("quotes", "muted", "text"))

    # wie FieldEdit: feste Größenwünsche – der Text wechselt ständig, das Fenster soll nicht neu aufteilen
    # (bei 50.000 Zeilen in der Liste spürbar langsam)
    def minimumSizeHint(self):
        return QSize(60, super().minimumSizeHint().height())

    def sizeHint(self):
        return QSize(200, super().sizeHint().height())

    def show_value(self, value: str, mixed: bool, modified: bool):
        self.value, self.mixed = value, mixed
        if mixed:
            text, tip = f"{MIXED} – ansehen/festlegen …", "Die gewählten Dateien haben verschiedene Songtexte"
        elif value:
            n = L.line_count(value)
            first = next((line.strip() for line in value.splitlines() if line.strip()), "")
            text = f"{n} Zeile{'n' if n != 1 else ''} · {first}"
            tip = value[:900] + (" …" if len(value) > 900 else "")
        else:
            text, tip = "Kein Songtext – hinzufügen …", "Songtext eintippen, einfügen oder aus .lrc/.txt laden"
        self.setText(self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(80, self.width() - 40)))
        self._full = text
        self.setToolTip(tip)
        empty = not value and not mixed
        if self.property("edited") != modified or self.property("empty") != empty:
            self.setProperty("edited", modified)
            self.setProperty("empty", empty)
            self.style().unpolish(self)
            self.style().polish(self)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        full = getattr(self, "_full", "")
        if full:
            self.setText(self.fontMetrics().elidedText(full, Qt.TextElideMode.ElideRight, max(80, self.width() - 40)))


class LyricsDialog(QDialog):
    """Songtext lesen und bearbeiten – für eine oder mehrere Dateien."""

    def __init__(self, items: list[FileItem], value: str, mixed: bool, parent=None):
        super().__init__(parent)
        self.items = items
        self.result_value: str | None = None             # neuer Songtext für alle
        self.result_each: list[tuple[FileItem, dict]] = []   # aus Begleitdateien (je Datei verschieden)
        self.setWindowTitle("Songtext")
        self.resize(560, 620)
        self.setMinimumSize(420, 380)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.icon("quotes", "accent").pixmap(22, 22))
        head.addWidget(ic)
        tbox = QVBoxLayout()
        tbox.setSpacing(1)
        n = len(items)
        title = QLabel(items[0].tags.get("title") or items[0].name if n == 1 else f"{n} Dateien")
        title.setProperty("role", "heading")
        tbox.addWidget(title)
        sub = items[0].tags.get("artist", "") if n == 1 else "Was du hier einträgst, gilt für alle gewählten Dateien"
        if sub:
            tbox.addWidget(hint(sub, "muted"))
        head.addLayout(tbox, 1)
        lay.addLayout(head)

        if mixed:
            lay.addWidget(hint("Die Dateien haben verschiedene Songtexte. Das Feld ist leer – "
                               "trägst du etwas ein, bekommen alle denselben Text.", "modified"))
        self.edit = QPlainTextEdit(value)
        self.edit.setObjectName("LyricsEdit")
        self.edit.setPlaceholderText("Songtext hier eintippen oder einfügen …")
        self.edit.setTabChangesFocus(True)
        self.edit.textChanged.connect(self._count)
        lay.addWidget(self.edit, 1)
        self.counter = hint("", "faint")
        lay.addWidget(self.counter)

        # Begleitdateien (.lrc/.txt) neben den Liedern
        self.found = L.companions([it.path for it in items])
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.btn_file = QPushButton("Aus Datei laden …")
        self.btn_file.setIcon(icons.icon("file-text", "text"))
        self.btn_file.setToolTip(".lrc oder .txt – Zeitmarken wie [01:23.45] werden entfernt")
        self.btn_file.clicked.connect(self._load_file)
        tools.addWidget(self.btn_file)
        if self.found:
            if n == 1:
                txt = f"Aus „{os.path.basename(next(iter(self.found.values())))}“"
            else:
                txt = f"Aus Begleitdateien ({len(self.found)} von {n})"
            self.btn_found = QPushButton(txt)
            self.btn_found.setIcon(icons.icon("music-notes", "text"))
            self.btn_found.setToolTip("Gleichnamige .lrc/.txt neben den Liedern – jede Datei bekommt ihren eigenen Text")
            self.btn_found.clicked.connect(self._from_companions)
            tools.addWidget(self.btn_found)
        tools.addStretch(1)
        clear = QPushButton("Leeren")
        clear.setIcon(icons.icon("eraser", "text"))
        clear.clicked.connect(self.edit.clear)
        tools.addWidget(clear)
        lay.addLayout(tools)

        foot = QHBoxLayout()
        foot.addWidget(hint("Wird gelb vorgemerkt · Strg+S speichert · Strg+Z nimmt zurück", "faint"), 1)
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        foot.addWidget(cancel)
        self.ok = QPushButton("Übernehmen")
        self.ok.setProperty("kind", "primary")
        self.ok.setDefault(False)
        self.ok.setAutoDefault(False)          # Enter macht im Textfeld eine neue Zeile
        self.ok.clicked.connect(self._accept)
        foot.addWidget(self.ok)
        lay.addLayout(foot)
        self._original = L.normalize(value)
        self._mixed = mixed
        self._count()

    def _count(self):
        text = self.edit.toPlainText()
        n = L.line_count(text)
        self.counter.setText(f"{n} Zeile{'n' if n != 1 else ''} · {len(text)} Zeichen" if text.strip() else "leer")

    def _load_file(self):
        start = self.items[0].dir
        path, _ = QFileDialog.getOpenFileName(self, "Songtext laden", start,
                                              "Songtexte (*.lrc *.txt);;Alle Dateien (*)")
        if not path:
            return
        try:
            self.edit.setPlainText(L.load(path))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Datei nicht lesbar", f"{os.path.basename(path)}: {exc}")

    def _from_companions(self):
        each, bad = [], []
        for it in self.items:
            src = self.found.get(it.path)
            if not src:
                continue
            try:
                each.append((it, {"lyrics": L.load(src)}))
            except (OSError, ValueError):
                bad.append(os.path.basename(src))
        if bad:
            QMessageBox.warning(self, "Nicht alles lesbar", "Diese Dateien wurden übersprungen:\n" + "\n".join(bad[:20]))
        if len(self.items) == 1 and each:
            self.edit.setPlainText(each[0][1]["lyrics"])   # bei einer Datei erst zeigen, dann übernehmen
            return
        self.result_each = each
        self.accept()

    def _accept(self):
        text = L.normalize(self.edit.toPlainText())
        if self._mixed and not text:
            self.reject()                    # nichts eingetragen – verschiedene Texte bleiben
            return
        if not self._mixed and text == self._original:
            self.reject()
            return
        self.result_value = text
        self.accept()


def open_lyrics(panel: QWidget, items: list[FileItem], value: str, mixed: bool, session) -> str:
    """Fenster zeigen und Ergebnis übernehmen. Gibt eine kurze Meldung zurück ('' = nichts geändert)."""
    dlg = LyricsDialog(items, value, mixed, panel)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return ""
    if dlg.result_each:
        n = session.apply_changes(dlg.result_each, f"Songtexte aus Begleitdateien ({len(dlg.result_each)})")
        return f"Songtext bei {n} Datei(en) aus .lrc/.txt übernommen – Strg+S speichert"
    if dlg.result_value is not None:
        label = "Songtext geleert" if not dlg.result_value else "Songtext geändert"
        n = session.apply_fields(items, {"lyrics": dlg.result_value}, f"{label} ({len(items)} Datei(en))")
        return f"{label} bei {n} Datei(en) – Strg+S speichert" if n else ""
    return ""
