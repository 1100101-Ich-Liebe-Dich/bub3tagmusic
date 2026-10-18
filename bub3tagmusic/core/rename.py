"""Dateien nach Muster umbenennen – mit Plan, Prüfung und sicherem Ausführen.

1. plan_renames():    berechnet für jede Datei den neuen Namen und prüft ihn
                       (fehlende Tags, doppelte Ziele, schon vorhandene Dateien, zu lang …)
2. execute_renames(): benennt in zwei Schritten um (erst auf Zwischennamen, dann
                       auf den Zielnamen). So klappen auch Tausche wie A→B und B→A,
                       und bei einem Fehler wird alles zurückgerollt.

Dateien: Umbenannt wird nur der Dateiname; die Endung bleibt. Gleichnamige
Begleitdateien (01 - Lied.lrc, 01 - Lied.en.srt …) im selben Ordner wandern mit.
Ordner: plan_folder_renames() benennt Album-Ordner nach den gemeinsamen Tags um.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

from .patterns import format_from_tags, placeholders
from .tags import AUDIO_EXTENSIONS

MAX_NAME_BYTES = 255

OK, SAME, MISSING, CONFLICT, INVALID, MIXED = "ok", "same", "missing", "conflict", "invalid", "mixed"

STATUS_TEXT = {
    OK: "wird umbenannt",
    SAME: "Name bleibt gleich",
    MISSING: "Tag fehlt",
    CONFLICT: "Name doppelt",
    INVALID: "ungültig",
    MIXED: "Werte verschieden",
}


@dataclass
class RenamePlan:
    old: str
    new: str
    status: str
    note: str = ""
    companions: list[tuple[str, str]] = field(default_factory=list)   # Begleitdateien (alt, neu)

    @property
    def will_rename(self) -> bool:
        return self.status == OK

    @property
    def all_pairs(self) -> list[tuple[str, str]]:
        return [(self.old, self.new), *self.companions] if self.status == OK else []


def find_companions(path: str, names: list[str]) -> list[str]:
    """Nicht-Audio-Dateien mit gleichem Namensanfang: '01 - Lied.mp3' → '01 - Lied.lrc', '01 - Lied.en.srt'."""
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0]
    out = []
    for n in names:
        if n == name or n.startswith(".") or not n.startswith(stem + "."):
            continue
        if os.path.splitext(n)[1].lower() in AUDIO_EXTENSIONS:
            continue
        out.append(os.path.join(folder, n))
    return sorted(out)


def plan_renames(entries: list[tuple[str, dict]], pattern: str, *, pad_track: int = 2,
                 windows_safe: bool = True, companions: bool = True, exists=os.path.exists,
                 listdir=os.listdir) -> list[RenamePlan]:
    """entries: [(pfad, tags)] in Listen-Reihenfolge."""
    from .fields import FIELD_BY_KEY

    folder_names: dict[str, list[str]] = {}

    def names_in(folder: str) -> list[str]:
        if folder not in folder_names:
            try:
                folder_names[folder] = listdir(folder)
            except OSError:
                folder_names[folder] = []
        return folder_names[folder]

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
        plan = RenamePlan(path, new, SAME if new == path else OK)
        if companions and plan.status == OK:
            old_stem = os.path.splitext(name)[0]
            for c in find_companions(path, names_in(folder)):
                suffix = os.path.basename(c)[len(old_stem):]
                plan.companions.append((c, os.path.join(folder, stem + suffix)))
        plans.append(plan)

    # Eine Begleitdatei gehört nur zu einer Musikdatei (z. B. Lied.mp3 + Lied.flac teilen sich Lied.lrc)
    claimed: set[str] = set()
    for p in plans:
        keep = []
        for c_old, c_new in p.companions:
            if c_old not in claimed:
                claimed.add(c_old)
                keep.append((c_old, c_new))
        p.companions = keep
    _check_conflicts(plans, exists, "Dateien")
    return plans


def _check_conflicts(plans: list[RenamePlan], exists, what: str) -> None:
    """Zwei Einträge wollen denselben Namen, oder das Ziel gibt es schon."""
    sources = {p.old for p in plans} | {c for p in plans for c, _ in p.companions}
    targets: dict[str, list[RenamePlan]] = {}
    for p in plans:
        if p.status in (OK, SAME):
            targets.setdefault(p.new, []).append(p)
            for _c, c_new in p.companions:
                targets.setdefault(c_new, []).append(p)
    for group in targets.values():
        if len({id(p) for p in group}) > 1:
            for p in group:
                p.status, p.note = CONFLICT, f"{len(group)} {what} bekämen denselben Namen"
    for p in plans:
        if p.status != OK:
            continue
        # Gleiche Datei mit anderer Groß-/Kleinschreibung (z. B. auf USB-Sticks) ist kein Konflikt
        if p.new not in sources and exists(p.new) and os.path.normcase(p.new) != os.path.normcase(p.old):
            p.status, p.note = CONFLICT, ("Datei" if what == "Dateien" else "Ordner") + " gibt es schon"
            continue
        for c_old, c_new in p.companions:
            if c_new not in sources and exists(c_new):
                p.status, p.note = CONFLICT, f"Begleitdatei {os.path.basename(c_new)} gibt es schon"
                break


def plan_folder_renames(folders: list[tuple[str, dict, set]], pattern: str, *, windows_safe: bool = True,
                        exists=os.path.exists) -> list[RenamePlan]:
    """Album-Ordner umbenennen.

    folders: [(ordner, gemeinsame_tags, felder_mit_verschiedenen_werten)]
    Der neue Name entsteht aus den Tags, die alle Dateien im Ordner gemeinsam haben.
    """
    from .fields import FIELD_BY_KEY

    pattern = pattern.strip()
    used = [p for p in placeholders(pattern) if p in FIELD_BY_KEY]
    plans: list[RenamePlan] = []
    for folder, tags, mixed in folders:
        folder = folder.rstrip("/")
        parent = os.path.dirname(folder)
        if "/" in pattern:
            plans.append(RenamePlan(folder, folder, INVALID, "Ordnerebenen im Muster sind hier nicht möglich"))
            continue
        clash = [FIELD_BY_KEY[k].label for k in used if k in mixed]
        if clash:
            plans.append(RenamePlan(folder, folder, MIXED, ", ".join(clash) + " unterschiedlich – erst angleichen"))
            continue
        missing = [FIELD_BY_KEY[k].label for k in used if not tags.get(k, "").strip()]
        if missing:
            plans.append(RenamePlan(folder, folder, MISSING, ", ".join(missing) + " fehlt"))
            continue
        name = format_from_tags(pattern, tags, pad_track=0, windows_safe=windows_safe)
        name = " ".join(name.split()).strip(" .")
        if not name:
            plans.append(RenamePlan(folder, folder, INVALID, "Name wäre leer"))
            continue
        if len(name.encode("utf-8")) > MAX_NAME_BYTES:
            plans.append(RenamePlan(folder, folder, INVALID, "Name zu lang"))
            continue
        new = os.path.join(parent, name)
        plans.append(RenamePlan(folder, new, SAME if new == folder else OK))
    _check_conflicts(plans, exists, "Ordner")
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
