"""Tests für die Werkzeuge der Phase 2 (ohne Oberfläche).

Aufruf: python3 tests/test_tools.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bub3tagmusic.core import tools  # noqa: E402
from bub3tagmusic.core.patterns import (format_from_tags, parse_with_pattern, tags_from_path,  # noqa: E402
                                        unknown_placeholders)
from bub3tagmusic.core.rename import CONFLICT, MISSING, OK, SAME, execute_renames, plan_renames  # noqa: E402

FAILS = []


def eq(got, want, msg):
    if got != want:
        FAILS.append(msg)
        print(f"   FEHLER: {msg}\n      bekommen: {got!r}\n      erwartet: {want!r}")


def main():
    # --- Muster ------------------------------------------------------------------
    eq(parse_with_pattern("%track% - %title%", "07 - Ein Lied - Live"),
       {"track": "07", "title": "Ein Lied - Live"}, "Muster: erster Trenner gewinnt")
    eq(parse_with_pattern("%track% - %title%", "Ein Lied"), None, "Muster: passt nicht")
    p = "/m/AC_DC/1980 - Back In Black/01 - Hells Bells.mp3"
    eq(tags_from_path(p, "%artist%/%year% - %album%/%track% - %title%"),
       {"artist": "AC_DC", "year": "1980", "album": "Back In Black", "track": "01", "title": "Hells Bells"},
       "Muster über drei Ordnerebenen")
    eq(tags_from_path(p, "%dummy%/%album%/%track% - %title%")["album"], "1980 - Back In Black", "%dummy% überspringt")
    eq(tags_from_path("/x/a.mp3", "%a%/%b%/%c%/%d%/%e%/%title%"), None, "zu wenige Ordnerebenen")
    eq(unknown_placeholders("%track% - %titel% %dummy%"), ["titel"], "Tippfehler im Muster erkannt")

    eq(tools.parse_from_path(p, "%dummy%/%year% - %album%/%track% - %title%"),
       {"year": "1980", "album": "Back In Black", "track": "1", "title": "Hells Bells"}, "führende Null weg")
    eq(tools.parse_from_path("/m/a/01_-_Mein_Lied.flac", "%track% - %title%"),
       None, "Unterstriche: Muster mit Leerzeichen passt nicht auf _-_")
    eq(tools.parse_from_path("/m/a/01 - Mein_Lied.flac", "%track% - %title%"),
       {"track": "1", "title": "Mein Lied"}, "Unterstriche → Leerzeichen")
    eq(tools.parse_from_path("/m/a/01 - Lied.flac", "%track% - %title%", only_empty=True,
                             current={"title": "Schon da", "track": ""}),
       {"track": "1"}, "nur leere Felder füllen")

    # --- Nummerieren ---------------------------------------------------------------
    dirs = ["/m/A", "/m/A", "/m/A", "/m/B", "/m/B"]
    eq([r["track"] for r in tools.autonumber(dirs)], ["1/3", "2/3", "3/3", "1/2", "2/2"], "pro Ordner mit Gesamtzahl")
    eq([r["track"] for r in tools.autonumber(dirs, per_folder=False, with_total=False, pad=2)],
       ["01", "02", "03", "04", "05"], "durchgehend, zweistellig")
    eq([r["track"] for r in tools.autonumber(dirs[:2], start=5, with_total=False)], ["5", "6"], "Startwert")
    tmp = tempfile.mkdtemp()
    for d in ("CD1", "CD2", "Bonus"):
        os.makedirs(os.path.join(tmp, "Album", d))
    eq(tools.disc_from_folder(os.path.join(tmp, "Album", "CD2")), 2, "Disc aus Ordnername")
    eq(tools.disc_from_folder("/x/Disc 3 (Live)"), 3, "Disc 3 erkannt")
    eq(tools.disc_from_folder("/x/Discovery"), None, "Discovery ist keine Disc")
    r = tools.autonumber([os.path.join(tmp, "Album", "CD2")], disc_from_folders=True)
    eq(r[0].get("disc"), "2/2", "Disc mit Gesamtzahl aus Nachbarordnern")

    # --- Schreibweise --------------------------------------------------------------
    small = tools.parse_word_list(tools.DEFAULT_SMALL_WORDS)
    fixed = tools.parse_word_list(tools.DEFAULT_FIXED_WORDS)
    T = tools.CASE_TITLE
    eq(tools.change_case("GEGEN DEN WIND", T, small_words=small), "Gegen den Wind", "Titel: kleine Wörter")
    eq(tools.change_case("der wind und das meer", T, small_words=small), "Der Wind und das Meer", "erstes Wort groß")
    eq(tools.change_case("don't stop (live)", T, small_words=small), "Don't Stop (Live)", "Apostroph + Klammer")
    eq(tools.change_case("hells bells (feat. some one)", T, small_words=small),
       "Hells Bells (feat. Some One)", "feat. bleibt klein")
    eq(tools.change_case("rocky ii", T, small_words=small), "Rocky II", "römische Zahl")
    eq(tools.change_case("mix it", T, small_words=small), "Mix It", "mix ist keine römische Zahl")
    eq(tools.change_case("ac/dc live", T, small_words=small, fixed_words=fixed), "AC/DC Live", "feste Schreibweise")
    eq(tools.change_case("iPhone Song", T, small_words=small), "iPhone Song", "gemischt bleibt unangetastet")
    eq(tools.change_case("iPhone Song", T, small_words=small, only_uniform=False), "Iphone Song", "… außer erzwungen")
    eq(tools.change_case("HIP-HOP HOORAY", T), "Hip-Hop Hooray", "Bindestrich")
    eq(tools.change_case("ÄRGER ÜBER ÖL", T), "Ärger Über Öl", "Umlaute")
    eq(tools.change_case("DAS IST GUT. ODER NICHT?", tools.CASE_SENTENCE), "Das ist gut. Oder nicht?", "Satzanfang")
    eq(tools.change_case("straße", tools.CASE_UPPER), "STRASSE", "GROSS")
    eq(tools.change_case("Hallo Welt", tools.CASE_LOWER), "hallo welt", "klein")
    eq(tools.change_case("1999", T), "1999", "nur Zahlen bleiben")

    # --- Suchen & Ersetzen ------------------------------------------------------------
    rx = tools.compile_search("live")
    eq(tools.replace_text("Song (Live) live", rx, "Konzert"), ("Song (Konzert) Konzert", 2), "ohne Groß/klein")
    rx = tools.compile_search("live", case=True)
    eq(tools.replace_text("Song (Live) live", rx, "X")[1], 1, "mit Groß/klein")
    rx = tools.compile_search("an", whole_word=True)
    eq(tools.replace_text("an Bananen an", rx, "AN")[0], "AN Bananen AN", "ganze Wörter")
    rx = tools.compile_search(r"(\d+) - (.*)", regex=True)
    eq(tools.replace_text("01 - Lied", rx, "$2 ($1)", regex=True)[0], "Lied (01)", "Regex mit $1/$2")
    eq(tools.replace_text("01 - Lied", rx, r"\2", regex=True)[0], "Lied", r"Regex mit \2")
    rx = tools.compile_search("a.b")
    eq(tools.replace_text("a.b axb", rx, "-")[0], "- axb", "ohne Regex ist . ein Punkt")
    try:
        tools.compile_search("(kaputt", regex=True)
        FAILS.append("kaputter Ausdruck nicht erkannt")
    except tools.PatternError as exc:
        eq("Ungültiger Ausdruck" in str(exc), True, "Fehlermeldung bei kaputtem Ausdruck")

    try:
        tools.replace_text("Lied", tools.compile_search("Lied", regex=True), "$1", regex=True)
        FAILS.append("$1 ohne Gruppe nicht erkannt")
    except tools.PatternError as exc:
        eq("keine Gruppe 1" in str(exc), True, "verständliche Meldung bei $1 ohne Gruppe")

    # --- Aufräumen ---------------------------------------------------------------------
    allr = {r.key for r in tools.CLEANUP_RULES}
    eq(tools.cleanup("  Mein__Lied  ( )  ", "title", allr), "Mein Lied", "Aufräumen komplett")
    eq(tools.cleanup("Song Ft. X", "title", {"feat"}), "Song feat. X", "ft. → feat.")
    eq(tools.cleanup("Lift Off featuring Y", "title", {"feat"}), "Lift Off feat. Y", "Lift bleibt Lift")
    eq(tools.cleanup("Ti​tel﻿", "title", {"invisible"}), "Titel", "unsichtbare Zeichen")
    eq(tools.cleanup("03/12", "track", {"zeros"}), "3/12", "Nullen bei Track")
    eq(tools.cleanup("( Live )", "title", {"spaces"}), "(Live)", "Leerzeichen in Klammern")

    # --- Umbenennen --------------------------------------------------------------------
    d = os.path.join(tmp, "ren")
    os.makedirs(d)
    names = ["a.mp3", "b.mp3", "c.mp3", "d.flac"]
    for n in names:
        with open(os.path.join(d, n), "w") as fh:
            fh.write(n)
    entries = [
        (os.path.join(d, "a.mp3"), {"track": "1", "title": "Erster: Teil?"}),
        (os.path.join(d, "b.mp3"), {"track": "2", "title": ""}),
        (os.path.join(d, "c.mp3"), {"track": "3", "title": "x"}),
        (os.path.join(d, "d.flac"), {"track": "3", "title": "x"}),
    ]
    plans = plan_renames(entries, "%track% - %title%")
    eq([p.status for p in plans], [OK, MISSING, OK, OK], "Plan-Status")
    eq(os.path.basename(plans[0].new), "01 - Erster_ Teil_.mp3", "verbotene Zeichen ersetzt")
    eq(os.path.basename(plans[3].new), "03 - x.flac", "Endung bleibt")
    plans = plan_renames(entries[2:3] + [(os.path.join(d, "c2.mp3"), {"track": "3", "title": "x"})],
                         "%track% - %title%")
    eq([p.status for p in plans], [CONFLICT, CONFLICT], "zwei Dateien – gleicher Name")
    # Tausch: a ↔ b
    swap = [(os.path.join(d, "a.mp3"), os.path.join(d, "b.mp3")), (os.path.join(d, "b.mp3"), os.path.join(d, "a.mp3"))]
    res = execute_renames(swap)
    eq([r["error"] for r in res], ["", ""], "Tausch ohne Fehler")
    eq(open(os.path.join(d, "a.mp3")).read(), "b.mp3", "Tausch wirklich vertauscht")
    # Ziel existiert schon → Fehler, Original bleibt
    res = execute_renames([(os.path.join(d, "c.mp3"), os.path.join(d, "d.flac"))])
    eq(bool(res[0]["error"]) and os.path.exists(os.path.join(d, "c.mp3")), True, "nichts überschrieben")
    eq(sorted(os.listdir(d)), sorted(names), "keine Zwischendateien übrig")
    plans = plan_renames([(os.path.join(d, "c.mp3"), {"track": "1", "title": "Erster: Teil?"})],
                         "%track% - %title%", windows_safe=False)
    eq(os.path.basename(plans[0].new), "01 - Erster: Teil?.mp3", "Linux-Namen erlauben : und ?")
    eq(plan_renames([(os.path.join(d, "c.mp3"), {"track": "3", "title": "x"})], "%dummy%")[0].status,
       "invalid", "Muster ohne Inhalt")
    eq(plan_renames([(os.path.join(d, "y.mp3"), {"title": "x"})], "x")[0].status, OK, "festes Muster")
    eq(plan_renames([(os.path.join(d, "x.mp3"), {"title": "x"})], "%title%")[0].status, SAME, "gleicher Name")
    eq(format_from_tags("%track% - %title%", {"track": "3/12", "title": "a"}, pad_track=0), "3 - a", "ohne Auffüllen")

    shutil.rmtree(tmp)
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
