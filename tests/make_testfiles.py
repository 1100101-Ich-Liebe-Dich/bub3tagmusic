"""Erzeugt Testdateien – einzeln in allen Formaten oder als ganze Test-Sammlung.

Aufruf:
  python3 tests/make_testfiles.py ZIEL                    nur Formate (ZIEL/formats/test.mp3 …)
  python3 tests/make_testfiles.py ZIEL --collection 60    zusätzlich ZIEL/Musik/Künstler/Jahr - Album/…

Die Sammlung ist realistisch gemischt (immer gleich, weil fest "gewürfelt"):
  * ein Viertel komplett getaggt mit eingebettetem Cover
  * ein Viertel komplett getaggt, aber ohne Cover
  * ein Viertel kaum getaggt (nur Titel = Dateiname)
  * ein Viertel komplett getaggt, mit Cover und cover.jpg im Ordner
Braucht ffmpeg.
"""

from __future__ import annotations

import io
import os
import random
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FORMATS = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "128k"],
    "flac": ["-c:a", "flac"],
    "m4a": ["-c:a", "aac", "-b:a", "96k"],
    "ogg": ["-c:a", "libvorbis"],
    "opus": ["-c:a", "libopus"],
    "wma": ["-c:a", "wmav2"],
    "wav": ["-c:a", "pcm_s16le"],
    "aiff": ["-c:a", "pcm_s16be"],
    "wv": ["-c:a", "wavpack"],
}

BANDS = ["Hafenkapelle", "Die Leuchtfeuer", "Nordwind Orchester", "Sturmflut", "Kielwasser",
         "Möwen & Moneten", "Ankerplatz", "Treibgut", "Die Bojen", "Gezeitenclub", "Salzwasser Soul",
         "Ebbe & Flut", "Kapitän Kurz", "Werftarbeiter", "Seemannsgarn", "Fischkopp", "Brandung",
         "Leinen los", "Flaschenpost", "Dünenblues"]
ALBUMS = ["Ostwind", "Hochsee", "Blaue Stunde", "Reling", "Achtern", "Kurs Nord", "Bilge", "Wellenbrecher"]
TITLES = ["Am Kai", "Nebelhorn", "Letzte Fähre", "Rostiger Rumpf", "Sonnendeck", "Gegen den Wind",
          "Tiefgang", "Heimathafen", "Backbord", "Steuerbord", "Ruhige See", "Mitternachtsfähre",
          "Kombüse", "Landgang", "Lotse", "Mastbruch"]
GENRES = ["Rock", "Indie", "Pop", "Folk", "Jazz", "Electronic"]
COLORS = [(180, 70, 40), (30, 90, 120), (60, 110, 80), (120, 60, 110), (200, 150, 40)]


def make(target: str, seconds: float = 1.0) -> dict[str, str]:
    os.makedirs(target, exist_ok=True)
    out = {}
    for ext, codec in FORMATS.items():
        path = os.path.join(target, f"test.{ext}")
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
               f"sine=frequency=440:duration={seconds}", "-ac", "2", *codec,
               "-map_metadata", "-1", path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            out[ext] = path
        else:
            print(f"  {ext}: ffmpeg kann das nicht erzeugen ({r.stderr.strip()[:80]})")
    return out


def _cover(color) -> bytes:
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (900, 900), color)
    d = ImageDraw.Draw(im)
    ring = tuple(min(255, c + 30) for c in color)
    for i in range(0, 900, 60):
        d.ellipse((450 - i, 450 - i, 450 + i, 450 + i), outline=ring, width=6)
    d.rectangle((0, 760, 900, 900), fill=(20, 20, 24))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def make_collection(target: str, albums: int, templates: dict[str, str], tagged: bool = True) -> int:
    from bub3tagmusic.core.covers import prepare_for_embedding
    from bub3tagmusic.core.tags import write_file

    rnd = random.Random(7)
    exts = [e for e in ("mp3", "flac", "m4a", "ogg", "opus") if e in templates]
    count = 0
    n_artists = max(1, (albums + 2) // 3)
    for a in range(n_artists):
        band = BANDS[a % len(BANDS)] + (f" {a // len(BANDS) + 1}" if a >= len(BANDS) else "")
        for b in range(3):
            if a * 3 + b >= albums:
                break
            year = 1980 + (a + b) % 40
            album = rnd.choice(ALBUMS) + (" II" if b else "")
            folder = os.path.join(target, band, f"{year} - {album}")
            os.makedirs(folder, exist_ok=True)
            ext = exts[(a + b) % len(exts)]
            n_tracks = rnd.randint(8, 16)
            cover = _cover(rnd.choice(COLORS)) if tagged else None
            mode = (a + b) % 4
            embed = prepare_for_embedding(cover, 600) if tagged and mode in (0, 3) else None
            for t in range(n_tracks):
                dst = os.path.join(folder, f"{t + 1:02d} - Song {t + 1}.{ext}")
                shutil.copyfile(templates[ext], dst)
                count += 1
                if not tagged:
                    continue
                if mode == 2:
                    tags = {"title": os.path.splitext(os.path.basename(dst))[0]}
                else:
                    tags = {"title": TITLES[t % len(TITLES)], "artist": band, "albumartist": band,
                            "album": album, "year": str(year), "track": f"{t + 1}/{n_tracks}",
                            "genre": GENRES[a % len(GENRES)]}
                write_file(dst, tags, embed, {"id3_version": 3})
            if tagged and mode == 3:
                with open(os.path.join(folder, "cover.jpg"), "wb") as fh:
                    fh.write(cover)
    return count


if __name__ == "__main__":
    dest = sys.argv[1]
    files = make(os.path.join(dest, "formats"))
    print("Formate:", ", ".join(sorted(files)))
    if "--collection" in sys.argv:
        n = int(sys.argv[sys.argv.index("--collection") + 1])
        c = make_collection(os.path.join(dest, "Musik"), n, files, tagged="--untagged" not in sys.argv)
        print(f"Sammlung: {n} Alben, {c} Dateien")
