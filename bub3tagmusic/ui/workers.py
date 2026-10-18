"""Hintergrund-Arbeiter: Ordnerbaum scannen, Dateien laden, Dateien speichern.

Die Oberfläche bleibt dadurch immer bedienbar. Jeder Auftrag bekommt eine
Nummer (token); veraltete Ergebnisse (z. B. wenn schon ein anderer Ordner
angeklickt wurde) werden verworfen.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ..core.cache import Cache
from ..core.scanner import list_audio, load_records, scan_tree
from ..core.rename import execute_renames
from ..core.tags import COVER_KEEP, TagWriteError, read_cover, write_file
from ..core.undo import SaveEntry


class TreeScanWorker(QThread):
    done = Signal(object, int)

    def __init__(self, root: str, token: int, parent=None):
        super().__init__(parent)
        self.root, self.token = root, token
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        node = scan_tree(self.root, lambda: self._cancel)
        if not self._cancel:
            self.done.emit(node, self.token)


class LoadWorker(QThread):
    progress = Signal(int, int, int)      # erledigt, gesamt, token
    done = Signal(list, int)              # records, token

    def __init__(self, dirs: list[str], recursive: bool, cache: Cache, token: int, parent=None):
        super().__init__(parent)
        self.dirs, self.recursive, self.cache, self.token = dirs, recursive, cache, token
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        paths = list_audio(self.dirs, self.recursive)
        if self._cancel:
            return
        recs = load_records(
            paths, self.cache,
            progress=lambda d, t: self.progress.emit(d, t, self.token),
            should_cancel=lambda: self._cancel,
        )
        if not self._cancel:
            self.done.emit(recs, self.token)


class SaveJob:
    __slots__ = ("path", "changes", "cover", "old_values")

    def __init__(self, path, changes, cover=COVER_KEEP, old_values=None):
        self.path, self.changes, self.cover = path, changes, cover
        self.old_values = old_values or {}


class SaveWorker(QThread):
    progress = Signal(int, int)
    done = Signal(list)   # [{path, rec, error, entry}]

    def __init__(self, jobs: list[SaveJob], opts: dict, cache: Cache, capture_undo: bool = True, parent=None):
        super().__init__(parent)
        self.jobs, self.opts, self.cache, self.capture_undo = jobs, opts, cache, capture_undo

    def run(self):
        results, fresh = [], []
        total = len(self.jobs)
        for i, job in enumerate(self.jobs, 1):
            res = {"path": job.path, "rec": None, "error": "", "entry": None}
            try:
                old_cover = None
                cover_changed = job.cover is not COVER_KEEP
                if self.capture_undo and cover_changed:
                    old_cover = read_cover(job.path)
                rec = write_file(job.path, job.changes, job.cover, self.opts)
                if rec.get("error"):
                    raise TagWriteError(rec["error"])
                res["rec"] = rec
                fresh.append(rec)
                if self.capture_undo:
                    res["entry"] = SaveEntry(job.path, dict(job.old_values), cover_changed, old_cover)
            except TagWriteError as exc:
                res["error"] = str(exc)
            except Exception as exc:  # eine kaputte Datei stoppt nie den Rest
                res["error"] = f"Unerwarteter Fehler: {exc}"
            results.append(res)
            if i % 5 == 0 or i == total:
                self.progress.emit(i, total)
        if fresh:
            try:
                self.cache.put_many(fresh)
            except Exception:
                pass
        self.done.emit(results)


class RenameWorker(QThread):
    done = Signal(list)   # [{old, new, error}]

    def __init__(self, pairs: list[tuple[str, str]], cache: Cache, parent=None):
        super().__init__(parent)
        self.pairs, self.cache = pairs, cache

    def run(self):
        results = execute_renames(self.pairs)
        ok = [(r["old"], r["new"]) for r in results if not r["error"]]
        if ok:
            try:
                self.cache.rename_paths(ok)
            except Exception:
                pass
        self.done.emit(results)
