# Änderungsprotokoll

Alle wichtigen Änderungen an BuB3TAGMUSIC – präsentiert von www.BAUENUNDBOOTEN.de

## [Unveröffentlicht]

### Neu
- GitHub-Repository eingerichtet: automatische Tests bei jedem Hochladen (Python 3.10 und 3.13),
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
