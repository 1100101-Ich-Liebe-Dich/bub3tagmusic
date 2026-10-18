# BuB3TAGMUSIC

**Moderner, schneller Musik-Tagger für Linux**
präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de)

![BuB3TAGMUSIC](docs/screenshot-dark.png)

Stand: **Version 0.1.2 – Phase 1 (Grundgerüst)**. Die Funktionen der Phasen 2–4 sind
in den Menüs „Werkzeuge“, „Online“ und „Extras“ schon als Platzhalter zu sehen.

---

## Starten – ohne Installation

BuB3TAGMUSIC ist **eine einzige Datei** (AppImage). Nichts installieren, nichts einrichten:

```bash
chmod +x BuB3TAGMUSIC-0.1.2-x86_64.AppImage     # einmalig ausführbar machen
./BuB3TAGMUSIC-0.1.2-x86_64.AppImage            # starten (oder Doppelklick)
./BuB3TAGMUSIC-0.1.2-x86_64.AppImage ~/Musik    # direkt mit einem Ordner
```

Im Programm unter ⚙ → **Ins Startmenü eintragen** – dann startet es künftig auch über das Menü.

**Läuft auf** jedem 64-Bit-Linux ab etwa 2018: Ubuntu 20.04+, Linux Mint 20+, Debian 10+, Fedora 29+,
openSUSE Leap 15.3+, Arch/Manjaro. Das AppImage bringt sein eigenes Python, Qt und alle Bibliotheken mit
(auch die Qt-Hilfsbibliotheken, die manchen Systemen fehlen – die werden aber nur benutzt, wenn sie wirklich fehlen).

Falls beim Start „FUSE“ bemängelt wird: `sudo apt install fuse3` (bzw. `fuse`), oder ohne FUSE starten mit
`./BuB3TAGMUSIC-…AppImage --appimage-extract-and-run`.

### Selbst bauen mit `make`

```bash
make              # baut dist/BuB3TAGMUSIC-<version>-x86_64.AppImage  (≈ 20 s, beim ersten Mal + Downloads)
make install      # legt die Datei nach ~/.local/bin und trägt sie ins Startmenü ein
make uninstall    # entfernt beides wieder
```

Zum Bauen reichen `bash`, `curl`, `tar` und `make` – Python, Qt & Co. lädt das Bauskript selbst
(nach `build/tools`). Auf GitHub wird das AppImage außerdem bei jedem Hochladen automatisch gebaut,
auf einem echten X-Bildschirm getestet und unter *Actions → Tests → BuB3TAGMUSIC-AppImage* bereitgestellt.

### Für Entwickler: aus dem Quellcode

```bash
./install.sh        # einmalig: eigene Python-Umgebung (.venv) + Startmenü-Eintrag
./start.sh ~/Musik  # bzw. make run
```

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
├── app.py              Programmstart (auch --version, --selftest)
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
packaging/
├── build_appimage.sh   baut das AppImage (eigenes Python 3.12, Qt 6.9, verschlankt)
├── requirements-appimage.txt   feste Versionen fürs AppImage (läuft ab glibc 2.28)
├── prune.py            wirft Ungenutztes raus (Qt-Bibliotheken per ldd ermittelt)
├── AppRun              Starter im AppImage, reicht fehlende xcb-Bibliotheken nach
└── libs/               diese xcb-Bibliotheken aus Ubuntu 20.04 (MIT/X11-Lizenz, siehe copyright/)
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
