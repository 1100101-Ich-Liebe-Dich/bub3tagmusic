# Änderungsprotokoll

Alle wichtigen Änderungen an BuB3TAGMUSIC – präsentiert von www.BAUENUNDBOOTEN.de

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
