"""Online-Quellen (Phase 3/4).

Die Schnittstellen und gemeinsamen Datentypen stehen schon fest,
damit die Oberfläche später nur noch angeschlossen werden muss.

Regeln:
  * MusicBrainz: höchstens 1 Anfrage pro Sekunde, eigener User-Agent,
    EINE Suche pro Album (Album + Künstler), nicht pro Track.
  * Alle Abfragen laufen im Hintergrund, nie im Oberflächen-Thread.
  * Nichts wird ohne Vorschau und Bestätigung in Dateien übernommen.
"""

from .base import AlbumMatch, CoverCandidate, OnlineError, TrackMatch  # noqa: F401
