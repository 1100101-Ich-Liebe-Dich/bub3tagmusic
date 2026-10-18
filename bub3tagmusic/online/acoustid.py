"""Erkennung unbekannter Dateien per Audio-Fingerabdruck (Phase 4).

Braucht das Programm `fpcalc` (Paket chromaprint / libchromaprint-tools)
und einen kostenlosen AcoustID-Key.
"""

from __future__ import annotations


def identify(path: str, api_key: str) -> list[dict]:
    raise NotImplementedError("Kommt in Phase 4")
