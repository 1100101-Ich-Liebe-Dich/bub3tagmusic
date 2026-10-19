# Release 1.1 veröffentlichen – Anleitung + fertiger Text

Wie bei 1.0 – nur mit neuem Tag. Das AppImage baut und hängt GitHub selbst an.

1. Auf GitHub: **Releases → Draft a new release**
2. **Choose a tag:** `v1.1.1` eintippen → *Create new tag: v1.1.1 on publish* (Ziel: `main`)
3. **Release title:** `BuB3TAGMUSIC 1.1 – Songtext an Bord`
4. Text unten (zwischen den Linien) in das Beschreibungsfeld kopieren
5. **Set as the latest release** angehakt lassen → **Publish release**
6. Nach ein paar Minuten unter *Actions* prüfen, dass „Release – AppImage anhängen“ grün ist –
   dann hängen `BuB3TAGMUSIC-1.1.1-x86_64.AppImage` und `SHA256SUMS.txt` am Release.

Das Release 1.0.0 bleibt stehen, wie es ist.

---

## BuB3TAGMUSIC 1.1 – Songtext an Bord 🎤

### Neu
- **Songtext** für alle Formate: im Bearbeitungsfeld eine Zeile, ein Klick öffnet das Songtext-Fenster.
  Eintippen, einfügen oder aus `.lrc`/`.txt` laden (Zeitmarken werden entfernt). Gleichnamige Songtext-Dateien
  neben den Liedern übernimmt **„Aus Begleitdateien“** für ein ganzes Album auf einmal.
- **Label** (Plattenfirma) und **Original-Jahr** (Erstveröffentlichung) – auch die Schreibweisen von Picard und
  Mp3tag werden erkannt.
- **Album suchen – Deezer:** dritte Quelle neben MusicBrainz und Discogs, ohne Anmeldung – stark bei neuer und
  deutscher Musik, große Cover, Label.
- Album suchen übernimmt jetzt auch **Label** und (MusicBrainz) **Original-Jahr**; **„Ohne Remaster-Zusätze“**
  macht aus „Titel (Remastered 2011)“ einfach „Titel“.

- **Aus `‹verschieden›` wählen:** Ein Pfeil im Feld (oder Alt+↓) zeigt die vorhandenen Werte – einer davon gilt
  dann für alle gewählten Dateien.

### Verbessert
- Bearbeitungsfeld kompakter – auch bei 1366×768 alle Felder ohne Blättern
- Lange Werte zeigen den Anfang statt das Ende

### Herunterladen
`BuB3TAGMUSIC-1.1.1-x86_64.AppImage` unten unter *Assets* – ausführbar machen, Doppelklick, fertig.
Einstellungen, Zwischenspeicher und eigene Aktionen aus 1.0 bleiben erhalten: einfach die alte Datei ersetzen.

Alle Details: [Änderungen](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic/blob/main/CHANGELOG.md) ·
[README](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic#readme)

*präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de)*

---
