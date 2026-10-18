"""Tests für die Extras der Phase 4 (ohne Oberfläche).

Aufruf: python3 tests/test_extras.py
Programme wie fpcalc und rsgain werden nur benutzt, wenn sie installiert sind.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bub3tagmusic.core import actions as A  # noqa: E402
from bub3tagmusic.core import duplicates as dup  # noqa: E402
from bub3tagmusic.core import export, filters  # noqa: E402
from bub3tagmusic.core.covers import CoverData  # noqa: E402
from bub3tagmusic.core.fields import FIELD_KEYS  # noqa: E402
from bub3tagmusic.core.fingerprint import compress, from_blob, similarity, to_blob  # noqa: E402
from bub3tagmusic.core.model import FileItem  # noqa: E402
from bub3tagmusic.core.tags import COVER_REMOVE  # noqa: E402
from bub3tagmusic.core.tools_external import distro_family, install_hint  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def eq(got, want, msg):
    if got != want:
        FAILS.append(msg)
        print(f"   FEHLER: {msg}\n      bekommen: {got!r}\n      erwartet: {want!r}")
    else:
        print(f"   ok  {msg}")


def rec(path, cover=None, error="", length=200.0, bitrate=320, fmt="MP3", size=8_000_000, **tags):
    t = dict.fromkeys(FIELD_KEYS, "")
    t.update(tags)
    return {"path": path, "tags": t, "cover": cover, "error": error, "length": length, "bitrate": bitrate,
            "format": fmt, "size": size, "mtime": 1}


def test_filters():
    print("Schnellfilter")
    big = {"w": 1000, "h": 1000, "hash": "a", "mime": "image/jpeg", "bytes": 1}
    small = {"w": 300, "h": 300, "hash": "b", "mime": "image/jpeg", "bytes": 1}
    full = dict(title="T", artist="A", album="B", track="1", year="1999")
    a = FileItem(rec("/m/a.mp3", big, **full))
    b = FileItem(rec("/m/b.mp3", small, **dict(full, year="")))
    c = FileItem(rec("/m/c.mp3", None, **dict(full, title="", year="")))
    d = FileItem(rec("/m/d.mp3", None, error="kaputt"))
    items = [a, b, c, d]
    sel = lambda keys: [it.name for it in items if filters.item_passes(it, keys)]  # noqa: E731
    eq(sel({"no_cover"}), ["c.mp3"], "ohne Cover (Lesefehler zählt nicht)")
    eq(sel({"small_cover"}), ["b.mp3"], "Cover < 500 px")
    eq(sel({"no_year"}), ["b.mp3", "c.mp3"], "ohne Jahr (Lesefehler zählt nicht)")
    eq(sel({"missing"}), ["c.mp3"], "fehlende Tags")
    eq(sel({"error"}), ["d.mp3"], "Lesefehler")
    eq(sel({"no_cover", "missing"}), ["c.mp3"], "Filter kombiniert (UND)")
    eq(sel(set()), ["a.mp3", "b.mp3", "c.mp3", "d.mp3"], "ohne Filter alles")
    # ungespeicherte Änderungen zählen
    c.cover_action = CoverData(b"\xff\xd8\xff", "image/jpeg")
    a.cover_action = COVER_REMOVE
    b.tags["year"] = "2001"
    eq(sel({"no_cover"}), ["a.mp3"], "neues/entferntes Cover zählt schon vor dem Speichern")
    eq(sel({"no_year"}), ["c.mp3"], "geändertes Jahr zählt schon vor dem Speichern")
    eq(sel({"modified"}), ["a.mp3", "b.mp3", "c.mp3"], "ungespeichert")
    counts = filters.count_items(items)
    eq(counts, {k: len(sel({k})) for k in filters.QUICK_FILTERS_ORDER}, "Zählen in einem Durchgang = einzeln")
    eq(filters.record_passes(rec("/x.mp3", None, **full), {"no_cover"}), True, "Datensatz aus dem Zwischenspeicher")
    eq(filters.text_passes(filters.text_words("ä b"), "Lied.mp3", {"title": "Bär", "artist": "B"}), True,
       "Textsuche: alle Wörter, Groß/klein egal")
    eq(filters.describe({"no_year", "no_cover"}, "abba"), "Ohne Cover + Ohne Jahr + „abba“", "Beschreibung")


def test_export(tmp):
    print("Export")
    headers = ["Dateiname", "Titel", "Jahr"]
    rows = [["01 - Bär.mp3", 'Sag "Hallo"; tschüss', "1999"], ["02.mp3", "<b>fett</b>", ""]]
    p = os.path.join(tmp, "liste.csv")
    export.write_csv(p, headers, rows, ";")
    raw = open(p, "rb").read()
    eq(raw[:3], b"\xef\xbb\xbf", "CSV mit BOM (Excel erkennt UTF-8)")
    back = list(csv.reader(open(p, encoding="utf-8-sig"), delimiter=";"))
    eq(back, [headers] + rows, "CSV liest sich verlustfrei zurück (Anführungszeichen, Semikolon, Umlaute)")
    h = os.path.join(tmp, "liste.html")
    export.write_html(h, headers, rows, title="Kurs Nord", subtitle="gefiltert: Ohne Cover", numeric={2},
                      dark={"bg": "#000", "text": "#fff"}, light={"bg": "#fff", "text": "#000"})
    page = open(h, encoding="utf-8").read()
    eq("&lt;b&gt;fett&lt;/b&gt;" in page and "<b>fett" not in page, True, "HTML: Inhalte sicher maskiert")
    eq("www.BAUENUNDBOOTEN.de" in page and "BuB3TAGMUSIC" in page, True, "HTML: Logo + präsentiert von")
    eq("2 Dateien" in page and "Kurs Nord" in page, True, "HTML: Titel und Anzahl")
    eq("font/ttf;base64," in page, True, "HTML: Logo-Schrift eingebettet")
    eq(page.count("<tr>"), 3, "HTML: Kopf + 2 Zeilen")
    eq('<td class=num>1999</td>' in page, True, "HTML: Zahlen rechtsbündig")
    eq(export.default_name("AC/DC: Live?", "csv"), "BuB3TAGMUSIC - AC_DC_ Live_.csv", "sicherer Dateiname")


def test_fingerprint():
    print("Fingerabdruck")
    fx = json.load(open(os.path.join(HERE, "fixtures", "fingerprint.json")))
    eq(compress(fx["raw"]), fx["compressed"], "kompakte Form genau wie fpcalc")
    eq(from_blob(to_blob(fx["raw"])), fx["raw"], "Speichern im Zwischenspeicher verlustfrei")
    eq(round(similarity(fx["raw"], fx["raw"]), 3), 1.0, "gleich = 1,0")
    shifted = fx["raw"][3:]
    eq(similarity(fx["raw"], shifted) > 0.99, True, "verschoben (3 Teile) wird erkannt")
    other = [x ^ 0x5A5A5A5A for x in fx["raw"]]
    eq(similarity(fx["raw"], other) < 0.7, True, "fremd < 0,7")


def test_duplicates():
    print("Duplikate")
    E = dup.Entry
    entries = [
        E("/m/a/01 - Schrei nach Liebe.mp3", "Die Ärzte", "Schrei nach Liebe", length=245, bitrate=192, format="MP3"),
        E("/m/b/05 - Schrei nach Liebe.flac", "die arzte", "Schrei nach Liebe!", length=246, bitrate=900,
          format="FLAC"),
        E("/m/c/09 - Schrei nach Liebe (Live).mp3", "Die Ärzte", "Schrei nach Liebe (Live)", length=310,
          bitrate=320),
        E("/m/d/01 - Westerland.mp3", "Die Ärzte", "Westerland", length=220, bitrate=320),
        E("/m/e/x.mp3", "", "", length=220, bitrate=128),
        E("/m/f/Schrei.mp3", "Die Ärzte", "Schrei nach Liebe", length=400, bitrate=320),
    ]
    groups, skipped = dup.by_tags(entries, tolerance=2)
    eq([[entries[i].path for i in g.members] for g in groups],
       [["/m/b/05 - Schrei nach Liebe.flac", "/m/a/01 - Schrei nach Liebe.mp3"]],
       "nach Tags: Umlaute/Satzzeichen egal, andere Länge = andere Fassung, FLAC = beste Qualität zuerst")
    eq(entries[groups[0].best].format, "FLAC", "beste Qualität: verlustfrei")
    eq(skipped, 1, "ohne Interpret/Titel übersprungen")
    groups, _ = dup.by_tags(entries, tolerance=0, ignore_brackets=True)
    eq(len(groups[0].members), 4, "Klammern ignorieren + Länge egal (0) → alle vier Fassungen")
    eq(dup.normalize("AC/DC & Friends – Highway (feat. X)", True), "ac dc and friends highway", "Normalisieren")

    # Klang: künstliche Fingerabdrücke
    import random
    rnd = random.Random(7)
    song = [rnd.getrandbits(32) for _ in range(400)]
    noisy = [x ^ (1 << rnd.randrange(32)) if rnd.random() < 0.3 else x for x in song]   # andere Kodierung
    other = [rnd.getrandbits(32) for _ in range(400)]
    from array import array
    se = [E("/s/1.flac", "A", "Lied", length=200, format="FLAC", bitrate=900, fp=array("I", song[:300])),
          E("/s/2.mp3", "", "", length=201, format="MP3", bitrate=128, fp=array("I", noisy[2:302])),
          E("/s/3.mp3", "A", "Anderes", length=200.5, fp=array("I", other[:300])),
          E("/s/4.mp3", "A", "Lied", length=260, fp=array("I", song[:300]))]
    g = dup.by_sound(se, tolerance=2)
    eq([[se[i].path for i in x.members] for x in g], [["/s/1.flac", "/s/2.mp3"]],
       "nach Klang: auch ohne Tags; fremder Klang und andere Länge nicht")
    merged = dup.merge(dup.by_tags(se, 2)[0], g, se)
    eq(len(merged), 1, "Tags + Klang zusammengeführt")


def test_tools_external(tmp):
    print("Hilfsprogramme")
    osr = os.path.join(tmp, "os-release")
    for text, want in (('ID=linuxmint\nID_LIKE="ubuntu debian"\n', "debian"), ("ID=fedora\n", "fedora"),
                       ('ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n', "suse"), ("ID=manjaro\nID_LIKE=arch\n", "arch"),
                       ("ID=nixos\n", "")):
        open(osr, "w").write(text)
        eq(distro_family(osr), want, f"Distribution erkannt: {want or 'unbekannt'}")
    eq("libchromaprint-tools" in install_hint("fpcalc", "debian"), True, "Hinweis fpcalc für Mint/Ubuntu")
    eq("dnf install rsgain" in install_hint("rsgain", ""), True, "unbekannte Distribution: alle Befehle")


def test_actions(tmp):
    print("Aktionen")
    path = os.path.join(tmp, "cfg", "actions.json")
    acts = A.load_actions(path)
    eq([a.name for a in acts][:2], ["Album fertig machen", "Nur aufräumen"], "ohne Datei: Beispiel-Aktionen")
    A.save_actions(path, acts)
    back = A.load_actions(path)
    eq([a.to_json() for a in back], [a.to_json() for a in acts], "speichern + laden verlustfrei")
    open(path, "w").write("{kaputt")
    eq(len(A.load_actions(path)) > 0, True, "kaputte Datei: Beispiele statt Absturz")

    rename, case = A.new_step("rename"), A.new_step("case")
    eq(A.validate(A.Action("x", [rename, case])), "Umbenennen muss der letzte Schritt sein (es nutzt die fertigen Tags)",
       "Umbenennen nur am Ende")
    bad = A.new_step("replace")
    bad["opts"].update(find="(", regex=True)
    eq(A.validate(A.Action("x", [bad])).startswith("Schritt 1: Ungültiger Ausdruck"), True, "kaputter Ausdruck")
    typo = A.new_step("set_field")
    typo["opts"]["value"] = "%artis%"
    eq(A.validate(A.Action("x", [typo])), "Schritt 1: unbekannter Platzhalter %artis%", "Tippfehler im Wert")
    eq(A.validate(A.Action("x", [])).startswith("Die Aktion hat noch keine Schritte"), True, "leere Aktion")

    steps = [A.new_step("cleanup"), A.new_step("case"), A.new_step("set_field"), A.new_step("replace"),
             A.new_step("tags_from_filename"), A.new_step("autonumber")]
    steps[3]["opts"].update(find="(live)", repl="", fields=["title"])
    steps[4]["opts"].update(pattern="%track% - %title%", only_empty=True)
    files = [("/m/A/01 - x.mp3", dict.fromkeys(FIELD_KEYS, "") | {"title": "  DER  LANGE WEG (LIVE) ",
                                                                    "artist": "die ärzte"}),
             ("/m/A/02 - Zweites Lied.mp3", dict.fromkeys(FIELD_KEYS, "") | {"artist": "X", "albumartist": "Y"}),
             ("/m/A/kein muster.mp3", dict.fromkeys(FIELD_KEYS, "") | {"title": "t"})]
    tags, notes = A.run_tag_steps(files, steps)
    eq(tags[0]["title"], "Der Lange Weg", "aufräumen → Schreibweise → (Live) entfernt (Reihenfolge zählt)")
    eq(tags[0]["albumartist"], "Die Ärzte", "Albuminterpret = %artist% (nach der Schreibweise)")
    eq(tags[1]["albumartist"], "Y", "nur wenn leer")
    eq(tags[1]["title"], "Zweites Lied", "Tags aus Dateiname (nur leere Felder)")
    eq([t["track"] for t in tags], ["1/3", "2/3", "3/3"], "nummerieren zum Schluss")
    eq(list(notes), [2], "Hinweis: Dateiname passt nicht zum Muster")
    eq(A.describe(steps[3]), "Ersetzen: „(live)“ → „nichts“ · Titel", "Beschreibung eines Schritts")
    eq(A.fill_value("%track% %artist%", {"track": "3/12", "artist": "AC/DC"}), "3 AC/DC",
       "Platzhalter im Wert: Schrägstrich bleibt, Track ohne Gesamtzahl")


def test_replaygain(tmp):
    print("ReplayGain")
    from bub3tagmusic.core import replaygain as rg
    cmd = rg.build_command("rsgain", ["/a/1.mp3", "/a/2.mp3"], rg.MODE_ALBUM, -18, True, False, 3)
    eq(cmd, ["rsgain", "custom", "-q", "-s", "i", "-O", "-l", "-18", "-c", "p", "-I", "3", "-a", "/a/1.mp3",
             "/a/2.mp3"], "Befehl für Album-Gain")
    eq(rg.build_command("rsgain", ["/a/1.mp3"], rg.MODE_SCAN, skip_existing=True)[3:6], ["-s", "s", "-O"],
       "Nur messen: rsgain schreibt nichts (-s s)")
    eq(rg.MODE_SCAN in rg.WRITES, False, "Messen zählt nicht als Schreiben")
    eq(rg.build_command("rsgain", ["/a/1.mp3"], rg.MODE_REMOVE), ["rsgain", "custom", "-q", "-s", "d", "/a/1.mp3"],
       "Befehl zum Entfernen")
    out = ("Filename\tLoudness (LUFS)\tGain (dB)\tPeak\t Peak (dB)\tPeak Type\tClipping Adjustment?\n"
           "01 - A.mp3\t-21.75\t3.75\t0.090820\t-20.84\tSample\tN\n"
           "01 - A.mp3\t-12.00\t-6.00\t0.990000\t-0.09\tSample\tY\n"
           "Album\t-15.00\t-3.00\t0.990000\t-0.09\tSample\tN\n")
    tracks, album = rg.parse_output(out, ["/x/CD1/01 - A.mp3", "/x/CD2/01 - A.mp3"])
    eq(tracks, {"/x/CD1/01 - A.mp3": ("+3.75 dB", "0.090820"), "/x/CD2/01 - A.mp3": ("-6.00 dB", "0.990000")},
       "Ausgabe lesen – auch bei gleichen Dateinamen in Reihenfolge")
    eq(album, ("-3.00 dB", "0.990000"), "Album-Zeile")
    from bub3tagmusic.core.tags import read_replaygain

    class _F:
        tags = {"R128_TRACK_GAIN": ["-1280"], "REPLAYGAIN_ALBUM_GAIN": ["-6.5 dB"]}
    eq(read_replaygain(_F()), {"track": "+0.00 dB", "album": "-6.50 dB"}, "R128 (Opus) umgerechnet")
    exe = rg.rsgain_path()
    if not exe or not shutil.which("ffmpeg"):
        print("   (rsgain oder ffmpeg fehlt – echter Durchlauf übersprungen)")
        return
    import subprocess
    files = []
    for n, ext in enumerate(("flac", "mp3", "ogg"), 1):
        p = os.path.join(tmp, "rg", f"0{n} - Lied.{ext}")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={300 * n}:duration=3",
                        p], check=True)
        files.append(p)
    bad = os.path.join(tmp, "rg", "04 - kaputt.mp3")
    open(bad, "wb").write(b"kein audio" * 100)
    before = os.stat(files[0]).st_mtime_ns
    res = rg.process_album(exe, files + [bad], rg.MODE_ALBUM, keep_mtime=True)
    eq([bool(r.gain) for r in res.files], [True, True, True, False], "kaputte Datei bremst das Album nicht")
    eq(bool(res.gain) and "lesen" in res.files[3].error, True, f"Album-Gain + Fehlertext ({res.files[3].error})")
    eq(os.stat(files[0]).st_mtime_ns, before, "Änderungsdatum bleibt (Einstellung)")
    from bub3tagmusic.core.tags import read_file
    eq(set(read_file(files[1]).get("rg", {})), {"track", "album"}, "Werte stehen in der Datei")
    rg.process_album(exe, files, rg.MODE_REMOVE)
    eq(read_file(files[1]).get("rg"), None, "entfernt")


def test_settings_theme(tmp):
    print("Farben")
    os.environ["XDG_CONFIG_HOME"] = os.path.join(tmp, "cfg_theme")
    from bub3tagmusic.core.settings import Settings
    path = Settings.path()
    json.dump({"theme": "dark", "recursive": True}, open(path, "w"))
    eq(Settings.load().theme, "bub", "altes Standard-Theme (Nachtwache) → neues Standard-Theme")
    json.dump({"theme": "dark", "theme_version": 1}, open(path, "w"))
    eq(Settings.load().theme, "dark", "bewusst gewählte Nachtwache bleibt")
    json.dump({"theme": "light"}, open(path, "w"))
    eq(Settings.load().theme, "light", "Seekarte bleibt")
    eq(Settings().theme, "bub", "neu: Bauen & Booten")
    os.remove(path)


def main():
    tmp = tempfile.mkdtemp()
    try:
        test_filters()
        test_export(tmp)
        test_fingerprint()
        test_duplicates()
        test_tools_external(tmp)
        test_actions(tmp)
        test_replaygain(tmp)
        test_settings_theme(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
