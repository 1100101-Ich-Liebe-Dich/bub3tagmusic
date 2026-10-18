# Änderungsprotokoll

Alle wichtigen Änderungen an BuB3TAGMUSIC – präsentiert von www.BAUENUNDBOOTEN.de

## [Unveröffentlicht]

### Neu
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
