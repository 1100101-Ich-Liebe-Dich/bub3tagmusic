# Release 1.1 veröffentlichen – Anleitung + fertiger Text

Wie bei 1.0 – nur mit neuem Tag. Das AppImage baut und hängt GitHub selbst an.

1. Auf GitHub: **Releases → Draft a new release**
2. **Choose a tag:** `v1.1.7` eintippen → *Create new tag: v1.1.7 on publish* (Ziel: `main`)
3. **Release title:** `BuB3TAGMUSIC 1.1 – Songtext an Bord`
4. Text unten (zwischen den Linien) in das Beschreibungsfeld kopieren
5. **Set as the latest release** angehakt lassen → **Publish release**
6. Nach ein paar Minuten unter *Actions* prüfen, dass „Release – AppImage anhängen“ grün ist –
   dann hängen `BuB3TAGMUSIC-1.1.7-x86_64.AppImage` und `SHA256SUMS.txt` am Release.

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
- **Mehr Quellen:** Album suchen auch bei **iTunes / Apple Music** und **Last.fm**; Cover suchen bei
  **Cover Art Archive, iTunes, TheAudioDB, Bandcamp und Discogs**; Künstlerbilder bei **TheAudioDB, Bandcamp, Discogs und
  Wikipedia**. Deezer liefert nur noch Tags, keine Bilder.
- **Album suchen bei allen Quellen gleichzeitig** und **„Übernehmen & weiter“**: speichert, hakt ab und sucht
  gleich im nächsten Ordner – das Fenster bleibt offen.
- **Bessere Zuordnung:** Tracks werden über Titel oder Dateinamen erkannt – auch mit „(feat. …)“, „[Live]“ und
  Nummern im Dateinamen. Suchbegriffe lassen alles in Klammern weg („Album (2020)“ → „Album“).
  Passt doch mal ein Track nicht: Zeile anklicken und den richtigen **von Hand** wählen.
- Album suchen übernimmt jetzt auch **Label** und (MusicBrainz) **Original-Jahr**; **„Ohne Remaster-Zusätze“**
  macht aus „Titel (Remastered 2011)“ einfach „Titel“.
- **Bilder Ordner für Ordner:** In Künstlerbild- und Cover-Suche springt **„Speichern & weiter“** zum nächsten
  Künstler bzw. Album ohne Bild und sucht dort gleich weiter.
- **Fehlende Tags finden** und **Fehlende Bilder finden** (*Extras*): zeigen auf einen Blick, wo in der Sammlung
  noch Titel, Interpret, Album, Tracknummer, `cover.jpg` oder `folder.jpg` fehlen.
- **Aus `‹verschieden›` wählen:** Ein Pfeil im Feld (oder Alt+↓) zeigt die vorhandenen Werte – einer davon gilt
  dann für alle gewählten Dateien.

### Verbessert
- Bearbeitungsfeld kompakter – auch bei 1366×768 alle Felder ohne Blättern
- Lange Werte zeigen den Anfang statt das Ende

### Herunterladen
`BuB3TAGMUSIC-1.1.7-x86_64.AppImage` unten unter *Assets* – ausführbar machen, Doppelklick, fertig.
Einstellungen, Zwischenspeicher und eigene Aktionen aus 1.0 bleiben erhalten: einfach die alte Datei ersetzen.

Alle Details: [Änderungen](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic/blob/main/CHANGELOG.md) ·
[README](https://github.com/1100101-Ich-Liebe-Dich/bub3tagmusic#readme)

*präsentiert von [www.BAUENUNDBOOTEN.de](https://www.BAUENUNDBOOTEN.de)*

---
