"""Erzeugt kurze Testdateien in allen Formaten, die ffmpeg schreiben kann.

Aufruf: python3 tests/make_testfiles.py ZIELORDNER [--collection N]
  --collection N  baut zusätzlich eine Test-Sammlung Künstler/Album/Tracks
                  mit N Alben (für Leistungstests, Dateien werden kopiert).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

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


def make_collection(target: str, albums: int, templates: dict[str, str]) -> int:
    import random
    random.seed(7)
    exts = ["mp3", "flac", "m4a", "ogg", "opus"]
    count = 0
    artists = max(1, albums // 3)
    for a in range(artists):
        artist = f"Künstler {a + 1:03d}"
        for b in range(3):
            if a * 3 + b >= albums:
                break
            album = os.path.join(target, artist, f"Album {b + 1} ({1980 + (a + b) % 40})")
            os.makedirs(album, exist_ok=True)
            ext = exts[(a + b) % len(exts)]
            for t in range(random.randint(8, 16)):
                dst = os.path.join(album, f"{t + 1:02d} - Song {t + 1}.{ext}")
                shutil.copyfile(templates[ext], dst)
                count += 1
    return count


if __name__ == "__main__":
    dest = sys.argv[1]
    files = make(os.path.join(dest, "formats"))
    print("Formate:", ", ".join(sorted(files)))
    if "--collection" in sys.argv:
        n = int(sys.argv[sys.argv.index("--collection") + 1])
        c = make_collection(os.path.join(dest, "Musik"), n, files)
        print(f"Sammlung: {n} Alben, {c} Dateien")
