# Release 1.0 veröffentlichen – Anleitung + fertiger Text

Tags und Releases kann nur der Repository-Besitzer anlegen. So geht's (5 Minuten):

## 1. AppImage holen

**Variante A – selbst bauen:** `git pull && make` → `dist/BuB3TAGMUSIC-1.0.0-x86_64.AppImage`

**Variante B – von GitHub:** *Actions* → letzter grüner Lauf von „Tests“ → unten unter *Artifacts*
„BuB3TAGMUSIC-AppImage“ herunterladen und entpacken (ZIP).

## 2. Release anlegen

1. Auf GitHub: **Releases → Draft a new release**
2. **Choose a tag:** `v1.0.0` eintippen → *Create new tag: v1.0.0 on publish* (Ziel: `main`)
3. **Release title:** `BuB3TAGMUSIC 1.0 – Werft frei!`
4. **Beschreibung:** den Text unten (zwischen den Linien) hineinkopieren
5. Das AppImage in das Feld *Attach binaries* ziehen
6. **Publish release**

## 3. Einmalig: Vorschaubild für Links

*Settings → General → Social preview → Edit → Upload an image* → `docs/social-preview.png` (1280 × 640).
Dann sieht ein geteilter Link auf das Projekt aus wie das Banner.

## 4. Einmalig: „About“ rechts auf der Startseite

Auf der Repository-Startseite rechts beim ⚙ neben **About**:

- **Description:**
  `BuB3TAGMUSIC – the modern, fast music tagger and cover art loader for Linux, built with Qt 6, Python and Mutagen. Edit tags, covers and file names folder by folder – individually or in bulk, always with preview. Offline, ad-free, no installation (one AppImage). Presented by www.BAUENUNDBOOTEN.de`
- **Website:** `https://www.BAUENUNDBOOTEN.de`
- **Topics:** `music-tagger` `id3` `mp3tag` `flac` `cover-art` `musicbrainz` `discogs` `acoustid` `replaygain`
  `linux` `appimage` `qt6` `pyside6` `python` `mutagen`
- Häkchen bei *Releases* setzen, *Packages* und *Deployments* weg – dann ist die Seitenleiste aufgeräumt.

---

<!-- ================= ab hier kopieren ================= -->

![BuB3TAGMUSIC](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic/raw/main/docs/banner.png)

## BuB3TAGMUSIC 1.0 – Werft frei! ⚓

**Der moderne, schnelle Musik-Tagger für Linux – präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de).**

Die erste stabile Version: Tags, Cover und Dateinamen deiner Sammlung aufräumen – Ordner für Ordner,
mit Vorschau, und auch mit zehntausenden Dateien auf einem alten Rechner flott.

### 🚀 Starten – ohne Installation

1. `BuB3TAGMUSIC-1.0.0-x86_64.AppImage` unten herunterladen
2. Rechtsklick → *Eigenschaften* → *Als Programm ausführen* erlauben (oder `chmod +x BuB3TAGMUSIC-1.0.0-x86_64.AppImage`)
3. Doppelklick – fertig. Im Programm: ⚙ → *Ins Startmenü eintragen*

Läuft auf jedem 64-Bit-Linux ab etwa 2018 (Ubuntu 20.04+, Mint 20+, Debian 10+, Fedora 29+, openSUSE, Arch).
Python, Qt, Schriften und die Hilfsprogramme `fpcalc` und `rsgain` sind schon drin.

### ✨ Das steckt drin

- **Ordner für Ordner:** Sammlungs-Baum mit Fertig-Status, *Speichern & nächster Ordner* (Strg+→)
- **Mehrfach-Bearbeitung:** ganzes Album oder ganzer Künstler auf einmal, `‹verschieden›` bleibt, wie es ist
- **Cover & Künstlerbild:** einbetten, `cover.jpg` im Album-, `folder.jpg` im Künstler-Ordner, Drag & Drop
- **Werkzeuge mit Live-Vorschau:** Tags aus Datei-/Ordnernamen, Dateinamen aus Tags, nummerieren, Schreibweise,
  Suchen & Ersetzen, Aufräumen, Ordner umbenennen
- **Aktionen:** mehrere Schritte auf einmal – ein Strg+Z nimmt alles zurück, auch das Umbenennen
- **Online:** MusicBrainz & Discogs (eine Anfrage pro Album), Cover bis 3000 px, Künstlerfotos,
  unbekannte Dateien per Fingerabdruck erkennen (AcoustID)
- **Schnellfilter:** ohne Cover, Cover < 500 px, ohne Jahr, fehlende Tags … – auch über die ganze Sammlung
- **Duplikate finden** nach Tags oder Klang – gelöscht wird nur, was du anhakst (Papierkorb)
- **ReplayGain:** messen als Standard, Schreiben nur nach ausdrücklicher Rückfrage
- **Export** als CSV oder schöne HTML-Seite
- **Fünf Farb-Themes**, Standard „Bauen & Booten“
- **Formate:** MP3, FLAC, M4A, OGG, Opus, WMA, WAV, AIFF, APE, WavPack, DSF

### 🛟 Sicher

Nur Tags werden geschrieben, nie die Musik. Alles mit Vorschau, Rückgängig auch nach dem Speichern,
Umbenennen überschreibt nie etwas, gelöscht wird nichts automatisch.

**Tipp:** Die ersten Schritte an einer Kopie eines Teils der Sammlung ausprobieren.

Alle Details: [README](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic#readme) ·
[Änderungen](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic/blob/main/CHANGELOG.md) ·
[Bau-Anleitung](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic/blob/main/ANLEITUNG.md)

<!-- ================= bis hier kopieren ================= -->
