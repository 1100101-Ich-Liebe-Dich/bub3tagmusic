# BuB3TAGMUSIC bauen – Schritt für Schritt

präsentiert von www.BAUENUNDBOOTEN.de

Am Ende hast du **eine einzige Datei**, die BuB3TAGMUSIC startet – ohne Installation.
Das Bauen dauert beim ersten Mal ein paar Minuten (Downloads), danach etwa 20 Sekunden.

**Du brauchst:** ein 64-Bit-Linux, Internet beim ersten Bauen und etwa 1 GB freien Platz.

---

## 1. Werkzeuge installieren (nur einmal)

| System | Befehl |
|---|---|
| Ubuntu, Linux Mint, Debian | `sudo apt install make wget git` |
| Fedora | `sudo dnf install make wget git` |
| Arch, Manjaro | `sudo pacman -S make wget git` |
| openSUSE | `sudo zypper install make wget git` |

Mehr braucht es nicht – Python, Qt und alles andere lädt der Bauvorgang selbst.
Auch die Hilfsprogramme für die Extras – `fpcalc` (Fingerabdruck: Erkennen, Duplikate) und `rsgain`
(ReplayGain) – lädt `make` gleich mit und packt sie ins AppImage. Es muss also nichts extra installiert werden.

## 2. Code holen

**Am einfachsten:** Auf GitHub im Repository oben auf **Code → Download ZIP** klicken und die ZIP-Datei
entpacken (z. B. nach `~/bub3tagmusic`).

**Oder mit git** (praktisch für spätere Updates):

```bash
git clone https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic.git ~/bub3tagmusic
```

Später aktualisieren: `cd ~/bub3tagmusic && git pull && make`

## 3. Bauen

```bash
cd ~/bub3tagmusic
make
```

Ohne `make` geht es genauso mit dem Skript: `sh build.sh` (mit `sh build.sh --install` gleich ins Startmenü).

Fertig ist es, wenn unten steht:

```
== Fertig
…/dist/BuB3TAGMUSIC-1.1.4-x86_64.AppImage (64M)
```

## 4. Starten

**Direkt:**

```bash
./dist/BuB3TAGMUSIC-*-x86_64.AppImage
```

**Ins Startmenü** (empfohlen):

```bash
make install
```

Danach findest du **BuB3TAGMUSIC** im Startmenü. Die Datei liegt dann unter `~/.local/bin/BuB3TAGMUSIC.AppImage`.

## 5. Neue Version

```bash
cd ~/bub3tagmusic
git pull            # oder neue ZIP herunterladen und drüber entpacken
make install
```

Deine Einstellungen und der Fertig-Status der Ordner bleiben erhalten.

## 6. Entfernen

```bash
make uninstall      # Datei und Startmenü-Eintrag weg
make distclean      # Bau-Ordner aufräumen (Downloads, ca. 300 MB)
```

Einstellungen liegen in `~/.config/bub3tagmusic`, der Zwischenspeicher in `~/.cache/bub3tagmusic` –
die kannst du bei Bedarf auch löschen. An deinen Musikdateien ändert nichts davon etwas.

---

## Wenn etwas nicht klappt

| Meldung | Lösung |
|---|---|
| `make: Befehl nicht gefunden` | Schritt 1 – Werkzeuge installieren |
| `Zum Herunterladen fehlt curl oder wget` | `sudo apt install wget` |
| `Nur x86_64 … wird unterstützt` | Es braucht einen 64-Bit-PC – Qt 6 gibt es nicht für 32 Bit |
| beim Start etwas mit **FUSE** | `sudo apt install fuse3` – oder starten mit `--appimage-extract-and-run` hinten dran |
| Programm startet nicht, kein Fenster | Im Terminal starten: `~/.local/bin/BuB3TAGMUSIC.AppImage` – die Ausgabe auf GitHub unter **Issues → Fehler melden** einfügen |

**Läuft auf:** Ubuntu 20.04+, Linux Mint 20+, Debian 10+, Fedora 29+, openSUSE Leap 15.3+, Arch/Manjaro.

**Kurzer Selbsttest** (prüft den Start, ändert nichts):

```bash
./dist/BuB3TAGMUSIC-*-x86_64.AppImage --selftest ~/Musik
```

→ Es sollte `SELFTEST OK` erscheinen.
