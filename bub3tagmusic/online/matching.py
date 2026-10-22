"""Eigene Dateien den Tracks eines gefundenen Albums zuordnen.

Modi:
  * "title":  über den Titel (Tag) bzw. den Dateinamen – Zusätze wie „(feat. …)“, „[Live]“, Tracknummern
              vorne im Dateinamen oder der Interpret im Dateinamen stören nicht (1.1.5)
  * "number": über Disc + Tracknummer aus den Tags
  * "order":  in der Reihenfolge der Liste (z. B. nach Dateiname sortiert)
  * "length": über die Spiellänge (nächstliegende zuerst)
  * "auto":   Titel, wenn die meisten Dateien sicher erkannt werden – sonst Tracknummern, Reihenfolge, Länge
"""

from __future__ import annotations

import difflib
import math
import os
import re
from dataclasses import dataclass

from ..core.fields import split_number
from .base import AlbumMatch, normalize, strip_edition

LENGTH_TOLERANCE = 7.0      # Sekunden, ab denen die Länge als „weicht ab“ gilt

MODES = {"auto": "Automatisch", "title": "Nach Titel / Dateiname", "number": "Nach Tracknummer",
         "order": "Nach Reihenfolge der Liste", "length": "Nach Länge"}

TITLE_MIN = 0.6        # darunter gilt ein Titel nicht als erkannt
TITLE_SURE = 0.8       # ab hier sicher – darunter zeigt die Vorschau „Titel nur ähnlich“
TITLE_SHARE = 0.6      # „auto“ nimmt Titel, wenn mindestens so viele Dateien sicher erkannt sind


@dataclass
class FileInfo:
    track: str = ""
    disc: str = ""
    length: float = 0.0
    title: str = ""          # Titel-Tag
    name: str = ""           # Dateiname


@dataclass
class Assignment:
    track_index: int | None          # Index in album.tracks, None = kein Treffer
    length_diff: float | None = None  # Sekunden Unterschied (wenn beide Längen bekannt)
    title_score: float | None = None  # 0–1 bei Zuordnung über den Titel

    @property
    def length_ok(self) -> bool:
        return self.length_diff is None or self.length_diff <= LENGTH_TOLERANCE


def _num(value: str) -> int | None:
    n, _ = split_number(value or "")
    digits = "".join(ch for ch in n if ch.isdigit())
    return int(digits) if digits else None


def _by_number(files: list[FileInfo], album: AlbumMatch) -> list[int | None] | None:
    index = {(t.disc, t.position): i for i, t in enumerate(album.tracks)}
    multi = album.disc_total > 1
    out, used = [], set()
    for f in files:
        track = _num(f.track)
        disc = _num(f.disc) or 1
        if track is None:
            return None
        key = (disc if multi else 1, track)
        if key not in index and not multi:
            key = (1, track)
        i = index.get(key)
        if i is None or i in used:
            return None
        used.add(i)
        out.append(i)
    return out


def _by_order(files: list[FileInfo], album: AlbumMatch) -> list[int | None]:
    return [i if i < len(album.tracks) else None for i in range(len(files))]


def _by_length(files: list[FileInfo], album: AlbumMatch) -> list[int | None]:
    pairs = []
    for fi, f in enumerate(files):
        for ti, t in enumerate(album.tracks):
            if f.length and t.length:
                pairs.append((abs(f.length - t.length), fi, ti))
    pairs.sort()
    out: list[int | None] = [None] * len(files)
    used_f, used_t = set(), set()
    for _d, fi, ti in pairs:
        if fi in used_f or ti in used_t:
            continue
        out[fi] = ti
        used_f.add(fi)
        used_t.add(ti)
    return out


# ----------------------------------------------------------------------
# Zuordnung über Titel / Dateiname
# ----------------------------------------------------------------------
_FEAT = re.compile(r"\s+(?:feat\.?|ft\.?|featuring)\s.*$", re.IGNORECASE)
_LEAD_NUMBER = re.compile(r"^(?:(?:cd|disc|disk)\s*\d+\s+)?(?:\d{1,3}\s+){1,2}")


def title_words(text: str, filename: bool = False) -> list[str]:
    """'Hells Bells (feat. X) [Live]' → ['hells', 'bells']. Bei Dateinamen auch Endung und Nummern vorne weg."""
    text = text or ""
    if filename:
        text = os.path.splitext(text)[0].replace("_", " ")
    text = _FEAT.sub("", re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text))
    key = normalize(text)
    if filename:
        key = _LEAD_NUMBER.sub("", key + " ").strip()
    return key.split()


_NAME_DISC_TRACK = re.compile(r"^\s*(?:(?:cd|disc|disk)\s*)?(\d)\s*[-.]\s*(\d{1,2})(?!\d)", re.IGNORECASE)
_NAME_TRACK = re.compile(r"^\s*(\d{1,3})(?!\d)")


def file_numbers(f: FileInfo) -> tuple[int | None, int]:
    """(Track, Disc) aus den Tags – sonst vorne aus dem Dateinamen („1-05 …“, „05 - …“)."""
    track, disc = _num(f.track), _num(f.disc)
    if track is None and f.name:
        m = _NAME_DISC_TRACK.match(f.name)
        if m:
            disc, track = int(m.group(1)), int(m.group(2))
        else:
            m = _NAME_TRACK.match(f.name)
            track = int(m.group(1)) if m else None
    return track, disc or 1


def title_similarity(track_title: str, file: FileInfo) -> float:
    """0–1: Wie gut passt der Track-Titel zum Titel-Tag oder zum Dateinamen der Datei?

    Ein Treffer zählt auch, wenn alle Wörter des Titels im Dateinamen vorkommen
    („03 - AC_DC - Hells Bells.mp3“) oder umgekehrt der Tag kürzer ist als der Titel."""
    want = title_words(track_title)
    if not want:
        return 0.0
    best = 0.0
    for words in (title_words(file.title), title_words(file.name, filename=True)):
        if not words:
            continue
        a, b = " ".join(want), " ".join(words)
        score = 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()
        sw, sb = set(want), set(words)
        if sw <= sb:                                   # alle Titel-Wörter stecken drin
            score = max(score, 0.85 + 0.15 * len(sw) / len(sb))
        elif sb <= sw:                                 # Tag ist eine Kurzform des Titels
            score = max(score, 0.8 + 0.15 * len(sb) / len(sw))
        best = max(best, score)
    return best


def _by_title(files: list[FileInfo], album: AlbumMatch) -> tuple[list[int | None], list[float | None]]:
    """Beste Paare zuerst, jeder Track höchstens einmal. Tracknummer und Länge helfen bei gleichen Titeln."""
    pairs = []
    for fi, f in enumerate(files):
        fnum, fdisc = file_numbers(f)
        for ti, t in enumerate(album.tracks):
            s = title_similarity(t.title, f)
            if s < TITLE_MIN:
                continue
            bonus = 0.0
            if fnum is not None and fnum == t.position and (album.disc_total == 1 or fdisc == t.disc):
                bonus += 0.06
            if f.length and t.length and abs(f.length - t.length) <= 3:
                bonus += 0.04
            pairs.append((s + bonus, s, fi, ti))
    pairs.sort(key=lambda p: (-p[0], p[2], p[3]))
    idx: list[int | None] = [None] * len(files)
    scores: list[float | None] = [None] * len(files)
    used_t: set[int] = set()
    for _total, s, fi, ti in pairs:
        if idx[fi] is not None or ti in used_t:
            continue
        idx[fi], scores[fi] = ti, s
        used_t.add(ti)
    return idx, scores


def _fill_by_number(idx: list[int | None], files: list[FileInfo], album: AlbumMatch) -> None:
    """Nicht erkannte Dateien über die Tracknummer ergänzen – nur auf noch freie Tracks."""
    index = {(t.disc, t.position): i for i, t in enumerate(album.tracks)}
    used = {i for i in idx if i is not None}
    for fi, f in enumerate(files):
        if idx[fi] is not None:
            continue
        n, fdisc = file_numbers(f)
        if n is None:
            continue
        i = index.get((fdisc if album.disc_total > 1 else 1, n))
        if i is not None and i not in used:
            idx[fi] = i
            used.add(i)


def assign(files: list[FileInfo], album: AlbumMatch, mode: str = "auto") -> tuple[list[Assignment], str]:
    """Ergebnis je Datei + der tatsächlich benutzte Modus."""
    used_mode = mode
    scores: list[float | None] = [None] * len(files)
    if mode in ("auto", "title"):
        t_idx, t_scores = _by_title(files, album)
        sure = sum(1 for s in t_scores if s is not None and s >= TITLE_SURE)
    if mode == "title":
        idx, scores = t_idx, t_scores
        _fill_by_number(idx, files, album)
    elif mode == "auto" and files and sure >= max(1, math.ceil(TITLE_SHARE * len(files))):
        idx, scores, used_mode = t_idx, t_scores, "title"
        _fill_by_number(idx, files, album)
    elif mode == "number":
        idx = _by_number(files, album) or [None] * len(files)
    elif mode == "order":
        idx = _by_order(files, album)
    elif mode == "length":
        idx = _by_length(files, album)
    else:
        idx = _by_number(files, album)
        used_mode = "number"
        if idx is None:
            if len(files) == len(album.tracks):
                idx, used_mode = _by_order(files, album), "order"
            else:
                idx, used_mode = _by_length(files, album), "length"
    out = []
    for f, i, s in zip(files, idx, scores):
        diff = None
        if i is not None and f.length and album.tracks[i].length:
            diff = abs(f.length - album.tracks[i].length)
        out.append(Assignment(i, diff, s if i is not None else None))
    return out, used_mode


def tags_for(album: AlbumMatch, track_index: int, fields: set[str], *, disc_only_if_multi: bool = True,
             clean: bool = False) -> dict:
    """Neue Tag-Werte für eine Datei, die dem Track track_index zugeordnet ist.

    clean: Zusätze von Neuauflagen („(Remastered 2011)“) aus Titel und Album entfernen.
    """
    t = album.tracks[track_index]
    out = {}
    if "title" in fields:
        out["title"] = t.title
    if "artist" in fields:
        out["artist"] = t.artist or album.albumartist
    if "album" in fields:
        out["album"] = album.album
        out["albumartist"] = album.albumartist
    if "year" in fields and album.year:
        out["year"] = album.year
    if "track" in fields:
        total = t.track_total or sum(1 for x in album.tracks if x.disc == t.disc)
        out["track"] = f"{t.position}/{total}" if total else str(t.position)
        if album.disc_total > 1 or not disc_only_if_multi:
            out["disc"] = f"{t.disc}/{album.disc_total}"
    if "genre" in fields and album.genre:
        out["genre"] = album.genre
    if "label" in fields and album.label:
        out["label"] = album.label
    if "originalyear" in fields and album.original_year:
        out["originalyear"] = album.original_year
    if clean:
        for k in ("title", "album"):
            if k in out:
                out[k] = strip_edition(out[k]) or out[k]
    return out


def rank_for_files(matches: list[AlbumMatch], n_files: int) -> list[AlbumMatch]:
    """Treffer mit genau so vielen Tracks wie Dateien nach oben; Kassetten/Vinyl leicht nach unten."""
    def key(m: AlbumMatch):
        bonus = 0
        if n_files and m.track_total == n_files:
            bonus += 25
        elif n_files and m.track_total:
            bonus -= min(15, abs(m.track_total - n_files) * 2)
        f = (m.formats or "").lower()
        if "cd" in f or "digital" in f:
            bonus += 5
        if "cassette" in f:
            bonus -= 5
        if m.extra.get("status") and m.extra.get("status") != "Official":
            bonus -= 10
        return -(m.score + bonus)
    return sorted(matches, key=key)


def mix_sources(ranked: list[AlbumMatch], good: int = 85) -> list[AlbumMatch]:
    """„Alle Quellen“: gute Treffer abwechselnd je Quelle nach oben (sonst stehen oben nur die vielen
    MusicBrainz-Ausgaben), danach der Rest in der bisherigen Reihenfolge."""
    by_source: dict[str, list[AlbumMatch]] = {}
    for m in ranked:
        if m.score >= good:
            by_source.setdefault(m.source, []).append(m)
    mixed: list[AlbumMatch] = []
    queues = list(by_source.values())                 # Reihenfolge: Quelle mit dem besten Treffer zuerst
    while queues:
        for q in list(queues):
            mixed.append(q.pop(0))
            if not q:
                queues.remove(q)
    seen = {id(m) for m in mixed}
    return mixed + [m for m in ranked if id(m) not in seen]
