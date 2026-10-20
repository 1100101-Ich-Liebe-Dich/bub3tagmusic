"""Deezer – dritte Quelle für Album-Daten (ohne Anmeldung, ohne Token).

Ablauf wie bei MusicBrainz:
  1. search_albums(artist, album) → EINE Suche, Liste von AlbumMatch (ohne Tracks)
  2. Nutzer wählt einen Treffer
  3. get_album(id) → Album (Label, Datum, Genre) + Trackliste mit Track-/Disc-Nummern (zwei Abrufe)

Stärken: viel neue und deutsche Musik, Label. Cover und Vorschaubilder von Deezer werden bewusst NICHT
benutzt (nicht zum Weiterverwenden gedacht) – Cover gibt es über die Cover-Suche (Strg+K).
Schwächen: das Datum ist oft das der Neuauflage (Remaster), Genres sind grob, Titel tragen gern
Zusätze wie „(Remastered 2011)“ – die entfernt das Album-Fenster auf Wunsch (base.strip_edition).
Deezer erlaubt 50 Anfragen in 5 Sekunden; wir bleiben weit darunter.
"""

from __future__ import annotations

from .base import AlbumMatch, OnlineError, RateLimiter, TrackMatch, match_score
from .http import get_json

API = "https://api.deezer.com/"
LIMITER = RateLimiter(per_second=4)

RECORD_TYPES = {"album": "Album", "single": "Single", "ep": "EP", "compile": "Compilation"}


def _check(data: dict) -> dict:
    """Deezer meldet Fehler mit Status 200 und {"error": {...}} im Inhalt."""
    err = data.get("error") if isinstance(data, dict) else None
    if not err:
        return data
    code = err.get("code") if isinstance(err, dict) else None
    if code == 4:
        raise OnlineError("Deezer: zu viele Anfragen – kurz warten und noch einmal versuchen")
    if code == 800:
        raise OnlineError("Deezer kennt dieses Album nicht (mehr)")
    msg = err.get("message", "") if isinstance(err, dict) else str(err)
    raise OnlineError(f"Deezer meldet einen Fehler: {msg or err}")


def _year(date: str) -> str:
    y = (date or "")[:4]
    return y if y.isdigit() and y != "0000" else ""


def search_albums(artist: str, album: str, limit: int = 25) -> list[AlbumMatch]:
    q = f'artist:"{artist}" album:"{album}"' if artist.strip() else album
    data = _check(get_json(API + "search/album", {"q": q, "limit": limit}, limiter=LIMITER))
    if not data.get("data") and artist.strip():        # strenge Suche ohne Treffer → locker suchen
        data = _check(get_json(API + "search/album", {"q": f"{artist} {album}", "limit": limit}, limiter=LIMITER))
    out = []
    for r in data.get("data") or []:
        who = (r.get("artist") or {}).get("name", "")
        kind = r.get("record_type", "")
        m = AlbumMatch(
            source="Deezer", source_id=str(r.get("id", "")), album=r.get("title", ""), albumartist=who,
            track_total=int(r.get("nb_tracks") or 0), formats=RECORD_TYPES.get(kind, kind.capitalize()),
            extra={"type": kind, "explicit": bool(r.get("explicit_lyrics"))})
        m.score = int(100 * match_score(artist, album, who, m.album))
        if kind not in ("album", "compile", ""):                  # Singles/EPs etwas nach hinten
            m.score = max(0, m.score - 8)
        out.append(m)
    out.sort(key=lambda m: -m.score)
    return out


def _tracks(album_id: str, embedded: list, albumartist: str) -> list[TrackMatch]:
    """Trackliste mit Disc-/Track-Nummern. Fällt auf die Liste im Album zurück (dann: Disc 1, fortlaufend)."""
    rows: list[dict] = []
    try:
        data = _check(get_json(API + f"album/{album_id}/tracks", {"limit": 500}, limiter=LIMITER))
        rows = list(data.get("data") or [])
    except OnlineError:
        rows = []
    if not rows or not all("track_position" in r for r in rows):
        rows = [dict(r, track_position=i, disk_number=1) for i, r in enumerate(embedded or [], 1)]
    tracks = []
    for i, r in enumerate(rows, 1):
        tracks.append(TrackMatch(
            position=int(r.get("track_position") or i), title=(r.get("title") or "").strip(),
            artist=(r.get("artist") or {}).get("name", "") or albumartist,
            length=float(r.get("duration") or 0), disc=int(r.get("disk_number") or 1)))
    tracks.sort(key=lambda t: (t.disc, t.position))
    discs = sorted({t.disc for t in tracks})
    remap = {d: i for i, d in enumerate(discs, 1)}            # Discs lückenlos 1, 2, …
    per_disc: dict[int, int] = {}
    for t in tracks:
        t.disc = remap[t.disc]
        per_disc[t.disc] = per_disc.get(t.disc, 0) + 1
    for t in tracks:
        t.track_total = per_disc[t.disc]
    return tracks


def get_album(album_id: str) -> AlbumMatch:
    data = _check(get_json(API + f"album/{album_id}", limiter=LIMITER))
    who = (data.get("artist") or {}).get("name", "")
    tracks = _tracks(album_id, (data.get("tracks") or {}).get("data") or [], who)
    genres = [g.get("name", "") for g in (data.get("genres") or {}).get("data") or [] if g.get("name")]
    kind = data.get("record_type", "")
    return AlbumMatch(
        source="Deezer", source_id=str(album_id), album=(data.get("title") or "").strip(), albumartist=who,
        year=_year(data.get("release_date", "")), label=(data.get("label") or "").strip(),
        genre=genres[0] if genres else "", track_total=len(tracks),
        disc_total=max([t.disc for t in tracks] or [1]), tracks=tracks,
        formats=RECORD_TYPES.get(kind, kind.capitalize()),
        extra={"release_date": data.get("release_date", ""), "upc": data.get("upc", ""), "type": kind},
    )
