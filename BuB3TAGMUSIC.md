# BuB3TAGMUSIC

**Moderner, schneller Musik-Tagger für Linux**
präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de)

> **Aktueller Stand:** Version 0.1.2 – **Phase 1 fertig, als eine ausführbare Datei (AppImage)** (18.10.2026).
> Nächster Schritt: Phase 1 an einer Kopie der echten Sammlung testen, dann Phase 2.
>
> Code + Aufgaben: privates GitHub-Repo `1100101-Ich-Liebe-Dich/bub3tagmusic`.
> Die Nummern `#n` im Fahrplan sind die zugehörigen GitHub-Aufgaben (mit Abnahmekriterien).

---

## 1. Ziel

Ein Tagger mit mindestens dem Kern-Funktionsumfang von Mp3tag, aber:

- **modern im Design**, schlicht und auf den ersten Blick verständlich
- **schnell**, auch auf alter Hardware und mit zehntausenden Dateien
- **auf Ordner-Arbeit ausgelegt**: Sammlung Ordner für Ordner zügig durchtaggen
- **stabil zuerst**, danach Schritt für Schritt erweitern

---

## 2. Grundsatz-Entscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Plattform | Linux | Zielsystem |
| Sprache | Python 3.10+ | schnelle Entwicklung, starke Bibliotheken |
| Oberfläche | Qt 6 über PySide6 (nur „Essentials“-Paket) | läuft flüssig auf alter Hardware, schlank |
| Tag-Bibliothek | mutagen | Standard unter Linux (auch von Picard genutzt), alle wichtigen Formate |
| Bilder | Pillow | Cover skalieren, konvertieren, prüfen |
| Zwischenspeicher | SQLite | Tags + Änderungsdatum merken, große Ordner öffnen fast sofort |
| Einlesen | mehrere CPU-Kerne ab 150 neuen Dateien | erstes Einlesen großer Ordner deutlich schneller |
| Icons | Phosphor (über qtawesome) | modern, einheitlich, in beiden Themes einfärbbar |
| Online-Abfragen | im Hintergrund, mit Wartezeit-Regel | Oberfläche friert nie ein (Phase 3) |
| Auslieferung | **AppImage** – eine Datei, ausführbar machen, starten; selbst bauen mit `make` | Wunsch: keine Installation |
| AppImage-Inhalt | eigenes Python 3.12 + Qt 6.9 (feste Versionen), Qt verschlankt (59 MB) | läuft ab glibc 2.28 (Ubuntu 20.04, Mint 20, Debian 10, Fedora 29) |
| Für Entwickler | `install.sh` → `.venv` im Programmordner, `start.sh` | Arbeiten direkt am Quellcode |

### Unterstützte Formate

MP3 (ID3v1, ID3v2.3, ID3v2.4), FLAC, M4A/AAC/ALAC, OGG Vorbis, Opus, WMA, WAV, AIFF, APE, WavPack, DSF

Getestet (Lesen, Schreiben mit Umlauten, Cover einbetten/entfernen): MP3, FLAC, M4A, OGG, Opus, WMA, WAV, AIFF, WavPack.
APE und DSF laufen über denselben Code wie WavPack bzw. MP3, konnten aber mangels Testdateien noch nicht geprüft werden.

---

## 3. Sammlungs-Struktur & Bild-Konvention

```
Musik/
├── Künstler A/
│   ├── folder.jpg          ← Künstlerbild
│   ├── Album 1/
│   │   ├── cover.jpg       ← Albumcover
│   │   ├── 01 - Titel.flac
│   │   └── 02 - Titel.flac
│   └── Album 2/
│       ├── cover.jpg
│       └── ...
└── Künstler B/
    └── ...
```

**Festgelegt:**
- `folder.jpg` im **Künstler-Ordner** = Künstlerbild
- `cover.jpg` im **Album-Ordner** = Albumcover
- Dateinamen in den Einstellungen änderbar
- Bearbeitung auf jeder Ebene: ganze Sammlung, Künstler, einzelnes Album oder einzelner Track
- „Album-Ordner“ = jeder Ordner, der direkt Musikdateien enthält

---

## 4. Oberfläche (so umgesetzt)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ BuB3TAGMUSIC [Sammlung öffnen][Unterordner][⟳] [Filter…] Werkzeuge Online Extras │ ↶ [Speichern (5)] ⚙ │
├──────────────┬──────────────────────────────────────┬───────────────────────┤
│ Musik        │ ● Dateiname    Titel    Interpret …  │ 14 Dateien ausgewählt │
│ 12 von 340   │ ● 01 - …       Am Kai   Band X       │ [COVER]  Cover eingebettet
│ ▬▬▬▬───────  │   02 - …       …                     │          600×600 · JPG
│ ▾ Künstler 2/3                                      │          [Bild laden][Aus Ordner][Weitere]
│   ◎ Album ✓  │                                      │ Titel    ‹verschieden›│
│   ◎ Album ○  │                                      │ Interpret Band X      │
│              │                                      │ …                     │
│              │                                      │ [Speichern & nächster Ordner] │
├──────────────┴──────────────────────────────────────┴───────────────────────┤
│ 14 Dateien  14 ausgewählt  5 ungespeichert        präsentiert von www.BAUENUNDBOOTEN.de │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Links: Ordnerbaum** mit Fortschrittsbalken („x von y Alben fertig“). Alben zeigen ✓ (fertig) oder ○ (offen),
  Künstler zeigen „2/3“. Status steht im Cache, nicht in den Musikdateien.
- **Mitte: Dateiliste** – sortierbar (3. Klick = Ordner-Reihenfolge), Spalten per Rechtsklick ein/aus,
  Zellen per Doppelklick/F2 bearbeitbar. Gelber Punkt = ungespeichert, roter Punkt = Lesefehler,
  geänderte Werte in Gelb mit „Vorher: …“ als Tooltip.
- **Rechts: Bearbeitungsfeld** – `‹verschieden›` bei unterschiedlichen Werten, gelber Rahmen bei geänderten Feldern,
  × leert ein Feld für alle gewählten Dateien, Esc verwirft Getipptes.
- **Unten: Statusleiste** mit Zählern und „präsentiert von www.BAUENUNDBOOTEN.de“.

### Design

| Thema | Entscheidung |
|---|---|
| Dunkles Theme „Nachtwache“ | tiefes Hafenblau `#121B24`, Flächen `#172230` |
| Helles Theme „Seekarte“ | Kartenpapier `#E8EDF1`, Flächen `#F5F8FA` |
| Akzentfarbe | Bojen-Orange `#FF8A2A` (hell: `#E26C0B`) |
| Status-Farben | fertig Grün `#3FCB8D`, ungespeichert Gelb `#F4C453`, Fehler Rot `#FF6B6B` |
| Logo-Schrift | Big Shoulders Stencil (Schablonen-Schrift wie Rumpf-Beschriftung auf der Werft) |
| Text-Schrift | Inter (mitgeliefert, sieht auf jeder Distribution gleich aus) |
| App-Icon | Rettungsring in Orange/Weiß – erinnert zugleich an eine Schallplatte |

### Kern-Arbeitsablauf: „Speichern & nächster Ordner“

1. Album im Baum anklicken → Dateien laden und sind sofort alle ausgewählt
2. Rechts gemeinsame Felder setzen, Cover reinziehen oder „Aus Ordner“
3. **Strg+→**: speichert, hakt die geladenen Ordner ✓ ab, springt zum nächsten offenen Album

### Mehrfach-Bearbeitung

- Strg+Klick im Baum für mehrere Ordner, oder Schalter **Unterordner** (Strg+R) für alles darunter
- Felder, die man nicht anfasst, bleiben unverändert

---

## 5. Feature-Fahrplan

### Phase 1: Stabiles Grundgerüst ✅ fertig

- [x] Projektstruktur, Theme (dunkel/hell), Hauptfenster mit 3 Bereichen
- [x] Ordnerbaum mit Status ✓ / ○ und Fortschritt pro Künstler und Sammlung
- [x] Ordner laden, optional rekursiv mit Unterordnern; mehrere Ordner per Strg+Klick
- [x] Einlesen im Hintergrund mit Fortschrittsanzeige, SQLite-Cache, mehrere CPU-Kerne
- [x] Dateiliste mit sortierbaren und ein-/ausblendbaren Spalten
- [x] Bearbeitungsfeld mit `<verschieden>`-Logik für Mehrfachauswahl
- [x] Felder: Titel, Interpret, Albuminterpret, Album, Jahr, Track, Disc, Genre, Komponist, Kommentar
- [x] Speichern im Hintergrund, nur geänderte Dateien und Felder
- [x] Rückgängig – für Bearbeitungen **und** für Speichervorgänge (letzte 20)
- [x] Cover: anzeigen, Drag & Drop, laden, einfügen, entfernen, als cover.jpg / unter … speichern, Großansicht
- [x] Vorhandene `cover.jpg` / `folder.jpg` erkennen und einbetten („Aus Ordner“)
- [x] „Speichern & nächster Ordner“ (Strg+→), vorheriger Ordner (Strg+←), fertig/offen (Strg+D)
- [x] Tastenkürzel für alles Wichtige + Übersicht (F1)

**Zusätzlich schon in Phase 1:**
- [x] Einfacher Textfilter über der Liste (Strg+F)
- [x] Künstlerbild manuell festlegen (Bild wählen → `folder.jpg` im Künstler-Ordner)
- [x] Einstellungen: ID3-Version, ID3v1, Änderungsdatum behalten, Cover-Dateinamen und -Größe, Online-Zugangsdaten
- [x] Sammlung per Drag & Drop öffnen, letzter Ordner wird beim Start wiederhergestellt
- [x] Ungespeicherte Änderungen: Nachfrage beim Ordnerwechsel und Schließen
- [x] Fehler einzelner Dateien stoppen nie den Rest – Fehlerliste zum Kopieren
- [x] Platzhalter für alle Funktionen der Phasen 2–4 in den Menüs (mit Beschreibung und geplantem Kürzel)

### Phase 2: Dateiname ↔ Tags & Werkzeuge

- [ ] #1 Tags aus Dateinamen/Ordnernamen, z. B. `%artist%/%album%/%track% - %title%` *(Kernfunktion schon fertig und getestet: `core/patterns.py`)*
- [ ] #2 Dateinamen aus Tags erzeugen (mit Vorschau vor dem Umbenennen)
- [ ] #3 Tracknummern automatisch vergeben (pro Ordner)
- [ ] #4 Groß-/Kleinschreibung korrigieren
- [ ] #5 Suchen & Ersetzen, auch mit Regex
- [ ] #6 Leerzeichen säubern, Sonderzeichen ersetzen

### Phase 3: Online

- [ ] #7 **Album-Suche** über MusicBrainz
  - **Eine Anfrage pro Album** mit Albumname + Künstler, nicht pro Track
  - Danach Trefferliste mit Vorschau: Titel, Tracks, Jahr, Label, Cover
  - Übernahme erst nach Bestätigung, Tracks werden über Nummer/Länge zugeordnet
- [ ] #8 **Discogs** als zweite Quelle (Token nötig, Account wird angelegt)
- [ ] #9 **Cover-Suche** über Cover Art Archive, iTunes, Deezer
  - Treffer als Bildergitter mit Auflösung
  - Speichern als `cover.jpg` im Album-Ordner und/oder einbetten
- [ ] #10 **Künstlerbild-Suche** über Deezer (ohne Key), optional TheAudioDB / fanart.tv → `folder.jpg`
- [x] Wartezeit-Regel vorbereitet (`online/base.py`: RateLimiter, 1 Anfrage/Sekunde)
- [x] Datentypen für Treffer vorbereitet (AlbumMatch, TrackMatch, CoverCandidate)

### Phase 4: Für Fortgeschrittene

- [ ] #11 Aktionsketten speichern und mit einem Klick ausführen
- [ ] #12 Erkennung unbekannter Dateien per Fingerabdruck (AcoustID, kostenloser Key)
- [ ] #13 ReplayGain berechnen (über das externe Programm rsgain)
- [ ] #14 Duplikate finden
- [ ] #15 Export als CSV / HTML
- [ ] #16 Erweiterte Filter („alle ohne Cover“, „alle ohne Jahr“ …) – einfacher Textfilter gibt es schon
- [x] #17 AppImage bauen – *vorgezogen in 0.1.2*: `make`, automatisch auf GitHub bei jedem Hochladen, Selbsttest auf X-Bildschirm

---

## 6. Projektstruktur (so umgesetzt)

```
BuB3TAGMUSIC/
├── Makefile                  make = AppImage bauen, make install, make test …
├── packaging/                AppImage-Bau (Skript, Starter, Verschlanken, xcb-Bibliotheken)
├── install.sh / start.sh     Start aus dem Quellcode (für Entwickler)
├── requirements.txt, pyproject.toml
├── BuB3TAGMUSIC.md           dieses Dokument
├── README.md                 Kurzanleitung
├── ANLEITUNG.md              Bauen mit make, Schritt für Schritt
├── docs/                     Screenshots
├── tests/                    Kern-Test, Oberflächen-Test, Leistungstest, Testdateien
└── bub3tagmusic/
    ├── app.py                Programmstart
    ├── features.py           Fahrplan als Daten → baut die Menüs der Phasen 2–4
    ├── core/                 ohne Qt (läuft auch in Hintergrund-Prozessen)
    │   ├── fields.py         einheitliche Feldnamen
    │   ├── tags.py           Lesen/Schreiben aller Formate
    │   ├── covers.py         Cover prüfen, verkleinern, als Datei speichern
    │   ├── scanner.py        Ordnerbaum, Dateilisten, paralleles Einlesen
    │   ├── cache.py          SQLite: Tags + Ordner-Status (mit Versions-Migration)
    │   ├── model.py          geladene Datei mit Bearbeitungsstand
    │   ├── undo.py           Rückgängig-Verlauf
    │   ├── patterns.py       Muster %artist% … (Phase-2-Baustein)
    │   └── settings.py       Einstellungen (JSON)
    ├── online/               Phase 3/4: Schnittstellen stehen, Inhalte folgen
    └── ui/                   Oberfläche (mainwindow, session, workers, foldertree,
                              filetable, editpanel, coverwidget, dialogs, theme, icons)
```

**Neue Funktion anschließen:** in `features.py` `ready=True` setzen und in `ui/mainwindow.py`
unter `FEATURE_HANDLERS` die Methode eintragen. Menüeintrag und Tastenkürzel existieren schon.

---

## 7. Regeln für Stabilität & Sicherheit

- **Nur Tags anfassen, nie die Audiodaten**
- Nur geänderte Felder werden geschrieben; unbekannte Tags bleiben erhalten
- Vor dem Speichern werden die alten Werte (und ggf. das alte Cover) gemerkt → Rückgängig möglich
- Fehler bei einzelnen Dateien brechen nie den ganzen Vorgang ab; sie werden gesammelt angezeigt
- Massenänderungen (Umbenennen, Online-Übernahme) immer mit Vorschau (ab Phase 2)
- Erste Tests **nur an einer Kopie** eines Teils der Sammlung

### Messwerte (Testrechner mit 2 Kernen)

| Vorgang | Zeit |
|---|---|
| Ordnerbaum mit 1.000 Alben / 12.000 Dateien zählen | 0,04 s |
| 12.000 Dateien erstmals einlesen | 1,7 s |
| dieselben 12.000 Dateien aus dem Cache | 0,14 s |
| Liste mit 50.000 Einträgen füllen / sortieren / filtern | 0,3 s / 0,1 s / 0,1 s |
| 50.000 Dateien auswählen + Bearbeitungsfeld | ca. 1 s |
| Genre für 50.000 Dateien setzen / rückgängig | 0,3 s / 0,3 s |

Echte MP3s mit großen Covern auf einer alten Festplatte brauchen beim ersten Einlesen länger
(grob 5–20 ms pro Datei). Danach greift der Cache.

---

### AppImage – wie es funktioniert

- `make` → `packaging/build_appimage.sh`: lädt bei Bedarf `uv`, ein eigenständiges Python 3.12
  (python-build-standalone, ab glibc 2.17) und `appimagetool`, installiert die Pakete aus
  `packaging/requirements-appimage.txt`, wirft Ungenutztes raus (`prune.py`: Testdateien, Tk,
  QML/Quick, virtuelle Tastatur, nicht gebrauchte Qt-Bibliotheken – per `ldd` ermittelt) und packt alles
  mit zstd zu einer Datei. Dauer ≈ 20 Sekunden.
- **Qt 6.9 statt 6.12 im AppImage:** Ab Qt 6.10 verlangen die Qt-Pakete glibc 2.34; mit 6.9 läuft
  BuB3TAGMUSIC auch auf älteren Systemen, wie sie auf alter Hardware oft laufen.
- **Fehlende Systembibliotheken:** Qt braucht unter X11 kleine xcb-Hilfsbibliotheken (z. B. `libxcb-cursor0`,
  fehlt auf Ubuntu 22.04). Sie liegen in `packaging/libs` (aus Ubuntu 20.04, MIT/X11). Der Starter `AppRun`
  reicht **nur die fehlenden** nach. `libxkbcommon-x11` wird nur zusammen mit der passenden `libxkbcommon`
  nachgereicht – gemischt mit einer anderen Version stürzt Qt ab (geprüft).
- Getestet: echtes X11 (virtueller Bildschirm) mit vollständigem System, „wie Ubuntu 22.04“ und ganz
  nacktem System; Wayland-Plugin ist enthalten. `--selftest` prüft den Start automatisch.
- Im Programm: ⚙ → **Ins Startmenü eintragen** (nur im AppImage sichtbar).

## 8. Standard-Einstellungen (änderbar)

| Einstellung | Standard |
|---|---|
| ID3-Version für MP3 | v2.3 (beste Kompatibilität), v2.4 wählbar |
| Alte ID3v1-Tags | vorhandene aktualisieren |
| Änderungsdatum der Datei beibehalten | aus |
| Albumcover-Datei | `cover.jpg` |
| Künstlerbild-Datei | `folder.jpg` |
| „Aus Ordner“ sucht | cover.jpg, folder.jpg, front.jpg, album.jpg … |
| Eingebettete Cover-Größe | 600 × 600, JPEG-Qualität 90 (Datei im Ordner bleibt voll) |
| Unterordner laden | aus (Strg+R) |
| Nach dem Öffnen alle Dateien auswählen | an |
| Theme | dunkel („Nachtwache“) |

Einstellungen: `~/.config/bub3tagmusic/settings.json` · Cache: `~/.cache/bub3tagmusic/cache.sqlite`

---

## 9. Offene Punkte

- [ ] #18 Phase 1 an einer Kopie der echten Sammlung testen (Rückmeldung: was fehlt, was stört?)
- [ ] #19 Welche Linux-Distribution wird genutzt? (für Feinschliff von `install.sh`)
- [ ] #20 Design bestätigen: Bojen-Orange, Stencil-Logo, Rettungsring-Icon
- [ ] #21 Discogs-Account + Token anlegen (übernimmt BAUENUNDBOOTEN zum Testen)
- [ ] #23 AcoustID-Key (später, Phase 4)
- [ ] #22 APE- und DSF-Dateien zum Testen (falls in der Sammlung vorhanden)

---

## 10. Nächster Schritt

1. Mit `make` bauen (siehe `ANLEITUNG.md`) und mit einer **Kopie** von ein paar Künstler-Ordnern testen
2. Rückmeldung sammeln und Phase 1 nachschärfen
3. Phase 2 starten: Tags ↔ Dateiname, Auto-Nummerierung, Schreibweise, Suchen & Ersetzen
