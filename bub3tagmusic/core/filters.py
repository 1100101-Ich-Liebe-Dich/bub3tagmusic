"""Schnellfilter für die Dateiliste (Phase 4) – reine Logik ohne Oberfläche.

Jeder Filter ist eine einfache Frage an eine Datei („hat kein Cover?“).
Mehrere aktive Filter gelten gemeinsam (UND). Dieselben Prüfungen laufen auf
geladenen Einträgen (FileItem, mit ungespeicherten Änderungen) und auf rohen
Datensätzen aus dem Zwischenspeicher (für die Suche in der ganzen Sammlung).
"""

from __future__ import annotations

from dataclasses import dataclass

from .covers import CoverData
from .model import FileItem
from .tags import COVER_REMOVE

SMALL_COVER_PX = 500


@dataclass(frozen=True)
class QuickFilter:
    key: str
    label: str
    tooltip: str
    collection: bool = True       # auch für die Suche in der ganzen Sammlung geeignet


QUICK_FILTERS: tuple[QuickFilter, ...] = (
    QuickFilter("no_cover", "Ohne Cover", "Dateien ohne eingebettetes Cover (Dateien mit Lesefehler zählen nicht)"),
    QuickFilter("small_cover", f"Cover < {SMALL_COVER_PX} px",
                f"Eingebettetes Cover ist schmaler oder niedriger als {SMALL_COVER_PX} Pixel"),
    QuickFilter("no_year", "Ohne Jahr", "Das Feld Jahr ist leer"),
    QuickFilter("missing", "Fehlende Tags", "Titel, Interpret, Album oder Track ist leer"),
    QuickFilter("modified", "Ungespeichert", "Dateien mit gelb markierten, noch nicht gespeicherten Änderungen",
                collection=False),
    QuickFilter("error", "Lesefehler", "Dateien, die nicht gelesen werden konnten (roter Punkt)"),
)
FILTER_BY_KEY = {f.key: f for f in QUICK_FILTERS}
MISSING_FIELDS = ("title", "artist", "album", "track")


def _check(key: str, tags: dict, cover_kind: str, cover_info: dict | None, modified: bool, error: str) -> bool:
    if key == "no_cover":
        return not error and cover_kind == "none"
    if key == "small_cover":
        if cover_kind != "disk" or not cover_info:
            return False
        w, h = cover_info.get("w") or 0, cover_info.get("h") or 0
        return bool(w and h) and min(w, h) < SMALL_COVER_PX
    if key == "no_year":
        return not error and not (tags.get("year") or "").strip()
    if key == "missing":
        return not error and any(not (tags.get(k) or "").strip() for k in MISSING_FIELDS)
    if key == "modified":
        return modified
    if key == "error":
        return bool(error)
    return True


def item_passes(it: FileItem, keys) -> bool:
    """Geladener Eintrag – berücksichtigt ungespeicherte Änderungen (neues/entferntes Cover, Felder)."""
    if not keys:
        return True
    action = it.cover_action
    if isinstance(action, CoverData):
        kind, info = "new", None
    elif action == COVER_REMOVE:
        kind, info = "none", None
    else:
        info = it.rec.get("cover")
        kind = "disk" if info else "none"
    modified = "modified" in keys and it.is_modified()
    return all(_check(k, it.tags, kind, info, modified, it.error) for k in keys)


def count_items(items: list[FileItem]) -> dict[str, int]:
    """Wie viele geladene Einträge passen zu jedem einzelnen Filter – in einem Durchgang (50.000 ≈ 0,1 s)."""
    no_cover = small = no_year = missing = modified = errors = 0
    for it in items:
        action = it.cover_action
        if it.error:
            errors += 1
            if action is not None:
                modified += 1
            continue
        tags = it.tags
        if action is None:
            info = it.rec.get("cover")
            if info is None:
                no_cover += 1
            else:
                w, h = info.get("w") or 0, info.get("h") or 0
                if w and h and min(w, h) < SMALL_COVER_PX:
                    small += 1
            if tags != it.orig and it.is_modified():
                modified += 1
        else:
            modified += 1
            if action == COVER_REMOVE:
                no_cover += 1
        if not (tags.get("year") or "").strip():
            no_year += 1
        for k in MISSING_FIELDS:
            if not (tags.get(k) or "").strip():
                missing += 1
                break
    return {"no_cover": no_cover, "small_cover": small, "no_year": no_year, "missing": missing,
            "modified": modified, "error": errors}


def record_passes(rec: dict, keys) -> bool:
    """Datensatz aus dem Zwischenspeicher (nichts ungespeichert)."""
    if not keys:
        return True
    info = rec.get("cover")
    return all(_check(k, rec.get("tags") or {}, "disk" if info else "none", info, False, rec.get("error", ""))
               for k in keys)


def text_words(text: str) -> list[str]:
    return text.strip().casefold().split()


def text_passes(words: list[str], name: str, tags: dict) -> bool:
    if not words:
        return True
    hay = " ".join((name, *tags.values())).casefold()
    return all(w in hay for w in words)


def describe(keys, text: str = "") -> str:
    """Kurzbeschreibung für Fenstertitel/Hinweise: „Ohne Cover + Ohne Jahr“."""
    parts = [FILTER_BY_KEY[k].label for k in QUICK_FILTERS_ORDER if k in keys]
    if text.strip():
        parts.append(f"„{text.strip()}“")
    return " + ".join(parts)


QUICK_FILTERS_ORDER = tuple(f.key for f in QUICK_FILTERS)
