"""Fahrplan als Daten: alle Funktionen der späteren Phasen.

Die Oberfläche baut ihre Menüs "Werkzeuge", "Online" und "Extras" aus
dieser Liste. Solange eine Funktion noch nicht fertig ist, öffnet ein
Klick einen kurzen Hinweis "Kommt in Phase X".

Wenn eine Funktion fertig ist: `ready=True` setzen und in
ui/mainwindow.py unter FEATURE_HANDLERS die Methode eintragen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    phase: int
    group: str            # "tools" | "online" | "extras"
    icon: str             # Phosphor-Icon-Name (qtawesome "ph.")
    description: str
    shortcut: str = ""
    ready: bool = False


FEATURES: tuple[Feature, ...] = (
    # --- Phase 2: Werkzeuge ----------------------------------------------
    Feature("tags_from_filename", "Tags aus Dateiname …", 2, "tools", "tag",
            "Füllt Titel, Track & Co. aus dem Dateinamen oder Ordnernamen, "
            "z. B. mit dem Muster %track% - %title%. Mit Vorschau vor dem Übernehmen.",
            "Alt+1", ready=True),
    Feature("filename_from_tags", "Dateinamen aus Tags …", 2, "tools", "swap",
            "Benennt Dateien nach einem Muster um, z. B. 01 - Titel.flac. "
            "Erst Vorschau, dann umbenennen – rückgängig machbar.", "Alt+2", ready=True),
    Feature("autonumber", "Tracks automatisch nummerieren", 2, "tools", "list-numbers",
            "Vergibt Tracknummern pro Ordner in der aktuellen Reihenfolge, "
            "auf Wunsch mit Gesamtzahl (3/12) und Disc-Nummer.", "Alt+3", ready=True),
    Feature("case", "Groß-/Kleinschreibung …", 2, "tools", "text-aa",
            "Macht aus 'DER TITEL' oder 'der titel' sauber 'Der Titel' – "
            "für ausgewählte Felder.", "Alt+4", ready=True),
    Feature("replace", "Suchen & Ersetzen …", 2, "tools", "magnifying-glass",
            "Text in ausgewählten Feldern ersetzen, auf Wunsch mit regulären Ausdrücken.",
            "Alt+5", ready=True),
    Feature("folder_rename", "Ordner umbenennen …", 2, "tools", "folders",
            "Benennt Album-Ordner nach ihren Tags um, z. B. %year% - %album%. Alles im Ordner bleibt "
            "beisammen; der Fertig-Status wandert mit.", "Alt+6", ready=True),
    Feature("cleanup", "Aufräumen …", 2, "tools", "lightning",
            "Doppelte Leerzeichen, Leerzeichen am Rand und störende Sonderzeichen entfernen.", ready=True),

    # --- Phase 3: Online ---------------------------------------------------
    Feature("musicbrainz", "Album suchen – MusicBrainz", 3, "online", "disc",
            "Eine Suche pro Album mit Album + Künstler. Treffer mit Trackliste, Jahr, "
            "Label und Cover; Übernahme erst nach deiner Bestätigung.", "Ctrl+L"),
    Feature("discogs", "Album suchen – Discogs", 3, "online", "disc",
            "Zweite Quelle für Album-Daten. Braucht einen kostenlosen Discogs-Token "
            "(Einstellungen → Online)."),
    Feature("cover_search", "Cover suchen …", 3, "online", "image-square",
            "Sucht bei Cover Art Archive, iTunes und Deezer. Treffer als Bildergitter "
            "mit Auflösung; speichern als cover.jpg und/oder einbetten.", "Ctrl+K"),
    Feature("artist_image", "Künstlerbild suchen …", 3, "online", "user-circle",
            "Sucht ein Künstlerfoto und legt es als folder.jpg im Künstler-Ordner ab."),

    # --- Phase 4: Extras ---------------------------------------------------
    Feature("actions", "Aktionen …", 4, "extras", "lightning",
            "Mehrere Schritte als Aktion speichern (z. B. Aufräumen + Schreibweise + "
            "Umbenennen) und mit einem Klick ausführen."),
    Feature("acoustid", "Unbekannte Dateien erkennen", 4, "extras", "fingerprint",
            "Erkennt Titel ohne Tags per Audio-Fingerabdruck (AcoustID)."),
    Feature("replaygain", "ReplayGain berechnen", 4, "extras", "sliders-horizontal",
            "Gleicht die Lautstärke an – pro Track und pro Album (über rsgain)."),
    Feature("duplicates", "Duplikate finden", 4, "extras", "copy",
            "Findet doppelte Titel in der Sammlung, nach Tags oder Fingerabdruck."),
    Feature("export", "Liste exportieren …", 4, "extras", "download-simple",
            "Exportiert die aktuelle Liste als CSV oder HTML."),
    Feature("filters", "Erweiterte Filter", 4, "extras", "funnel",
            "Schnellfilter wie 'ohne Cover', 'ohne Jahr', 'Cover kleiner als 500 px'."),
)

GROUP_TITLES = {"tools": "Werkzeuge", "online": "Online", "extras": "Extras"}


def by_group(group: str) -> list[Feature]:
    return [f for f in FEATURES if f.group == group]


def get(feature_id: str) -> Feature:
    return next(f for f in FEATURES if f.id == feature_id)
