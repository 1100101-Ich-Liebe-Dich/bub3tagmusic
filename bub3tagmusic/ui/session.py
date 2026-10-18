"""Die geladenen Dateien und alle Bearbeitungen daran.

Liste, Bearbeitungsfeld und Werkzeuge ändern Dateien ausschließlich über
diese Klasse. So landet jede Änderung automatisch im Rückgängig-Verlauf und
alle Ansichten werden benachrichtigt.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..core.covers import CoverData
from ..core.fields import FIELD_BY_KEY
from ..core.model import FileItem
from ..core.tags import COVER_KEEP, COVER_REMOVE
from ..core.undo import EditStep, RenameStep, SaveStep, UndoStack
from .workers import SaveJob


class Session(QObject):
    itemsReplaced = Signal()          # neue Liste geladen
    itemsChanged = Signal(list)       # diese Einträge haben sich geändert
    stateChanged = Signal()           # Anzahl geändert / Rückgängig verfügbar

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[FileItem] = []
        self.undo = UndoStack()

    # --- Laden -------------------------------------------------------------
    def set_records(self, recs: list[dict]) -> None:
        self.items = [FileItem(r) for r in recs]
        self.undo.drop_edits()
        self.itemsReplaced.emit()
        self.stateChanged.emit()

    def clear(self) -> None:
        self.set_records([])

    # --- Abfragen ----------------------------------------------------------
    def modified_items(self) -> list[FileItem]:
        return [it for it in self.items if it.is_modified()]

    def modified_count(self) -> int:
        return sum(1 for it in self.items if it.is_modified())

    def dirs(self) -> list[str]:
        seen, out = set(), []
        for it in self.items:
            if it.dir not in seen:
                seen.add(it.dir)
                out.append(it.dir)
        return out

    # --- Bearbeiten ----------------------------------------------------------
    def apply_fields(self, items: list[FileItem], changes: dict[str, str], label: str = "") -> int:
        changes = {k: v for k, v in changes.items() if k in FIELD_BY_KEY}
        step = EditStep(label or self._label(changes, items))
        touched = []
        for it in items:
            if any(it.tags.get(k, "") != v for k, v in changes.items()):
                step.entries.append((it, it.snapshot()))
                it.tags.update(changes)
                touched.append(it)
        if touched:
            self.undo.push_edit(step)
            self.itemsChanged.emit(touched)
            self.stateChanged.emit()
        return len(touched)

    def apply_changes(self, changes: list[tuple[FileItem, dict[str, str]]], label: str, cover=None) -> int:
        """Unterschiedliche Änderungen je Datei – als EIN Rückgängig-Schritt (Werkzeuge, Online).

        cover: optional CoverData, das alle genannten Dateien zusätzlich bekommen.
        """
        step = EditStep(label)
        touched = []
        for it, ch in changes:
            ch = {k: v for k, v in ch.items() if k in FIELD_BY_KEY and it.tags.get(k, "") != v}
            if not ch and cover is None:
                continue
            step.entries.append((it, it.snapshot()))
            it.tags.update(ch)
            if cover is not None:
                it.cover_action = cover
            touched.append(it)
        if touched:
            self.undo.push_edit(step)
            self.itemsChanged.emit(touched)
            self.stateChanged.emit()
        return len(touched)

    def apply_cover(self, items: list[FileItem], action, label: str = "") -> int:
        """action: CoverData (neu setzen) oder COVER_REMOVE."""
        step = EditStep(label or ("Cover entfernt" if action == COVER_REMOVE else "Cover gesetzt"))
        touched = []
        for it in items:
            if action == COVER_REMOVE and not it.has_cover():
                continue
            step.entries.append((it, it.snapshot()))
            it.cover_action = action
            # Entfernen eines nur vorgemerkten Covers = einfach zurücknehmen
            if action == COVER_REMOVE and not it.rec.get("cover"):
                it.cover_action = COVER_KEEP
            touched.append(it)
        if touched:
            self.undo.push_edit(step)
            self.itemsChanged.emit(touched)
            self.stateChanged.emit()
        return len(touched)

    def revert(self, items: list[FileItem] | None = None) -> None:
        items = [it for it in (items or self.items) if it.is_modified()]
        if not items:
            return
        step = EditStep("Änderungen verworfen", [(it, it.snapshot()) for it in items])
        for it in items:
            it.revert()
        self.undo.push_edit(step)
        self.itemsChanged.emit(items)
        self.stateChanged.emit()

    def undo_edit(self, step: EditStep) -> None:
        items = []
        for it, snap in reversed(step.entries):
            it.restore(snap)
            items.append(it)
        self.itemsChanged.emit(items)
        self.stateChanged.emit()

    # --- Speichern ---------------------------------------------------------------
    def save_jobs(self, items: list[FileItem] | None = None) -> list[SaveJob]:
        jobs = []
        for it in (items if items is not None else self.items):
            if not it.is_modified():
                continue
            changes = it.changed_fields()
            old = {k: it.orig.get(k, "") for k in changes}
            jobs.append(SaveJob(it.path, changes, it.cover_action, old))
        return jobs

    def finish_save(self, results: list[dict], label: str, record_undo: bool = True) -> tuple[int, list]:
        by_path = {it.path: it for it in self.items}
        ok, errors, changed = 0, [], []
        step = SaveStep(label)
        for res in results:
            it = by_path.get(res["path"])
            if res["error"]:
                errors.append((res["path"], res["error"]))
                continue
            ok += 1
            if res.get("entry") is not None:
                step.entries.append(res["entry"])
            if it is not None and res["rec"] is not None:
                it.apply_saved(res["rec"])
                changed.append(it)
        if record_undo:
            self.undo.push_save(step)
        if changed:
            self.itemsChanged.emit(changed)
        self.stateChanged.emit()
        return ok, errors

    def finish_rename(self, results: list[dict], label: str, record_undo: bool = True) -> tuple[int, list]:
        import os
        by_path = {it.path: it for it in self.items}
        done, errors, changed = [], [], []
        for r in results:
            if r["error"]:
                errors.append((r["old"], r["error"]))
                continue
            done.append((r["old"], r["new"]))
            it = by_path.get(r["old"])
            if it is not None:
                it.set_path(r["new"])
                changed.append(it)
            elif os.path.isdir(r["new"]):
                # Ordner umbenannt: alle Dateien darin bekommen den neuen Pfad
                prefix = r["old"].rstrip("/") + "/"
                for item in self.items:
                    if item.path.startswith(prefix):
                        item.set_path(r["new"].rstrip("/") + "/" + item.path[len(prefix):])
                        changed.append(item)
        if record_undo and done:
            self.undo.push_rename(RenameStep(label, done))
        if changed:
            self.itemsChanged.emit(changed)
        self.stateChanged.emit()
        return len(done), errors

    @staticmethod
    def undo_jobs(step: SaveStep) -> list[SaveJob]:
        jobs = []
        for e in step.entries:
            cover = COVER_KEEP
            if e.cover_changed:
                cover = e.old_cover if isinstance(e.old_cover, CoverData) else COVER_REMOVE
            jobs.append(SaveJob(e.path, dict(e.old_values), cover))
        return jobs

    # --- Hilfen ------------------------------------------------------------------
    @staticmethod
    def _label(changes: dict, items: list) -> str:
        names = ", ".join(FIELD_BY_KEY[k].label for k in changes)
        n = len(items)
        return f"{names} geändert ({n} Datei{'en' if n != 1 else ''})"
