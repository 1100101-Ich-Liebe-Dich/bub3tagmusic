"""Ordner durchsuchen und Dateien einlesen – schnell und im Hintergrund.

* scan_tree():     nur Ordnernamen + Anzahl Musikdateien (keine Tags).
                   Läuft auch bei großen Sammlungen in Sekunden.
* list_audio():    Musikdateien eines oder mehrerer Ordner, optional rekursiv.
* load_records():  Tags lesen. Aus dem Cache, wenn die Datei unverändert ist;
                   viele neue Dateien werden auf mehrere CPU-Kerne verteilt.
"""

from __future__ import annotations

import multiprocessing
import os
import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from .cache import Cache
from .tags import AUDIO_EXTENSIONS, read_file

_num_re = re.compile(r"(\d+)")


def natural_key(text: str):
    """'Track 2' vor 'Track 10', Groß-/Kleinschreibung egal."""
    return [int(part) if part.isdigit() else part.casefold() for part in _num_re.split(text)]


@dataclass
class FolderNode:
    path: str
    name: str
    audio_count: int = 0          # Musikdateien direkt in diesem Ordner
    total_count: int = 0          # inkl. aller Unterordner
    children: list["FolderNode"] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def scan_tree(root: str, should_cancel: Callable[[], bool] = lambda: False) -> FolderNode:
    root = os.path.abspath(root)
    node = FolderNode(root, os.path.basename(root) or root)
    _scan_into(node, should_cancel, depth=0)
    return node


def _scan_into(node: FolderNode, should_cancel, depth: int) -> None:
    if should_cancel() or depth > 40:
        return
    try:
        entries = list(os.scandir(node.path))
    except OSError:
        return
    subdirs = []
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False):
                if not e.name.startswith("."):
                    subdirs.append(e)
            elif os.path.splitext(e.name)[1].lower() in AUDIO_EXTENSIONS:
                node.audio_count += 1
        except OSError:
            continue
    subdirs.sort(key=lambda e: natural_key(e.name))
    total = node.audio_count
    for e in subdirs:
        child = FolderNode(e.path, e.name)
        _scan_into(child, should_cancel, depth + 1)
        if child.total_count:            # leere Ordner ausblenden
            node.children.append(child)
            total += child.total_count
    node.total_count = total


def list_audio(dirs: list[str], recursive: bool) -> list[str]:
    """Alle Musikdateien – sortiert nach Ordner, dann natürlich nach Name."""
    seen, out = set(), []

    def add_dir(d: str):
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        files, subdirs = [], []
        for e in entries:
            try:
                if e.is_file() and os.path.splitext(e.name)[1].lower() in AUDIO_EXTENSIONS:
                    files.append(e.path)
                elif recursive and e.is_dir(follow_symlinks=False) and not e.name.startswith("."):
                    subdirs.append(e.path)
            except OSError:
                continue
        for p in sorted(files, key=lambda p: natural_key(os.path.basename(p))):
            if p not in seen:
                seen.add(p)
                out.append(p)
        for sd in sorted(subdirs, key=lambda p: natural_key(os.path.basename(p))):
            add_dir(sd)

    for d in dirs:
        add_dir(d)
    return out


# Ab so vielen neuen Dateien lohnt sich das Verteilen auf mehrere Kerne
PARALLEL_THRESHOLD = 150


def load_records(
    paths: list[str],
    cache: Cache | None,
    progress: Callable[[int, int], None] = lambda done, total: None,
    should_cancel: Callable[[], bool] = lambda: False,
    workers: int | None = None,
) -> list[dict]:
    total = len(paths)
    stats: dict[str, tuple[int, int]] = {}
    for p in paths:
        try:
            st = os.stat(p)
            stats[p] = (st.st_mtime_ns, st.st_size)
        except OSError:
            stats[p] = (0, 0)

    cached = cache.get_many(stats) if cache else {}
    results: dict[str, dict] = dict(cached)
    todo = [p for p in paths if p not in cached]
    done = len(cached)
    progress(done, total)

    fresh: list[dict] = []
    workers = workers or max(1, min(4, (os.cpu_count() or 2)))

    def collect(rec: dict):
        nonlocal done
        results[rec["path"]] = rec
        fresh.append(rec)
        done += 1
        if done % 25 == 0 or done == total:
            progress(done, total)
        if cache and len(fresh) >= 500:
            cache.put_many(fresh)
            fresh.clear()

    if len(todo) >= PARALLEL_THRESHOLD and workers > 1:
        try:
            ctx = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
                for rec in pool.map(read_file, todo, chunksize=16):
                    collect(rec)
                    if should_cancel():
                        pool.shutdown(cancel_futures=True)
                        break
        except Exception:
            # Fallback: einfach nacheinander lesen
            for p in todo:
                if p in results:
                    continue
                if should_cancel():
                    break
                collect(read_file(p))
    else:
        for p in todo:
            if should_cancel():
                break
            collect(read_file(p))

    if cache and fresh:
        cache.put_many(fresh)
    progress(min(done, total), total)
    return [results[p] for p in paths if p in results]
