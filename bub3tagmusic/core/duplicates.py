"""Duplikate finden (Phase 4) – reine Logik ohne Oberfläche.

Zwei Wege:
  * nach Tags: gleicher Interpret + gleicher Titel (Groß-/Kleinschreibung,
    Satzzeichen und Akzente egal) und Länge innerhalb weniger Sekunden
  * nach Klang: Audio-Fingerabdruck (fpcalc) – findet Duplikate auch, wenn
    die Tags verschieden oder leer sind

Es wird NIE etwas gelöscht. Die Oberfläche zeigt Gruppen; was weg soll,
entscheidet der Mensch.
"""

from __future__ import annotations

import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from array import array
from dataclasses import dataclass, field
from typing import Callable

from .fingerprint import FingerprintError, fingerprint, from_blob, similarity, to_blob

LOSSLESS = {"FLAC", "ALAC", "WAV", "AIFF", "APE", "WavPack", "WV", "DSF", "OggFLAC"}
SIMILAR = 0.93                     # ab hier gilt der Klang als gleich (Anteil gleicher Bits)
FP_KEEP = 300                      # so viele Teil-Abdrücke (≈ 40 s) reichen zum Vergleichen
MIN_SHARED = 3                     # so viele exakt gleiche Teil-Abdrücke machen ein Paar verdächtig


@dataclass
class Entry:
    path: str
    artist: str = ""
    title: str = ""
    album: str = ""
    length: float = 0.0
    bitrate: int = 0
    format: str = ""
    size: int = 0
    mtime: int = 0
    fp: array | None = None              # Anfang des Fingerabdrucks (spart Speicher)

    @classmethod
    def from_record(cls, rec: dict, tags: dict | None = None) -> "Entry":
        t = tags if tags is not None else (rec.get("tags") or {})
        return cls(rec["path"], t.get("artist", ""), t.get("title", ""), t.get("album", ""),
                   float(rec.get("length") or 0), int(rec.get("bitrate") or 0), rec.get("format", ""),
                   int(rec.get("size") or 0), int(rec.get("mtime") or 0))

    @property
    def lossless(self) -> bool:
        return self.format in LOSSLESS or os.path.splitext(self.path)[1].lower() in (
            ".flac", ".wav", ".aif", ".aiff", ".ape", ".wv", ".dsf")


@dataclass
class Group:
    members: list[int]                       # Indizes in entries
    reason: str = ""                         # "Tags" | "Klang"
    best: int = -1                           # Index der Datei mit der besten Qualität
    title: str = ""
    extra: dict = field(default_factory=dict)


_BRACKETS = re.compile(r"\s*[(\[][^)\]]*[)\]]")
_FEAT = re.compile(r"\s+(?:feat\.?|ft\.?|featuring)\s.*$", re.IGNORECASE)
_NONWORD = re.compile(r"[^\w]+")


def normalize(text: str, ignore_brackets: bool = False) -> str:
    """'Die Ärzte – Schrei nach Liebe!' → 'die arzte schrei nach liebe'."""
    t = (text or "").strip()
    if ignore_brackets:
        t = _BRACKETS.sub("", t)
        t = _FEAT.sub("", t)
    t = t.replace("&", " and ").replace("+", " and ")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = _NONWORD.sub(" ", t.casefold()).replace("_", " ")
    return " ".join(t.split())


def quality_key(e: Entry) -> tuple:
    """Größer = besser: verlustfrei vor verlustbehaftet, dann Bitrate, dann Dateigröße."""
    return (1 if e.lossless else 0, e.bitrate, e.size)


def _split_by_length(idx: list[int], entries: list[Entry], tolerance: float) -> list[list[int]]:
    """Gleiche Tags, aber sehr verschiedene Länge (z. B. Single- und Live-Fassung) = keine Duplikate."""
    if tolerance <= 0:
        return [idx] if len(idx) > 1 else []
    idx = sorted(idx, key=lambda i: entries[i].length)
    out, cur = [], [idx[0]]
    for i in idx[1:]:
        if entries[i].length - entries[cur[-1]].length <= tolerance:
            cur.append(i)
        else:
            out.append(cur)
            cur = [i]
    out.append(cur)
    return [g for g in out if len(g) > 1]


def by_tags(entries: list[Entry], tolerance: float = 2.0, ignore_brackets: bool = False) -> tuple[list[Group], int]:
    """→ (Gruppen, Anzahl Dateien ohne Interpret/Titel, die nicht verglichen werden konnten)."""
    buckets: dict[tuple[str, str], list[int]] = {}
    skipped = 0
    for i, e in enumerate(entries):
        a, t = normalize(e.artist, ignore_brackets), normalize(e.title, ignore_brackets)
        if not a or not t:
            skipped += 1
            continue
        buckets.setdefault((a, t), []).append(i)
    groups = []
    for (_a, _t), idx in buckets.items():
        if len(idx) < 2:
            continue
        for g in _split_by_length(idx, entries, tolerance):
            first = entries[g[0]]
            groups.append(Group(g, "Tags", title=f"{first.artist} – {first.title}"))
    return _finish(groups, entries), skipped


def by_sound(entries: list[Entry], tolerance: float = 2.0, threshold: float = SIMILAR) -> list[Group]:
    """Nur Einträge mit Fingerabdruck (e.fp) werden verglichen.

    Statt jede Datei mit jeder zu vergleichen (bei 50.000 Dateien unmöglich), kommen nur
    Paare in Frage, die mehrere exakt gleiche Teil-Abdrücke haben (Index wie bei AcoustID)
    und ähnlich lang sind. Erst die werden genau verglichen.
    """
    have = [i for i, e in enumerate(entries) if e.fp]
    index: dict[int, list[int]] = {}
    for i in have:
        for v in set(entries[i].fp[:FP_KEEP]):
            index.setdefault(v, []).append(i)
    shared: dict[tuple[int, int], int] = {}
    for ids in index.values():
        if len(ids) < 2 or len(ids) > 200:        # sehr häufige Werte (Stille …) sagen nichts aus
            continue
        for n, a in enumerate(ids):
            for b in ids[n + 1:]:
                key = (a, b) if a < b else (b, a)
                shared[key] = shared.get(key, 0) + 1

    parent = {i: i for i in have}

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    best_sim: dict[int, float] = {}
    max_diff = max(tolerance, 0.5)
    for (a, b), count in shared.items():
        if count < MIN_SHARED or abs(entries[a].length - entries[b].length) > max_diff:
            continue
        sim = similarity(entries[a].fp, entries[b].fp)
        if sim >= threshold:
            parent[root(b)] = root(a)
            best_sim[a] = max(best_sim.get(a, 0), sim)
            best_sim[b] = max(best_sim.get(b, 0), sim)
    clusters: dict[int, list[int]] = {}
    for i in have:
        clusters.setdefault(root(i), []).append(i)
    groups = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        named = next((entries[i] for i in members if entries[i].title), entries[members[0]])
        title = f"{named.artist} – {named.title}" if named.title else os.path.basename(named.path)
        sim = min(best_sim.get(i, 1.0) for i in members)
        groups.append(Group(sorted(members), "Klang", title=title, extra={"similarity": sim}))
    return _finish(groups, entries)


def _finish(groups: list[Group], entries: list[Entry]) -> list[Group]:
    for g in groups:
        g.best = max(g.members, key=lambda i: quality_key(entries[i]))
        g.members.sort(key=lambda i: (i != g.best, entries[i].path))
    groups.sort(key=lambda g: (normalize(g.title), g.members[0]))
    return groups


def merge(a: list[Group], b: list[Group], entries: list[Entry]) -> list[Group]:
    """Tags- und Klang-Gruppen zusammenführen (eine Datei landet nur in einer Gruppe)."""
    out = list(a)
    seen = {i for g in a for i in g.members}
    for g in b:
        rest = [i for i in g.members if i not in seen]
        overlap = [x for x in out if set(x.members) & set(g.members)]
        if overlap:
            target = overlap[0]
            target.members += rest
            target.reason = "Tags + Klang"
            seen.update(rest)
        elif len(rest) > 1:
            out.append(Group(rest, g.reason, title=g.title, extra=g.extra))
            seen.update(rest)
    return _finish(out, entries)


def fingerprints_for(entries: list[Entry], cache=None, progress: Callable[[int, int], None] = lambda d, t: None,
                     cancelled: Callable[[], bool] = lambda: False, workers: int = 0) -> dict[str, str]:
    """Füllt e.fp (aus dem Zwischenspeicher oder per fpcalc). Rückgabe: {pfad: fehlermeldung}."""
    errors: dict[str, str] = {}
    stats = {e.path: (e.mtime, e.size) for e in entries}
    known = cache.get_fingerprints(stats) if cache is not None else {}
    todo = []
    for e in entries:
        if e.path in known:
            e.fp = array("I", from_blob(known[e.path][1])[:FP_KEEP])
        else:
            todo.append(e)
    total, done = len(entries), len(entries) - len(todo)
    progress(done, total)
    fresh = []

    def work(e: Entry):
        if cancelled():
            return e, None, "abgebrochen"
        try:
            dur, fp = fingerprint(e.path)
            return e, (dur, fp), ""
        except FingerprintError as exc:
            return e, None, str(exc)

    workers = workers or max(1, min(4, os.cpu_count() or 2))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for e, res, err in pool.map(work, todo):
            done += 1
            if res is not None:
                e.fp = array("I", res[1][:FP_KEEP])
                if e.mtime:
                    fresh.append((e.path, e.mtime, e.size, res[0], to_blob(res[1])))
            elif err != "abgebrochen":
                errors[e.path] = err
            if done % 5 == 0 or done == total:
                progress(done, total)
            if cache is not None and len(fresh) >= 50:
                cache.put_fingerprints(fresh)
                fresh = []
    if cache is not None:
        cache.put_fingerprints(fresh)
    return errors
