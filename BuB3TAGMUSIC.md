# BuB3TAGMUSIC

**Moderner, schneller Musik-Tagger für Linux**
präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de)

> **Aktueller Stand:** Version **1.1.6** (23.10.2026): Album suchen bei MusicBrainz, Discogs, Deezer (nur Tags),
> iTunes und Last.fm; Cover bei Cover Art Archive, iTunes, TheAudioDB, Bandcamp und Discogs; Künstlerbilder bei TheAudioDB,
> Bandcamp, Discogs und Wikipedia. 1.1.4: Album suchen bei allen Quellen gleichzeitig + „Übernehmen & weiter“.
> 1.1.5: Zuordnung über Titel/Dateiname, Suchbegriffe ohne Klammern.
> 1.1.6: „Speichern & weiter“ für Künstlerbilder und Cover, Fehlende Tags / Fehlende Bilder finden.
> Lizenz GPL-3.0.
> 1.0.0 ist veröffentlicht (Release auf GitHub). Release 1.1: Anleitung + Text in `docs/RELEASE-1.1.md`.
> Nächster Schritt: Praxis mit der echten Sammlung, Rückmeldungen sammeln.
>
> Code + Aufgaben: GitHub-Repo `1100101-Ich-Liebe-Dich/bub3tagmusic` (Lizenz GPL-3.0 oder später).
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
| **Standard-Theme „Bauen & Booten“** (ab 0.9) | Farben der Website: Seite `#1C1F1C`, Kopfzeile/Leisten `#171A17`, Karten/Knöpfe `#232622`, Hover `#2A2E28` |
| Schrift | Betonung `#E4ECE0`, Fließtext `#B4C6AF`, Nebensächliches `#7F8B7B` |
| Akzent | Bernstein `#E5A00D` (Überfahren `#F2B32B`), Linien Erdgrün `#7A8B76` (22 % bzw. 40 %, auf den Grund gerechnet) |
| Status-Farben | fertig `#7FA872`, ungespeichert Gelb `#EDC453`, Fehler `#B5563C` (als Schrift etwas heller) |
| Weitere Themes | „Bauen & Booten – hell“, „Ankerplatz – Graphit“, „Nachtwache – Hafenblau“ (bis 0.4 Standard), „Seekarte – hell“ – umschalten unter ⚙ → Farben |
| Logo-Schrift | Big Shoulders Stencil (Schablonen-Schrift wie Rumpf-Beschriftung auf der Werft) |
| Text-Schrift | Inter (mitgeliefert, sieht auf jeder Distribution gleich aus) |
| App-Icon | Rettungsring in Bernstein/Erdgrün auf `#1C1F1C` – erinnert zugleich an eine Schallplatte |
| Logo-Farbe | Bernstein `#E5A00D` (in Nachtwache/Seekarte/Graphit wie die Schrift) |

### Künstler-Ordner (ab 1.0)

Ordner ohne eigene Musik, in dem Alben liegen (nicht: reine CD1/CD2-Unterordner) = Künstler-Ordner. Rechts erscheint
statt der Tag-Felder `ui/artistpanel.py`: Künstlerbild (`folder.jpg` in diesem Ordner) reinziehen/laden/einfügen/
entfernen/online suchen (Ordnername als Künstlername, änderbar), Alben mit cover.jpg-Häkchen, „Alle Alben laden“.
Ersetzte/entfernte Bilder → Papierkorb. Baum-Rechtsklick: „Künstlerbild für diesen Ordner suchen …“ für jeden Ordner.

### Kern-Arbeitsablauf: „Speichern & nächster Ordner“

1. Album im Baum anklicken → Dateien laden und sind sofort alle ausgewählt
2. Rechts gemeinsame Felder setzen, Cover reinziehen oder „Aus Ordner“
3. **Strg+→**: speichert, hakt die geladenen Ordner ✓ ab, springt zum nächsten offenen Album

### Mehrfach-Bearbeitung

- Strg+Klick im Baum für mehrere Ordner, oder Schalter **Unterordner** (Strg+R) für alles darunter
- Felder, die man nicht anfasst, bleiben unverändert
- Bei `‹verschieden›` zeigt ein Pfeil im Feld (oder Alt+↓) die vorhandenen Werte – einer davon gilt dann für alle (nicht bei Track)

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

### Phase 2: Dateiname ↔ Tags & Werkzeuge ✅ fertig (0.2.0)

- [x] #1 Tags aus Datei-/Ordnernamen, z. B. `%artist%/%year% - %album%/%track% - %title%`
  - „/“ = Ordnerebene, `%dummy%` überspringt, Vorlagen + die letzten 12 Muster, Tippfehler-Hinweis („meintest du %title%?“)
  - Führende Nullen weg, Unterstriche als Leerzeichen, „nur leere Felder füllen“
- [x] #2 Dateinamen aus Tags – Vorschau alt → neu, prüft fehlende Tags, doppelte Namen, vorhandene Dateien, Länge
  - Zweistufiges Umbenennen (auch Tauschen A↔B), überschreibt nie, Fehler werden zurückgerollt
  - USB-/Windows-taugliche Namen (Standard), Tracknummer auffüllen, Rückgängig benennt zurück
  - Ordner umbenennen: bewusst noch nicht (siehe offene Punkte)
- [x] #3 Tracks nummerieren – Listen-Reihenfolge, pro Ordner neu, Gesamtzahl, führende Null, Startwert,
  Disc-Nummer aus Ordnernamen (CD1, Disc 2 …) samt Gesamtzahl der Discs
- [x] #4 Groß-/Kleinschreibung – 4 Modi, Felder wählbar, kleine Wörter + feste Schreibweisen einstellbar,
  römische Zahlen, „(feat. …)“ bleibt klein, gemischte Schreibweise (iPhone) geschützt
- [x] #5 Suchen & Ersetzen – Groß/klein, ganze Wörter, reguläre Ausdrücke mit `$1`/`\1`,
  verständliche Fehlermeldungen, Trefferzahl
- [x] #6 Aufräumen – 7 Regeln einzeln schaltbar (unsichtbare Zeichen, Unterstriche, feat., leere Klammern,
  doppelte Leerzeichen, Rand, führende Nullen)

**Gemeinsam für alle Werkzeuge:** Live-Vorschau (geändert gelb, Probleme rot, unveränderte ausblendbar),
wirken auf die Auswahl oder sonst die ganze Liste, Einstellungen werden gemerkt, Übernehmen = ein
Rückgängig-Schritt. Erreichbar über Menü „Werkzeuge“, Alt+1 … Alt+5 und Rechtsklick in der Liste.

### Phase 3: Online ✅ fertig (0.3.0)

- [x] #7 **Album-Suche über MusicBrainz** (Strg+L)
  - **Eine** Suchanfrage pro Album (Album + Interpret, vorbelegt aus Tags bzw. Ordnernamen
    `Künstler/Jahr - Album`), danach **eine** Anfrage für die Trackliste des gewählten Treffers
  - Höchstens 1 Anfrage/Sekunde, eigener User-Agent, Antworten werden im Speicher gemerkt (nichts doppelt)
  - Trefferliste mit Cover-Vorschau, Jahr · Land · Label · Format · Trackzahl und Passt-Wert;
    Treffer mit genau so vielen Tracks wie Dateien kommen nach oben
  - Zuordnung Datei → Track: automatisch, nach Tracknummer (mit Disc), nach Reihenfolge oder nach Länge;
    Abweichende Längen werden markiert
  - Felder einzeln wählbar (Titel, Interpret, Album + Albuminterpret, Jahr, Track/Disc, Genre, Cover)
  - Disc-Nummer nur bei Mehrfach-CDs; Übernahme = ein Rückgängig-Schritt
- [x] #8 **Discogs** als zweite Quelle (im selben Dialog umschaltbar) – braucht den Token (#21);
  Positionen wie A1/B2 (Vinyl), 1-03, 2-2a werden richtig gelesen
- [x] #9 **Cover-Suche** (Strg+K) über Cover Art Archive, iTunes (bis 3000 px) und Deezer (1000 px)
  - Bildergitter mit Größe und Quelle, Quellen einzeln schaltbar, Doppelklick übernimmt
  - Einbetten (verkleinert) und/oder `cover.jpg` in voller Größe in den Album-Ordner
- [x] #10 **Künstlerbild-Suche** (Strg+J) über Deezer und TheAudioDB → `folder.jpg` im Künstler-Ordner
- [x] Fehlt das Internet oder fällt eine Quelle aus, gibt es eine klare Meldung; die anderen Quellen liefern weiter

**Testen ohne Musikdienste:** Die Arbeitsumgebung erreicht MusicBrainz & Co. nicht. Deshalb zeichnet der
GitHub-Workflow „Testdaten aufzeichnen“ echte Antworten auf (`tests/record_online.py` → `tests/fixtures/online/`),
und alle Tests spielen sie ab. Neu aufzeichnen: Datei `tests/fixtures/online/RECORD` ändern und hochladen.

### Phase 4: Für Fortgeschrittene ✅ fertig (0.4.0)

- [x] #16 **Schnellfilter** über der Liste: Ohne Cover · Cover < 500 px · Ohne Jahr · Fehlende Tags ·
  Ungespeichert · Lesefehler – kombinierbar, mit Zählern; **„Ganze Sammlung“** sucht mit denselben
  Filtern (und dem Suchtext) in der ganzen Sammlung (aus dem Zwischenspeicher, nur Neues wird gelesen).
  Ein-/ausblenden: Extras → Erweiterte Filter
- [x] #15 **Liste exportieren** (Strg+Shift+E): sichtbare Spalten in ihrer Reihenfolge, Sortierung und
  Filter wie in der Liste; CSV (UTF-8, Semikolon/Komma/Tab) oder eine eigenständige HTML-Seite im
  BuB3TAGMUSIC-Look (sortierbar, Suchfeld, hell/dunkel, druckbar)
- [x] #14 **Duplikate finden**: in der Liste oder der ganzen Sammlung, nach Interpret + Titel (Akzente,
  Satzzeichen egal; Länge ± einstellbar; Klammerzusätze optional ignorieren) und/oder nach **Klang**
  (Fingerabdruck, auch ohne Tags). Gruppen mit „beste Qualität“; nichts wird automatisch gelöscht –
  angehakte Dateien wandern auf Wunsch in den Papierkorb (eine pro Gruppe bleibt immer)
- [x] #11 **Aktionen** (Alt+7): Ketten aus Aufräumen, Schreibweise, Ersetzen, Feld setzen (mit Platzhaltern
  wie `%artist%`), Tags aus Dateiname, Nummerieren und Umbenennen; gespeichert in
  `~/.config/bub3tagmusic/actions.json`; Beispiel-Aktionen; Vorschau; **ein** Rückgängig-Schritt – auch
  mit Umbenennen
- [x] #13 **ReplayGain** über `rsgain`: Standard **„Nur messen“** (nichts wird geschrieben). Schreiben (Track + Album,
  nur Track) oder Entfernen nur nach roter Warnung im Fenster und ausdrücklicher Rückfrage („Abbrechen“ ist
  vorausgewählt); Album = Ordner; −18/−23/−14
  LUFS, Übersteuern verhindern; Fortschritt, Abbrechen, Fehlerliste; Spalten „RG Track“/„RG Album“
- [x] #12 **Unbekannte Dateien erkennen** (Strg+Shift+L): Fingerabdruck mit `fpcalc`, Abfrage bei AcoustID
  (≤ 3/s), passendste Veröffentlichung (Album aus den Tags > Studioalbum > frühestes Jahr), Vorschau mit
  Treffer-Prozent, nur sichere Treffer übernehmen. Braucht den kostenlosen AcoustID-Key (#23)
- [x] #17 AppImage bauen – *vorgezogen in 0.1.2*: `make`, automatisch auf GitHub bei jedem Hochladen, Selbsttest auf X-Bildschirm

### Version 1.1 ✅ fertig (1.1.0)

- [x] #26 **Songtext**: alle Formate; Zeile im Bearbeitungsfeld + eigenes Fenster (eintippen, einfügen, `.lrc`/`.txt`
  laden, Zeitmarken entfernen); „Aus Begleitdateien“ füllt viele Dateien auf einmal aus gleichnamigen `.lrc`/`.txt`
- [x] #27 **Label + Original-Jahr**: alle Formate (inkl. Picard-/Mp3tag-Schreibweisen), im Bearbeitungsfeld in einer
  Zeile; MusicBrainz liefert beide (Original-Jahr = erste Veröffentlichung der Release-Group), Discogs/Deezer das Label
- [x] **Album suchen – Deezer**: dritte Quelle, ohne Anmeldung, eine Suche + Album + Trackliste;
  „Ohne Remaster-Zusätze“ (Standard an) kürzt „(Remastered 2011)“, „(Deluxe Edition)“, „(2019 Mix)“

- [x] **1.1.1:** `‹verschieden›` → Pfeil im Feld (oder Alt+↓) zeigt die vorhandenen Werte (häufigste zuerst, mit
  Anzahl); die Wahl gilt für alle gewählten Dateien, ohne Wahl ändert sich nichts. Nicht bei Track.

- [x] **1.1.2:** Album-Quellen iTunes / Apple Music und Last.fm (API-Key); Deezer nur noch Tags (keine Bilder);
  Cover-Suche: Cover Art Archive, iTunes, TheAudioDB, Bandcamp (über Bandcamps eigene Such-Schnittstelle –
  die Suchseite sperrt Programme). Bewusst nicht: Genius (ändert ständig etwas).

- [x] **1.1.3:** Künstlerbilder aus TheAudioDB, Bandcamp (Bands), Discogs (nur mit Token) und Wikipedia
  (MusicBrainz → Wikidata → Commons); keine Bilder mehr von Deezer.
- [x] **1.1.4:** Album suchen – „Alle Quellen“ gleichzeitig (Treffer mit Quelle, gute Treffer gemischt);
  „Übernehmen & weiter“ / „Nächster Ordner“ im Fenster (speichert, hakt ab, sucht im nächsten Ordner weiter);
  Strg+L merkt sich die Quelle. (Ersetzt die Idee „Rückfall auf die nächste Quelle“.)
- [x] **1.1.5:** Zuordnung „Nach Titel / Dateiname“ (auch in „Automatisch“, wenn ≥ 60 % sicher erkannt);
  Suchbegriffe ohne Inhalt von ( ) [ ] { }.
- [x] **1.1.6:** „Speichern & weiter“ / „Nächster Künstler“ bzw. „Nächstes Album“ in Künstlerbild- und Cover-Suche
  (springt zum nächsten Ordner ohne folder.jpg bzw. cover.jpg); *Extras → Fehlende Tags finden* (Titel, Interpret,
  Album, Tracknummer); *Extras → Fehlende Bilder finden …* (Liste, Doppelklick öffnet die Bildsuche); Discogs in
  der Cover-Suche (mit Token). Grüne Haken weiterhin nur fürs Speichern der Tags. (Ersetzt die Idee „Bilder für
  viele Ordner auf einmal“.)

**Hilfsprogramme:** `make` packt `fpcalc` 1.5.1 und `rsgain` 3.8 (fertige Programme der Hersteller,
Prüfsumme geprüft) ins AppImage – nichts extra zu installieren. Ohne AppImage nutzt BuB3TAGMUSIC die
Programme des Systems und zeigt sonst eine Installationsanleitung passend zur Distribution.

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
    │   ├── patterns.py       Muster %artist% … in beide Richtungen, mit Ordnerebenen
    │   ├── tools.py          Werkzeug-Logik (Phase 2)
    │   ├── rename.py         Umbenennen: Plan, Prüfung, zweistufig ausführen
    │   ├── filters.py        Schnellfilter (Phase 4)
    │   ├── export.py         CSV / HTML (Phase 4)
    │   ├── actions.py        Aktionen: Schritte, Ausführen, actions.json (Phase 4)
    │   ├── duplicates.py     Duplikate nach Tags / Klang (Phase 4)
    │   ├── fingerprint.py    fpcalc, kompakte Form, Vergleich (Phase 4)
    │   ├── replaygain.py     rsgain aufrufen und auswerten (Phase 4)
    │   ├── tools_external.py Hilfsprogramme finden + Installationshinweis je Distribution
    │   └── settings.py       Einstellungen (JSON)
    ├── online/               http (Limiter, Zertifikate), musicbrainz, discogs, coversearch,
    │                         artistimages, matching (Datei ↔ Track), acoustid (Erkennen)
    └── ui/                   Oberfläche (mainwindow, session, workers, foldertree,
                              filetable, editpanel, coverwidget, dialogs, theme, icons,
                              tools = Werkzeug-Dialoge, online = Online-Dialoge,
                              filterbar, export, actions, extras (Duplikate, ReplayGain),
                              acoustid, widgets = Bausteine)
```

**Neue Funktion anschließen:** in `features.py` `ready=True` setzen und – bei einem Werkzeug mit
Vorschau – eine `ToolDialog`-Unterklasse in `ui/tools.py` unter `TOOL_DIALOGS` eintragen; Online-Dialoge
unter `ONLINE_DIALOGS` (`ui/online.py`), eigene Extras-Fenster unter `EXTRA_DIALOGS` (`ui/extras.py`),
sonst die Methode in `ui/mainwindow.py` unter `FEATURE_HANDLERS`. Menüeintrag und Tastenkürzel existieren schon.

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
| Werkzeug-Vorschau für ≈ 42.000 Dateien (je nach Werkzeug) | 0,25 – 1,4 s |

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
| Theme | „Bauen & Booten“ (dunkel); wer bis 0.4 Nachtwache als Standard hatte, wird einmalig umgestellt |

Einstellungen: `~/.config/bub3tagmusic/settings.json` · Cache: `~/.cache/bub3tagmusic/cache.sqlite`

---

## 9. Offene Punkte

- [x] #26 Songtext-Feld (1.1)
- [x] #27 Label (Plattenfirma) und Original-Jahr (1.1)
- [ ] #24 Windows-Version (nach 1.0) – Pfade plattformneutral, `.exe` per GitHub Actions
- [ ] #25 macOS-Version (nach 1.0) – `.app`/`.dmg`, Signatur-Frage (Apple-Konto)
- [ ] #18 Phase 1 an einer Kopie der echten Sammlung testen (Rückmeldung: was fehlt, was stört?)
- [ ] #19 Welche Linux-Distribution wird genutzt? (für Feinschliff von `install.sh`)
- [ ] #20 Design bestätigen: Bojen-Orange, Stencil-Logo, Rettungsring-Icon
- [ ] #21 Discogs-Account + Token anlegen (übernimmt BAUENUNDBOOTEN zum Testen)
- [ ] #23 AcoustID-Key anlegen (acoustid.org/new-application) und in Einstellungen → Online eintragen –
      dann „Unbekannte Dateien erkennen“ ausprobieren
- [ ] #22 APE- und DSF-Dateien zum Testen (falls in der Sammlung vorhanden)
- [x] Ordner umbenennen – umgesetzt als eigenes Werkzeug (Alt+6), Fertig-Status wandert mit
- [x] Gleichnamige Begleitdateien (.lrc, .txt, .srt …) wandern beim Umbenennen mit

---

## 10. Nächster Schritt

1. Letzter Praxistest mit 1.0.0 (an einer **Kopie**) – AcoustID-Key (#23) und Discogs-Token (#21) dabei ausprobieren
2. Veröffentlichen: Anleitung und fertiger Text in `docs/RELEASE-1.0.md`
3. Danach: Rückmeldungen sammeln (Issues), Feinschliff nach Wunsch
4. **1.1.0** fertig: #26 Songtext + #27 Label/Original-Jahr + Album suchen bei Deezer.
   Bewusst nicht gewünscht: MusicBrainz-IDs, Sortier-Namen, Tags entfernen, Playlists, Update-Hinweis.
5. Danach: Fehler aus der Praxis direkt beheben (1.1.x)
