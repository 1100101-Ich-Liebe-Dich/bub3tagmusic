"""Aktionen (Phase 4): Schrittketten anlegen, bearbeiten und mit Vorschau ausführen.

Links: Aktion wählen, Schritte (hinzufügen, bearbeiten, verschieben, löschen).
Rechts: Vorschau des Gesamtergebnisses. „Ausführen“ übernimmt alles in EINEM
Rückgängig-Schritt – auch wenn am Ende umbenannt wird.
Jede Änderung an einer Aktion wird sofort in actions.json gespeichert.
"""

from __future__ import annotations

import copy
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                               QPlainTextEdit, QRadioButton, QSpinBox, QToolButton, QVBoxLayout)

from ..core import actions as A
from ..core import tools
from ..core.fields import FIELD_BY_KEY, FIELD_KEYS
from ..core.rename import CONFLICT, INVALID, MISSING, OK, SAME, STATUS_TEXT, plan_renames
from ..core.settings import config_dir
from . import icons
from .tools import CHANGED, ERROR, UNCHANGED, WARN, Preview, PreviewRow, ToolDialog
from .widgets import FieldPicker, PatternBox, chip, hint, section


def actions_path() -> str:
    return str(config_dir() / "actions.json")


# ======================================================================
# Einen Schritt bearbeiten
# ======================================================================
class StepDialog(QDialog):
    def __init__(self, step: dict, parent=None):
        super().__init__(parent)
        self.step = copy.deepcopy(step)
        self.o = self.step["opts"]
        st = A.STEP_TYPES[self.step["type"]]
        self.setWindowTitle(f"Schritt: {st.label}")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.icon(st.icon, "accent").pixmap(22, 22))
        head.addWidget(ic)
        t = QLabel(st.label)
        t.setProperty("role", "heading")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)
        self.form = lay
        self.collect = []                      # Funktionen, die beim OK die Werte einsammeln
        getattr(self, "_build_" + self.step["type"])()
        lay.addSpacing(6)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
        btns.button(QDialogButtonBox.StandardButton.Ok).setProperty("kind", "primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        btns.accepted.connect(self._ok)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _ok(self):
        for fn in self.collect:
            fn()
        self.accept()

    # --- Bausteine -------------------------------------------------------------
    def _check(self, text: str, key: str):
        cb = QCheckBox(text)
        cb.setChecked(bool(self.o.get(key)))
        self.form.addWidget(cb)
        self.collect.append(lambda: self.o.__setitem__(key, cb.isChecked()))
        return cb

    def _fields(self, keys: list[str]):
        self.form.addWidget(section("Felder"))
        fp = FieldPicker(keys, self.o.get("fields", []))
        self.form.addWidget(fp)
        self.collect.append(lambda: self.o.__setitem__("fields", fp.selected()))

    def _line(self, label: str, key: str, placeholder: str = ""):
        self.form.addWidget(section(label))
        le = QLineEdit(str(self.o.get(key, "")))
        le.setPlaceholderText(placeholder)
        self.form.addWidget(le)
        self.collect.append(lambda: self.o.__setitem__(key, le.text()))
        return le

    def _pattern(self, label: str, presets, keys):
        self.form.addWidget(section(label))
        pb = PatternBox(tuple(presets), [], self.o.get("pattern", ""), keys)
        self.form.addWidget(pb)
        self.collect.append(lambda: self.o.__setitem__("pattern", pb.text()))

    # --- je Schritt-Typ ------------------------------------------------------------
    def _build_cleanup(self):
        self.form.addWidget(section("Regeln"))
        rules = set(self.o.get("rules") or [])
        boxes = []
        for r in tools.CLEANUP_RULES:
            cb = QCheckBox(r.label)
            cb.setChecked(r.key in rules)
            if r.detail:
                cb.setToolTip(r.detail)
            self.form.addWidget(cb)
            boxes.append((r.key, cb))
        self.collect.append(lambda: self.o.__setitem__("rules", [k for k, cb in boxes if cb.isChecked()]))
        self._fields(list(tools.TEXT_FIELDS) + ["track", "disc"])

    def _build_case(self):
        self.form.addWidget(section("Schreibweise"))
        grp = QButtonGroup(self)
        for mode, text in A.CASE_NAMES.items():
            rb = QRadioButton(text)
            rb.setProperty("mode", mode)
            rb.setChecked(mode == self.o.get("mode"))
            grp.addButton(rb)
            self.form.addWidget(rb)
        self.collect.append(lambda: self.o.__setitem__("mode", grp.checkedButton().property("mode")
                                                       if grp.checkedButton() else tools.CASE_TITLE))
        self._check("Gemischte Schreibweise schützen (iPhone, McCartney …)", "only_uniform")
        self._fields(["title", "artist", "albumartist", "album", "genre", "composer", "comment"])
        self.form.addWidget(QLabel("Bleiben klein (außer am Anfang):"))
        small = QPlainTextEdit(self.o.get("small", ""))
        small.setFixedHeight(56)
        self.form.addWidget(small)
        self.collect.append(lambda: self.o.__setitem__("small", small.toPlainText()))
        self._line("Feste Schreibweisen", "fixed")

    def _build_replace(self):
        le = self._line("Suchen", "find", "z. B. (Live) oder Remastered")
        le.setFocus()
        self._line("Ersetzen durch", "repl", "leer lassen = entfernen")
        self._check("Groß-/Kleinschreibung beachten", "case")
        self._check("Nur ganze Wörter", "whole")
        self._check("Regulärer Ausdruck ($1 für Gruppen)", "regex")
        self._fields(list(tools.TEXT_FIELDS) + ["year", "track", "disc"])

    def _build_set_field(self):
        self.form.addWidget(section("Feld"))
        combo = QComboBox()
        for k in FIELD_KEYS:
            combo.addItem(FIELD_BY_KEY[k].label, k)
        combo.setCurrentIndex(max(0, combo.findData(self.o.get("field"))))
        self.form.addWidget(combo)
        self.collect.append(lambda: self.o.__setitem__("field", combo.currentData()))
        le = self._line("Wert", "value", "leer = Feld leeren")
        self.form.addWidget(hint("Platzhalter erlaubt, z. B. %artist% oder %year% - %album%."))
        chips = QHBoxLayout()
        for key in ("artist", "albumartist", "album", "year", "genre"):
            c = chip(f"%{key}%", tooltip=FIELD_BY_KEY[key].label)
            c.clicked.connect(lambda _=False, k=key: le.insert(f"%{k}%"))
            chips.addWidget(c)
        chips.addStretch(1)
        self.form.addLayout(chips)
        self._check("Nur wenn das Feld leer ist", "only_empty")

    def _build_tags_from_filename(self):
        self._pattern("Muster", tools.PATTERN_PRESETS, [*FIELD_KEYS, "dummy"])
        self.form.addWidget(hint("„/“ trennt Ordnerebenen, %dummy% überspringt einen Teil."))
        self._check("Führende Nullen bei Track und Disc entfernen", "strip_zeros")
        self._check("Unterstriche als Leerzeichen lesen", "underscores")
        self._check("Nur leere Felder füllen", "only_empty")

    def _build_autonumber(self):
        row = QHBoxLayout()
        row.addWidget(QLabel("Beginnen bei"))
        sp = QSpinBox()
        sp.setRange(0, 999)
        sp.setValue(int(self.o.get("start", 1)))
        row.addWidget(sp)
        row.addStretch(1)
        self.form.addLayout(row)
        self.collect.append(lambda: self.o.__setitem__("start", sp.value()))
        self._check("Pro Ordner neu beginnen", "per_folder")
        self._check("Mit Gesamtzahl (3/12)", "with_total")
        self._check("Mit führender Null (01, 02 …)", "leading_zero")
        self.form.addWidget(hint("Reihenfolge = aktuelle Reihenfolge der Liste."))

    def _build_rename(self):
        from .tools import RENAME_PRESETS
        self._pattern("Muster für den Dateinamen", RENAME_PRESETS, list(FIELD_KEYS))
        self.form.addWidget(hint("Läuft immer als letzter Schritt und nutzt die fertigen Tags. Endung bleibt."))
        row = QHBoxLayout()
        row.addWidget(QLabel("Tracknummer auffüllen auf"))
        sp = QSpinBox()
        sp.setRange(0, 4)
        sp.setSuffix(" Stellen")
        sp.setValue(int(self.o.get("pad", 2)))
        row.addWidget(sp)
        row.addStretch(1)
        self.form.addLayout(row)
        self.collect.append(lambda: self.o.__setitem__("pad", sp.value()))
        self._check("USB-/Windows-taugliche Namen", "windows_safe")
        self._check("Begleitdateien mitnehmen (.lrc, .txt …)", "companions")


# ======================================================================
# Aktionen-Fenster
# ======================================================================
class ActionsDialog(ToolDialog):
    feature_id = "actions"
    apply_verb = "Ausführen"

    def build_options(self):
        self.path = actions_path()
        self.actions = A.load_actions(self.path)
        if not os.path.exists(self.path):
            self._save()
        f = self.form
        f.addWidget(section("Aktion"))
        row = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(12)
        self.combo.currentIndexChanged.connect(self._action_changed)
        row.addWidget(self.combo, 1)
        more = QToolButton()
        more.setIcon(icons.icon("dots-three", "muted"))
        more.setToolTip("Neue Aktion, umbenennen, kopieren, löschen")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(more)
        m.addAction(icons.icon("plus", "muted"), "Neue Aktion …", self.new_action)
        m.addAction(icons.icon("pencil-simple", "muted"), "Umbenennen …", self.rename_action)
        m.addAction(icons.icon("copy", "muted"), "Kopieren", self.copy_action)
        m.addSeparator()
        m.addAction(icons.icon("trash", "muted"), "Löschen", self.delete_action)
        m.addAction(icons.icon("arrow-counter-clockwise", "muted"), "Beispiel-Aktionen wiederherstellen",
                    self.restore_examples)
        more.setMenu(m)
        row.addWidget(more)
        f.addLayout(row)

        f.addSpacing(6)
        f.addWidget(section("Schritte – werden nacheinander ausgeführt"))
        self.steps = QListWidget()
        self.steps.setMinimumHeight(170)
        self.steps.setWordWrap(True)
        self.steps.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.steps.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.steps.itemDoubleClicked.connect(lambda _it: self.edit_step())
        self.steps.currentRowChanged.connect(lambda _r: self._update_step_buttons())
        f.addWidget(self.steps)
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.btn_add = QToolButton()
        self.btn_add.setText("Schritt hinzufügen")
        self.btn_add.setProperty("kind", "side")
        self.btn_add.setIcon(icons.icon("plus", "text"))
        self.btn_add.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_add.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        add_menu = QMenu(self.btn_add)
        for st in A.STEP_TYPES.values():
            add_menu.addAction(icons.icon(st.icon, "muted"), st.label, lambda k=st.key: self.add_step(k))
        self.btn_add.setMenu(add_menu)
        bar.addWidget(self.btn_add)
        bar.addStretch(1)
        self.btn_edit = self._small("pencil-simple", "Schritt bearbeiten (Doppelklick)", self.edit_step)
        self.btn_up = self._small("arrow-up", "Nach oben", lambda: self.move_step(-1))
        self.btn_down = self._small("arrow-down", "Nach unten", lambda: self.move_step(+1))
        self.btn_del = self._small("x", "Schritt entfernen", self.remove_step)
        for b in (self.btn_edit, self.btn_up, self.btn_down, self.btn_del):
            bar.addWidget(b)
        f.addLayout(bar)
        f.addWidget(hint("Umbenennen läuft immer zuletzt. Alles wird automatisch gespeichert "
                         "(actions.json im Einstellungs-Ordner)."))
        last = self.opts.get("last", "")
        names = [a.name for a in self.actions]
        self._fill_combo(names.index(last) if last in names else 0)

    def _small(self, icon_name: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setIcon(icons.icon(icon_name, "muted"))
        b.setToolTip(tip)
        b.clicked.connect(slot)
        return b

    # --- Verwaltung ------------------------------------------------------------------
    @property
    def action(self) -> A.Action | None:
        i = self.combo.currentIndex()
        return self.actions[i] if 0 <= i < len(self.actions) else None

    def _fill_combo(self, index: int = 0):
        self.combo.blockSignals(True)
        self.combo.clear()
        for a in self.actions:
            self.combo.addItem(icons.icon("lightning", "muted"), a.name)
        self.combo.setCurrentIndex(min(max(0, index), len(self.actions) - 1))
        self.combo.blockSignals(False)
        self._action_changed()

    def _action_changed(self, *_):
        a = self.action
        self.opts["last"] = a.name if a else ""
        self._fill_steps()
        self.later()

    def _fill_steps(self, select: int = -1):
        self.steps.clear()
        a = self.action
        for n, st in enumerate(a.steps if a else [], 1):
            it = QListWidgetItem(icons.icon(A.STEP_TYPES[st["type"]].icon, "muted"), f"{n}.  {A.describe(st)}")
            it.setToolTip(A.describe(st))
            self.steps.addItem(it)
        if select >= 0 and self.steps.count():
            self.steps.setCurrentRow(min(select, self.steps.count() - 1))
        self._update_step_buttons()

    def _update_step_buttons(self):
        r = self.steps.currentRow()
        n = self.steps.count()
        self.btn_edit.setEnabled(r >= 0)
        self.btn_del.setEnabled(r >= 0)
        self.btn_up.setEnabled(r > 0)
        self.btn_down.setEnabled(0 <= r < n - 1)
        self.btn_add.setEnabled(self.action is not None)

    def _changed(self, select: int = -1):
        self._save()
        self._fill_steps(select)
        self.later()

    def _save(self):
        try:
            A.save_actions(self.path, self.actions)
        except OSError as exc:
            self.message.setText(f"Aktionen konnten nicht gespeichert werden: {exc.strerror or exc}")
            self.message.show()

    def _unique(self, name: str) -> str:
        names = {a.name for a in self.actions}
        if name not in names:
            return name
        n = 2
        while f"{name} ({n})" in names:
            n += 1
        return f"{name} ({n})"

    def new_action(self, name: str = ""):
        if not name:
            name, ok = QInputDialog.getText(self, "Neue Aktion", "Name der Aktion:", text="Meine Aktion")
            if not ok or not name.strip():
                return
        self.actions.append(A.Action(self._unique(name.strip())))
        self._save()
        self._fill_combo(len(self.actions) - 1)

    def rename_action(self):
        a = self.action
        if a is None:
            return
        name, ok = QInputDialog.getText(self, "Aktion umbenennen", "Neuer Name:", text=a.name)
        if ok and name.strip() and name.strip() != a.name:
            a.name = self._unique(name.strip())
            self._save()
            self._fill_combo(self.combo.currentIndex())

    def copy_action(self):
        a = self.action
        if a is None:
            return
        self.actions.append(A.Action(self._unique(a.name + " – Kopie"), copy.deepcopy(a.steps)))
        self._save()
        self._fill_combo(len(self.actions) - 1)

    def delete_action(self):
        a = self.action
        if a is None:
            return
        r = QMessageBox.question(self, "Aktion löschen?", f"Die Aktion „{a.name}“ löschen?")
        if r != QMessageBox.StandardButton.Yes:
            return
        i = self.combo.currentIndex()
        del self.actions[i]
        self._save()
        self._fill_combo(max(0, i - 1))

    def restore_examples(self):
        names = {a.name for a in self.actions}
        added = [a for a in A.default_actions() if a.name not in names]
        self.actions += added
        self._save()
        self._fill_combo(self.combo.currentIndex())
        self.win.toast.show_message(f"{len(added)} Beispiel-Aktion(en) wiederhergestellt" if added
                                    else "Alle Beispiel-Aktionen sind schon da")

    # --- Schritte ------------------------------------------------------------------------
    def add_step(self, kind: str, edit: bool = True):
        a = self.action
        if a is None:
            self.new_action("Meine Aktion")
            a = self.action
        step = A.new_step(kind)
        if edit and kind != "cleanup":
            d = StepDialog(step, self)
            if not d.exec():
                return
            step = d.step
        # Umbenennen bleibt am Ende
        if kind != "rename" and a.renames:
            a.steps.insert(len(a.steps) - 1, step)
            pos = len(a.steps) - 2
        else:
            a.steps.append(step)
            pos = len(a.steps) - 1
        self._changed(pos)

    def edit_step(self):
        a, r = self.action, self.steps.currentRow()
        if a is None or r < 0:
            return
        d = StepDialog(a.steps[r], self)
        if d.exec():
            a.steps[r] = d.step
            self._changed(r)

    def move_step(self, delta: int):
        a, r = self.action, self.steps.currentRow()
        if a is None or r < 0 or not 0 <= r + delta < len(a.steps):
            return
        a.steps[r], a.steps[r + delta] = a.steps[r + delta], a.steps[r]
        self._changed(r + delta)

    def remove_step(self):
        a, r = self.action, self.steps.currentRow()
        if a is None or r < 0:
            return
        del a.steps[r]
        self._changed(r)

    # --- Vorschau ---------------------------------------------------------------------------
    def compute(self) -> Preview:
        self._changes, self._pairs, self._renamed = [], [], 0
        a = self.action
        if a is None:
            return Preview(message="Noch keine Aktion – im Menü „…“ eine neue anlegen")
        err = A.validate(a)
        if err:
            return Preview(message=err)
        try:
            new_tags, notes = A.run_tag_steps([(it.path, it.tags) for it in self.items], a.steps)
        except A.ActionError as exc:
            return Preview(message=str(exc))
        diffs = [{k: v for k, v in nt.items() if it.tags.get(k, "") != v} for it, nt in zip(self.items, new_tags)]
        columns = [k for k in FIELD_KEYS if any(k in d for d in diffs)]
        rename = next((s for s in a.steps if s["type"] == "rename"), None)
        plans = None
        if rename:
            o = rename["opts"]
            plans = plan_renames([(it.path, nt) for it, nt in zip(self.items, new_tags)], o.get("pattern", ""),
                                 pad_track=int(o.get("pad", 2)), windows_safe=o.get("windows_safe", True),
                                 companions=o.get("companions", True))
        rows, problems = [], 0
        kind_of = {OK: CHANGED, SAME: UNCHANGED, MISSING: WARN, CONFLICT: ERROR, INVALID: ERROR}
        for i, (it, diff) in enumerate(zip(self.items, diffs)):
            cells = [(diff[k], it.tags.get(k, "")) if k in diff else (it.tags.get(k, ""), None) for k in columns]
            status, kind = [], UNCHANGED
            if diff:
                self._changes.append((it, diff))
                status.append(f"{len(diff)} Feld{'er' if len(diff) != 1 else ''}")
                kind = CHANGED
            if plans is not None:
                p = plans[i]
                new_name, old_name = os.path.basename(p.new), os.path.basename(p.old)
                cells.append((new_name if p.status in (OK, SAME, CONFLICT) else "",
                               old_name if p.status == OK else None))
                if p.status == OK:
                    status.append("umbenennen")
                    kind = CHANGED
                elif p.status != SAME:
                    status.append(p.note or STATUS_TEXT[p.status])
                    kind = kind_of[p.status] if kind == UNCHANGED else WARN
                    problems += 1
            for note in notes.get(i, []):
                status.append(note.split(": ", 1)[-1])
                kind = WARN if kind != ERROR else kind
            rows.append(PreviewRow(it.name, cells, " · ".join(status) or "unverändert", kind, it.path))
        if plans is not None:
            self._pairs = [pair for p in plans if p.will_rename for pair in p.all_pairs]
            self._renamed = sum(1 for p in plans if p.will_rename)
        col_labels = [FIELD_BY_KEY[k].label for k in columns] + (["Neuer Name"] if plans is not None else [])
        touched = {id(it) for it, _d in self._changes}
        if plans is not None:
            touched |= {id(self.items[i]) for i, p in enumerate(plans) if p.will_rename}
        n = len(touched)
        parts = [f"{len(self._changes):,} Dateien mit neuen Tags".replace(",", ".")]
        if plans is not None:
            verb = "wird" if self._renamed == 1 else "werden"
            parts.append(f"{self._renamed:,} {verb} umbenannt".replace(",", "."))
        if problems:
            parts.append(f"{problems} mit Hinweis")
        if notes:
            parts.append(f"{len(notes)} passen nicht zum Muster")
        self.foot_hint.setText("Benennt sofort um · Strg+Z nimmt alles zurück"
                               if plans is not None else
                               "Danach gelb markiert · Strg+S speichert · Strg+Z nimmt zurück")
        return Preview(col_labels, rows, "  ·  ".join(parts), n)


    def apply_changes(self):
        a = self.action
        label = f"Aktion „{a.name}“"
        n = self.session.apply_changes(self._changes, label) if self._changes else 0
        if self._pairs:
            self.win.run_rename(self._pairs, label, chain=n > 0)
        else:
            self.win.toast.show_message(f"{label}: {n} Datei(en) geändert – Strg+S speichert")

