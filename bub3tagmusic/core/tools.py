"""Werkzeuge der Phase 2 – reine Logik ohne Oberfläche.

Jede Funktion bekommt Werte und Optionen und liefert die *vorgeschlagenen*
neuen Werte zurück. Übernommen wird erst in der Oberfläche (über die Session,
damit alles im Rückgängig-Verlauf landet).
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

from .fields import split_number
from .patterns import tags_from_path

TEXT_FIELDS = ("title", "artist", "albumartist", "album", "genre", "composer", "comment")
NUMBER_FIELDS = ("track", "disc", "year")


# ======================================================================
# #1 Tags aus Dateiname / Ordnername
# ======================================================================
PATTERN_PRESETS = (
    "%track% - %title%",
    "%track% - %artist% - %title%",
    "%artist% - %title%",
    "%track%. %title%",
    "%track% %title%",
    "%artist%/%album%/%track% - %title%",
    "%artist%/%year% - %album%/%track% - %title%",
    "%year% - %album%/%track% - %title%",
)


def strip_leading_zeros(value: str) -> str:
    """'03/12' → '3/12', '007' → '7', '0' bleibt '0'."""
    num, total = split_number(value)
    def z(s: str) -> str:
        return (s.lstrip("0") or "0") if s.isdigit() else s
    num, total = z(num), z(total)
    return f"{num}/{total}" if total else num


def parse_from_path(path: str, pattern: str, *, strip_zeros: bool = True, underscores: bool = True,
                    only_empty: bool = False, current: dict | None = None) -> dict[str, str] | None:
    """Neue Werte aus dem Pfad – oder None, wenn der Pfad nicht zum Muster passt."""
    found = tags_from_path(path, pattern)
    if found is None:
        return None
    out = {}
    for key, value in found.items():
        if underscores:
            value = re.sub(r"\s+", " ", value.replace("_", " ")).strip()
        if strip_zeros and key in ("track", "disc"):
            value = strip_leading_zeros(value)
        if only_empty and current and current.get(key, "").strip():
            continue
        out[key] = value
    return out


# ======================================================================
# #3 Tracks automatisch nummerieren
# ======================================================================
_DISC_RE = re.compile(r"(?:^|[\s_\-(\[])(?:cd|disc|disk|disco|dvd)[\s_\-]*(\d{1,2})(?:\b|$)", re.IGNORECASE)


def disc_from_folder(folder: str) -> int | None:
    m = _DISC_RE.search(os.path.basename(folder.rstrip("/")))
    return int(m.group(1)) if m else None


def autonumber(dirs: list[str], *, start: int = 1, per_folder: bool = True, with_total: bool = True,
               pad: int = 0, disc_from_folders: bool = False) -> list[dict[str, str]]:
    """Tracknummern in der übergebenen Reihenfolge (eine Liste Ordner je Datei).

    Liefert je Datei die neuen Werte ({'track': '3/12'} und ggf. {'disc': '1/2'}).
    """
    groups: list[list[int]] = []
    if per_folder:
        index: dict[str, int] = {}
        for i, d in enumerate(dirs):
            if d not in index:
                index[d] = len(groups)
                groups.append([])
            groups[index[d]].append(i)
    else:
        groups = [list(range(len(dirs)))]

    out: list[dict[str, str]] = [{} for _ in dirs]
    disc_totals: dict[str, int] = {}
    for group in groups:
        total = start + len(group) - 1
        for n, i in enumerate(group, start):
            track = str(n).zfill(pad) if pad else str(n)
            if with_total:
                track += f"/{str(total).zfill(pad) if pad else total}"
            out[i]["track"] = track
        if disc_from_folders and group:
            folder = dirs[group[0]]
            disc = disc_from_folder(folder)
            if disc is not None:
                parent = os.path.dirname(folder.rstrip("/"))
                if parent not in disc_totals:
                    try:
                        siblings = [e.name for e in os.scandir(parent) if e.is_dir()]
                    except OSError:
                        siblings = []
                    nums = [d for d in (disc_from_folder(s) for s in siblings) if d is not None]
                    disc_totals[parent] = max(nums) if nums else disc
                for i in group:
                    out[i]["disc"] = f"{disc}/{disc_totals[parent]}"
    return out


# ======================================================================
# #4 Groß-/Kleinschreibung
# ======================================================================
CASE_TITLE, CASE_SENTENCE, CASE_UPPER, CASE_LOWER = "title", "sentence", "upper", "lower"

DEFAULT_SMALL_WORDS = ("und, oder, der, die, das, des, dem, den, ein, eine, einer, von, vom, zu, zum, zur, "
                       "im, in, am, an, auf, aus, mit, bei, für, a, an, the, of, and, or, on, at, to, for, "
                       "by, vs, feat, ft")
DEFAULT_FIXED_WORDS = "AC/DC, ABBA, BAP, DJ, MC, TV, UK, USA, R&B, EP, LP, CD"

_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
_ROMAN_RE = re.compile(r"^[IVX]{2,}$", re.IGNORECASE)
_VALID_ROMAN = re.compile(r"^X{0,3}(IX|IV|V?I{0,3})$", re.IGNORECASE)


def parse_word_list(text: str) -> list[str]:
    return [w.strip() for w in text.split(",") if w.strip()]


def change_case(text: str, mode: str, *, small_words: list[str] | None = None,
                fixed_words: list[str] | None = None, only_uniform: bool = True) -> str:
    if not text or not any(ch.isalpha() for ch in text):
        return text
    if mode == CASE_UPPER:
        return text.upper()
    if mode == CASE_LOWER:
        return text.lower()
    if only_uniform:
        letters = [ch for ch in text if ch.isalpha()]
        if not (all(ch.isupper() for ch in letters) or all(ch.islower() for ch in letters)):
            return text  # bewusst gemischte Schreibweise (iPhone, McCartney …) nicht anfassen

    small = {w.lower().rstrip(".") for w in (small_words or [])}
    always_small = {"feat", "ft", "vs"} & small     # bleiben klein, auch in Klammern: (feat. X)
    result = []
    last = 0
    first_word = True
    for m in _WORD_RE.finditer(text):
        word = m.group(0)
        before = text[last:m.start()]
        result.append(before if mode == CASE_TITLE else before.lower())
        lower = word.lower()
        prev = text[:m.start()]
        after_sentence = bool(re.search(r"[.!?]\s+$", prev))
        after_break = bool(re.search(r"[(\[\-:\"„“/]\s*$", prev))   # (Live), Teil - Zwei, „Zitat“
        cap = lower[:1].upper() + lower[1:]
        if _ROMAN_RE.match(word) and _VALID_ROMAN.match(word):
            new = word.upper()
        elif mode == CASE_TITLE:
            if first_word:
                new = cap
            elif lower in always_small:
                new = lower
            elif lower in small and not (after_break or after_sentence):
                new = lower
            else:
                new = cap
        else:  # Satzanfang groß, Rest klein
            new = cap if (first_word or after_sentence) else lower
        result.append(new)
        last = m.end()
        first_word = False
    tail = text[last:]
    result.append(tail if mode == CASE_TITLE else tail.lower())
    out = "".join(result)
    for fixed in fixed_words or []:
        out = re.sub(r"(?<!\w)" + re.escape(fixed) + r"(?!\w)", fixed, out, flags=re.IGNORECASE)
    return out


# ======================================================================
# #5 Suchen & Ersetzen
# ======================================================================
class PatternError(ValueError):
    pass


def compile_search(find: str, *, regex: bool = False, case: bool = False, whole_word: bool = False) -> re.Pattern:
    if not find:
        raise PatternError("Suchbegriff fehlt")
    body = find if regex else re.escape(find)
    if whole_word:
        body = rf"(?<!\w)(?:{body})(?!\w)"
    try:
        return re.compile(body, 0 if case else re.IGNORECASE)
    except re.error as exc:
        raise PatternError(f"Ungültiger Ausdruck: {exc.msg} (Stelle {exc.pos})") from exc


def replace_text(text: str, rx: re.Pattern, replacement: str, *, regex: bool = False) -> tuple[str, int]:
    if regex:
        # Mp3tag-Schreibweise $1 zusätzlich zu \1 erlauben
        repl = re.sub(r"\$(\d+)", r"\\\1", replacement)
        try:
            return rx.subn(repl, text)
        except (re.error, IndexError) as exc:
            m = re.search(r"group reference (\d+)", str(exc))
            if m:
                raise PatternError(f"Im Ersetzen steht ${m.group(1)}, aber der Suchausdruck hat keine "
                                   f"Gruppe {m.group(1)} – Gruppen mit ( … ) bilden") from exc
            raise PatternError(f"Ersetzung passt nicht zum Suchausdruck ({exc})") from exc
    return rx.subn(lambda _m: replacement, text)


# ======================================================================
# #6 Aufräumen
# ======================================================================
@dataclass(frozen=True)
class CleanupRule:
    key: str
    label: str
    default: bool
    detail: str = ""


CLEANUP_RULES = (
    CleanupRule("invisible", "Unsichtbare Zeichen entfernen", True,
                "Steuerzeichen und unsichtbare Zeichen, die beim Kopieren aus dem Netz mitkommen."),
    CleanupRule("underscores", "Unterstriche durch Leerzeichen", True),
    CleanupRule("feat", "„feat.“ vereinheitlichen", False, "ft., Ft., Featuring … → feat."),
    CleanupRule("brackets", "Leere Klammern entfernen", True, "( ), [ ] und { } ohne Inhalt"),
    CleanupRule("spaces", "Doppelte Leerzeichen zusammenfassen", True),
    CleanupRule("trim", "Leerzeichen am Rand entfernen", True),
    CleanupRule("zeros", "Führende Nullen bei Track und Disc", False, "03 → 3, 03/12 → 3/12"),
)

_FEAT_RE = re.compile(r"(?<!\w)(?:featuring|feat|ft)(?!\w)\.?", re.IGNORECASE)
_EMPTY_BRACKETS = re.compile(r"\(\s*\)|\[\s*\]|\{\s*\}")


def _strip_invisible(text: str) -> str:
    return "".join(ch for ch in text
                   if ch in "\t" or unicodedata.category(ch) not in ("Cc", "Cf", "Co", "Cn"))


def cleanup(text: str, field: str, rules: set[str]) -> str:
    if field in ("track", "disc"):
        out = text.strip()
        if "zeros" in rules:
            out = strip_leading_zeros(out)
        return out
    out = text
    if "invisible" in rules:
        out = _strip_invisible(out).replace("\t", " ")
    if "underscores" in rules:
        out = out.replace("_", " ")
    if "feat" in rules:
        out = _FEAT_RE.sub("feat.", out)
    if "brackets" in rules:
        out = _EMPTY_BRACKETS.sub("", out)
    if "spaces" in rules:
        out = re.sub(r" {2,}", " ", out)
        out = re.sub(r"\s+([)\]}])", r"\1", out)
        out = re.sub(r"([(\[{])\s+", r"\1", out)
    if "trim" in rules:
        out = out.strip()
    return out
