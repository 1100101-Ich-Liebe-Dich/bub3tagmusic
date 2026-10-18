"""Audio-Fingerabdrücke über fpcalc (Chromaprint) – für AcoustID und die Duplikat-Suche.

* fpcalc wird gesucht: mitgeliefert (AppImage), dann im System (PATH)
* EIN Aufruf pro Datei liefert den Roh-Fingerabdruck; die kompakte Form für
  AcoustID wird hier selbst berechnet (gleiches Verfahren wie Chromaprint)
* Vergleich zweier Roh-Fingerabdrücke: Anteil gleicher Bits, mit kleiner Verschiebung
"""

from __future__ import annotations

import array
import base64
import json
import subprocess
import sys

from .tools_external import find_tool

FPCALC_LENGTH = 120          # Sekunden – reicht für AcoustID und Duplikate


class FingerprintError(Exception):
    pass


def fpcalc_path() -> str:
    return find_tool("fpcalc")


def fingerprint(path: str, length: int = FPCALC_LENGTH, exe: str = "") -> tuple[float, list[int]]:
    """(Dauer in Sekunden, Roh-Fingerabdruck als Liste von 32-Bit-Zahlen)."""
    exe = exe or fpcalc_path()
    if not exe:
        raise FingerprintError("fpcalc fehlt")
    try:
        r = subprocess.run([exe, "-raw", "-json", "-length", str(length), path], capture_output=True,
                           text=True, timeout=120, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise FingerprintError("fpcalc braucht zu lange für diese Datei") from exc
    except OSError as exc:
        raise FingerprintError(f"fpcalc lässt sich nicht starten: {exc.strerror or exc}") from exc
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()
        msg = msg[-1] if msg else f"Fehler {r.returncode}"
        if "Empty fingerprint" in msg:
            msg = "zu kurz oder still – kein Fingerabdruck möglich"
        elif msg.startswith("ERROR: "):
            msg = msg[7:]
        raise FingerprintError(msg)
    try:
        data = json.loads(r.stdout)
        fp = [int(x) & 0xFFFFFFFF for x in data["fingerprint"]]
        return float(data.get("duration") or 0), fp
    except (ValueError, KeyError, TypeError) as exc:
        raise FingerprintError("Unerwartete Ausgabe von fpcalc") from exc


# ----------------------------------------------------------------------
# Kompakte Form (wie chromaprint_encode_fingerprint, base64 ohne Polster)
# ----------------------------------------------------------------------
def _pack(values: list[int], bits: int) -> bytes:
    out = bytearray()
    acc = n = 0
    mask = (1 << bits) - 1
    for v in values:
        acc |= (v & mask) << n
        n += bits
        while n >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            n -= 8
    if n:
        out.append(acc & 0xFF)
    return bytes(out)


def compress(fp: list[int], algorithm: int = 1) -> str:
    """Roh-Fingerabdruck → Zeichenkette, wie fpcalc sie ohne -raw ausgibt (für AcoustID)."""
    normal: list[int] = []
    exceptional: list[int] = []
    prev = 0
    for i, value in enumerate(fp):
        x = value if i == 0 else (value ^ prev)
        prev = value
        bit, last = 1, 0
        while x:
            if x & 1:
                d = bit - last
                normal.append(min(d, 7))
                if d >= 7:
                    exceptional.append(d - 7)
                last = bit
            x >>= 1
            bit += 1
        normal.append(0)
    size = len(fp)
    head = bytes([algorithm & 0xFF, (size >> 16) & 0xFF, (size >> 8) & 0xFF, size & 0xFF])
    raw = head + _pack(normal, 3) + _pack(exceptional, 5)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


# ----------------------------------------------------------------------
# Vergleich
# ----------------------------------------------------------------------
def similarity(a, b, max_offset: int = 10, limit: int = 400) -> float:
    """0..1 – Anteil gleicher Bits bei bester Verschiebung. Gleiche Aufnahme ≈ 0,95–1, fremde ≈ 0,5–0,7."""
    a, b = list(a[:limit]), list(b[:limit])
    if not a or not b:
        return 0.0
    best = 0.0
    for off in range(-max_offset, max_offset + 1):
        if off >= 0:
            pairs = zip(a[off:], b)
        else:
            pairs = zip(a, b[-off:])
        errors = n = 0
        for x, y in pairs:
            errors += (x ^ y).bit_count()
            n += 1
        if n < 30:
            continue
        best = max(best, 1.0 - errors / (32.0 * n))
    return best


def to_blob(fp: list[int]) -> bytes:
    arr = array.array("I", fp)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr.tobytes()


def from_blob(blob: bytes) -> list[int]:
    arr = array.array("I")
    arr.frombytes(blob)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr.tolist()

