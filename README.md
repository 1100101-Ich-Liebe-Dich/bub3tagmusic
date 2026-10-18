# BuB3TAGMUSIC

**Moderner, schneller Musik-Tagger für Linux**
präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de)

![BuB3TAGMUSIC](docs/screenshot-dark.png)

Stand: **Version 0.1.0 – Phase 1 (Grundgerüst)**. Die Funktionen der Phasen 2–4 sind
in den Menüs „Werkzeuge“, „Online“ und „Extras“ schon als Platzhalter zu sehen.

---

## Installieren & starten

```bash
cd BuB3TAGMUSIC
./install.sh        # einmalig: eigene Python-Umgebung + Startmenü-Eintrag
./start.sh          # oder über das Startmenü „BuB3TAGMUSIC“
./start.sh ~/Musik  # direkt mit einem Ordner starten
```

Voraussetzung ist Python 3.10 oder neuer. Fehlt etwas, sagt `install.sh` genau, was zu tun ist.

- Debian/Ubuntu/Mint: `sudo apt install python3-venv libxcb-cursor0`
- Fedora: `sudo dnf install python3 xcb-util-cursor`
- Arch/Manjaro: `sudo pacman -S python`

Es wird nichts systemweit installiert: alles liegt im Programmordner (`.venv`).
Einstellungen: `~/.config/bub3tagmusic/`, Zwischenspeicher: `~/.cache/bub3tagmusic/`.

> **Erste Tests bitte an einer Kopie** eines Teils der Sammlung.

---

## So arbeitest du damit

1. **Sammlung öffnen** (Strg+O) – oder den Musik-Ordner ins Fenster ziehen.
   Links erscheint der Baum: Künstler → Alben, mit Fortschritt („12 von 340 Alben fertig“).
2. **Album anklicken.** Alle Dateien werden geladen und gleich ausgewählt.
3. **Rechts bearbeiten.** Gleiche Werte stehen im Feld, unterschiedliche zeigen `‹verschieden›`.
   Was du einträgst, gilt für alle ausgewählten Dateien. Nicht angefasste Felder bleiben, wie sie sind.
   Geänderte Werte werden gelb markiert, bis gespeichert ist.
4. **Cover:** Bild aufs Cover-Feld ziehen, „Bild laden …“, „Aus Ordner“ (übernimmt `cover.jpg`/`folder.jpg`)
   oder unter „Weitere“: einfügen, als `cover.jpg` speichern, Künstlerbild (`folder.jpg`) festlegen, entfernen.
5. **Strg+→ – Speichern & nächster Ordner:** speichert, hakt das Album ab ✓ und springt zum nächsten offenen Album.

**Mehrere Ordner auf einmal:** Strg+Klick im Baum, oder den Schalter **Unterordner** (Strg+R) einschalten
und einen Künstler- oder den Sammlungsordner anklicken.

**Rückgängig (Strg+Z)** nimmt Bearbeitungen zurück – und auch schon Gespeichertes:
Vor jedem Speichern merkt sich das Programm die alten Werte (die letzten 20 Speichervorgänge).

### Tastenkürzel

| Kürzel | Funktion |
|---|---|
| Strg+→ / Strg+← | Speichern & nächster offener Ordner / vorheriger Ordner |
| Strg+S | Speichern |
| Strg+Z | Rückgängig |
| Strg+D | Ordner als fertig / offen markieren |
| Strg+R | Unterordner mitladen an/aus |
| Strg+A | Alle Dateien auswählen |
| Strg+E | Zum Feld „Titel“ |
| F2 | Zelle in der Liste bearbeiten |
| Strg+F | Liste filtern |
| Strg+Shift+V | Bild aus der Zwischenablage als Cover |
| F5 | Neu einlesen |
| Strg+, | Einstellungen |
| F1 | Alle Tastenkürzel |

Rechtsklick auf die Spaltenköpfe blendet Spalten ein/aus (Albuminterpret, Komponist, Kommentar, Ordner …).
Klick auf einen Spaltenkopf sortiert, ein dritter Klick stellt die Ordner-Reihenfolge wieder her.

---

## Formate

MP3 (ID3v2.3 / v2.4, ID3v1), FLAC, M4A/AAC/ALAC, OGG Vorbis, Opus, WMA, WAV, AIFF, APE, WavPack, DSF.

- MP3 wird standardmäßig als **ID3v2.3** geschrieben (läuft auch auf Autoradios); v2.4 ist in den Einstellungen wählbar.
- Es werden **nur geänderte Felder** geschrieben – alle anderen Tags bleiben unberührt. Audiodaten werden nie verändert.
- Eingebettete Cover werden auf 600 px verkleinert (einstellbar), `cover.jpg` im Ordner bleibt in voller Größe.

---

## Für Entwickler

```
bub3tagmusic/
├── app.py              Programmstart
├── features.py         Fahrplan: alle Funktionen der Phasen 2–4 (baut die Menüs)
├── core/               ohne Qt – auch in Hintergrund-Prozessen nutzbar
│   ├── fields.py       einheitliche Feldnamen (title, artist, …)
│   ├── tags.py         Lesen/Schreiben aller Formate (mutagen)
│   ├── covers.py       Bilder prüfen, verkleinern, als Datei speichern
│   ├── scanner.py      Ordnerbaum, Dateilisten, paralleles Einlesen
│   ├── cache.py        SQLite: Tags + Ordner-Status
│   ├── model.py        eine geladene Datei mit Bearbeitungsstand
│   ├── undo.py         Rückgängig-Verlauf (Bearbeiten + Speichern)
│   ├── patterns.py     %artist% - %title% (Baustein Phase 2, schon getestet)
│   └── settings.py     Einstellungen (JSON)
├── online/             Phase 3/4: Schnittstellen + Datentypen stehen schon
│   ├── base.py         AlbumMatch, CoverCandidate, RateLimiter (1 Anfrage/s)
│   └── musicbrainz.py, discogs.py, coversearch.py, artistimages.py, acoustid.py
├── ui/
│   ├── mainwindow.py   Hauptfenster, Speichern, Rückgängig, Navigation
│   ├── session.py      alle Bearbeitungen laufen hier durch (→ Rückgängig)
│   ├── workers.py      Hintergrund: Baum scannen, laden, speichern
│   ├── foldertree.py   Ordnerbaum mit Fertig-Status
│   ├── filetable.py    schnelle Tabelle (Sortieren/Filtern im Modell)
│   ├── editpanel.py    Bearbeitungsfeld + Cover-Aktionen
│   ├── coverwidget.py  Cover-Anzeige mit Drag & Drop
│   ├── dialogs.py      Einstellungen, Tastenkürzel, Über, Fehlerliste, Toast
│   ├── theme.py        Farben „Nachtwache“ (dunkel) und „Seekarte“ (hell)
│   └── icons.py        Phosphor-Icons
└── resources/          Schriften (Inter, Big Shoulders Stencil), App-Icon
```

**Neue Funktion aus dem Fahrplan fertig?** In `features.py` `ready=True` setzen und in
`ui/mainwindow.py` unter `FEATURE_HANDLERS` die Methode eintragen – Menüeintrag und Tastenkürzel gibt es dann schon.

### Tests

```bash
tests/run_all.sh           # alles: Kern (alle Formate) + Oberfläche durchklicken (braucht ffmpeg)
tests/run_all.sh --perf    # zusätzlich Leistung mit 1.000 Alben / 50.000 Listeneinträgen
python3 tests/make_testfiles.py ZIEL --collection 100   # Test-Sammlung zum Ausprobieren erzeugen
```

Auf GitHub laufen die Tests bei jedem Hochladen automatisch (Python 3.10, 3.11 und 3.13), inklusive Screenshots.
Arbeitsnotizen und Regeln fürs Weiterentwickeln: `CLAUDE.md`. Änderungen: `CHANGELOG.md`.

Lizenzen der mitgelieferten Schriften: `bub3tagmusic/resources/fonts/OFL-*.txt` (SIL Open Font License).
