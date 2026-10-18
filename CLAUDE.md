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
- Start: `python3 -m bub3tagmusic [ORDNER]`; Installation beim Nutzer: `install.sh` → `.venv` + Startmenü.
- Einstellungen `~/.config/bub3tagmusic/settings.json`, Cache `~/.cache/bub3tagmusic/cache.sqlite`.

### Architektur-Regeln

- `core/` bleibt **ohne Qt** (läuft in Hintergrund-Prozessen, ist ohne Oberfläche testbar).
- Jede Änderung an Dateien läuft über **`ui/session.py`** → landet automatisch im Rückgängig-Verlauf.
- Langsame Arbeit (Einlesen, Speichern, später Online) **immer** in `ui/workers.py`, nie im UI-Thread.
- Neue Tag-Felder: `core/fields.py` + Zuordnung je Format in `core/tags.py`.
- Spätere Funktionen stehen in **`features.py`**. Fertig → `ready=True` + Methode in
  `FEATURE_HANDLERS` (`ui/mainwindow.py`). Menü + Tastenkürzel existieren schon.
- Online-Code: `online/` – Datentypen (`AlbumMatch`, `CoverCandidate`) und `RateLimiter` sind da.
- Nur geänderte Felder schreiben, Audiodaten nie anfassen, ein Dateifehler stoppt nie den Rest.
- Massenänderungen (Umbenennen, Online-Übernahme) immer mit Vorschau.

### Design

- Themes in `ui/theme.py`: „Nachtwache“ (dunkel, Hafenblau) und „Seekarte“ (hell). Akzent Bojen-Orange.
  Farben nur über `theme.tok("name")`, nie hart im Code.
- Schriften mitgeliefert: Inter (Text), Big Shoulders Stencil ExtraBold (nur Logo). Icons: Phosphor (`ph.`).
- Status: Grün = fertig, Gelb = ungespeichert, Rot = Fehler.
- Texte: Satzanfang groß, klare Verben („Speichern“, nicht „Absenden“), Fehler sagen, was zu tun ist.
- Muss bei **1366×768** noch bedienbar sein.

## Vor jedem Hochladen

```bash
tests/run_all.sh          # Kern (alle Formate) + Oberfläche durchklicken, ~1 Min.
tests/run_all.sh --perf   # zusätzlich Leistung mit 1.000 Alben / 50.000 Listeneinträgen
```

- Bei Oberflächen-Änderungen die Screenshots ansehen (`SHOTS=ordner tests/run_all.sh`).
- `BuB3TAGMUSIC.md` + `CHANGELOG.md` aktualisieren, Issues schließen (`Closes #n` im Commit).
- Commit-Nachrichten auf Deutsch, mit den Attribution-Zeilen aus den Sitzungs-Hinweisen.
- GitHub Actions führt `tests/run_all.sh` bei jedem Push aus (Python 3.10, 3.11 und 3.13).
- Logs der Actions sind von der Arbeitsumgebung aus nicht abrufbar → Fehler lokal mit
  `uv python install 3.10` + eigener venv nachstellen.
- Tags (`git push --tags`, Releases) sind über den Zugang hier nicht erlaubt.

## Stolperfallen (schon einmal reingefallen)

- **PySide6 6.11/6.12 + Python < 3.12 = Absturz** („Fatal Python error: none_dealloc“, Exit 134).
  `QModelIndex.data()` mit leerem Ergebnis und `QFont.setHintingPreference()` geben `None` zu oft frei;
  ab Python 3.12 ist `None` unsterblich, daher fällt es dort nie auf. Lösung: `requirements.txt` installiert
  auf Python < 3.12 nur PySide6 6.8–6.10; `app._check_qt_version()` warnt sonst. Bei jedem PySide6-Update
  unter Python 3.10 testen (CI macht das). Prüfen geht mit `sys.getrefcount(None)` vor/nach vielen Aufrufen.

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

## Noch nicht geprüft

- APE- und DSF-Dateien (ffmpeg kann keine erzeugen) – gleicher Code wie WavPack bzw. MP3.
- Echtes Verhalten auf alter Hardware und mit echten großen MP3-Sammlungen (Rückmeldung abwarten).
