"""Hintergrund-Arbeiter: Ordnerbaum scannen, Dateien laden, Dateien speichern.

Die Oberfläche bleibt dadurch immer bedienbar. Jeder Auftrag bekommt eine
Nummer (token); veraltete Ergebnisse (z. B. wenn schon ein anderer Ordner
angeklickt wurde) werden verworfen.
"""

from __future__ import annotations

import os

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

    def __init__(self, dirs: list[str], recursive: bool, cache: Cache, token: int, parent=None, keep=None,
                 files: list[str] | None = None):
        super().__init__(parent)
        self.dirs, self.recursive, self.cache, self.token = dirs, recursive, cache, token
        self.files = files            # feste Dateiliste statt Ordner (z. B. Duplikate in der Liste zeigen)
        self.keep = keep              # optional: nur passende Datensätze behalten (Suche in der Sammlung)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        paths = [p for p in self.files if os.path.exists(p)] if self.files is not None else \
            list_audio(self.dirs, self.recursive)
        if self._cancel:
            return
        recs = load_records(
            paths, self.cache,
            progress=lambda d, t: self.progress.emit(d, t, self.token),
            should_cancel=lambda: self._cancel,
        )
        if self.keep is not None:
            recs = [r for r in recs if self.keep(r)]
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
        import os
        results = execute_renames(self.pairs)
        ok = [(r["old"], r["new"]) for r in results if not r["error"]]
        try:
            files = [(o, n) for o, n in ok if not os.path.isdir(n)]
            if files:
                self.cache.rename_paths(files)
            for o, n in ok:
                if os.path.isdir(n):
                    self.cache.rename_folder(o, n)
        except Exception:
            pass
        self.done.emit(results)


class Job(QThread):
    """Führt eine Funktion im Hintergrund aus (z. B. eine Online-Abfrage)."""

    done = Signal(object)
    failed = Signal(str)
    _running: set = set()          # hält laufende Jobs am Leben, auch wenn der Dialog schon zu ist

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args
        Job._running.add(self)
        self.finished.connect(lambda: Job._running.discard(self))

    def run(self):
        try:
            result = self.fn(*self.args)
        except Exception as exc:       # Online-Fehler sind verständlich formuliert, alles andere kurz melden
            from ..online.base import OnlineError
            self.failed.emit(str(exc) if isinstance(exc, OnlineError) else f"Unerwarteter Fehler: {exc}")
            return
        self.done.emit(result)


class ImageLoader(QThread):
    """Lädt viele kleine Vorschaubilder (bis zu 4 gleichzeitig) und meldet jedes einzeln."""

    loaded = Signal(int, bytes)

    def __init__(self, jobs: list[tuple[int, str]]):
        super().__init__()
        self.jobs = jobs
        self._stop = False
        Job._running.add(self)
        self.finished.connect(lambda: Job._running.discard(self))

    def stop(self):
        self._stop = True

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from ..online.http import get_image

        def load(job):
            idx, url = job
            if self._stop:
                return idx, b""
            try:
                return idx, get_image(url)
            except Exception:
                return idx, b""

        with ThreadPoolExecutor(max_workers=4) as pool:
            for fut in as_completed([pool.submit(load, j) for j in self.jobs]):
                idx, data = fut.result()
                if self._stop:
                    break
                if data:
                    self.loaded.emit(idx, data)


class Task(QThread):
    """Längere Arbeit mit Fortschritt und Abbrechen (Fingerabdrücke, ReplayGain, Erkennen …).

    fn(*args, progress=..., cancelled=...) – progress(erledigt, gesamt, text="").
    """

    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args
        self._cancel = False
        Job._running.add(self)
        self.finished.connect(lambda: Job._running.discard(self))

    def cancel(self):
        self._cancel = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancel

    def run(self):
        try:
            result = self.fn(*self.args,
                             progress=lambda d, t, text="": self.progress.emit(int(d), int(t), str(text)),
                             cancelled=lambda: self._cancel)
        except Exception as exc:
            from ..online.base import OnlineError
            self.failed.emit(str(exc) if isinstance(exc, OnlineError) else f"Unerwarteter Fehler: {exc}")
            return
        self.done.emit(result)
