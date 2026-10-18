"""Aktionen (Phase 4): mehrere Werkzeug-Schritte als gespeicherte Kette.

Eine Aktion ist eine Liste von Schritten, jeder mit Typ und Optionen – genau
die Optionen der Werkzeuge aus Phase 2. Gespeichert wird als JSON unter
~/.config/bub3tagmusic/actions.json (lesbar, sicherbar, weitergebbar).

Ausführen:
  run_tag_steps()  – alle Tag-Schritte nacheinander im Speicher (Ergebnis = neue Tags je Datei)
  rename-Schritt   – immer zuletzt; nutzt die neuen Tags (Pläne über core/rename)
Die Oberfläche zeigt erst eine Vorschau und übernimmt dann in EINEM Rückgängig-Schritt.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass, field

from . import tools
from .fields import FIELD_BY_KEY, FIELD_KEYS, split_number
from .patterns import PLACEHOLDER_RE, unknown_placeholders


class ActionError(ValueError):
    """Ein Schritt ist falsch eingestellt (z. B. ungültiger Suchausdruck)."""


@dataclass(frozen=True)
class StepType:
    key: str
    label: str
    icon: str
    defaults: dict


STEP_TYPES: dict[str, StepType] = {s.key: s for s in (
    StepType("cleanup", "Aufräumen", "lightning",
             {"rules": [r.key for r in tools.CLEANUP_RULES if r.default], "fields": list(tools.TEXT_FIELDS)}),
    StepType("case", "Groß-/Kleinschreibung", "text-aa",
             {"mode": tools.CASE_TITLE, "fields": ["title", "artist", "albumartist", "album"], "only_uniform": True,
              "small": tools.DEFAULT_SMALL_WORDS, "fixed": tools.DEFAULT_FIXED_WORDS}),
    StepType("replace", "Suchen & Ersetzen", "magnifying-glass",
             {"find": "", "repl": "", "regex": False, "case": False, "whole": False,
              "fields": list(tools.TEXT_FIELDS)}),
    StepType("set_field", "Feld setzen", "pencil-simple",
             {"field": "albumartist", "value": "%artist%", "only_empty": True}),
    StepType("tags_from_filename", "Tags aus Dateiname", "tag",
             {"pattern": "%track% - %title%", "strip_zeros": True, "underscores": True, "only_empty": False}),
    StepType("autonumber", "Tracks nummerieren", "list-numbers",
             {"start": 1, "per_folder": True, "with_total": True, "leading_zero": False}),
    StepType("rename", "Dateinamen aus Tags", "swap",
             {"pattern": "%track% - %title%", "pad": 2, "windows_safe": True, "companions": True}),
)}
TAG_STEPS = tuple(k for k in STEP_TYPES if k != "rename")

CASE_NAMES = {tools.CASE_TITLE: "Jedes Wort groß", tools.CASE_SENTENCE: "Satzanfang groß",
              tools.CASE_UPPER: "ALLES GROSS", tools.CASE_LOWER: "alles klein"}


@dataclass
class Action:
    name: str
    steps: list[dict] = field(default_factory=list)     # [{"type": "...", "opts": {...}}]

    def to_json(self) -> dict:
        return {"name": self.name, "steps": self.steps}

    @classmethod
    def from_json(cls, data: dict) -> "Action":
        steps = []
        for st in data.get("steps") or []:
            kind = st.get("type")
            if kind in STEP_TYPES:
                steps.append({"type": kind, "opts": {**STEP_TYPES[kind].defaults, **(st.get("opts") or {})}})
        return cls(str(data.get("name") or "Aktion"), steps)

    @property
    def renames(self) -> bool:
        return any(s["type"] == "rename" for s in self.steps)


def new_step(kind: str) -> dict:
    return {"type": kind, "opts": copy.deepcopy(STEP_TYPES[kind].defaults)}


def _fields_text(keys) -> str:
    keys = [k for k in keys if k in FIELD_BY_KEY]
    if not keys:
        return "keine Felder"
    if len(keys) > 3:
        return f"{len(keys)} Felder"
    return ", ".join(FIELD_BY_KEY[k].label for k in keys)


def describe(step: dict) -> str:
    """Kurzer Text für die Schrittliste: „Ersetzen: (Live) → leer · Titel“."""
    t, o = step["type"], step["opts"]
    if t == "cleanup":
        n = len(o.get("rules") or [])
        return f"Aufräumen: {n} Regel{'n' if n != 1 else ''} · {_fields_text(o.get('fields', []))}"
    if t == "case":
        return f"Schreibweise: {CASE_NAMES.get(o.get('mode'), '?')} · {_fields_text(o.get('fields', []))}"
    if t == "replace":
        repl = o.get("repl") or "nichts"
        rx = " (Ausdruck)" if o.get("regex") else ""
        return f"Ersetzen{rx}: „{o.get('find', '')}“ → „{repl}“ · {_fields_text(o.get('fields', []))}"
    if t == "set_field":
        label = FIELD_BY_KEY.get(o.get("field"), FIELD_BY_KEY["comment"]).label
        value = o.get("value") or "(leeren)"
        only = " (wenn leer)" if o.get("only_empty") else ""
        return f"{label} = {value}{only}"
    if t == "tags_from_filename":
        return f"Tags aus Dateiname: {o.get('pattern', '')}"
    if t == "autonumber":
        extra = " mit Gesamtzahl" if o.get("with_total") else ""
        return f"Tracks nummerieren ab {o.get('start', 1)}{extra}"
    if t == "rename":
        return f"Umbenennen: {o.get('pattern', '')}"
    return t


def validate(action: Action) -> str:
    """Leer = alles gut, sonst eine verständliche Meldung."""
    if not action.steps:
        return "Die Aktion hat noch keine Schritte – mit „Schritt hinzufügen“ anfangen"
    renames = [i for i, s in enumerate(action.steps) if s["type"] == "rename"]
    if len(renames) > 1:
        return "Umbenennen darf nur einmal vorkommen"
    if renames and renames[0] != len(action.steps) - 1:
        return "Umbenennen muss der letzte Schritt sein (es nutzt die fertigen Tags)"
    for n, s in enumerate(action.steps, 1):
        o = s["opts"]
        if s["type"] in ("cleanup", "case", "replace") and not o.get("fields"):
            return f"Schritt {n}: mindestens ein Feld auswählen"
        if s["type"] == "replace":
            if not o.get("find"):
                return f"Schritt {n}: Suchbegriff fehlt"
            try:
                tools.compile_search(o["find"], regex=o.get("regex", False), case=o.get("case", False),
                                     whole_word=o.get("whole", False))
            except tools.PatternError as exc:
                return f"Schritt {n}: {exc}"
        if s["type"] in ("tags_from_filename", "rename", "set_field"):
            pat = o.get("pattern", "") if s["type"] != "set_field" else o.get("value", "")
            if s["type"] != "set_field" and not pat.strip():
                return f"Schritt {n}: Muster fehlt"
            bad = unknown_placeholders(pat)
            if bad:
                return f"Schritt {n}: unbekannter Platzhalter %{bad[0]}%"
        if s["type"] == "set_field" and o.get("field") not in FIELD_BY_KEY:
            return f"Schritt {n}: Feld fehlt"
    return ""


def fill_value(template: str, tags: dict) -> str:
    """'%artist%' → Wert. Bei Track/Disc nur die Nummer (ohne /Gesamt)."""
    def repl(m: re.Match) -> str:
        key = m.group(1)
        v = tags.get(key, "")
        if key in ("track", "disc"):
            return split_number(v)[0]
        return v
    return " ".join(PLACEHOLDER_RE.sub(repl, template).split())


def run_tag_steps(files: list[tuple[str, dict]], steps: list[dict]) -> tuple[list[dict], dict[int, list[str]]]:
    """files: [(pfad, aktuelle_tags)] in Listen-Reihenfolge.

    → (neue Tags je Datei, Hinweise je Datei-Index – z. B. „Muster passt nicht“).
    Fehler in den Einstellungen lösen ActionError aus.
    """
    tags = [dict(t) for _p, t in files]
    notes: dict[int, list[str]] = {}
    for n, step in enumerate(steps, 1):
        kind, o = step["type"], step["opts"]
        if kind == "rename":
            continue
        if kind == "cleanup":
            rules = set(o.get("rules") or [])
            keys = [k for k in o.get("fields", []) if k in FIELD_BY_KEY]
            for t in tags:
                for k in keys:
                    t[k] = tools.cleanup(t.get(k, ""), k, rules)
        elif kind == "case":
            small = tools.parse_word_list(o.get("small", ""))
            fixed = tools.parse_word_list(o.get("fixed", ""))
            keys = [k for k in o.get("fields", []) if k in FIELD_BY_KEY]
            for t in tags:
                for k in keys:
                    t[k] = tools.change_case(t.get(k, ""), o.get("mode", tools.CASE_TITLE), small_words=small,
                                             fixed_words=fixed, only_uniform=o.get("only_uniform", True))
        elif kind == "replace":
            regex = o.get("regex", False)
            try:
                rx = tools.compile_search(o.get("find", ""), regex=regex, case=o.get("case", False),
                                          whole_word=o.get("whole", False))
                keys = [k for k in o.get("fields", []) if k in FIELD_BY_KEY]
                for t in tags:
                    for k in keys:
                        if t.get(k):
                            out, hits = tools.replace_text(t[k], rx, o.get("repl", ""), regex=regex)
                            if hits:
                                t[k] = out.strip()
            except tools.PatternError as exc:
                raise ActionError(f"Schritt {n} ({STEP_TYPES[kind].label}): {exc}") from exc
        elif kind == "set_field":
            key = o.get("field")
            if key not in FIELD_BY_KEY:
                continue
            for t in tags:
                if o.get("only_empty") and t.get(key, "").strip():
                    continue
                t[key] = fill_value(o.get("value", ""), t)
        elif kind == "tags_from_filename":
            for i, (path, _t) in enumerate(files):
                new = tools.parse_from_path(path, o.get("pattern", ""), strip_zeros=o.get("strip_zeros", True),
                                            underscores=o.get("underscores", True),
                                            only_empty=o.get("only_empty", False), current=tags[i])
                if new is None:
                    notes.setdefault(i, []).append(f"Schritt {n}: Dateiname passt nicht zum Muster")
                else:
                    tags[i].update(new)
        elif kind == "autonumber":
            res = tools.autonumber([os.path.dirname(p) for p, _t in files], start=int(o.get("start", 1)),
                                   per_folder=o.get("per_folder", True), with_total=o.get("with_total", True),
                                   pad=2 if o.get("leading_zero") else 0)
            for t, r in zip(tags, res):
                t.update(r)
    for t in tags:
        for k in list(t):
            if k not in FIELD_KEYS:
                del t[k]
    return tags, notes


# ----------------------------------------------------------------------
# Speichern / Laden
# ----------------------------------------------------------------------
def default_actions() -> list[Action]:
    cleanup = new_step("cleanup")
    case = new_step("case")
    aa = new_step("set_field")
    rename = new_step("rename")
    feat = new_step("cleanup")
    feat["opts"]["rules"] = ["feat", "spaces", "trim"]
    feat["opts"]["fields"] = ["title", "artist"]
    live = new_step("replace")
    live["opts"].update(find=r"\s*[\(\[](remaster(ed)?|\d{4} remaster(ed)?)[^)\]]*[\)\]]", repl="", regex=True,
                        fields=["title", "album"])
    return [
        Action("Album fertig machen", [cleanup, case, aa, rename]),
        Action("Nur aufräumen", [new_step("cleanup")]),
        Action("feat. vereinheitlichen", [feat]),
        Action("„(Remastered …)“ entfernen", [live]),
    ]


def load_actions(path: str) -> list[Action]:
    """Fehlt die Datei, gibt es die Beispiel-Aktionen. Kaputte Datei → Beispiele, Datei bleibt liegen."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return default_actions()
    except (OSError, ValueError):
        return default_actions()
    items = data.get("actions") if isinstance(data, dict) else data
    out = [Action.from_json(a) for a in items or [] if isinstance(a, dict)]
    return out


def save_actions(path: str, actions: list[Action]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "actions": [a.to_json() for a in actions]}, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
