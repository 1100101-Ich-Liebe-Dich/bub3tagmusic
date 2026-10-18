"""Eigene Dateien den Tracks eines gefundenen Albums zuordnen.

Modi:
  * "number": über Disc + Tracknummer aus den Tags
  * "order":  in der Reihenfolge der Liste (z. B. nach Dateiname sortiert)
  * "length": über die Spiellänge (nächstliegende zuerst)
  * "auto":   Tracknummern, wenn sie eindeutig passen – sonst Reihenfolge, sonst Länge
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.fields import split_number
from .base import AlbumMatch

LENGTH_TOLERANCE = 7.0      # Sekunden, ab denen die Länge als „weicht ab“ gilt

MODES = {"auto": "Automatisch", "number": "Nach Tracknummer", "order": "Nach Reihenfolge der Liste",
         "length": "Nach Länge"}


@dataclass
class FileInfo:
    track: str = ""
    disc: str = ""
    length: float = 0.0


@dataclass
class Assignment:
    track_index: int | None          # Index in album.tracks, None = kein Treffer
    length_diff: float | None = None  # Sekunden Unterschied (wenn beide Längen bekannt)

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


def assign(files: list[FileInfo], album: AlbumMatch, mode: str = "auto") -> tuple[list[Assignment], str]:
    """Ergebnis je Datei + der tatsächlich benutzte Modus."""
    used_mode = mode
    if mode == "number":
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
    for f, i in zip(files, idx):
        diff = None
        if i is not None and f.length and album.tracks[i].length:
            diff = abs(f.length - album.tracks[i].length)
        out.append(Assignment(i, diff))
    return out, used_mode


def tags_for(album: AlbumMatch, track_index: int, fields: set[str], *, disc_only_if_multi: bool = True) -> dict:
    """Neue Tag-Werte für eine Datei, die dem Track track_index zugeordnet ist."""
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
    return out
