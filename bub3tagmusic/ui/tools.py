"""Werkzeuge der Phase 2 – alle mit Live-Vorschau.

Aufbau jedes Werkzeugs:  links Optionen, rechts Vorschau, unten Übernehmen.
Übernommen wird wie jede Bearbeitung: gelb markiert, erst Speichern schreibt
in die Dateien, Strg+Z nimmt alles in einem Schritt zurück. Umbenennen ist die
Ausnahme – es passiert sofort auf der Festplatte (ebenfalls rückgängig machbar).
"""

from __future__ import annotations

import difflib
import os
from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QDialog, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QRadioButton,
                               QScrollArea, QSpinBox, QTableView, QVBoxLayout, QWidget)

from .. import features
from ..core import tools
from ..core.fields import FIELD_BY_KEY, FIELD_KEYS
from ..core.model import FileItem
from ..core.patterns import KNOWN, unknown_placeholders
from ..core.rename import CONFLICT, INVALID, MISSING, MIXED, OK, SAME, STATUS_TEXT, plan_renames
from . import icons, theme
from .widgets import FieldPicker, PatternBox, chip, hint, section

CHANGED, UNCHANGED, WARN, ERROR = "changed", "same", "warn", "error"


# ======================================================================
# Vorschau
# ======================================================================
@dataclass
class PreviewRow:
    label: str                                   # Dateiname
    cells: list[tuple[str, str | None]]          # (neu, alt) – alt=None: unverändert
    status: str = ""
    kind: str = CHANGED
    tooltip: str = ""


@dataclass
class Preview:
    columns: list[str] = field(default_factory=list)
    rows: list[PreviewRow] = field(default_factory=list)
    summary: str = ""
    apply_count: int = 0
    message: str = ""                            # z. B. Fehler im Suchausdruck
    first_column: str = "Datei"


class PreviewModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview = Preview()
        self.rows: list[PreviewRow] = []
        self.show_unchanged = False

    def set_preview(self, p: Preview):
        self.beginResetModel()
        self.preview = p
        self.rows = p.rows if self.show_unchanged else [r for r in p.rows if r.kind != UNCHANGED]
        self.endResetModel()

    def set_show_unchanged(self, on: bool):
        self.show_unchanged = on
        self.set_preview(self.preview)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.preview.columns) + 2

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        cols = [self.preview.first_column, *self.preview.columns, "Hinweis"]
        return cols[section] if section < len(cols) else None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        c = index.column()
        last = len(self.preview.columns) + 1
        if role == Qt.ItemDataRole.DisplayRole:
            if c == 0:
                return row.label
            if c == last:
                return row.status
            new, _old = row.cells[c - 1]
            return new
        if role == Qt.ItemDataRole.ForegroundRole:
            if c == last:
                return theme.qcolor({CHANGED: "done", WARN: "modified", ERROR: "danger"}.get(row.kind, "faint"))
            if c == 0:
                return theme.qcolor("muted" if row.kind != ERROR else "danger")
            if row.kind == ERROR:
                return theme.qcolor("faint")
            _new, old = row.cells[c - 1]
            return theme.qcolor("modified") if old is not None else theme.qcolor("faint")
        if role == Qt.ItemDataRole.FontRole and 0 < c < last and row.cells[c - 1][1] is not None:
            f = theme.ui_font(13, QFont.Weight.DemiBold)
            return f
        if role == Qt.ItemDataRole.ToolTipRole:
            if 0 < c < last:
                _new, old = row.cells[c - 1]
                if old is not None:
                    return f"Vorher: {old or '(leer)'}"
            return row.tooltip or None
        return None


# ======================================================================
# Basis-Dialog
# ======================================================================
class ToolDialog(QDialog):
    feature_id = ""
    apply_verb = "Übernehmen"
    renames = False

    def __init__(self, win, items: list[FileItem], scope: str):
        super().__init__(win)
        self.win = win
        self.session = win.session
        self.settings = win.settings
        self.items = items
        self.feature = features.get(self.feature_id)
        self.opts: dict = dict(self.settings.tool_options.get(self.feature_id, {}))
        self._changes: list = []
        self.setWindowTitle(self.feature.title.replace(" …", ""))
        self.resize(1040, 640)
        self.setMinimumSize(860, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Kopf
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
        tbox.addWidget(hint(scope, "muted"))
        hl.addLayout(tbox, 1)
        root.addWidget(head)

        # Körper: Optionen | Vorschau
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        opt_scroll = QScrollArea()
        opt_scroll.setObjectName("ToolOptions")
        opt_scroll.setWidgetResizable(True)
        opt_scroll.setFixedWidth(360)
        opt_scroll.setFrameShape(QFrame.Shape.NoFrame)
        opt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        opt_inner = QWidget(objectName="ToolOptionsInner")
        opt_inner.setMaximumWidth(360)
        self.form = QVBoxLayout(opt_inner)
        self.form.setContentsMargins(20, 16, 20, 16)
        self.form.setSpacing(8)
        opt_scroll.setWidget(opt_inner)
        body.addWidget(opt_scroll)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.message = QLabel()
        self.message.setObjectName("ToolMessage")
        self.message.setWordWrap(True)
        self.message.hide()
        right.addWidget(self.message)
        self.model = PreviewModel(self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setShowGrid(False)
        self.view.setWordWrap(False)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(30)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        right.addWidget(self.view, 1)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        # Fuß
        foot = QWidget(objectName="ToolFoot")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(20, 12, 20, 12)
        fl.setSpacing(10)
        left = QVBoxLayout()
        left.setSpacing(2)
        self.summary = QLabel()
        self.summary.setObjectName("ToolSummary")
        left.addWidget(self.summary)
        self.show_same = QCheckBox("Auch unveränderte Dateien zeigen")
        self.show_same.toggled.connect(self.model.set_show_unchanged)
        left.addWidget(self.show_same)
        fl.addLayout(left, 1)
        self.foot_hint = hint(
            "Danach gelb markiert · Strg+S speichert · Strg+Z nimmt zurück"
            if not self.renames else
            "Benennt sofort um · Strg+Z benennt zurück")
        self.foot_hint.setWordWrap(False)
        fl.addWidget(self.foot_hint)
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        fl.addWidget(cancel)
        self.apply_btn = QPushButton(self.apply_verb)
        self.apply_btn.setProperty("kind", "primary")
        self.apply_btn.setMinimumWidth(170)
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self._apply)
        fl.addWidget(self.apply_btn)
        root.addWidget(foot)

        self._timer = QTimer(self, singleShot=True)
        self._timer.setInterval(min(600, 120 + len(items) // 150))
        self._timer.timeout.connect(self.refresh)

        self.build_options()
        self.form.addStretch(1)
        self.refresh()

    # --- für Unterklassen ----------------------------------------------------------
    def build_options(self):
        raise NotImplementedError

    def compute(self) -> Preview:
        raise NotImplementedError

    def apply_changes(self):
        n = self.session.apply_changes(self._changes, f"{self.feature.title.replace(' …', '')} "
                                       f"({len(self._changes)} Datei{'en' if len(self._changes) != 1 else ''})")
        self.win.toast.show_message(f"{n} Datei(en) geändert – Strg+S speichert")

    # --- Hilfen ----------------------------------------------------------------------
    def later(self, *_):
        self._timer.start()

    def check(self, text: str, key: str, default: bool, detail: str = "") -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(bool(self.opts.get(key, default)))
        cb.toggled.connect(lambda on: (self.opts.__setitem__(key, on), self.later()))
        if detail:
            cb.setToolTip(detail)
            self._pending_detail = detail
        return cb

    def add_check(self, text: str, key: str, default: bool, detail: str = "") -> QCheckBox:
        """Häkchen mit kurzem Text – Erklärung (falls nötig) klein darunter."""
        cb = self.check(text, key, default, detail)
        self.form.addWidget(cb)
        if detail:
            d = hint(detail)
            d.setContentsMargins(26, 0, 0, 4)
            self.form.addWidget(d)
        return cb

    def refresh(self):
        try:
            p = self.compute()
        except Exception as exc:     # ein Fehler im Werkzeug darf das Fenster nicht schließen
            p = Preview(message=f"Fehler: {exc}")
        self.model.set_preview(p)
        if p.message:
            self.message.setText(p.message)
            self.message.show()
        else:
            self.message.hide()
        self.summary.setText(p.summary)
        self.apply_btn.setEnabled(p.apply_count > 0)
        n = p.apply_count
        self.apply_btn.setText(self.apply_label(n))
        self._fit_columns()

    def apply_label(self, n: int) -> str:
        return f"{self.apply_verb} ({n:,})".replace(",", ".") if n else self.apply_verb

    def _fit_columns(self):
        """Spaltenbreite nach Inhalt (die ersten 300 Zeilen reichen), mit Obergrenze."""
        hh = self.view.horizontalHeader()
        n = self.model.columnCount()
        if n == 0:
            return
        fm_bold = QFontMetrics(theme.ui_font(13, QFont.Weight.DemiBold))
        fm = QFontMetrics(theme.ui_font(13))
        rows = self.model.rows[:300]
        widths = []
        for c in range(n - 1):
            head = str(self.model.headerData(c, Qt.Orientation.Horizontal) or "")
            w = fm_bold.horizontalAdvance(head)
            for r in rows:
                text = r.label if c == 0 else r.cells[c - 1][0]
                w = max(w, (fm_bold if c and r.cells[c - 1][1] is not None else fm).horizontalAdvance(text))
            widths.append(min(w + 28, 320 if c == 0 else 260))
        for c, w in enumerate(widths):
            hh.resizeSection(c, max(60, w))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit_columns()

    def _apply(self):
        if not self.apply_btn.isEnabled():
            return
        self.store_options()
        self.apply_changes()
        self.accept()

    def store_options(self):
        self.settings.tool_options[self.feature_id] = self.opts
        try:
            self.settings.save()
        except OSError:
            pass

    @staticmethod
    def summary_text(changed: int, total: int, extra: list[str] | None = None) -> str:
        parts = [f"{changed:,} von {total:,} Dateien werden geändert".replace(",", ".")]
        parts += [e for e in (extra or []) if e]
        return "  ·  ".join(parts)

    def field_rows(self, proposals: list[tuple[FileItem, dict | None, str]], columns: list[str]) -> Preview:
        """Gemeinsame Vorschau für Werkzeuge, die Tag-Felder ändern."""
        rows, changes, errors = [], [], 0
        for it, new, err in proposals:
            if new is None:
                errors += 1
                rows.append(PreviewRow(it.name, [(it.tags.get(k, ""), None) for k in columns],
                                       err or "passt nicht", ERROR, it.path))
                continue
            diff = {k: v for k, v in new.items() if it.tags.get(k, "") != v}
            cells = []
            for k in columns:
                if k in diff:
                    cells.append((diff[k], it.tags.get(k, "")))
                else:
                    cells.append((it.tags.get(k, ""), None))
            if diff:
                changes.append((it, diff))
                rows.append(PreviewRow(it.name, cells, f"{len(diff)} Feld{'er' if len(diff) != 1 else ''}",
                                       CHANGED, it.path))
            else:
                rows.append(PreviewRow(it.name, cells, "unverändert", UNCHANGED, it.path))
        self._changes = changes
        extra = [f"{errors} passen nicht" if errors else ""]
        return Preview([FIELD_BY_KEY[k].label for k in columns], rows,
                       self.summary_text(len(changes), len(self.items), extra), len(changes))


def _suggest(unknown: list[str]) -> str:
    tips = []
    for u in unknown:
        close = difflib.get_close_matches(u, list(KNOWN), n=1)
        tips.append(f"%{u}%" + (f" – meintest du %{close[0]}%?" if close else ""))
    return "Unbekannter Platzhalter: " + "; ".join(tips) + "  (Teile überspringen: %dummy%)"


# ======================================================================
# #1 Tags aus Dateiname / Ordnername
# ======================================================================
class TagsFromFilenameDialog(ToolDialog):
    feature_id = "tags_from_filename"

    def build_options(self):
        f = self.form
        f.addWidget(section("Muster"))
        self.pattern = PatternBox(tools.PATTERN_PRESETS, self.opts.get("history", []),
                                  self.opts.get("pattern", ""), [*FIELD_KEYS, "dummy"])
        self.pattern.changed.connect(self.later)
        f.addWidget(self.pattern)
        f.addWidget(hint("„/“ trennt Ordnerebenen, z. B. %artist%/%year% - %album%/%track% - %title%. "
                         "%dummy% überspringt einen Teil."))
        self.example = hint("", "muted")
        f.addWidget(self.example)
        f.addSpacing(8)
        f.addWidget(section("Optionen"))
        f.addWidget(self.check("Führende Nullen bei Track und Disc entfernen", "strip_zeros", True))
        f.addWidget(self.check("Unterstriche als Leerzeichen lesen", "underscores", True))
        f.addWidget(self.check("Nur leere Felder füllen", "only_empty", False))

    def compute(self) -> Preview:
        pattern = self.pattern.text()
        self.opts["pattern"] = pattern
        if self.items:
            from ..core.patterns import path_subject
            subj = path_subject(self.items[0].path, pattern.strip("/")) or "(zu wenige Ordnerebenen)"
            self.example.setText(f"Das Muster wird verglichen mit:\n{subj}")
        if not pattern:
            return Preview(message="Muster eingeben, z. B. %track% - %title%")
        msg = _suggest(unknown_placeholders(pattern)) if unknown_placeholders(pattern) else ""
        columns = [k for k in FIELD_KEYS if f"%{k}%" in pattern]
        if not columns:
            return Preview(message="Das Muster enthält kein Feld – z. B. %title% einfügen")
        props = []
        for it in self.items:
            new = tools.parse_from_path(it.path, pattern, strip_zeros=self.opts.get("strip_zeros", True),
                                        underscores=self.opts.get("underscores", True),
                                        only_empty=self.opts.get("only_empty", False), current=it.tags)
            props.append((it, new, "passt nicht zum Muster"))
        p = self.field_rows(props, columns)
        p.message = msg
        return p

    def store_options(self):
        self.opts["history"] = PatternBox.remember(self.opts.get("history", []), self.pattern.text())
        super().store_options()


# ======================================================================
# #2 Dateinamen aus Tags
# ======================================================================
RENAME_PRESETS = (
    "%track% - %title%",
    "%track% - %artist% - %title%",
    "%artist% - %title%",
    "%track%. %title%",
    "%disc%-%track% - %title%",
)


class FilenameFromTagsDialog(ToolDialog):
    feature_id = "filename_from_tags"
    apply_verb = "Umbenennen"
    renames = True

    def build_options(self):
        f = self.form
        f.addWidget(section("Muster für den Dateinamen"))
        self.pattern = PatternBox(RENAME_PRESETS, self.opts.get("history", []), self.opts.get("pattern", ""),
                                  list(FIELD_KEYS))
        self.pattern.changed.connect(self.later)
        f.addWidget(self.pattern)
        f.addWidget(hint("Die Endung (.mp3, .flac …) bleibt. Ordner benennt das Werkzeug „Ordner umbenennen“ um."))
        f.addSpacing(8)
        f.addWidget(section("Optionen"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Tracknummer auffüllen auf"))
        self.pad = QSpinBox()
        self.pad.setRange(0, 4)
        self.pad.setValue(int(self.opts.get("pad", 2)))
        self.pad.setSuffix(" Stellen")
        self.pad.valueChanged.connect(lambda v: (self.opts.__setitem__("pad", v), self.later()))
        row.addWidget(self.pad)
        row.addStretch(1)
        f.addLayout(row)
        self.add_check("USB-/Windows-taugliche Namen", "windows_safe", True,
                       "Ersetzt : ? * \" < > | durch _ – wichtig für USB-Sticks und Autoradios.")
        self.add_check("Begleitdateien mitnehmen", "companions", True,
                       "Gleichnamige Dateien im Ordner (01 - Lied.lrc, .txt, .srt …) bekommen den neuen Namen mit.")
        unsaved = sum(1 for it in self.items if it.is_modified())
        if unsaved:
            f.addSpacing(6)
            f.addWidget(hint(f"{unsaved} Datei(en) haben ungespeicherte Änderungen – die neuen Namen nutzen "
                             "schon die geänderten Werte.", "muted"))

    def compute(self) -> Preview:
        pattern = self.pattern.text()
        self.opts["pattern"] = pattern
        if not pattern:
            return Preview(message="Muster eingeben, z. B. %track% - %title%")
        msg = _suggest(unknown_placeholders(pattern)) if unknown_placeholders(pattern) else ""
        plans = plan_renames([(it.path, it.tags) for it in self.items], pattern,
                             pad_track=self.pad.value(), windows_safe=self.opts.get("windows_safe", True),
                             companions=self.opts.get("companions", True))
        kind = {OK: CHANGED, SAME: UNCHANGED, MISSING: WARN, CONFLICT: ERROR, INVALID: ERROR}
        rows, counts = [], {}
        for p in plans:
            counts[p.status] = counts.get(p.status, 0) + 1
            new_name = os.path.basename(p.new)
            old_name = os.path.basename(p.old)
            cells = [(new_name if p.status in (OK, SAME, CONFLICT) else "", old_name if p.status == OK else None)]
            status = p.note or STATUS_TEXT[p.status]
            if p.status == OK and p.companions:
                n = len(p.companions)
                status += f" + {n} Begleitdatei{'en' if n != 1 else ''}"
            tip = p.old + "".join(f"\n+ {os.path.basename(c)} → {os.path.basename(cn)}" for c, cn in p.companions)
            rows.append(PreviewRow(old_name, cells, status, kind[p.status], tip))
        self._pairs = [pair for p in plans for pair in p.all_pairs]
        self._file_count = sum(1 for p in plans if p.will_rename)
        extra = [f"{counts[MISSING]} mit fehlenden Tags" if counts.get(MISSING) else "",
                 f"{counts[CONFLICT]} mit doppeltem Namen" if counts.get(CONFLICT) else "",
                 f"{counts[INVALID]} ungültig" if counts.get(INVALID) else ""]
        comp = len(self._pairs) - self._file_count
        extra.append((f"{comp} Begleitdateien wandern mit" if comp != 1 else "1 Begleitdatei wandert mit") if comp else "")
        summary = f"{self._file_count:,} von {len(self.items):,} Dateien werden umbenannt".replace(",", ".")
        summary = "  ·  ".join([summary] + [e for e in extra if e])
        return Preview(["Neuer Name"], rows, summary, self._file_count, msg)

    def apply_changes(self):
        n = self._file_count
        self.win.run_rename(self._pairs, f"{n} Datei{'en' if n != 1 else ''} umbenannt")

    def store_options(self):
        self.opts["history"] = PatternBox.remember(self.opts.get("history", []), self.pattern.text())
        super().store_options()


# ======================================================================
# Ordner umbenennen
# ======================================================================
FOLDER_PRESETS = (
    "%year% - %album%",
    "%album% (%year%)",
    "%album%",
    "%albumartist% - %album%",
    "%year% - %albumartist% - %album%",
)


class FolderRenameDialog(ToolDialog):
    feature_id = "folder_rename"
    apply_verb = "Ordner umbenennen"
    renames = True

    def build_options(self):
        f = self.form
        f.addWidget(section("Muster für den Ordnernamen"))
        self.pattern = PatternBox(FOLDER_PRESETS, self.opts.get("history", []), self.opts.get("pattern", ""),
                                  ["year", "album", "albumartist", "artist", "genre", "disc"])
        self.pattern.changed.connect(self.later)
        f.addWidget(self.pattern)
        f.addWidget(hint("Benennt die Ordner um, in denen die gewählten Dateien liegen – mit allem, was "
                         "darin liegt (Musik, cover.jpg, Begleitdateien). Der Name kommt aus den Tags, die alle "
                         "Dateien im Ordner gemeinsam haben."))
        f.addSpacing(8)
        f.addWidget(section("Optionen"))
        self.add_check("USB-/Windows-taugliche Namen", "windows_safe", True,
                       "Ersetzt : ? * \" < > | durch _ – wichtig für USB-Sticks und Autoradios.")
        f.addWidget(hint("Der Fertig-Status im Ordnerbaum wandert mit. Strg+Z benennt zurück.", "muted"))

    def _folders(self) -> list[tuple[str, dict, set]]:
        groups: dict[str, list[FileItem]] = {}
        for it in self.items:
            groups.setdefault(it.dir, []).append(it)
        out = []
        for folder, its in groups.items():
            common, mixed = {}, set()
            for key in FIELD_KEYS:
                values = {it.tags.get(key, "").strip() for it in its}
                if len(values) == 1:
                    common[key] = values.pop()
                else:
                    mixed.add(key)
            # Album-Interpret fehlt oft: dann gilt ein einheitlicher Interpret
            if not common.get("albumartist") and common.get("artist"):
                common["albumartist"] = common["artist"]
                mixed.discard("albumartist")
            out.append((folder, common, mixed))
        return out

    def compute(self) -> Preview:
        from ..core.rename import plan_folder_renames
        pattern = self.pattern.text()
        self.opts["pattern"] = pattern
        if not pattern:
            return Preview(message="Muster eingeben, z. B. %year% - %album%")
        msg = _suggest(unknown_placeholders(pattern)) if unknown_placeholders(pattern) else ""
        plans = plan_folder_renames(self._folders(), pattern, windows_safe=self.opts.get("windows_safe", True))
        # Ordner, die in einem anderen umzubenennenden Ordner liegen, erst im zweiten Durchgang
        renaming = [p.old + "/" for p in plans if p.will_rename]
        for p in plans:
            if p.will_rename and any(p.old.startswith(r) for r in renaming):
                p.status, p.note = INVALID, "liegt in einem Ordner, der auch umbenannt wird – danach nochmal"
        kind = {OK: CHANGED, SAME: UNCHANGED, MISSING: WARN, CONFLICT: ERROR, INVALID: ERROR, MIXED: WARN}
        rows = []
        for p in plans:
            old_name, new_name = os.path.basename(p.old), os.path.basename(p.new)
            cells = [(new_name if p.status in (OK, SAME, CONFLICT) else "", old_name if p.status == OK else None)]
            rows.append(PreviewRow(old_name, cells, p.note or STATUS_TEXT[p.status], kind[p.status], p.old))
        self._pairs = [(p.old, p.new) for p in plans if p.will_rename]
        n = len(self._pairs)
        problems = sum(1 for p in plans if p.status in (MISSING, MIXED, CONFLICT, INVALID))
        verb = "wird" if n == 1 else "werden"
        summary = f"{n} von {len(plans)} Ordner{'n' if len(plans) != 1 else ''} {verb} umbenannt" + \
            (f"  ·  {problems} mit Hinweis" if problems else "")
        return Preview(["Neuer Ordnername"], rows, summary, n, msg, first_column="Ordner")

    def apply_label(self, n: int) -> str:
        return f"{n} Ordner umbenennen" if n else "Ordner umbenennen"

    def apply_changes(self):
        n = len(self._pairs)
        self.win.run_rename(self._pairs, f"{n} Ordner umbenannt")

    def store_options(self):
        self.opts["history"] = PatternBox.remember(self.opts.get("history", []), self.pattern.text())
        super().store_options()


# ======================================================================
# #3 Tracks automatisch nummerieren
# ======================================================================
class AutonumberDialog(ToolDialog):
    feature_id = "autonumber"

    def build_options(self):
        f = self.form
        f.addWidget(section("Nummerierung"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Beginnen bei"))
        self.start = QSpinBox()
        self.start.setRange(0, 999)
        self.start.setValue(int(self.opts.get("start", 1)))
        self.start.valueChanged.connect(lambda v: (self.opts.__setitem__("start", v), self.later()))
        row.addWidget(self.start)
        row.addStretch(1)
        f.addLayout(row)
        f.addWidget(self.check("Pro Ordner neu beginnen", "per_folder", True))
        f.addWidget(self.check("Mit Gesamtzahl (3/12)", "with_total", True))
        f.addWidget(self.check("Mit führender Null (01, 02 …)", "leading_zero", False))
        f.addWidget(self.check("Disc-Nummer aus Ordnernamen (CD1, Disc 2 …)", "disc", False))
        f.addSpacing(8)
        f.addWidget(hint("Die Reihenfolge ist die aktuelle Reihenfolge der Liste. "
                         "Tipp: vorher auf den Spaltenkopf „Dateiname“ klicken."))

    def compute(self) -> Preview:
        res = tools.autonumber([it.dir for it in self.items], start=self.start.value(),
                               per_folder=self.opts.get("per_folder", True),
                               with_total=self.opts.get("with_total", True),
                               pad=2 if self.opts.get("leading_zero", False) else 0,
                               disc_from_folders=self.opts.get("disc", False))
        cols = ["track"] + (["disc"] if any("disc" in r for r in res) else [])
        return self.field_rows([(it, r, "") for it, r in zip(self.items, res)], cols)


# ======================================================================
# #4 Groß-/Kleinschreibung
# ======================================================================
CASE_FIELDS = ["title", "artist", "albumartist", "album", "genre", "composer", "comment"]


class CaseDialog(ToolDialog):
    feature_id = "case"

    def build_options(self):
        f = self.form
        f.addWidget(section("Schreibweise"))
        self.modes = QButtonGroup(self)
        current = self.opts.get("mode", tools.CASE_TITLE)
        for mode, text in ((tools.CASE_TITLE, "Jedes Wort groß  –  Gegen den Wind"),
                           (tools.CASE_SENTENCE, "Nur Satzanfang groß  –  Gegen den wind"),
                           (tools.CASE_UPPER, "ALLES GROSS"),
                           (tools.CASE_LOWER, "alles klein")):
            rb = QRadioButton(text)
            rb.setProperty("mode", mode)
            rb.setChecked(mode == current)
            self.modes.addButton(rb)
            f.addWidget(rb)
        self.modes.buttonToggled.connect(self._mode_changed)
        f.addSpacing(8)
        f.addWidget(section("Felder"))
        self.fields = FieldPicker(CASE_FIELDS, self.opts.get("fields", ["title", "artist", "albumartist", "album"]))
        self.fields.changed.connect(lambda: (self.opts.__setitem__("fields", self.fields.selected()), self.later()))
        f.addWidget(self.fields)
        f.addSpacing(8)
        f.addWidget(section("Feinheiten"))
        self.add_check("Gemischte Schreibweise schützen", "only_uniform", True,
                       "Ändert nur, was komplett GROSS oder klein ist – „iPhone“ oder „McCartney“ bleiben.")
        f.addWidget(QLabel("Bleiben klein (außer am Anfang):"))
        self.small = QPlainTextEdit(self.opts.get("small", tools.DEFAULT_SMALL_WORDS))
        self.small.setFixedHeight(64)
        self.small.textChanged.connect(lambda: (self.opts.__setitem__("small", self.small.toPlainText()),
                                                self.later()))
        f.addWidget(self.small)
        f.addWidget(QLabel("Feste Schreibweisen:"))
        self.fixed = QLineEdit(self.opts.get("fixed", tools.DEFAULT_FIXED_WORDS))
        self.fixed.setCursorPosition(0)
        self.fixed.textChanged.connect(lambda t: (self.opts.__setitem__("fixed", t), self.later()))
        f.addWidget(self.fixed)
        reset = chip("Standard wiederherstellen")
        reset.clicked.connect(lambda: (self.small.setPlainText(tools.DEFAULT_SMALL_WORDS),
                                       self.fixed.setText(tools.DEFAULT_FIXED_WORDS)))
        f.addWidget(reset, 0, Qt.AlignmentFlag.AlignLeft)

    def _mode_changed(self, btn, on):
        if on:
            self.opts["mode"] = btn.property("mode")
            self.later()

    def compute(self) -> Preview:
        keys = self.fields.selected()
        if not keys:
            return Preview(message="Mindestens ein Feld auswählen")
        mode = self.opts.get("mode", tools.CASE_TITLE)
        small = tools.parse_word_list(self.small.toPlainText())
        fixed = tools.parse_word_list(self.fixed.text())
        uniform = self.opts.get("only_uniform", True)
        props = []
        for it in self.items:
            props.append((it, {k: tools.change_case(it.tags.get(k, ""), mode, small_words=small, fixed_words=fixed,
                                                    only_uniform=uniform) for k in keys}, ""))
        cols = [k for k in keys if any(it.tags.get(k, "") != n.get(k, "") for it, n, _ in props)] or keys[:1]
        return self.field_rows(props, cols)


# ======================================================================
# #5 Suchen & Ersetzen
# ======================================================================
class ReplaceDialog(ToolDialog):
    feature_id = "replace"

    def build_options(self):
        f = self.form
        f.addWidget(section("Suchen"))
        self.find = QLineEdit(self.opts.get("find", ""))
        self.find.setPlaceholderText("z. B. (Live) oder Remastered")
        self.find.textChanged.connect(self.later)
        f.addWidget(self.find)
        f.addWidget(section("Ersetzen durch"))
        self.repl = QLineEdit(self.opts.get("repl", ""))
        self.repl.setPlaceholderText("leer lassen = entfernen")
        self.repl.textChanged.connect(self.later)
        f.addWidget(self.repl)
        f.addSpacing(4)
        f.addWidget(self.check("Groß-/Kleinschreibung beachten", "case", False))
        f.addWidget(self.check("Nur ganze Wörter", "whole", False))
        f.addWidget(self.check("Regulärer Ausdruck", "regex", False))
        f.addWidget(hint("Bei regulären Ausdrücken: Gruppen mit ( … ) im Suchen, im Ersetzen $1 oder \\1."))
        f.addSpacing(8)
        f.addWidget(section("Felder"))
        self.fields = FieldPicker(list(tools.TEXT_FIELDS) + ["year", "track", "disc"],
                                  self.opts.get("fields", list(tools.TEXT_FIELDS)))
        self.fields.changed.connect(lambda: (self.opts.__setitem__("fields", self.fields.selected()), self.later()))
        f.addWidget(self.fields)
        self.find.setFocus()

    def compute(self) -> Preview:
        self.opts["find"], self.opts["repl"] = self.find.text(), self.repl.text()
        keys = self.fields.selected()
        if not self.find.text():
            return Preview(message="Suchbegriff eingeben")
        if not keys:
            return Preview(message="Mindestens ein Feld auswählen")
        regex = self.opts.get("regex", False)
        try:
            rx = tools.compile_search(self.find.text(), regex=regex, case=self.opts.get("case", False),
                                      whole_word=self.opts.get("whole", False))
        except tools.PatternError as exc:
            return Preview(message=str(exc))
        props, hits = [], 0
        try:
            for it in self.items:
                new = {}
                for k in keys:
                    val = it.tags.get(k, "")
                    if not val:
                        continue
                    out, n = tools.replace_text(val, rx, self.repl.text(), regex=regex)
                    if n:
                        hits += n
                        new[k] = out.strip()
                props.append((it, new, ""))
        except tools.PatternError as exc:
            self._changes = []
            return Preview(message=str(exc))
        cols = [k for k in keys if any(k in n for _, n, _ in props)] or keys[:1]
        p = self.field_rows(props, cols)
        p.summary += f"  ·  {hits:,} Treffer".replace(",", ".")
        return p


# ======================================================================
# #6 Aufräumen
# ======================================================================
class CleanupDialog(ToolDialog):
    feature_id = "cleanup"

    def build_options(self):
        f = self.form
        f.addWidget(section("Was soll aufgeräumt werden?"))
        for rule in tools.CLEANUP_RULES:
            self.add_check(rule.label, "rule_" + rule.key, rule.default, rule.detail)
        f.addSpacing(8)
        f.addWidget(section("Felder"))
        self.fields = FieldPicker(list(tools.TEXT_FIELDS) + ["track", "disc"],
                                  self.opts.get("fields", list(tools.TEXT_FIELDS) + ["track", "disc"]))
        self.fields.changed.connect(lambda: (self.opts.__setitem__("fields", self.fields.selected()), self.later()))
        f.addWidget(self.fields)

    def compute(self) -> Preview:
        rules = {r.key for r in tools.CLEANUP_RULES if self.opts.get("rule_" + r.key, r.default)}
        keys = self.fields.selected()
        if not keys:
            return Preview(message="Mindestens ein Feld auswählen")
        if not rules:
            return Preview(message="Mindestens eine Regel auswählen")
        props = [(it, {k: tools.cleanup(it.tags.get(k, ""), k, rules) for k in keys}, "") for it in self.items]
        cols = [k for k in keys if any(it.tags.get(k, "") != n.get(k, "") for it, n, _ in props)] or keys[:1]
        return self.field_rows(props, cols)


TOOL_DIALOGS = {
    "tags_from_filename": TagsFromFilenameDialog,
    "filename_from_tags": FilenameFromTagsDialog,
    "autonumber": AutonumberDialog,
    "case": CaseDialog,
    "replace": ReplaceDialog,
    "cleanup": CleanupDialog,
    "folder_rename": FolderRenameDialog,
}
