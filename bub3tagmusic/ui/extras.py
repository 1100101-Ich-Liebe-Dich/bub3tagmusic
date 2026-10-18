"""Extras der Phase 4 mit eigenem Fenster: Duplikate finden, ReplayGain.

Aufbau wie die Werkzeuge: Kopf, links Optionen, rechts Ergebnis, unten Knöpfe.
Langsame Arbeit läuft als Task im Hintergrund – mit Fortschritt und Abbrechen.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QFile, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame,
                               QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton,
                               QRadioButton, QScrollArea, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import features
from ..core import duplicates as dup
from ..core import replaygain as rg
from ..core.tools_external import find_tool, install_hint
from . import icons, theme
from .filetable import fmt_length
from .widgets import hint, section
from .workers import Task


def fmt_size(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB".replace(".", ",")
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.1f} MB".replace(".", ",")
    return f"{max(1, n // 1024)} KB"


class ExtraDialog(QDialog):
    """Rahmen: Kopf · Optionen | Inhalt · Fuß mit Fortschritt."""

    feature_id = ""

    def __init__(self, win, scope: str = ""):
        super().__init__(win)
        self.win = win
        self.settings = win.settings
        self.feature = features.get(self.feature_id)
        self.opts: dict = dict(self.settings.tool_options.get(self.feature_id, {}))
        self.task: Task | None = None
        self.setWindowTitle(self.feature.title.replace(" …", ""))
        self.resize(1060, 650)
        self.setMinimumSize(880, 540)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head = QWidget(objectName="ToolHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(20, 14, 20, 14)
        ic = QLabel()
        ic.setPixmap(icons.icon(self.feature.icon, "accent").pixmap(26, 26))
        hl.addWidget(ic)
        hl.addSpacing(6)
        tbox = QVBoxLayout()
        tbox.setSpacing(1)
        title = QLabel(self.feature.title.replace(" …", ""))
        title.setProperty("role", "heading")
        tbox.addWidget(title)
        self.scope_label = hint(scope, "muted")
        tbox.addWidget(self.scope_label)
        hl.addLayout(tbox, 1)
        root.addWidget(head)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        opt_scroll = QScrollArea()
        opt_scroll.setObjectName("ToolOptions")
        opt_scroll.setWidgetResizable(True)
        opt_scroll.setFixedWidth(360)
        opt_scroll.setFrameShape(QFrame.Shape.NoFrame)
        opt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget(objectName="ToolOptionsInner")
        inner.setMaximumWidth(360)
        self.form = QVBoxLayout(inner)
        self.form.setContentsMargins(20, 16, 20, 16)
        self.form.setSpacing(8)
        opt_scroll.setWidget(inner)
        body.addWidget(opt_scroll)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.message = QLabel(objectName="ToolMessage")
        self.message.setWordWrap(True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message.hide()
        right.addWidget(self.message)
        self.content = right
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        foot = QWidget(objectName="ToolFoot")
        self.foot = QHBoxLayout(foot)
        self.foot.setContentsMargins(20, 12, 20, 12)
        self.foot.setSpacing(10)
        left = QVBoxLayout()
        left.setSpacing(4)
        self.summary = QLabel(objectName="ToolSummary")
        left.addWidget(self.summary)
        prow = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(220)
        self.progress.hide()
        prow.addWidget(self.progress)
        self.progress_text = hint("", "muted")
        self.progress_text.setWordWrap(False)
        prow.addWidget(self.progress_text)
        prow.addStretch(1)
        left.addLayout(prow)
        self.foot.addLayout(left, 1)
        root.addWidget(foot)

    # --- Hilfen --------------------------------------------------------------
    def add_check(self, text: str, key: str, default: bool, detail: str = "") -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(bool(self.opts.get(key, default)))
        cb.toggled.connect(lambda on: self.opts.__setitem__(key, on))
        self.form.addWidget(cb)
        if detail:
            d = hint(detail)
            d.setContentsMargins(26, 0, 0, 4)
            self.form.addWidget(d)
        return cb

    def show_message(self, text: str):
        self.message.setText(text)
        self.message.setVisible(bool(text))

    def start_task(self, fn, *args, done, label: str):
        self.task = Task(fn, *args)
        self.task.progress.connect(self._progress)
        self.task.done.connect(lambda r: (self._task_end(), done(r)))
        self.task.failed.connect(lambda m: (self._task_end(), self.show_message(m)))
        self.progress.setRange(0, 0)
        self.progress.show()
        self.progress_text.setText(label)
        self.set_busy(True)
        self.task.start()

    def _progress(self, d: int, t: int, text: str):
        self.progress.setRange(0, max(1, t))
        self.progress.setValue(d)
        if text:
            self.progress_text.setText(f"{text} {d:,} / {t:,}".replace(",", "."))

    def _task_end(self):
        self.progress.hide()
        self.progress_text.setText("")
        self.set_busy(False)

    def set_busy(self, busy: bool):
        pass

    def store_options(self):
        self.settings.tool_options[self.feature_id] = self.opts
        try:
            self.settings.save()
        except OSError:
            pass

    def done(self, r):
        if self.task is not None and self.task.isRunning():
            self.task.cancel()
        self.store_options()
        super().done(r)


# ======================================================================
# Duplikate finden
# ======================================================================
ROLE_INDEX = Qt.ItemDataRole.UserRole + 1


class DuplicatesDialog(ExtraDialog):
    feature_id = "duplicates"

    def __init__(self, win, items, scope):
        super().__init__(win, "Doppelte Titel finden – gelöscht wird nur, was du selbst anhakst")
        self.items = list(win.session.items)       # immer alle geladenen Dateien, nicht nur die Auswahl
        self.entries: list[dup.Entry] = []
        self.groups: list[dup.Group] = []
        f = self.form
        f.addWidget(section("Wo suchen?"))
        self.rb_list = QRadioButton(f"In der Liste ({len(self.items):,} Dateien)".replace(",", "."))
        self.rb_all = QRadioButton("In der ganzen Sammlung")
        self.rb_all.setEnabled(bool(win.tree.root_path))
        grp = QButtonGroup(self)
        grp.addButton(self.rb_list)
        grp.addButton(self.rb_all)
        whole = self.opts.get("scope") == "all" or not self.items
        (self.rb_all if whole and self.rb_all.isEnabled() else self.rb_list).setChecked(True)
        self.rb_list.setEnabled(bool(self.items))
        f.addWidget(self.rb_list)
        f.addWidget(self.rb_all)
        f.addWidget(hint("Die ganze Sammlung kommt aus dem Zwischenspeicher – nur neue Dateien werden gelesen."))
        f.addSpacing(8)
        f.addWidget(section("Vergleichen nach"))
        self.cb_tags = self.add_check("Interpret und Titel", "tags", True,
                                      "Groß-/Kleinschreibung, Satzzeichen und Akzente sind egal.")
        self.fpcalc = find_tool("fpcalc")
        self.cb_sound = self.add_check("Klang (Audio-Fingerabdruck)", "sound", False,
                                       "Findet Duplikate auch mit falschen oder leeren Tags. Beim ersten Mal "
                                       "etwa eine Sekunde pro Datei – die Abdrücke werden gemerkt.")
        if not self.fpcalc:
            self.cb_sound.setChecked(False)
            self.cb_sound.setEnabled(False)
            h = hint(install_hint("fpcalc"), "muted")
            h.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            h.setContentsMargins(26, 0, 0, 4)
            f.addWidget(h)
        row = QHBoxLayout()
        row.addWidget(QLabel("Länge darf abweichen um"))
        self.tol = QDoubleSpinBox()
        self.tol.setRange(0, 30)
        self.tol.setDecimals(0)
        self.tol.setSuffix(" s")
        self.tol.setValue(float(self.opts.get("tolerance", 2)))
        self.tol.valueChanged.connect(lambda v: self.opts.__setitem__("tolerance", v))
        row.addWidget(self.tol)
        row.addStretch(1)
        f.addLayout(row)
        self.cb_brackets = self.add_check("Zusätze in Klammern ignorieren", "brackets", False,
                                          "„(Remastered 2011)“, „[Live]“, „feat. …“ – Vorsicht: Live- und "
                                          "Studiofassung gelten dann als gleich (wenn die Länge passt).")
        f.addSpacing(10)
        self.search_btn = QPushButton("Duplikate suchen")
        self.search_btn.setProperty("kind", "primary")
        self.search_btn.clicked.connect(self.search)
        f.addWidget(self.search_btn)
        f.addWidget(hint("Gelöscht wird nie etwas von selbst. Du entscheidest, was weg kann – es landet im "
                         "Papierkorb.", "muted"))
        f.addStretch(1)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(["Datei", "Ordner", "Länge", "Format", "kbit/s", "Größe", "Hinweis"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(False)
        hh = self.tree.header()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.resizeSection(1, 170)
        self.tree.itemChanged.connect(lambda *_: self._update_buttons())
        self.tree.itemDoubleClicked.connect(lambda it, _c: self._open_folder(it))
        self.content.addWidget(self.tree, 1)
        self.empty = hint("Optionen wählen und „Duplikate suchen“ klicken.", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setContentsMargins(20, 30, 20, 30)
        self.content.addWidget(self.empty)
        self.tree.hide()

        self.btn_folder = QPushButton("Ordner öffnen")
        self.btn_folder.clicked.connect(lambda: self._open_folder(self.tree.currentItem()))
        self.btn_show = QPushButton("In der Liste zeigen")
        self.btn_show.setToolTip("Alle gefundenen Dateien in die Dateiliste holen – zum Vergleichen und Bearbeiten")
        self.btn_show.clicked.connect(self.show_in_list)
        self.btn_trash = QPushButton("In den Papierkorb")
        self.btn_trash.setToolTip("Nur die angehakten Dateien – sie lassen sich aus dem Papierkorb wiederherstellen")
        self.btn_trash.clicked.connect(self.trash)
        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.reject)
        for b in (self.btn_folder, self.btn_show, self.btn_trash, self.btn_close):
            self.foot.addWidget(b)
        self.summary.setText("Noch nicht gesucht")
        self._update_buttons()

    # --- Suche ---------------------------------------------------------------------
    def search(self):
        if self.task is not None and self.task.isRunning():
            self.task.cancel()
            return
        use_tags, use_sound = self.cb_tags.isChecked(), self.cb_sound.isChecked() and bool(self.fpcalc)
        if not use_tags and not use_sound:
            self.show_message("Mindestens eine Vergleichsart wählen")
            return
        self.show_message("")
        whole = self.rb_all.isChecked()
        self.opts["scope"] = "all" if whole else "list"
        tol, brackets = self.tol.value(), self.cb_brackets.isChecked()
        cache = self.win.cache
        if whole:
            source = ("all", self.win.tree.root_path)
        else:
            source = ("list", [dup.Entry.from_record(it.rec, it.tags) for it in self.items if not it.error])

        def work(progress, cancelled):
            if source[0] == "all":
                from ..core.scanner import list_audio, load_records
                progress(0, 0, "Sammlung lesen …")
                paths = list_audio([source[1]], True)
                recs = load_records(paths, cache, progress=lambda d, t: progress(d, t, "Sammlung lesen …"),
                                    should_cancel=cancelled)
                entries = [dup.Entry.from_record(r) for r in recs if not r.get("error")]
            else:
                entries = source[1]
            groups, skipped, errors = [], 0, {}
            if use_tags:
                groups, skipped = dup.by_tags(entries, tol, brackets)
            stopped = False
            if use_sound and not cancelled():
                errors = dup.fingerprints_for(entries, cache, progress=lambda d, t: progress(d, t, "Fingerabdrücke …"),
                                              cancelled=cancelled)
                stopped = cancelled()
                groups = dup.merge(groups, dup.by_sound(entries, tol), entries)
            return entries, groups, skipped, errors, stopped

        self.start_task(work, done=self._found, label="Suche …")

    def set_busy(self, busy: bool):
        self.search_btn.setText("Abbrechen" if busy else "Duplikate suchen")
        self.search_btn.setProperty("kind", "" if busy else "primary")
        self.search_btn.style().unpolish(self.search_btn)
        self.search_btn.style().polish(self.search_btn)
        for w in (self.btn_show, self.btn_trash, self.btn_folder):
            w.setEnabled(not busy)
        if not busy:
            self._update_buttons()

    def _found(self, result):
        self.entries, self.groups, skipped, errors, stopped = result
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = theme.ui_font(13)
        bold.setBold(True)
        for g in self.groups:
            top = QTreeWidgetItem([f"{g.title}    ·  {len(g.members)} Dateien, gleich nach {g.reason}"])
            top.setFont(0, bold)
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            for i in g.members:
                e = self.entries[i]
                note = "beste Qualität" if i == g.best else ""
                child = QTreeWidgetItem([os.path.basename(e.path), os.path.basename(os.path.dirname(e.path)),
                                         fmt_length(e.length), e.format, str(e.bitrate or ""), fmt_size(e.size), note])
                child.setData(0, ROLE_INDEX, i)
                child.setToolTip(0, e.path)
                child.setToolTip(1, os.path.dirname(e.path))
                child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                               | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                if note:
                    child.setForeground(6, theme.qcolor("done"))
                for c in (2, 4, 5):
                    child.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                top.addChild(child)
            top.setExpanded(True)
        self.tree.blockSignals(False)
        self.tree.setVisible(bool(self.groups))
        self.empty.setVisible(not self.groups)
        n_files = sum(len(g.members) for g in self.groups)
        if self.groups:
            self.summary.setText(f"{len(self.groups):,} Gruppen · {n_files:,} Dateien".replace(",", "."))
        else:
            self.summary.setText("Keine Duplikate gefunden")
            self.empty.setText(f"Keine Duplikate unter {len(self.entries):,} Dateien – alles sauber.".replace(",", "."))
        notes = []
        if skipped:
            n = f"{skipped:,}".replace(",", ".")
            what = "1 Datei ohne Interpret oder Titel konnte" if skipped == 1 else \
                f"{n} Dateien ohne Interpret oder Titel konnten"
            notes.append(f"{what} nach Tags nicht verglichen werden"
                         + (" – „Klang“ hilft da." if self.fpcalc and not self.cb_sound.isChecked() else "."))
        if errors:
            notes.append(f"{len(errors)} Datei(en) ohne Fingerabdruck (z. B. zu kurz oder beschädigt).")
        if stopped:
            notes.append("Abgebrochen – die bisher berechneten Fingerabdrücke sind gemerkt, beim nächsten Mal geht "
                         "es schneller.")
        self.show_message("  ".join(notes))
        self._update_buttons()

    # --- Aktionen --------------------------------------------------------------------
    def _checked(self) -> list[QTreeWidgetItem]:
        out = []
        for t in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(t)
            for c in range(top.childCount()):
                ch = top.child(c)
                if ch.checkState(0) == Qt.CheckState.Checked:
                    out.append(ch)
        return out

    def _update_buttons(self):
        n = len(self._checked())
        self.btn_trash.setText(f"In den Papierkorb ({n})" if n else "In den Papierkorb")
        self.btn_trash.setEnabled(n > 0)
        self.btn_show.setEnabled(bool(self.groups))
        self.btn_folder.setEnabled(bool(self.groups))

    def _path_of(self, item: QTreeWidgetItem | None) -> str:
        if item is None:
            return ""
        idx = item.data(0, ROLE_INDEX)
        if idx is None and item.childCount():
            idx = item.child(0).data(0, ROLE_INDEX)
        return self.entries[idx].path if idx is not None else ""

    def _open_folder(self, item):
        path = self._path_of(item)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def show_in_list(self):
        paths = [self.entries[i].path for g in self.groups for i in g.members]
        if paths and self.win.show_files(paths, "Duplikate"):
            self.accept()

    def trash(self):
        items = self._checked()
        if not items:
            return
        # Schutz: nie alle Dateien einer Gruppe auf einmal
        for t in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(t)
            kids = [top.child(c) for c in range(top.childCount())]
            if kids and all(k.checkState(0) == Qt.CheckState.Checked for k in kids):
                QMessageBox.information(self, "Eine Datei bleibt",
                                        f"Bei „{top.text(0)}“ sind alle Dateien angehakt.\n\n"
                                        "Mindestens eine Datei jeder Gruppe muss bleiben.")
                return
        unsaved = {it.path for it in self.win.session.items if it.is_modified()}
        paths = [self._path_of(i) for i in items]
        warn = "\n\nAchtung: Einige davon haben ungespeicherte Änderungen." if unsaved & set(paths) else ""
        r = QMessageBox.question(self, "In den Papierkorb verschieben?",
                                 f"{len(paths)} Datei(en) in den Papierkorb verschieben?\n\n"
                                 "Sie lassen sich von dort wiederherstellen." + warn)
        if r != QMessageBox.StandardButton.Yes:
            return
        done, errors = [], []
        for p in paths:
            ok = QFile.moveToTrash(p)
            ok = ok[0] if isinstance(ok, tuple) else ok
            (done if ok else errors).append(p)
        if done:
            self.win.session.remove_paths(done)
            try:
                self.win.cache.forget(done)
            except Exception:
                pass
        # Ergebnis aktualisieren: weg damit, Gruppen mit nur noch einer Datei auflösen
        gone = set(done)
        for g in self.groups:
            g.members = [i for i in g.members if self.entries[i].path not in gone]
        self.groups = dup._finish([g for g in self.groups if len(g.members) > 1], self.entries)
        self._found((self.entries, self.groups, 0, {}, False))
        self.win.toast.show_message(f"{len(done)} Datei(en) im Papierkorb")
        if errors:
            from .dialogs import ErrorListDialog
            ErrorListDialog("Nicht alles verschoben", [(p, "Konnte nicht in den Papierkorb verschoben werden – "
                                                           "Schreibrechte prüfen") for p in errors], self).exec()


# ======================================================================
# ReplayGain
# ======================================================================
class ReplayGainDialog(ExtraDialog):
    feature_id = "replaygain"

    def __init__(self, win, items, scope):
        super().__init__(win, scope)
        self.items = list(items)
        self.albums: list[tuple[str, list[str]]] = []
        groups: dict[str, list[str]] = {}
        for it in self.items:
            if not it.error:
                groups.setdefault(it.dir, []).append(it.path)
        self.albums = list(groups.items())
        self.exe = rg.rsgain_path()
        self.results: list[rg.AlbumResult] = []
        self._run_mode = rg.MODE_SCAN

        f = self.form
        f.addWidget(section("Was soll passieren?"))
        self.modes = QButtonGroup(self)
        # Nur messen ist immer der Start – Schreiben muss man bewusst auswählen
        for mode, text in ((rg.MODE_SCAN, "Nur messen – nichts wird geschrieben"),
                           (rg.MODE_ALBUM, "Track- und Album-Gain in die Dateien schreiben"),
                           (rg.MODE_TRACK, "Nur Track-Gain in die Dateien schreiben"),
                           (rg.MODE_REMOVE, "ReplayGain-Tags aus den Dateien entfernen")):
            rb = QRadioButton(text)
            rb.setProperty("mode", mode)
            rb.setChecked(mode == rg.MODE_SCAN)
            self.modes.addButton(rb)
            f.addWidget(rb)
        self.modes.buttonToggled.connect(self._mode_changed)
        f.addWidget(hint("Album = Ordner: alle Dateien eines Ordners werden gemeinsam gemessen. "
                         "Die Musik selbst bleibt immer unverändert."))
        f.addSpacing(8)
        f.addWidget(section("Ziel-Lautstärke"))
        self.target = QComboBox()
        for value, label in rg.TARGETS:
            self.target.addItem(label, value)
        self.target.setCurrentIndex(max(0, self.target.findData(self.opts.get("target", -18))))
        self.target.currentIndexChanged.connect(lambda _i: self.opts.__setitem__("target", self.target.currentData()))
        f.addWidget(self.target)
        f.addSpacing(4)
        self.cb_clip = self.add_check("Übersteuern verhindern", "clip", True,
                                      "Senkt die Verstärkung, wenn laute Spitzen sonst verzerren würden.")
        self.cb_skip = self.add_check("Schon berechnete überspringen", "skip", False,
                                      "Dateien mit vorhandenen ReplayGain-Tags werden nicht neu gemessen.")
        f.addSpacing(10)
        self.start_btn = QPushButton("Messen")
        self.start_btn.setProperty("kind", "primary")
        self.start_btn.clicked.connect(self.start)
        f.addWidget(self.start_btn)
        if not self.exe:
            self.start_btn.setEnabled(False)
            h = hint(install_hint("rsgain"), "muted")
            h.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            f.addWidget(h)
            self.show_message("rsgain fehlt – ohne das Programm lässt sich ReplayGain nicht berechnen. "
                              "Anleitung links.")
        f.addStretch(1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Album (Ordner)", "Dateien", "Album-Gain", "Spitze", "Status"])
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        hh = self.tree.header()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for folder, paths in self.albums:
            top = QTreeWidgetItem([os.path.basename(folder) or folder, str(len(paths)), "", "", "wartet"])
            top.setToolTip(0, folder)
            top.setForeground(4, theme.qcolor("faint"))
            for c in (1, 2, 3):
                top.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for p in paths:
                ch = QTreeWidgetItem([os.path.basename(p), "", "", "", ""])
                ch.setToolTip(0, p)
                for c in (2, 3):
                    ch.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                top.addChild(ch)
            self.tree.addTopLevelItem(top)
        self.content.addWidget(self.tree, 1)

        self.btn_errors = QPushButton("Fehler anzeigen")
        self.btn_errors.clicked.connect(self._show_errors)
        self.btn_errors.hide()
        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.reject)
        self.foot.addWidget(self.btn_errors)
        self.foot.addWidget(self.btn_close)
        n_files = sum(len(p) for _f, p in self.albums)
        n_alb = len(self.albums)
        self.summary.setText(f"{n_alb:,} {'Album' if n_alb == 1 else 'Alben'} · {n_files:,} Dateien".replace(",", "."))
        self._mode_changed()

    def _mode(self) -> str:
        b = self.modes.checkedButton()
        return b.property("mode") if b else rg.MODE_SCAN

    START_TEXT = {rg.MODE_SCAN: "Messen", rg.MODE_ALBUM: "In die Dateien schreiben …",
                  rg.MODE_TRACK: "In die Dateien schreiben …", rg.MODE_REMOVE: "Aus den Dateien entfernen …"}
    WARNING = ("Achtung: Diese Einstellung schreibt direkt in deine Musikdateien. "
               "Das lässt sich NICHT mit Strg+Z zurücknehmen – vorher kommt noch eine Rückfrage.")

    def _mode_changed(self, *_):
        mode = self._mode()
        self.opts["mode"] = mode
        remove = mode == rg.MODE_REMOVE
        for w in (self.target, self.cb_clip):
            w.setEnabled(not remove)
        self.cb_skip.setEnabled(mode in (rg.MODE_ALBUM, rg.MODE_TRACK))
        self.start_btn.setText(self.START_TEXT[mode])
        writes = mode in rg.WRITES
        if self.exe:
            self.show_message(self.WARNING if writes else "")
        self.message.setProperty("kind", "warning" if writes else "")
        self.start_btn.setProperty("kind", "danger" if writes else "primary")
        for w in (self.message, self.start_btn):
            w.style().unpolish(w)
            w.style().polish(w)

    def confirm_write(self, mode: str, n_files: int) -> bool:
        """Deutliche Warnung, bevor rsgain die Dateien verändert. Standard-Knopf ist „Abbrechen“."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Wirklich in die Dateien schreiben?")
        what = ("ReplayGain-Tags aus" if mode == rg.MODE_REMOVE else "ReplayGain-Tags in")
        box.setText(f"{what} {n_files:,} Datei(en) {'entfernen' if mode == rg.MODE_REMOVE else 'schreiben'}?"
                    .replace(",", "."))
        box.setInformativeText("Das passiert sofort und direkt in den Musikdateien.\n"
                               "Strg+Z kann das NICHT rückgängig machen.\n\n"
                               "Die Musik selbst bleibt unverändert – es geht nur um die Lautstärke-Angaben.\n"
                               "Wer nur nachsehen will: „Nur messen“ wählen.")
        ok = box.addButton("Ja, in die Dateien schreiben" if mode != rg.MODE_REMOVE else "Ja, entfernen",
                           QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() is ok

    def set_busy(self, busy: bool):
        self.start_btn.setText("Abbrechen" if busy else self.START_TEXT[self._mode()])
        self.start_btn.setProperty("kind", "" if busy else ("danger" if self._mode() in rg.WRITES else "primary"))
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        for b in self.modes.buttons():
            b.setEnabled(not busy)
        self.btn_close.setEnabled(not busy)

    def start(self):
        if self.task is not None and self.task.isRunning():
            self.task.cancel()
            self.progress_text.setText("Breche ab …")
            return
        mode = self._mode()
        paths = {p for _f, ps in self.albums for p in ps}
        if mode in rg.WRITES and not self.confirm_write(mode, len(paths)):
            return
        unsaved = [it for it in self.win.session.items if it.path in paths and it.is_modified()] \
            if mode in rg.WRITES else []
        if unsaved:
            r = QMessageBox.question(self, "Erst speichern?",
                                     f"{len(unsaved)} Datei(en) haben ungespeicherte Änderungen.\n\n"
                                     "ReplayGain schreibt direkt in die Dateien – deshalb vorher speichern?")
            if r != QMessageBox.StandardButton.Yes:
                return
            self.win.save(then=self._start_confirmed, quiet=True)
            return
        self._run(mode)

    def _start_confirmed(self):
        self._run(self._mode())

    def _run(self, mode: str):
        self.show_message("")
        self.btn_errors.hide()
        self._run_mode = mode
        opts = dict(target=int(self.target.currentData()), clip=self.cb_clip.isChecked(),
                    skip_existing=self.cb_skip.isChecked() and mode != rg.MODE_REMOVE,
                    id3v2=int(self.settings.id3_version), keep_mtime=bool(self.settings.keep_mtime))
        exe, albums = self.exe, list(self.albums)
        self.results = []
        results = self.results
        for t in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(t)
            for c in (2, 3):
                top.setText(c, "")
            top.setText(4, "wartet")
            top.setForeground(4, theme.qcolor("faint"))

        def work(progress, cancelled):
            from ..core.tags import read_file
            fresh = []
            for n, (_folder, paths) in enumerate(albums):
                if cancelled():
                    break
                progress(n, len(albums), "Album")
                res = rg.process_album(exe, paths, mode, cancelled=cancelled, **opts)
                results.append(res)
                if mode in rg.WRITES:
                    fresh += [read_file(p) for p in paths]
                if res.cancelled:
                    break
            progress(len(results), len(albums), "Album")
            return fresh

        self.start_task(work, done=self._finished, label="Messe Lautheit …")

    def _progress(self, d: int, t: int, text: str):
        super()._progress(d, t, text)
        self._show_results()
        if d < self.tree.topLevelItemCount() and d >= len(self.results):
            top = self.tree.topLevelItem(d)
            top.setText(4, "läuft …")
            top.setForeground(4, theme.qcolor("modified"))
            self.tree.scrollToItem(top)

    def _show_results(self):
        for i, res in enumerate(list(self.results)):
            top = self.tree.topLevelItem(i)
            if top is None or top.data(0, ROLE_INDEX) == "done":
                continue
            top.setData(0, ROLE_INDEX, "done")
            top.setText(2, res.gain.replace(".", ","))
            top.setText(3, res.peak.replace(".", ","))
            errs = [r for r in res.files if r.error]
            if res.cancelled:
                status, color = "abgebrochen", "faint"
            elif errs and len(errs) == len(res.files):
                status, color = "Fehler", "danger"
            elif errs:
                status, color = f"{len(errs)} Fehler", "danger"
            else:
                status, color = {rg.MODE_REMOVE: "entfernt", rg.MODE_SCAN: "gemessen"}.get(
                    self._run_mode, "geschrieben"), "done"
            top.setText(4, status)
            top.setForeground(4, theme.qcolor(color))
            if res.error:
                top.setToolTip(4, res.error)
            for c, r in enumerate(res.files):
                ch = top.child(c)
                if ch is None:
                    continue
                ch.setText(2, r.gain.replace(".", ","))
                ch.setText(3, r.peak.replace(".", ","))
                if r.error:
                    ch.setText(4, r.error)
                    ch.setForeground(4, theme.qcolor("danger"))

    def _finished(self, fresh: list):
        self._show_results()
        try:
            self.win.cache.put_many(fresh)
        except Exception:
            pass
        self.win.session.refresh_records(fresh)
        errors = [e for res in self.results for e in res.errors]
        done = sum(1 for res in self.results if not res.cancelled)
        stopped = any(res.cancelled for res in self.results) or done < len(self.albums)
        verb = {rg.MODE_REMOVE: "entfernt", rg.MODE_SCAN: "gemessen"}.get(self._run_mode, "geschrieben")
        self.summary.setText(f"{done} von {len(self.albums)} {'Album' if len(self.albums) == 1 else 'Alben'} {verb}" + (f" · {len(errors)} Fehler" if errors
                                                                              else ""))
        if stopped:
            self.show_message("Abgebrochen – fertige Alben sind schon gespeichert." if self._run_mode in rg.WRITES
                              else "Abgebrochen.")
        elif self._run_mode == rg.MODE_SCAN:
            self.show_message("Nur gemessen – an den Dateien wurde nichts geändert.")
        self.btn_errors.setVisible(bool(errors))
        self.win.toast.show_message(f"ReplayGain {verb}: {done} {'Album' if done == 1 else 'Alben'}")

    def _show_errors(self):
        from .dialogs import ErrorListDialog
        ErrorListDialog("ReplayGain – nicht alles geklappt",
                        [e for res in self.results for e in res.errors], self).exec()


def _actions_dialog(win, items, scope):
    from .actions import ActionsDialog
    return ActionsDialog(win, items, scope)


def _acoustid_dialog(win, items, scope):
    from .acoustid import AcoustIDDialog
    return AcoustIDDialog(win, items, scope)


EXTRA_DIALOGS = {
    "duplicates": DuplicatesDialog,
    "actions": _actions_dialog,
    "replaygain": ReplayGainDialog,
    "acoustid": _acoustid_dialog,
}
