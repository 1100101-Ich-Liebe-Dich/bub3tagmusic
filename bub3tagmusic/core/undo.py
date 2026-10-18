"""Rückgängig-Verlauf.

Zwei Arten von Schritten liegen im selben Stapel:

* EditStep – eine Bearbeitung im Speicher (noch nicht gespeichert).
             Rückgängig stellt einfach die alten Werte in der Liste her.
* SaveStep – ein Speichervorgang. Vorher wurden die alten Werte und ggf.
             das alte Cover jeder Datei gemerkt. Rückgängig schreibt diese
             alten Werte zurück auf die Festplatte.
* RenameStep – Dateien umbenannt. Rückgängig benennt zurück.

Beim Speichern fallen alle EditSteps weg (sie sind ja jetzt Teil des SaveSteps).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .covers import CoverData


@dataclass
class EditStep:
    label: str
    # (FileItem, snapshot vor der Änderung)
    entries: list = field(default_factory=list)


@dataclass
class SaveEntry:
    path: str
    old_values: dict[str, str]          # nur Felder, die geändert wurden
    cover_changed: bool = False
    old_cover: CoverData | None = None  # None = vorher kein Cover


@dataclass
class SaveStep:
    label: str
    entries: list[SaveEntry] = field(default_factory=list)


@dataclass
class RenameStep:
    label: str
    pairs: list[tuple[str, str]] = field(default_factory=list)   # (alt, neu)


DISK_STEPS = (SaveStep, RenameStep)


class UndoStack:
    MAX_SAVES = 20     # so viele Speichervorgänge bleiben rückgängig machbar
    MAX_EDITS = 200

    def __init__(self):
        self._steps: list = []

    def push_edit(self, step: EditStep) -> None:
        if step.entries:
            self._steps.append(step)
            self._trim()

    def push_save(self, step: SaveStep) -> None:
        # Alle Bearbeitungen sind jetzt gespeichert und damit Teil des SaveSteps
        self.drop_edits()
        if step.entries:
            self._steps.append(step)
            self._trim()

    def push_rename(self, step: RenameStep) -> None:
        if step.pairs:
            self._steps.append(step)
            self._trim()

    def drop_edits(self) -> None:
        """z. B. beim Ordnerwechsel ohne Speichern."""
        self._steps = [s for s in self._steps if isinstance(s, DISK_STEPS)]

    def pop(self):
        return self._steps.pop() if self._steps else None

    def peek(self):
        return self._steps[-1] if self._steps else None

    def __len__(self) -> int:
        return len(self._steps)

    def _trim(self) -> None:
        saves = [i for i, s in enumerate(self._steps) if isinstance(s, DISK_STEPS)]
        while len(saves) > self.MAX_SAVES:
            del self._steps[saves.pop(0)]
            saves = [i for i, s in enumerate(self._steps) if isinstance(s, DISK_STEPS)]
        edits = [i for i, s in enumerate(self._steps) if isinstance(s, EditStep)]
        while len(edits) > self.MAX_EDITS:
            del self._steps[edits.pop(0)]
            edits = [i for i, s in enumerate(self._steps) if isinstance(s, EditStep)]
