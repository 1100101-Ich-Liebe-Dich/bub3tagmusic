# Änderungsprotokoll

Alle wichtigen Änderungen an BuB3TAGMUSIC – präsentiert von www.BAUENUNDBOOTEN.de

## [1.1.3] – 2026-10-20 – Mehr Künstlerbilder

### Neu
- **Künstlerbild suchen** jetzt bei **TheAudioDB, Bandcamp, Discogs und Wikipedia** – mehr Treffer, auch für kleine
  und unbekannte Künstler:
  - **Bandcamp:** Fotos der Bands (mit Ort, damit gleichnamige Bands unterscheidbar sind)
  - **Discogs:** alle Fotos des passenden Künstlers – braucht den Discogs-Token, ohne ist die Quelle aus
  - **Wikipedia:** freie Bilder von Wikimedia Commons (über MusicBrainz → Wikidata)

### Geändert
- **Keine Künstlerbilder mehr von Deezer** – von Deezer kommen jetzt nur noch Tags.
- Bei neuen Quellen wird die gemerkte Quellen-Auswahl einmal zurückgesetzt, damit die neuen auch an sind
  (betraf auch TheAudioDB/Bandcamp in der Cover-Suche aus 1.1.2).

## [1.1.2] – 2026-10-20 – Mehr Quellen

### Neu
- **Album suchen – iTunes / Apple Music** (ohne Anmeldung): genaue Tracklisten mit Discs, meist das Jahr der
  Erstveröffentlichung, Cover bis 3000 px.
- **Album suchen – Last.fm**: Titel, Längen und Genres aus den Tags der Hörer. Braucht einen kostenlosen API-Key
  (*Einstellungen → Online → Last.fm-API-Key*).
- **Cover suchen** jetzt bei **Cover Art Archive, iTunes, TheAudioDB und Bandcamp**.
- Lizenz: GNU GPL 3.0 oder später (`LICENSE`, auch im AppImage und im Fenster „Über“).

### Geändert
- **Deezer liefert nur noch Tags** – keine Cover und keine Vorschaubilder mehr (deren Bilder sind nicht zum
  Weiterverwenden gedacht). Cover gibt es über *Cover suchen* (Strg+K).

## [1.1.1] – 2026-10-19 – Aus ‹verschieden› wählen

### Neu
- Steht ein Feld auf `‹verschieden›` (z. B. mehrere Interpreten in einem Album), zeigt es einen kleinen **Pfeil**.
  Ein Klick (oder **Alt+↓**) listet die vorhandenen Werte – die häufigsten zuerst, mit Anzahl. Die Wahl gilt für alle
  gewählten Dateien (gelb, Strg+S speichert, Strg+Z nimmt zurück). Wird nichts gewählt, bleibt alles, wie es ist.
  Gilt für alle Felder außer Track; beim Songtext gibt es weiterhin das Songtext-Fenster.

## [1.1.0] – 2026-10-19 – Songtext, Label, Original-Jahr, Deezer

### Neu
- **Songtext** für alle Formate (MP3 USLT, FLAC/OGG/Opus LYRICS, M4A, WMA, APE/WavPack). Im Bearbeitungsfeld eine
  kompakte Zeile („8 Zeilen · Leinen los …“), ein Klick öffnet das Songtext-Fenster: eintippen, einfügen, aus
  `.lrc`/`.txt` laden (Zeitmarken wie `[01:23.45]` werden entfernt). Liegt neben den Liedern eine gleichnamige
  `.lrc`/`.txt`, übernimmt **„Aus Begleitdateien“** die Songtexte für alle gewählten Dateien auf einmal.
- **Label** (Plattenfirma) und **Original-Jahr** (Erstveröffentlichung) – im Bearbeitungsfeld in einer Zeile.
  Auch die Schreibweisen von Picard und Mp3tag werden gelesen (TORY/TXXX, ORIGINALYEAR, ORGANIZATION …) und beim
  Ändern ohne Reste ersetzt.
- **Album suchen – Deezer:** dritte Quelle neben MusicBrainz und Discogs, ohne Anmeldung. Stark bei neuer und
  deutscher Musik, Cover in 1000 px, Label. Hinweis im Fenster: Das Jahr ist bei Deezer oft das der Neuauflage.
- Album suchen übernimmt jetzt auch **Label** und (bei MusicBrainz) das **Original-Jahr**. Neuer Schalter
  **„Ohne Remaster-Zusätze“** (an): „Titel (Remastered 2011)“ → „Titel“, „Album (Deluxe Edition)“ → „Album“ –
  Live, Remix, Acoustic usw. bleiben stehen. Spalten für Felder, die eine Quelle nicht kennt, werden ausgeblendet.
- Neue Listenspalten Label, Orig.-Jahr, Songtext (anfangs ausgeblendet – Rechtsklick auf die Spaltenköpfe).
- Suchen & Ersetzen kennt Label, Original-Jahr und Songtext; Schreibweise und Aufräumen kennen das Label;
  Muster kennen `%label%` und `%originalyear%`.

### Geändert
- Lange Werte im Bearbeitungsfeld zeigen den Anfang statt das Ende.
- Bearbeitungsfeld etwas kompakter – auch bei 1366×768 passen alle Felder ohne Blättern.
- Der Listenfilter durchsucht keine Songtexte (sonst findet „liebe“ jedes Lied, das davon singt).
- „1 Track“ statt „1 Tracks“ in den Suchergebnissen.

## [1.0.0] – 2026-10-19 – Erste stabile Version

BuB3TAGMUSIC 1.0 – alle vier geplanten Phasen sind fertig, getestet und dokumentiert.

### Auf einen Blick
- Sammlung Ordner für Ordner bearbeiten: Baum mit Fertig-Status, Mehrfach-Bearbeitung, „Speichern & nächster Ordner“
- Cover und Künstlerbild: einbetten, `cover.jpg`, `folder.jpg`, Drag & Drop, online suchen
- Werkzeuge mit Live-Vorschau (Tags ↔ Dateinamen, nummerieren, Schreibweise, Ersetzen, Aufräumen, Ordner umbenennen)
- Aktionen: mehrere Schritte als ein Rückgängig-Schritt
- Online: MusicBrainz, Discogs, Cover Art Archive, iTunes, Deezer, TheAudioDB, AcoustID
- Schnellfilter, Duplikate, ReplayGain (Nur messen als Standard), Export als CSV/HTML
- Fünf Farb-Themes, Standard „Bauen & Booten“
- Eine Datei, keine Installation: `make` baut das AppImage – inklusive fpcalc und rsgain

### Neu seit 0.9.0
- **Künstler-Ordner:** Wird links ein Ordner ohne eigene Musik gewählt, in dem die Alben liegen, zeigt die rechte
  Seite das Künstlerbild (`folder.jpg` in diesem Ordner) – reinziehen, laden, einfügen, entfernen oder online suchen
  (Strg+J). Der Ordnername ist als Künstlername vorbelegt und änderbar. Dazu alle Alben mit cover.jpg-Häkchen und
  „Alle Alben laden“. Ein ersetztes Bild kommt in den Papierkorb.
- Rechtsklick auf einen Ordner im Baum: „Künstlerbild für diesen Ordner suchen …“
- `sh build.sh` baut die Datei auch ohne `make`
- Bei jedem veröffentlichten Release baut GitHub das AppImage selbst, prüft es und hängt es samt Prüfsumme an
- GitHub-Seite neu: Banner, Bildergalerie aller Funktionen, Schnellstart, Fragen & Antworten
- Bilder für die Seite lassen sich jederzeit neu erzeugen: `python3 docs/make_images.py`
- Fehlervorlage fragt nach der Version und dem Selbsttest

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
