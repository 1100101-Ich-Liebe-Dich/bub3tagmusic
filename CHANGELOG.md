# Änderungsprotokoll

Alle wichtigen Änderungen an BuB3TAGMUSIC – präsentiert von www.BAUENUNDBOOTEN.de

## [0.9.0] – 2026-10-18 – Release-Kandidat vor 1.0

### Neu
- **Neues Standard-Theme „Bauen & Booten“** in den Farben von www.BAUENUNDBOOTEN.de (Erdgrün-Dunkel, Bernstein),
  dazu „Bauen & Booten – hell“ und „Ankerplatz – Graphit“. „Nachtwache“ und „Seekarte“ bleiben wählbar.
  Schnell wechseln: ⚙ → Farben. Wer bisher das alte Standard-Theme hatte, bekommt einmalig das neue.
- App-Icon (Rettungsring) und Logo in Bernstein/Erdgrün.

### Geändert
- **ReplayGain startet jetzt immer mit „Nur messen“** – da wird nichts geschrieben. Schreiben oder Entfernen
  zeigt eine rote Warnung im Fenster, einen roten Knopf und fragt vorher ausdrücklich nach („Abbrechen“ ist
  vorausgewählt), weil sich das nicht mit Strg+Z zurücknehmen lässt.
- „1 Album“ statt „1 Alben“ im ReplayGain-Fenster.

## [0.4.0] – 2026-10-18 – Phase 4: Extras

### Neu
- **Schnellfilter** über der Liste: Ohne Cover, Cover < 500 px, Ohne Jahr, Fehlende Tags, Ungespeichert,
  Lesefehler – kombinierbar, mit Zählern. **Ganze Sammlung** sucht dieselben Filter in der ganzen Sammlung.
- **Liste exportieren** (Strg+Shift+E) als CSV (UTF-8) oder eigenständige HTML-Seite im BuB3TAGMUSIC-Look.
- **Duplikate finden** nach Interpret + Titel oder nach Klang (Fingerabdruck) – in der Liste oder der ganzen
  Sammlung; beste Qualität markiert; nur Angehaktes wandert in den Papierkorb, eine Datei je Gruppe bleibt.
- **Aktionen** (Alt+7): Schrittketten (Aufräumen, Schreibweise, Ersetzen, Feld setzen, Tags aus Dateiname,
  Nummerieren, Umbenennen) mit Vorschau; Strg+Z nimmt alles in einem Schritt zurück – auch das Umbenennen.
- **ReplayGain** über rsgain: Track + Album, nur Track oder entfernen; Spalten „RG Track“/„RG Album“.
- **Unbekannte Dateien erkennen** (Strg+Shift+L) per Fingerabdruck und AcoustID (kostenloser Key).
- `make` packt die Hilfsprogramme `fpcalc` und `rsgain` gleich ins AppImage.

### Behoben
- Gelber Rahmen im Bearbeitungsfeld blieb manchmal stehen, obwohl nichts mehr geändert war
  (z. B. nach Rückgängig oder Speichern).

### Technik
- Zwischenspeicher Version 2: Fingerabdrücke werden gemerkt; Tags werden einmalig neu gelesen
  (wegen der ReplayGain-Werte).

## [0.3.0] – 2026-10-18 – Phase 3: Online

### Neu
- **Album suchen** (Strg+L) bei MusicBrainz oder Discogs: eine Anfrage pro Album, Trefferliste mit Cover,
  Trackliste automatisch den Dateien zugeordnet (Tracknummer/Disc, Reihenfolge oder Länge), Felder wählbar,
  Cover auf Wunsch gleich mit. Übernahme ist ein einziger Rückgängig-Schritt.
- **Cover suchen** (Strg+K): Cover Art Archive, iTunes (bis 3000 px), Deezer – einbetten und/oder cover.jpg.
- **Künstlerbild suchen** (Strg+J): Deezer und TheAudioDB → folder.jpg im Künstler-Ordner.
- **Ordner umbenennen** (Alt+6) nach Tags, z. B. `%year% - %album%`; Fertig-Status wandert mit.
- **Begleitdateien** (.lrc, .txt, .srt …) wandern beim Umbenennen mit.
- Rechtsklick-Menü in der Liste enthält jetzt auch die Online-Funktionen.

### Technik
- Online ohne Zusatzbibliotheken (urllib); Zertifikate der Distribution werden gezielt geladen, sonst certifi.
- Echte Antworten der Dienste werden auf GitHub aufgezeichnet; alle Online-Tests spielen sie ab.

## [0.2.0] – 2026-10-18 – Phase 2: Werkzeuge

### Neu
- **Tags aus Dateiname / Ordnername** (Alt+1) – Muster mit Ordnerebenen, `%dummy%`, Vorlagen + Verlauf,
  Tippfehler-Hinweis, „nur leere Felder füllen“.
- **Dateinamen aus Tags** (Alt+2) – sicheres zweistufiges Umbenennen mit Prüfung auf fehlende Tags,
  doppelte Namen und vorhandene Dateien; USB-/Windows-taugliche Namen; Rückgängig benennt zurück.
- **Tracks nummerieren** (Alt+3) – pro Ordner, Gesamtzahl, führende Null, Disc-Nummer aus Ordnernamen.
- **Groß-/Kleinschreibung** (Alt+4) – vier Modi, kleine Wörter und feste Schreibweisen einstellbar,
  gemischte Schreibweise geschützt.
- **Suchen & Ersetzen** (Alt+5) – auch mit regulären Ausdrücken und `$1`.
- **Aufräumen** – sieben einzeln schaltbare Regeln.
- Alle Werkzeuge mit Live-Vorschau; Übernehmen ist ein einziger Rückgängig-Schritt; Einstellungen werden gemerkt.
- Rechtsklick in der Dateiliste: Werkzeuge, Änderungen verwerfen, Ordner im Dateimanager öffnen.
- Tastenkürzel-Übersicht (F1) mit den Werkzeugen.

### Verbessert
- Auswahllisten und Zahlenfelder zeigen wieder ihre Pfeile (z. B. Genre-Feld).
- Speichern verwirft jetzt alle vorherigen Bearbeitungsschritte aus dem Verlauf (sie sind ja gespeichert).

### Außerdem
- `ANLEITUNG.md`: Bauen mit `make` Schritt für Schritt, mit Hilfe bei Problemen.
- Bauen klappt jetzt auch nur mit `wget` (Ubuntu hat `curl` oft nicht vorinstalliert).

## [0.1.2] – 2026-10-18

### Neu
- **BuB3TAGMUSIC als eine ausführbare Datei (AppImage)** – keine Installation mehr nötig:
  `chmod +x`, Doppelklick, läuft. Bringt eigenes Python und Qt mit; läuft ab Ubuntu 20.04 / Mint 20 /
  Debian 10 / Fedora 29. Fehlende Qt-Hilfsbibliotheken (z. B. libxcb-cursor0) werden automatisch nachgereicht.
- `make` baut das AppImage selbst, `make install` / `make uninstall` für Startmenü-Eintrag.
- GitHub baut das AppImage bei jedem Hochladen, testet es auf einem X-Bildschirm und stellt es bereit.
- Im AppImage: ⚙ → „Ins Startmenü eintragen“.
- `--version` und `--selftest [ORDNER]` (automatischer Starttest, ändert nichts).
- Qt-eigene Texte auf Deutsch (z. B. „Ja/Nein“ in Rückfragen, Datei-Dialoge).

### Behoben
- Beim ersten Start war das Fenster höher als ein 1366×768-Bildschirm (Statusleiste abgeschnitten).
  Jetzt passt es sich an; kleine Bildschirme starten maximiert.

## [0.1.1] – 2026-10-18

### Neu
- GitHub-Repository eingerichtet: automatische Tests bei jedem Hochladen (Python 3.10, 3.11 und 3.13),
  Vorlagen für Fehlermeldungen und Wünsche, Fahrplan als Aufgaben mit Meilensteinen Phase 2–4.
- `tests/run_all.sh` führt alle Tests mit einem Befehl aus; die Test-Sammlung erzeugt sich selbst
  (mit Tags, Covern und cover.jpg).
- `CLAUDE.md` mit Arbeitsnotizen, Regeln und Stolperfallen.

### Behoben
- Absturz nach einiger Zeit unter Python 3.10/3.11 („Fatal Python error: none_dealloc“). Ursache ist ein
  Fehler in PySide6 6.11/6.12. Auf Python < 3.12 wird jetzt automatisch PySide6 6.10 installiert;
  beim Start gibt es eine Warnung, falls doch eine betroffene Version vorhanden ist.
  **Wer schon installiert hat: `./install.sh` einfach noch einmal ausführen.**

## [0.1.0] – 2026-10-18 – Phase 1: Grundgerüst

### Neu
- Hauptfenster mit Ordnerbaum, Dateiliste und Bearbeitungsfeld; Themes „Nachtwache“ (dunkel) und „Seekarte“ (hell).
- Ordnerbaum mit Fertig-Status je Album, Fortschritt je Künstler und für die ganze Sammlung.
- Laden einzelner oder mehrerer Ordner, optional mit allen Unterordnern (Strg+R).
- Einlesen im Hintergrund auf mehreren CPU-Kernen, SQLite-Zwischenspeicher.
- Mehrfach-Bearbeitung mit `‹verschieden›`; nur geänderte Felder werden geschrieben.
- Formate: MP3 (ID3v2.3/2.4, ID3v1), FLAC, M4A, OGG, Opus, WMA, WAV, AIFF, APE, WavPack, DSF.
- Cover: Drag & Drop, laden, einfügen, aus Ordner übernehmen, als cover.jpg speichern, entfernen, Großansicht;
  Künstlerbild als folder.jpg festlegen.
- „Speichern & nächster Ordner“ (Strg+→), Rückgängig auch für Gespeichertes (Strg+Z).
- Textfilter, sortierbare und ausblendbare Spalten, Tastenkürzel-Übersicht (F1), Einstellungen.
- Platzhalter für alle Funktionen der Phasen 2–4.
- `install.sh` / `start.sh` mit Startmenü-Eintrag.
