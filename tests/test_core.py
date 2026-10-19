"""Kern-Tests: Lesen, Schreiben, Cover, ID3-Version, Muster, Cache.

Aufruf: python3 tests/test_core.py
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from bub3tagmusic.core import patterns  # noqa: E402
from bub3tagmusic.core.cache import Cache  # noqa: E402
from bub3tagmusic.core.covers import prepare_for_embedding  # noqa: E402
from bub3tagmusic.core.scanner import list_audio, load_records, scan_tree  # noqa: E402
from bub3tagmusic.core.tags import COVER_REMOVE, read_cover, read_file, write_file  # noqa: E402
from make_testfiles import make  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("   FEHLER:", msg)


def png_bytes(size=1200, color=(255, 120, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, "PNG")
    return buf.getvalue()


def main():
    tmp = tempfile.mkdtemp(prefix="bub3test_")
    files = make(os.path.join(tmp, "formats"))
    changes = {
        "title": "Größenwahn – Über Äpfel", "artist": "Die Ärzte; Gast", "albumartist": "Die Ärzte",
        "album": "Jazz ist anders", "year": "2007", "track": "3/12", "disc": "1/2",
        "genre": "Deutschrock", "composer": "Farin Urlaub", "comment": "Test-Kommentar",
        "label": "Hot Action Records", "originalyear": "1987",
        "lyrics": "Erste Zeile – Äpfel\nZweite Zeile\n\nRefrain: Ölkanne",
    }
    cover = prepare_for_embedding(png_bytes(), max_size=600)
    check(cover.mime == "image/jpeg", "großes PNG wird zu JPEG verkleinert")

    for ext, path in files.items():
        print(f"-- {ext}")
        rec = read_file(path)
        check(not rec["error"], f"{ext}: leere Datei lesbar ({rec['error']})")
        rec = write_file(path, changes, cover, {"id3_version": 3})
        check(not rec["error"], f"{ext}: nach Schreiben lesbar ({rec['error']})")
        for k, v in changes.items():
            got = rec["tags"].get(k)
            if ext == "wma" and k == "artist":
                pass
            check(got == v, f"{ext}: {k} = {got!r}, erwartet {v!r}")
        check(rec["cover"] and rec["cover"]["w"] == 600, f"{ext}: Cover 600px eingebettet ({rec['cover']})")
        c = read_cover(path)
        check(c is not None and c.data == cover.data, f"{ext}: Cover-Bytes identisch")

        # Nur ein Feld ändern – die anderen müssen bleiben
        rec = write_file(path, {"title": "Neu"}, None, {"id3_version": 3})
        check(rec["tags"]["title"] == "Neu" and rec["tags"]["album"] == changes["album"],
              f"{ext}: einzelnes Feld ändern lässt Rest in Ruhe")
        # Feld löschen
        rec = write_file(path, {"comment": "", "track": "5"}, None, {})
        check(rec["tags"]["comment"] == "", f"{ext}: Kommentar gelöscht")
        check(rec["tags"]["track"] == "5", f"{ext}: Track ohne Gesamtzahl = {rec['tags']['track']!r}")
        # Cover entfernen
        rec = write_file(path, {}, COVER_REMOVE, {})
        check(rec["cover"] is None, f"{ext}: Cover entfernt")
        # Neue Felder (1.1) einzeln ändern und leeren
        rec = write_file(path, {"lyrics": "Nur eine Zeile", "label": ""}, None, {"id3_version": 4})
        check(rec["tags"]["lyrics"] == "Nur eine Zeile" and rec["tags"]["label"] == ""
              and rec["tags"]["originalyear"] == "1987", f"{ext}: Songtext/Label ändern ({rec['tags']})")
        rec = write_file(path, {"originalyear": "", "lyrics": ""}, None, {"id3_version": 3})
        check(rec["tags"]["originalyear"] == "" and rec["tags"]["lyrics"] == "",
              f"{ext}: Original-Jahr + Songtext geleert")

    interop(tmp)

    if "mp3" in files:
        with open(files["mp3"], "rb") as fh:
            head = fh.read(10)
        check(head[:3] == b"ID3" and head[3] == 3, f"mp3: ID3v2.3 geschrieben (Version {head[3]})")
        write_file(files["mp3"], {"title": "v24"}, None, {"id3_version": 4})
        with open(files["mp3"], "rb") as fh:
            check(fh.read(4)[3] == 4, "mp3: ID3v2.4 wählbar")

    # keep_mtime
    p = files["flac"]
    os.utime(p, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    write_file(p, {"title": "zeit"}, None, {"keep_mtime": True})
    check(os.stat(p).st_mtime_ns == 1_000_000_000_000_000_000, "Änderungsdatum beibehalten")

    # Muster (Phase-2-Baustein)
    check(patterns.format_from_tags("%track% - %artist% - %title%",
                                    {"track": "3/12", "artist": "AC/DC", "title": "T.N.T."})
          == "03 - AC_DC - T.N.T", "Muster: Dateiname aus Tags")
    check(patterns.parse_with_pattern("%track% - %title%", "07 - Ein Lied - Live")
          == {"track": "07", "title": "Ein Lied - Live"}, "Muster: Tags aus Dateiname")

    # Scanner + Cache
    col = os.path.join(tmp, "Musik", "Band", "Album")
    os.makedirs(col)
    for ext, src in files.items():
        shutil.copy(src, os.path.join(col, f"{ext}.{ext}"))
    tree = scan_tree(os.path.join(tmp, "Musik"))
    check(tree.total_count == len(files), f"Baum zählt {tree.total_count} Dateien")
    paths = list_audio([os.path.join(tmp, "Musik")], recursive=True)
    check(len(paths) == len(files), "rekursive Liste")
    check(list_audio([os.path.join(tmp, "Musik")], recursive=False) == [], "nicht rekursiv = leer")
    cache = Cache(os.path.join(tmp, "cache.sqlite"))
    recs = load_records(paths, cache)
    check(len(recs) == len(files), "alle eingelesen")
    hits = cache.get_many({r["path"]: (r["mtime"], r["size"]) for r in recs})
    check(len(hits) == len(files), "Cache gefüllt")

    shutil.rmtree(tmp)
    print()
    print("ALLES OK" if not FAILS else f"{len(FAILS)} Fehler")
    return 1 if FAILS else 0


def interop(tmp):
    """Tags, wie Picard/Mp3tag sie schreiben, werden erkannt – und beim Ändern ohne Reste ersetzt."""
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, TORY, TXXX, USLT
    from mutagen.mp4 import MP4, MP4FreeForm
    files = make(os.path.join(tmp, "interop"))
    print("-- Fremde Schreibweisen")
    f = FLAC(files["flac"])
    f["ORIGINALDATE"] = ["1977-05-25"]
    f["ORIGINALYEAR"] = ["1977"]
    f["ORGANIZATION"] = ["Harvest"]
    f["UNSYNCEDLYRICS"] = ["Zeile 1\r\nZeile 2"]
    f.save()
    t = read_file(files["flac"])["tags"]
    check(t["originalyear"] == "1977-05-25" and t["label"] == "Harvest", f"flac: Picard-Felder gelesen ({t})")
    check(t["lyrics"] == "Zeile 1\nZeile 2", f"flac: Zeilenenden vereinheitlicht ({t['lyrics']!r})")
    write_file(files["flac"], {"originalyear": "1978"}, None, {})
    f = FLAC(files["flac"])
    check(f.get("ORIGINALDATE") == ["1978"] and "ORIGINALYEAR" not in f, "flac: Original-Jahr ohne Reste ersetzt")

    id3 = ID3()
    id3.add(TORY(encoding=3, text=["1969"]))
    id3.add(USLT(encoding=3, lang="deu", desc="", text="Hallo"))
    id3.save(files["mp3"], v2_version=3)
    t = read_file(files["mp3"])["tags"]
    check(t["originalyear"] == "1969" and t["lyrics"] == "Hallo", f"mp3: TORY + USLT gelesen ({t})")
    write_file(files["mp3"], {"lyrics": "Neu"}, None, {"id3_version": 3})
    id3 = ID3(files["mp3"])
    check([fr.lang for fr in id3.getall("USLT")] == ["deu"], "mp3: Songtext-Sprache bleibt")
    id3 = ID3(files["mp3"])
    id3.delall("TORY")
    id3.delall("TDOR")           # mutagen macht beim Laden aus TORY schon TDOR
    id3.add(TXXX(encoding=3, desc="originalyear", text=["1970"]))
    id3.save(v2_version=4)
    check(read_file(files["mp3"])["tags"]["originalyear"] == "1970", "mp3: TXXX:originalyear gelesen")
    write_file(files["mp3"], {"originalyear": "1971"}, None, {"id3_version": 4})
    id3 = ID3(files["mp3"])
    check(not id3.getall("TXXX") and str(id3["TDOR"].text[0]) == "1971", "mp3: Original-Jahr als TDOR")
    write_file(files["mp3"], {"title": "x"}, None, {"id3_version": 3})
    id3 = ID3(files["mp3"], translate=False)
    check("TORY" in id3 and str(id3["TORY"].text[0]) == "1971", "mp3: v2.3 speichert TORY")
    check(read_file(files["mp3"])["tags"]["originalyear"] == "1971", "mp3: TORY wieder gelesen")

    m = MP4(files["m4a"])
    m["----:com.apple.iTunes:ORIGINALYEAR"] = [MP4FreeForm(b"1999")]
    m.save()
    check(read_file(files["m4a"])["tags"]["originalyear"] == "1999", "m4a: ORIGINALYEAR gelesen")
    write_file(files["m4a"], {"originalyear": "2000"}, None, {})
    m = MP4(files["m4a"])
    check("----:com.apple.iTunes:ORIGINALYEAR" not in m and
          bytes(m["----:com.apple.iTunes:ORIGINALDATE"][0]) == b"2000", "m4a: Original-Jahr ohne Reste ersetzt")

    check("lyrics" not in patterns.KNOWN and "label" in patterns.KNOWN, "Songtext ist kein Muster-Platzhalter")


if __name__ == "__main__":
    sys.exit(main())
