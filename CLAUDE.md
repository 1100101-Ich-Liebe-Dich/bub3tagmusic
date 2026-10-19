# CLAUDE.md – Arbeitsnotizen für BuB3TAGMUSIC

Diese Datei ist das Gedächtnis für die Arbeit an diesem Projekt. Vor jeder Sitzung lesen,
nach jeder Sitzung aktuell halten.

## Projekt

- **BuB3TAGMUSIC** – moderner, schneller Musik-Tagger für Linux (Mp3tag-Funktionsumfang, aber modern).
- Schreibweise genau so: **BuB3TAGMUSIC**. Überall „präsentiert von www.BAUENUNDBOOTEN.de“.
- Auftraggeber: BAUENUNDBOOTEN. Gespräch auf **Deutsch, per du**, locker. Oberflächentexte Deutsch.
- Repo privat: `1100101-Ich-Liebe-Dich/bub3tagmusic`, Branch `main`, direkt auf `main` arbeiten.
- **Masterplan: `BuB3TAGMUSIC.md`** (Entscheidungen, Fahrplan mit Checkboxen, offene Punkte).
  Fortschritt dort abhaken. Änderungen zusätzlich in `CHANGELOG.md`.
- Aufgaben je Funktion als GitHub-Issues mit Meilensteinen „Phase 2/3/4“.

## Was dem Auftraggeber wichtig ist

- **Keine Installation** – lieber eine ausführbare Datei, die er **selbst mit `make` baut**.
  Fertige AppImages (≈ 60 MB) **nicht ungefragt schicken**, ihm sind sie zu groß. Anleitung: `ANLEITUNG.md`.

- **Einfach** zu bedienen, alles auf den ersten Blick klar. **Super modern** aussehen.
- **Alte Hardware + zehntausende Dateien** dürfen kein Problem sein.
- Arbeitsweise: **Ordner für Ordner** durch eine riesige Sammlung (Musik/Künstler/Album/).
- **Mehrfach-Bearbeitung** (ein Ordner oder mit Unterordnern) ist sehr wichtig.
- Bilder: `folder.jpg` im **Künstler**-Ordner = Künstlerbild, `cover.jpg` im **Album**-Ordner = Albumcover.
  Einzelne Alben/Tracks müssen trotzdem einzeln bearbeitbar sein.
- MusicBrainz: **eine** Anfrage pro Album (Album + Künstler), nicht pro Track. Max. 1 Anfrage/Sekunde.
- Discogs-Token besorgt der Auftraggeber (dann in Einstellungen → Online).
- Erst stabiles Grundgerüst, dann Schritt für Schritt. **Platzhalter für spätere Phasen immer mit anlegen.**

## Technik

- Python ≥ 3.10, **PySide6-Essentials** (nicht das volle PySide6 – spart ~250 MB; unter Python < 3.12 Version 6.8–6.10), mutagen, Pillow, qtawesome.
- **Auslieferung: AppImage** (Wunsch: keine Installation). `make` → `packaging/build_appimage.sh`
  → `dist/BuB3TAGMUSIC-<version>-x86_64.AppImage`. Fürs AppImage feste Versionen in
  `packaging/requirements-appimage.txt` (Qt 6.9 = läuft ab glibc 2.28; ab Qt 6.10 wäre glibc 2.34 nötig).
- Entwickeln: `python3 -m bub3tagmusic [ORDNER]` oder `install.sh` → `.venv`, `start.sh`.
- Version steht in `bub3tagmusic/__init__.py` (APP_VERSION) **und** `pyproject.toml` – beide ändern.
- Einstellungen `~/.config/bub3tagmusic/settings.json`, Cache `~/.cache/bub3tagmusic/cache.sqlite`.

### Architektur-Regeln

- `core/` bleibt **ohne Qt** (läuft in Hintergrund-Prozessen, ist ohne Oberfläche testbar).
- Jede Änderung an Dateien läuft über **`ui/session.py`** → landet automatisch im Rückgängig-Verlauf.
- Langsame Arbeit (Einlesen, Speichern, später Online) **immer** in `ui/workers.py`, nie im UI-Thread.
- Neue Tag-Felder: `core/fields.py` + Zuordnung je Format in `core/tags.py`.
- Spätere Funktionen stehen in **`features.py`**. Fertig → `ready=True` und
  - Werkzeug mit Vorschau: `ToolDialog`-Unterklasse in `ui/tools.py`, in `TOOL_DIALOGS` eintragen
    (`build_options()` baut links die Optionen, `compute()` liefert eine `Preview`; für Tag-Änderungen
    `field_rows()` benutzen, Häkchen mit `add_check(text, key, default, detail)`, Optionen landen
    automatisch in `settings.tool_options`)
  - sonst: Methode in `FEATURE_HANDLERS` (`ui/mainwindow.py`). Menü + Tastenkürzel existieren schon.
- Werkzeug-Logik gehört nach `core/tools.py` bzw. `core/rename.py` (ohne Qt, mit Tests in `tests/test_tools.py`).
- Änderungen pro Datei verschieden → `session.apply_changes([(item, {feld: wert})], label)` = ein Rückgängig-Schritt.
- Umbenennen: `mainwindow.run_rename(pairs, label)` → `RenameWorker` → `session.finish_rename` (+ Cache-Umzug).
- Online-Code: `online/` (ohne Qt). Alle Abrufe über `online/http.py` (`get_json`, `get_image`) – nie direkt
  urllib. Jeder Dienst hat einen eigenen `RateLimiter`; MusicBrainz ≤ 1/s, EINE Suche + EINE Trackliste pro Album.
- Extras-Fenster (Phase 4): `ui/extras.py` → `EXTRA_DIALOGS` (Duplikate, ReplayGain; Aktionen und Erkennen
  werden dort nur verlinkt). Rahmen `ExtraDialog`; lange Arbeit per `Task` (workers.py: Fortschritt + Abbrechen,
  `fn(..., progress=, cancelled=)`). Aktionen/Erkennen sind `ToolDialog`s (`ui/actions.py`, `ui/acoustid.py`).
- Externe Programme (fpcalc, rsgain) nur über `core/tools_external.find_tool()` – sucht `BUB3_FPCALC`/`BUB3_RSGAIN`,
  dann mitgeliefert (`$BUB3_BIN`, prüft ob es startet), dann PATH. Fehlt es: `install_hint(name)` anzeigen.
- Tags + Umbenennen in einem Rutsch: `mainwindow.run_rename(pairs, label, chain=True)` → `ChainStep` (ein Strg+Z).
- Dateien von außen geändert (rsgain …): danach `read_file` + `cache.put_many` + `session.refresh_records(recs)`.
- Künstler-Ordner (keine Musik direkt, Alben darunter): `artistpanel.is_artist_folder(node)`; rechts ein
  `QStackedWidget` (`win.right`) mit `win.panel` (Tags) und `win.artist_panel` (folder.jpg). Umschalten in
  `mainwindow._update_right_panel()` nach jedem Laden. Online-Suche: `win.search_artist_image(ordner)` →
  `ArtistImageDialog(win, [], "", folder=…, artist=…)`.
- Ergebnislisten statt Ordner: `win.show_files(pfade, "Bezeichnung")` bzw. `win.search_collection()`;
  `win.is_result_list` → kein „nächster Ordner“.
- Neue Felder im Datensatz (`read_file`) → `tags.RECORD_VERSION` erhöhen, dann liest der Cache alte Einträge neu.
- Neue Spalten in `filetable.COLUMNS` bei bestehenden Einstellungen ausgeblendet lassen → `NEW_HIDDEN`.
- Mehrzeilige Felder (Songtext): `Field(multiline=True)` → nicht in `PATTERN_KEYS`/`patterns.KNOWN`, nicht im
  Listenfilter, in Tabellen über `fields.one_line()`. Im Bearbeitungsfeld `ui/lyrics.LyricsField` (gleiche
  Schnittstelle wie `FieldEdit`: `show_value`, `dirty`, `refresh_icons`) + `LyricsDialog`; .lrc/.txt-Logik in `core/lyrics.py`.
- Album-Quellen: `ui/online.ALBUM_SOURCES` (MusicBrainz, Discogs, Deezer) – neue Quelle = Modul in `online/` mit
  `search_albums` + `get_album` → `AlbumMatch`, dann in `AlbumSearchDialog.search/_pick` eintragen. Felder, die eine
  Quelle nicht liefert, blendet die Vorschau aus. Neue Album-Felder → `ALBUM_FIELDS` + `ALBUM_FIELDS_VERSION` erhöhen.
- Online-Dialoge: `ui/online.py` → `ONLINE_DIALOGS` (wie `TOOL_DIALOGS`). Abfragen per `Job`, Vorschaubilder per
  `ImageLoader` (beide in `ui/workers.py`). Album-Daten + Cover gemeinsam: `session.apply_changes(..., cover=CoverData)`.
- Nur geänderte Felder schreiben, Audiodaten nie anfassen, ein Dateifehler stoppt nie den Rest.
- Massenänderungen (Umbenennen, Online-Übernahme) immer mit Vorschau.

### Design

- Themes in `ui/theme.py`: Standard **„Bauen & Booten“ (`bub`)** = Farben der Website (Erdgrün-Dunkel, Bernstein
  `#E5A00D`), dazu `bub_light`, `graphite`, `dark` (Nachtwache, bis 0.4 Standard) und `light` (Seekarte).
  `THEME_INFO` = Name, hell/dunkel, Gegenstück. Neuer Token → in ALLEN Themes ergänzen. Website-Linien sind
  halbtransparent – hier deckend auf den Grund gerechnet (QColor kennt kein rgba-Text).
  Farben nur über `theme.tok("name")`, nie hart im Code. Logo-Farbe: Token `wordmark`.
- Alte Einstellungen ohne `theme_version` mit `theme == "dark"` werden einmalig auf `bub` umgestellt.
- Schriften mitgeliefert: Inter (Text), Big Shoulders Stencil ExtraBold (nur Logo). Icons: Phosphor (`ph.`).
- Status: Grün = fertig, Gelb = ungespeichert, Rot = Fehler.
- Alles, was Dateien ohne Strg+Z verändert (ReplayGain schreiben/entfernen), braucht rote Warnung im Fenster
  (`#ToolMessage[kind="warning"]`), roten Knopf (`QPushButton[kind="danger"]`) und eine Rückfrage mit
  „Abbrechen“ als Standard. Standard-Modus ist immer der harmlose („Nur messen“).
- Texte: Satzanfang groß, klare Verben („Speichern“, nicht „Absenden“), Fehler sagen, was zu tun ist.
- Muss bei **1366×768** noch bedienbar sein.

## Vor jedem Hochladen

```bash
tests/run_all.sh          # Kern (alle Formate + Werkzeuge) + Oberfläche + Werkzeuge bedienen, ~2 Min.
tests/run_all.sh --perf   # zusätzlich Leistung mit 1.000 Alben / 50.000 Listeneinträgen
make && dist/*.AppImage --selftest ORDNER   # AppImage bauen + Starttest
```

- **Musikdienste sind von der Arbeitsumgebung aus gesperrt** (MusicBrainz, CAA, iTunes, Deezer, Discogs,
  TheAudioDB, AcoustID). Echte Antworten zeichnet GitHub auf: `tests/fixtures/online/RECORD` ändern → pushen → Workflow
  „Testdaten aufzeichnen“ abwarten → `git pull`. Die Zusammenfassung steht als Hinweise (::notice::) im Lauf und ist
  über `gh api repos/…/check-runs/<job-id>/annotations` lesbar (Logs selbst sind nicht abrufbar).
  Tests: `tests/test_online.py`, `tests/ui_online.py` (fehlende große Bilder ersetzt der Test durch ein JPEG).
  AcoustID: Key aus GitHub-Secret `ACOUSTID_KEY`, sonst Beispiel-Key der Doku; in den Aufnahmen steht immer
  `client=TESTKEY`. MusicBrainz antwortet nach vielen Aufnahmen kurz mit 503 → der Recorder wartet und wiederholt.
- Phase-4-Tests: `tests/test_extras.py` (Kern) und `tests/ui_extras.py` (eigene kleine Sammlung mit Melodien –
  Sinustöne geben keinen Fingerabdruck). fpcalc/rsgain hier: `apt-get install -y libchromaprint-tools rsgain`;
  ohne sie testen: `BUB3_FPCALC=/nix BUB3_RSGAIN=/nix` (Teile werden übersprungen bzw. Hinweis geprüft).
- Echter X-Bildschirm zum Testen: `apt-get install -y xvfb` funktioniert in der Arbeitsumgebung,
  dann `Xvfb :77 -screen 0 1366x768x24 &` und `DISPLAY=:77 …`. Screenshot: `PIL.ImageGrab.grab(xdisplay=":77")`.
- Fehlende Systembibliotheken simulieren: Dateien aus `/usr/lib/x86_64-linux-gnu` kurz wegschieben +
  `ldconfig`, danach zurück. `BUB3_DEBUG=1` zeigt, was AppRun nachreicht.

- Bei Oberflächen-Änderungen die Screenshots ansehen (`SHOTS=ordner tests/run_all.sh`).
- `BuB3TAGMUSIC.md` + `CHANGELOG.md` aktualisieren, Issues schließen (`Closes #n` im Commit).
- Commit-Nachrichten auf Deutsch, mit den Attribution-Zeilen aus den Sitzungs-Hinweisen.
- GitHub Actions führt `tests/run_all.sh` bei jedem Push aus (Python 3.10, 3.11 und 3.13).
- Logs der Actions sind von der Arbeitsumgebung aus nicht abrufbar → Fehler lokal mit
  `uv python install 3.10` + eigener venv nachstellen.
- Tags (`git push --tags`, Releases) sind über den Zugang hier nicht erlaubt – ebenso Repo-Einstellungen
  (Beschreibung, Topics, Social Preview). Dafür steht alles fertig in `docs/RELEASE-1.0.md` für den Auftraggeber.
- Bilder der GitHub-Seite (README, Banner, Theme-Collage, Vorschaubild) erzeugt `docs/make_images.py`
  (offscreen, Demo-Sammlung, ~20 s). Nach sichtbaren Oberflächen-Änderungen neu erzeugen und mit hochladen.

## Stolperfallen (schon einmal reingefallen)

- **PySide6 6.11/6.12 + Python < 3.12 = Absturz** („Fatal Python error: none_dealloc“, Exit 134).
  `QModelIndex.data()` mit leerem Ergebnis und `QFont.setHintingPreference()` geben `None` zu oft frei;
  ab Python 3.12 ist `None` unsterblich, daher fällt es dort nie auf. Lösung: `requirements.txt` installiert
  auf Python < 3.12 nur PySide6 6.8–6.10; `app._check_qt_version()` warnt sonst. Bei jedem PySide6-Update
  unter Python 3.10 testen (CI macht das). Prüfen geht mit `sys.getrefcount(None)` vor/nach vielen Aufrufen.

- **`libxkbcommon-x11` nie allein nachreichen**: Gemischt mit einer anderen `libxkbcommon`-Version
  stürzt Qt beim Start ab (Segfault). AppRun reicht sie nur als Paar nach und sonst nur, was fehlt.
- Nicht alle mitgebrachten Bibliotheken pauschal per `LD_LIBRARY_PATH` voranstellen – Systemversionen
  haben Vorrang (AppRun baut pro Start ein Temp-Verzeichnis mit Links nur auf die fehlenden).
- Erststart-Fenstergröße muss auf 1366×768 passen (`MainWindow._fit_to_screen`).
- **Comboboxen mit langem Text** sprengen schmale Spalten → `SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon`
  + `setMinimumContentsLength(12)`; dazu `setMaximumWidth` am Inhalts-Widget.
- **QSS lässt Pfeile von Combobox/Spinbox verschwinden** → `theme._arrow_files()` erzeugt SVG-Pfeile je Theme
  im Cache; im QSS per `image: url(...)`.
- **Häkchen-Texte brechen nicht um** → kurzer Text + Erklärung darunter (`ToolDialog.add_check(..., detail)`).
- Fehlermeldungen von `re` sind englisch/technisch → in `core/tools.py` in verständliches Deutsch übersetzen.
- AppImage nutzt Qt 6.9, die Entwicklung 6.12: Oberflächentests zusätzlich mit dem Python aus dem
  AppImage laufen lassen (`dist/*.AppImage --appimage-extract`, dann `squashfs-root/usr/python/bin/python3 tests/ui_tools.py …`).
- **Eigenes Python (AppImage) lädt keine System-Zertifikate von selbst** (`cert_store_stats` = 0, nur capath).
  `online/http.ca_file()` nimmt daher die Zertifikatsdatei der Distribution (Debian/Fedora/openSUSE/Alpine …),
  sonst certifi. `SSL_CERT_FILE` hat Vorrang.
- Matching nach Länge ist bei fast gleich langen Tracks mehrdeutig – nur Rückfallebene, Vorschau markiert Abweichungen.
- **Stylesheet schlägt `setFont()`**: `* { font-family … }` im QSS überschreibt Schriften aus dem Code.
  Besondere Schriften/Größen per `objectName` im QSS setzen (z. B. `QLabel#Wordmark`).
- **Variable Fonts**: Qt sieht nur die Standard-Instanz. Feste Instanz mit
  `fontTools.varLib.instancer` erzeugen (so entstand `BigShouldersStencil-ExtraBold.ttf`).
- **`selectedRows()` ist bei 50.000 Zeilen extrem langsam** (4 s) → Auswahl über `selection()`-Bereiche lesen.
- Pro Feld nicht `any(item.methode())` über 50.000 Einträge – geänderte Einträge einmal vorfiltern.
- **Prozess-Pool (spawn)** startet das Hauptskript neu → jedes ausführbare Skript braucht `if __name__ == "__main__":`.
- `&` in Button-Texten ist ein Tastenkürzel-Zeichen → `&&` schreiben.
- Gestrichelte Fokus-Rahmen kommen von Fusion → werden in `app.prepare_app()` per ProxyStyle unterdrückt.
- Combobox mit eigener QLineEdit: QSS `QComboBox QLineEdit` ohne Rahmen/Padding, sonst wird Text abgeschnitten.
- Beim Start gemerkte Ordner mit `emit=True` auswählen, sonst wird nichts geladen.
- Nach Text-/Stiländerung an Statusleisten-Labels/Buttons `adjustSize()`/`updateGeometry()`, sonst abgeschnitten.
- Cover: `CoverData.original` behält das Bild in voller Größe für `cover.jpg`; eingebettet wird verkleinert.

- **QLineEdit hat schon eine Qt-Eigenschaft `modified`** (setText() setzt sie still zurück). Eigene
  QSS-Eigenschaften nie so nennen – im Bearbeitungsfeld heißt sie `edited`, sonst bleibt der gelbe Rahmen stehen.
- `os.access(pfad, X_OK)` ist auch für Ordner wahr → Programme mit `os.path.isfile` + X_OK prüfen.
- rsgain bricht bei EINER kaputten Datei das ganze Album ab (Exit 1, keine Ausgabe) → einzeln prüfen, dann ohne sie.
- Fingerabdrücke nie jeder-gegen-jeden vergleichen (50.000² …): Index über exakt gleiche Teil-Abdrücke, dann genau.
- `QFile.moveToTrash` braucht im Test ein eigenes `XDG_DATA_HOME`, sonst landet es im echten Papierkorb.
- **Nie `pkill -f muster`**, wenn das Muster im eigenen Befehl steht – das killt die eigene Shell (Exit 144).
  Hängende Tests: PIDs über `ps -eo pid,comm` + `/proc/PID/cmdline` suchen. Hänger finden:
  `faulthandler.dump_traceback_later(25, exit=True)` – meist ein `exec()` eines Dialogs im Test.
- Release-Assets baut `.github/workflows/release.yml` (bei „Publish release“) – nicht von hier hochladen.
- **mutagen + Original-Jahr:** Beim Laden macht mutagen aus v2.3-`TORY` schon `TDOR`; beim Speichern als v2.3
  bleibt `TDOR` aber stehen (ungültig in v2.3) → `ID3Handler.save` wandelt selbst in `TORY` um. Prüfen nur mit
  `ID3(pfad, translate=False)`.
- **Deezer meldet Fehler mit Status 200** und `{"error": {...}}` im Inhalt → `deezer._check()`.
- **Aufnahme der Online-Testdaten:** MusicBrainz antwortet zwischendurch mit 503. Der Recorder wiederholt jetzt und
  behält Einträge der letzten Aufnahme, die diesmal fehlen; `acoustid.json` wird nur mit Treffern überschrieben.
  Nach jeder Aufnahme `summary.txt` lesen.

## Noch nicht geprüft

- APE- und DSF-Dateien (ffmpeg kann keine erzeugen) – gleicher Code wie WavPack bzw. MP3.
- Echtes Verhalten auf alter Hardware und mit echten großen MP3-Sammlungen (Rückmeldung abwarten).
- AcoustID mit echtem Key und echter Musik (die Aufnahme nutzt den Doku-Key + Track-ID-Abfrage).
- Mitgeliefertes rsgain braucht glibc 2.30 – auf Debian 10 nimmt das Programm dann das vom System (falls da).
