"""Dateien nach Muster umbenennen – mit Plan, Prüfung und sicherem Ausführen.

1. plan_renames():    berechnet für jede Datei den neuen Namen und prüft ihn
                       (fehlende Tags, doppelte Ziele, schon vorhandene Dateien, zu lang …)
2. execute_renames(): benennt in zwei Schritten um (erst auf Zwischennamen, dann
                       auf den Zielnamen). So klappen auch Tausche wie A→B und B→A,
                       und bei einem Fehler wird alles zurückgerollt.

Umbenannt wird nur der Dateiname, nie der Ordner; die Endung bleibt.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from .patterns import format_from_tags, placeholders

MAX_NAME_BYTES = 255

OK, SAME, MISSING, CONFLICT, INVALID = "ok", "same", "missing", "conflict", "invalid"

STATUS_TEXT = {
    OK: "wird umbenannt",
    SAME: "Name bleibt gleich",
    MISSING: "Tag fehlt",
    CONFLICT: "Name doppelt",
    INVALID: "ungültig",
}


@dataclass
class RenamePlan:
    old: str
    new: str
    status: str
    note: str = ""

    @property
    def will_rename(self) -> bool:
        return self.status == OK


def plan_renames(entries: list[tuple[str, dict]], pattern: str, *, pad_track: int = 2,
                 windows_safe: bool = True, exists=os.path.exists) -> list[RenamePlan]:
    """entries: [(pfad, tags)] in Listen-Reihenfolge."""
    from .fields import FIELD_BY_KEY

    pattern = pattern.strip()
    used = [p for p in placeholders(pattern) if p in FIELD_BY_KEY]
    plans: list[RenamePlan] = []
    for path, tags in entries:
        folder, name = os.path.split(path)
        ext = os.path.splitext(name)[1]
        if "/" in pattern:
            plans.append(RenamePlan(path, path, INVALID, "Ordner im Muster werden noch nicht unterstützt"))
            continue
        missing = [FIELD_BY_KEY[k].label for k in used if not tags.get(k, "").strip()]
        if missing:
            plans.append(RenamePlan(path, path, MISSING, ", ".join(missing) + " fehlt"))
            continue
        stem = format_from_tags(pattern, tags, pad_track=pad_track, windows_safe=windows_safe)
        stem = " ".join(stem.split()).strip(" .")
        if not stem:
            plans.append(RenamePlan(path, path, INVALID, "Name wäre leer"))
            continue
        new_name = stem + ext
        if len(new_name.encode("utf-8")) > MAX_NAME_BYTES:
            plans.append(RenamePlan(path, path, INVALID, "Name zu lang"))
            continue
        new = os.path.join(folder, new_name)
        plans.append(RenamePlan(path, new, SAME if new == path else OK))

    # Konflikte: zwei Dateien wollen denselben Namen, oder das Ziel gibt es schon
    sources = {p.old for p in plans}
    targets: dict[str, list[RenamePlan]] = {}
    for p in plans:
        if p.status in (OK, SAME):
            targets.setdefault(p.new, []).append(p)
    for group in targets.values():
        if len(group) > 1:
            for p in group:
                p.status, p.note = CONFLICT, f"{len(group)} Dateien bekämen denselben Namen"
    for p in plans:
        if p.status == OK and p.new not in sources and exists(p.new):
            # Gleiche Datei mit anderer Groß-/Kleinschreibung (z. B. auf USB-Sticks) ist kein Konflikt
            if not (os.path.normcase(p.new) == os.path.normcase(p.old)):
                p.status, p.note = CONFLICT, "Datei gibt es schon"
    return plans


def execute_renames(pairs: list[tuple[str, str]]) -> list[dict]:
    """[(alt, neu)] umbenennen. Ergebnis je Paar: {old, new, error}."""
    results = [{"old": o, "new": n, "error": ""} for o, n in pairs]
    tag = uuid.uuid4().hex[:8]
    staged: list[tuple[int, str]] = []

    # Schritt 1: alle auf Zwischennamen
    for i, (old, _new) in enumerate(pairs):
        tmp = os.path.join(os.path.dirname(old), f".bub3ren-{tag}-{i}")
        try:
            os.rename(old, tmp)
            staged.append((i, tmp))
        except OSError as exc:
            results[i]["error"] = f"Umbenennen fehlgeschlagen: {exc.strerror or exc}"

    # Schritt 2: Zwischennamen → Ziel (nie etwas überschreiben)
    for i, tmp in staged:
        old, new = pairs[i]
        try:
            if os.path.exists(new):
                raise FileExistsError(new)
            os.rename(tmp, new)
        except OSError as exc:
            msg = "Zieldatei gibt es schon" if isinstance(exc, FileExistsError) else (exc.strerror or str(exc))
            results[i]["error"] = f"Umbenennen fehlgeschlagen: {msg}"
            try:
                os.rename(tmp, old)          # zurück zum alten Namen
            except OSError:
                results[i]["error"] += f" – Datei liegt jetzt als {os.path.basename(tmp)} im Ordner"
    return results
