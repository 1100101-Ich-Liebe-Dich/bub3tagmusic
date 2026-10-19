"""Aufgezeichnete Online-Antworten abspielen (für Tests ohne Internet).

    from online_fixtures import use_fixtures
    use_fixtures()          # ab jetzt beantwortet bub3tagmusic.online alles aus tests/fixtures/online

Unbekannte Adressen bekommen 404 – genau wie ein Dienst, der nichts findet.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
FIXTURES = os.path.join(HERE, "fixtures", "online")

# Die aufgezeichneten Suchen (record_online.py und die Tests benutzen dieselben)
ALBUMS = [
    ("AC/DC", "Back in Black"),
    ("Die Ärzte", "Die Bestie in Menschengestalt"),
    ("Pink Floyd", "The Wall"),
]
ARTISTS = ["AC/DC", "Die Ärzte"]
DISCOGS_RELEASES = ["249504", "1"]
# Deezer (1.1): die ALBUMS oben + ein Album mit Remaster-Zusätzen in den Titeln
DEEZER_ALBUMS = [("The Beatles", "Abbey Road")]


def load_index() -> dict:
    path = os.path.join(FIXTURES, "index.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def available() -> bool:
    return bool(load_index())


def use_fixtures(record_misses: list | None = None):
    from bub3tagmusic.online import http
    index = load_index()

    def transport(url, headers):
        name = index.get(url)
        if name is None:
            if record_misses is not None:
                record_misses.append(url)
            return 404, b""
        with open(os.path.join(FIXTURES, name), "rb") as fh:
            return 200, fh.read()

    http.set_transport(transport)
    return index
