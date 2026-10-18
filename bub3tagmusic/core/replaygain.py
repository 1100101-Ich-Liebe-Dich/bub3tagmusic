"""ReplayGain (Phase 4) über das externe Programm rsgain.

* Ein Album = ein Ordner: alle Dateien eines Ordners werden in EINEM Aufruf
  gemessen (nur so stimmt der Album-Gain).
* Kann rsgain eine Datei nicht lesen, bricht es das ganze Album ab. Dann wird
  jede Datei einzeln geprüft, die kaputte gemeldet und der Rest normal gemessen.
* rsgain schreibt die Tags selbst (ReplayGain 2.0). Audiodaten bleiben unberührt.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from .tools_external import find_tool

MODE_ALBUM, MODE_TRACK, MODE_REMOVE = "album", "track", "remove"
TARGETS = (
    (-18, "−18 LUFS – ReplayGain 2.0 (Standard)"),
    (-23, "−23 LUFS – EBU R128 (Rundfunk)"),
    (-14, "−14 LUFS – wie Streamingdienste"),
)
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class Result:
    path: str
    gain: str = ""          # Track-Gain, z. B. "-7.21 dB"
    peak: str = ""
    error: str = ""


@dataclass
class AlbumResult:
    folder: str
    files: list[Result]
    gain: str = ""          # Album-Gain
    peak: str = ""
    error: str = ""         # Fehler, der das ganze Album betrifft
    cancelled: bool = False

    @property
    def errors(self) -> list[tuple[str, str]]:
        out = [(r.path, r.error) for r in self.files if r.error]
        if self.error and not out:
            out.append((self.folder, self.error))
        return out


def rsgain_path() -> str:
    return find_tool("rsgain")


def build_command(exe: str, files: list[str], mode: str, target: int = -18, clip: bool = True,
                  skip_existing: bool = False, id3v2: int = 3) -> list[str]:
    cmd = [exe, "custom", "-q"]
    if mode == MODE_REMOVE:
        return cmd + ["-s", "d", *files]
    cmd += ["-s", "i", "-O", "-l", str(int(target)), "-c", "p" if clip else "n", "-I", str(id3v2)]
    if mode == MODE_ALBUM:
        cmd.append("-a")
    if skip_existing:
        cmd.append("-S")
    return cmd + list(files)


def parse_output(text: str, files: list[str]) -> tuple[dict[str, tuple[str, str]], tuple[str, str] | None]:
    """Tabulator-Ausgabe von rsgain (-O) → ({pfad: (gain, peak)}, (album_gain, album_peak) | None).

    Spalten: Filename, Loudness (LUFS), Gain (dB), Peak, Peak (dB), Peak Type, Clipping Adjustment?
    Die Dateinamen stehen ohne Ordner da – zugeordnet wird über den Namen (in der Reihenfolge).
    """
    by_name: dict[str, list[str]] = {}
    for p in files:
        by_name.setdefault(os.path.basename(p), []).append(p)
    out: dict[str, tuple[str, str]] = {}
    album = None
    for line in _ANSI.sub("", text).splitlines():
        cols = line.split("\t")
        if len(cols) < 4 or cols[0] == "Filename":
            continue
        name, gain, peak = cols[0], cols[2].strip(), cols[3].strip()
        try:
            g = f"{float(gain):+.2f} dB"
        except ValueError:
            continue
        if name == "Album" and "Album" not in by_name:
            album = (g, peak)
            continue
        cands = by_name.get(name) or by_name.get(os.path.basename(name)) or []
        target = next((c for c in cands if c not in out), None)
        if target:
            out[target] = (g, peak)
    return out, album


def _run(cmd: list[str], cancelled: Callable[[], bool], timeout: float) -> tuple[int, str, str, bool]:
    """Startet rsgain; bricht bei Abbruch ab. → (exit, stdout, stderr, abgebrochen)."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                text=True, errors="replace")
    except OSError as exc:
        return 127, "", f"rsgain lässt sich nicht starten: {exc.strerror or exc}", False
    start = time.monotonic()
    while True:
        try:
            out, err = proc.communicate(timeout=0.3)
            return proc.returncode, out, err, False
        except subprocess.TimeoutExpired:
            if cancelled() or time.monotonic() - start > timeout:
                proc.kill()
                out, err = proc.communicate()
                return -9, out, err, cancelled()


def _message(stderr: str, code: int) -> str:
    lines = [ln.strip() for ln in _ANSI.sub("", stderr).splitlines() if ln.strip()]
    msg = lines[-1] if lines else f"rsgain meldet Fehler {code}"
    msg = re.sub(r"^\[?[✘✔!xX]\]?\s*", "", msg)
    if "Could not open input" in msg:
        return "Datei lässt sich nicht lesen (beschädigt oder kein Audio)"
    if "Permission denied" in msg or "permission" in msg.lower():
        return "Keine Schreibrechte für diese Datei"
    return msg


def process_album(exe: str, files: list[str], mode: str = MODE_ALBUM, *, target: int = -18, clip: bool = True,
                  skip_existing: bool = False, id3v2: int = 3, keep_mtime: bool = False,
                  cancelled: Callable[[], bool] = lambda: False) -> AlbumResult:
    folder = os.path.dirname(files[0]) if files else ""
    res = AlbumResult(folder, [Result(p) for p in files])
    mtimes = {}
    if keep_mtime:
        for p in files:
            try:
                st = os.stat(p)
                mtimes[p] = (st.st_atime_ns, st.st_mtime_ns)
            except OSError:
                pass
    timeout = 120 + 60 * len(files)

    def run(paths):
        return _run(build_command(exe, paths, mode, target, clip, skip_existing, id3v2), cancelled, timeout)

    code, out, err, stopped = run(files)
    if stopped:
        res.cancelled = True
        return res
    if code != 0 and len(files) > 1:
        # eine kaputte Datei bremst das Album: einzeln prüfen, dann ohne sie nochmal
        good = []
        for r in res.files:
            if cancelled():
                res.cancelled = True
                return res
            check = [exe, "custom", "-q", "-s", "s", r.path] if mode != MODE_REMOVE else \
                build_command(exe, [r.path], MODE_REMOVE)
            c, _o, e, _s = _run(check, cancelled, timeout)
            if c != 0:
                r.error = _message(e, c)
            else:
                good.append(r.path)
        if good:
            code, out, err, stopped = run(good)
            if stopped:
                res.cancelled = True
                return res
        else:
            code, out, err = 0, "", ""
    if code != 0:
        msg = _message(err, code)
        for r in res.files:
            r.error = r.error or msg
        res.error = msg
    elif mode != MODE_REMOVE:
        tracks, album = parse_output(out, [r.path for r in res.files if not r.error])
        for r in res.files:
            if r.path in tracks:
                r.gain, r.peak = tracks[r.path]
        if album and mode == MODE_ALBUM:
            res.gain, res.peak = album
    for p, (at, mt) in mtimes.items():
        try:
            os.utime(p, ns=(at, mt))
        except OSError:
            pass
    return res
