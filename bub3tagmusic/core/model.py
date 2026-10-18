"""Eine geladene Musikdatei mit ihrem Bearbeitungsstand."""

from __future__ import annotations

import os

from .covers import CoverData
from .fields import FIELD_KEYS
from .tags import COVER_KEEP, COVER_REMOVE


class FileItem:
    """Hält Original-Tags (wie auf der Platte) und den aktuellen Bearbeitungsstand.

    tags          – aktuelle Werte (was in der Liste angezeigt wird)
    orig          – Werte auf der Festplatte
    cover_action  – COVER_KEEP (None), COVER_REMOVE oder CoverData
    """

    __slots__ = ("path", "rec", "orig", "tags", "cover_action", "_dir", "_name")

    def __init__(self, rec: dict):
        self.path = rec["path"]
        self._dir = os.path.dirname(self.path)
        self._name = os.path.basename(self.path)
        self.rec = rec
        self.orig = dict(rec.get("tags") or dict.fromkeys(FIELD_KEYS, ""))
        self.tags = dict(self.orig)
        self.cover_action = COVER_KEEP

    def set_path(self, new: str) -> None:
        """Nach dem Umbenennen."""
        self.path = new
        self._dir = os.path.dirname(new)
        self._name = os.path.basename(new)
        self.rec = dict(self.rec, path=new)

    # --- Bequemlichkeit ---------------------------------------------------
    @property
    def dir(self) -> str:
        return self._dir

    @property
    def name(self) -> str:
        return self._name

    @property
    def error(self) -> str:
        return self.rec.get("error", "")

    # --- Änderungen --------------------------------------------------------
    def changed_fields(self) -> dict[str, str]:
        return {k: v for k, v in self.tags.items() if v != self.orig.get(k, "")}

    def is_modified(self) -> bool:
        if self.cover_action is not COVER_KEEP:
            return True
        if self.tags == self.orig:          # der häufigste Fall – Vergleich in C, sehr schnell
            return False
        return any(v != self.orig.get(k, "") for k, v in self.tags.items())

    def is_field_modified(self, key: str) -> bool:
        return self.tags.get(key, "") != self.orig.get(key, "")

    def snapshot(self):
        """Für Rückgängig (ungespeicherte Bearbeitung)."""
        return dict(self.tags), self.cover_action

    def restore(self, snap) -> None:
        self.tags, self.cover_action = dict(snap[0]), snap[1]

    def revert(self) -> None:
        self.tags = dict(self.orig)
        self.cover_action = COVER_KEEP

    def apply_saved(self, rec: dict) -> None:
        """Nach erfolgreichem Speichern: neuer Stand von der Platte."""
        self.rec = rec
        self.orig = dict(rec.get("tags") or {})
        self.tags = dict(self.orig)
        self.cover_action = COVER_KEEP

    # --- Cover -------------------------------------------------------------
    def cover_state(self) -> tuple[str, str | None]:
        """('none'|'disk'|'new'|'removed', vergleichs-schlüssel)"""
        if isinstance(self.cover_action, CoverData):
            return "new", "new:" + str(id(self.cover_action))
        if self.cover_action == COVER_REMOVE:
            return "removed", None
        cov = self.rec.get("cover")
        if cov:
            return "disk", "disk:" + cov["hash"]
        return "none", None

    def has_cover(self) -> bool:
        return self.cover_state()[0] in ("disk", "new")
