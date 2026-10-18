# BuB3TAGMUSIC

**Moderner, schneller Musik-Tagger für Linux**
präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de)

![BuB3TAGMUSIC](docs/screenshot-dark.png)

Stand: **Version 0.9.0 – Release-Kandidat vor 1.0**. Alle geplanten Phasen sind umgesetzt.

---

## Bauen & starten – ohne Installation

BuB3TAGMUSIC wird mit `make` zu **einer einzigen Datei** (AppImage) gebaut, die ohne Installation läuft.
**Schritt-für-Schritt-Anleitung: [ANLEITUNG.md](ANLEITUNG.md)** – in Kurzform:

```bash
sudo apt install make wget      # einmalig (Fedora: dnf, Arch: pacman)
make                            # baut dist/BuB3TAGMUSIC-<version>-x86_64.AppImage
make install                    # optional: ins Startmenü (make uninstall entfernt es wieder)
```

Zum Bauen reichen `make` und `curl` oder `wget` – Python, Qt & Co. lädt das Bauskript selbst
(nach `build/tools`). Läuft auf jedem 64-Bit-Linux ab etwa 2018: Ubuntu 20.04+, Linux Mint 20+,
Debian 10+, Fedora 29+, openSUSE Leap 15.3+, Arch/Manjaro.

Fertige AppImages baut GitHub außerdem bei jedem Hochladen (*Actions → Tests → BuB3TAGMUSIC-AppImage*).

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

### Werkzeuge (Menü „Werkzeuge“, Alt+1 … Alt+6 oder Rechtsklick in der Liste)

Alle Werkzeuge arbeiten auf der Auswahl (oder auf allen Dateien der Liste, wenn nichts ausgewählt ist)
und zeigen **vorher eine Live-Vorschau**: geänderte Werte gelb, Probleme rot.

![Werkzeug](docs/screenshot-werkzeug.png)

| Werkzeug | Was es macht |
|---|---|
| **Tags aus Dateiname** (Alt+1) | Füllt Felder aus Datei- und Ordnernamen, z. B. `%artist%/%year% - %album%/%track% - %title%`. „/“ trennt Ordnerebenen, `%dummy%` überspringt Teile. Tippfehler im Muster werden erkannt. |
| **Dateinamen aus Tags** (Alt+2) | Benennt Dateien um, z. B. `%track% - %title%` → `03 - Am Kai.mp3`. Prüft vorher fehlende Tags und doppelte Namen, überschreibt nie etwas, auch Tauschen klappt. Wahlweise USB-/Windows-tauglich. |
| **Tracks nummerieren** (Alt+3) | In Listen-Reihenfolge, pro Ordner neu, mit Gesamtzahl (3/12), führender Null oder Disc-Nummer aus Ordnernamen (CD1, Disc 2 …). |
| **Groß-/Kleinschreibung** (Alt+4) | `DER TITEL` → `Der Titel`. Kleine Wörter (und, der, the …) und feste Schreibweisen (AC/DC …) einstellbar; gemischte Schreibweisen wie „iPhone“ bleiben geschützt. |
| **Suchen & Ersetzen** (Alt+5) | In gewählten Feldern, wahlweise Groß/klein, ganze Wörter oder reguläre Ausdrücke (`$1` / `\1`). |
| **Aufräumen** | Doppelte Leerzeichen, Unterstriche, leere Klammern, unsichtbare Zeichen, „ft.“ → „feat.“, führende Nullen. |
| **Ordner umbenennen** (Alt+6) | Album-Ordner nach ihren Tags, z. B. `%year% - %album%`. Alles im Ordner bleibt beisammen, der Fertig-Status wandert mit. |

Beim Umbenennen von Dateien wandern gleichnamige Begleitdateien (`01 - Lied.lrc`, `.txt`, `.srt` …) mit.

Übernehmen wirkt wie jede Bearbeitung: gelb markiert, **Strg+S** speichert, **Strg+Z** nimmt das ganze
Werkzeug in einem Schritt zurück. Umbenennen passiert sofort – Strg+Z benennt zurück.

### Online (Menü „Online“ oder Rechtsklick in der Liste)

![Album suchen](docs/screenshot-online.png)

| Funktion | Was sie macht |
|---|---|
| **Album suchen** (Strg+L) | Sucht das Album bei **MusicBrainz** oder **Discogs** – eine Anfrage pro Album, Interpret und Album sind aus Tags oder Ordnernamen vorbelegt. Zeigt die Trackliste zugeordnet zu deinen Dateien (nach Tracknummer, Reihenfolge oder Länge) und übernimmt nur die Felder, die du auswählst – auf Wunsch samt Cover. |
| **Cover suchen** (Strg+K) | Bildergitter aus Cover Art Archive, iTunes (bis 3000 px) und Deezer. Einbetten und/oder als `cover.jpg` in den Album-Ordner. Doppelklick übernimmt. |
| **Künstlerbild suchen** (Strg+J) | Fotos von Deezer und TheAudioDB, gespeichert als `folder.jpg` im Künstler-Ordner. |

Alles außer Discogs funktioniert ohne Anmeldung. Für Discogs einen kostenlosen Token unter
*Einstellungen → Online* eintragen (discogs.com → Settings → Developers).

### Schnellfilter (über der Liste)

Chips **Ohne Cover · Cover < 500 px · Ohne Jahr · Fehlende Tags · Ungespeichert · Lesefehler** – mehrere
gleichzeitig möglich, mit Anzahl. **Ganze Sammlung** sucht dieselben Filter (und den Suchtext) in der ganzen
Sammlung und holt die Treffer in die Liste – z. B. „alle ohne Cover“ und dann gleich *Cover suchen*.
Ein-/ausblenden über *Extras → Erweiterte Filter*.

### Extras (Menü „Extras“)

![Aktionen](docs/screenshot-aktionen.png)

| Funktion | Was sie macht |
|---|---|
| **Aktionen** (Alt+7) | Mehrere Schritte als Aktion speichern und auf einmal ausführen: Aufräumen, Schreibweise, Ersetzen, Feld setzen (z. B. Albuminterpret = `%artist%`), Tags aus Dateiname, Nummerieren, Umbenennen. Mit Vorschau; Strg+Z nimmt alles in einem Schritt zurück. Beispiel: „Album fertig machen“. |
| **Unbekannte Dateien erkennen** (Strg+Shift+L) | Erkennt Dateien ohne Tags am Klang (Fingerabdruck + AcoustID) und schlägt Titel, Interpret, Album, Jahr, Track vor. Braucht einen kostenlosen AcoustID-Key (*Einstellungen → Online*). |
| **ReplayGain** | Misst die Lautheit (Track + Album, Album = Ordner). Standard ist **„Nur messen“** – da wird nichts geschrieben. In die Dateien schreiben oder ReplayGain-Tags entfernen geht nur nach roter Warnung und ausdrücklicher Rückfrage (lässt sich nicht mit Strg+Z zurücknehmen). Die Musik selbst bleibt immer unverändert. Spalten „RG Track“/„RG Album“ per Rechtsklick auf den Spaltenkopf. |
| **Duplikate finden** | In der Liste oder der ganzen Sammlung – nach Interpret + Titel oder nach Klang (auch ohne Tags). Beste Qualität ist markiert; gelöscht wird nur, was du anhakst (in den Papierkorb). |
| **Liste exportieren** (Strg+Shift+E) | Sichtbare Spalten als CSV (für LibreOffice/Excel) oder als schöne HTML-Seite zum Weitergeben und Drucken. |

Die Hilfsprogramme `fpcalc` (Fingerabdruck) und `rsgain` (ReplayGain) bringt das mit `make` gebaute
AppImage mit. Wer aus dem Quellcode startet, installiert sie über die Paketverwaltung – das Programm
zeigt bei Bedarf den passenden Befehl.

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
| Alt+1 … Alt+6 | Werkzeuge (Tags aus Dateiname, Umbenennen, Nummerieren, Schreibweise, Ersetzen, Ordner) |
| Alt+7 | Aktionen |
| Strg+L / Strg+K / Strg+J | Album / Cover / Künstlerbild online suchen |
| Strg+Shift+L | Unbekannte Dateien erkennen (AcoustID) |
| Strg+Shift+E | Liste exportieren |
| F5 | Neu einlesen |
| Strg+, | Einstellungen |
| F1 | Alle Tastenkürzel |

Rechtsklick auf die Spaltenköpfe blendet Spalten ein/aus (Albuminterpret, Komponist, Kommentar, Ordner, ReplayGain …).

**Farben:** ⚙ → *Farben* – „Bauen & Booten“ (Standard, Farben von www.BAUENUNDBOOTEN.de), „Bauen & Booten – hell“,
„Ankerplatz – Graphit“, „Nachtwache“ und „Seekarte“. *Hell / Dunkel umschalten* wechselt zum passenden Gegenstück.
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
│   ├── patterns.py     Muster %artist% - %title% (beide Richtungen, mit Ordnerebenen)
│   ├── tools.py        Werkzeug-Logik: nummerieren, Schreibweise, ersetzen, aufräumen
│   ├── rename.py       Umbenennen: Plan + Prüfung + sicheres Ausführen (zweistufig)
│   ├── filters.py      Schnellfilter
│   ├── export.py       CSV / HTML
│   ├── actions.py      Aktionen (Schrittketten, actions.json)
│   ├── duplicates.py   Duplikate nach Tags / Klang
│   ├── fingerprint.py  fpcalc, kompakte Form für AcoustID, Vergleich
│   ├── replaygain.py   rsgain aufrufen und auswerten
│   ├── tools_external.py  Hilfsprogramme finden, Installationshinweis je Distribution
│   └── settings.py     Einstellungen (JSON)
├── online/             ohne Qt
│   ├── base.py         AlbumMatch, CoverCandidate, RateLimiter, Ähnlichkeit
│   ├── http.py         urllib, Wartezeiten, Zertifikate, Speicher, austauschbar für Tests
│   ├── musicbrainz.py, discogs.py, coversearch.py, artistimages.py
│   ├── matching.py     Dateien ↔ Album-Tracks zuordnen
│   └── acoustid.py     Erkennen per Fingerabdruck (AcoustID)
├── ui/
│   ├── mainwindow.py   Hauptfenster, Speichern, Rückgängig, Navigation
│   ├── session.py      alle Bearbeitungen laufen hier durch (→ Rückgängig)
│   ├── workers.py      Hintergrund: Baum scannen, laden, speichern, Task (Fortschritt + Abbrechen)
│   ├── foldertree.py   Ordnerbaum mit Fertig-Status
│   ├── filetable.py    schnelle Tabelle (Sortieren/Filtern im Modell)
│   ├── editpanel.py    Bearbeitungsfeld + Cover-Aktionen
│   ├── coverwidget.py  Cover-Anzeige mit Drag & Drop
│   ├── dialogs.py      Einstellungen, Tastenkürzel, Über, Fehlerliste, Toast
│   ├── tools.py        Werkzeug-Dialoge mit Live-Vorschau (ToolDialog + 6 Werkzeuge)
│   ├── widgets.py      Bausteine: Muster-Feld, Feld-Chips, Fließ-Layout
│   ├── online.py       Album-, Cover- und Künstlerbild-Suche
│   ├── filterbar.py    Schnellfilter-Leiste
│   ├── export.py       Export-Dialog
│   ├── actions.py      Aktionen-Fenster + Schritt-Editor
│   ├── extras.py       Duplikate, ReplayGain (EXTRA_DIALOGS)
│   ├── acoustid.py     Unbekannte Dateien erkennen
│   ├── theme.py        Farb-Themes: „Bauen & Booten“ (Standard), hell, Graphit, Nachtwache, Seekarte
│   └── icons.py        Phosphor-Icons
└── resources/          Schriften (Inter, Big Shoulders Stencil), App-Icon, Logo-Schrift für HTML-Export
packaging/
├── build_appimage.sh   baut das AppImage (eigenes Python 3.12, Qt 6.9, fpcalc, rsgain, verschlankt)
├── requirements-appimage.txt   feste Versionen fürs AppImage (läuft ab glibc 2.28)
├── prune.py            wirft Ungenutztes raus (Qt-Bibliotheken per ldd ermittelt)
├── AppRun              Starter im AppImage, reicht fehlende xcb-Bibliotheken nach
└── libs/               diese xcb-Bibliotheken aus Ubuntu 20.04 (MIT/X11-Lizenz, siehe copyright/)
```

**Neue Funktion aus dem Fahrplan fertig?** In `features.py` `ready=True` setzen und
– für ein Werkzeug mit Vorschau – eine `ToolDialog`-Unterklasse in `ui/tools.py` unter `TOOL_DIALOGS` eintragen
(Online: `ONLINE_DIALOGS`, eigene Fenster: `EXTRA_DIALOGS` in `ui/extras.py`),
sonst die Methode in `ui/mainwindow.py` unter `FEATURE_HANDLERS`. Menüeintrag und Tastenkürzel gibt es dann schon.

### Tests

```bash
tests/run_all.sh           # alles: Formate, Werkzeuge, Online (aufgezeichnet), Extras, Oberfläche
                           # (braucht ffmpeg; fpcalc + rsgain für die Extras-Teile, sonst übersprungen)
tests/run_all.sh --perf    # zusätzlich Leistung mit 1.000 Alben / 50.000 Listeneinträgen
python3 tests/make_testfiles.py ZIEL --collection 100   # Test-Sammlung zum Ausprobieren erzeugen
```

Auf GitHub laufen die Tests bei jedem Hochladen automatisch (Python 3.10, 3.11 und 3.13), inklusive Screenshots.
Die Online-Tests spielen echte, aufgezeichnete Antworten ab (`tests/fixtures/online/`). Neu aufzeichnen:
`tests/fixtures/online/RECORD` ändern und hochladen – der Workflow „Testdaten aufzeichnen“ erledigt den Rest.
Arbeitsnotizen und Regeln fürs Weiterentwickeln: `CLAUDE.md`. Änderungen: `CHANGELOG.md`.

Lizenzen der mitgelieferten Schriften: `bub3tagmusic/resources/fonts/OFL-*.txt` (SIL Open Font License).
Im AppImage: `fpcalc` (Chromaprint, LGPL 2.1) und `rsgain` (BSD 2-Clause), siehe `usr/share/doc/bub3tagmusic/`.
