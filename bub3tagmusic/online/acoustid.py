"""Unbekannte Dateien erkennen (Phase 4): Audio-Fingerabdruck → AcoustID → MusicBrainz-Daten.

* Fingerabdruck per fpcalc (core/fingerprint.py), im Zwischenspeicher gemerkt
* Eine Anfrage pro Datei an api.acoustid.org, höchstens 3 pro Sekunde
* Braucht einen kostenlosen AcoustID-Key (Einstellungen → Online)
* Aus mehreren Veröffentlichungen eines Titels wird die passendste gewählt:
  gleiches Album wie in den Tags > reguläres Studioalbum > frühestes Jahr
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import OnlineError, RateLimiter, similarity
from .http import get_json

LOOKUP = "https://api.acoustid.org/v2/lookup"
META = "recordings releasegroups releases tracks"
LIMITER = RateLimiter(per_second=3)
KEY_URL = "https://acoustid.org/new-application"
GOOD_SCORE = 0.8


@dataclass
class AcoustMatch:
    score: float                 # 0..1 – wie sicher der Fingerabdruck passt
    recording_id: str
    title: str
    artist: str
    album: str = ""
    albumartist: str = ""
    year: str = ""
    track: int = 0
    track_total: int = 0
    disc: int = 0
    disc_total: int = 0
    release_id: str = ""
    kind: str = ""               # Album, Single, Compilation …
    others: int = 0              # weitere Veröffentlichungen desselben Titels
    extra: dict = field(default_factory=dict)

    def tags(self) -> dict[str, str]:
        out = {"title": self.title, "artist": self.artist}
        if self.album:
            out["album"] = self.album
        if self.albumartist:
            out["albumartist"] = self.albumartist
        if self.year:
            out["year"] = self.year
        if self.track:
            out["track"] = f"{self.track}/{self.track_total}" if self.track_total else str(self.track)
        if self.disc and self.disc_total > 1:
            out["disc"] = f"{self.disc}/{self.disc_total}"
        return out


def _artists(items) -> str:
    out = ""
    for a in items or []:
        out += (a.get("name") or "") + (a.get("joinphrase") or ("; " if a is not items[-1] else ""))
    return out.strip().rstrip(";").strip()


def _year(date) -> str:
    if isinstance(date, dict) and date.get("year"):
        return str(date["year"])
    if isinstance(date, str) and date[:4].isdigit():
        return date[:4]
    return ""


def _releases(recording: dict, current_album: str):
    """Alle Veröffentlichungen eines Titels mit Position – bewertet."""
    out = []
    for rg in recording.get("releasegroups") or []:
        rg_title = rg.get("title") or ""
        rg_type = rg.get("type") or ""
        secondary = rg.get("secondarytypes") or []
        rg_artist = _artists(rg.get("artists"))
        for rel in rg.get("releases") or [{}]:
            title = rel.get("title") or rg_title
            year = _year(rel.get("date"))
            if not year:
                events = rel.get("releaseevents") or []
                years = [_year(e.get("date")) for e in events if _year(e.get("date"))]
                year = min(years) if years else ""
            disc = track = track_total = 0
            for medium in rel.get("mediums") or []:
                for t in medium.get("tracks") or []:
                    track = int(t.get("position") or 0)
                    disc = int(medium.get("position") or 0)
                    track_total = int(medium.get("track_count") or 0)
                    break
                if track:
                    break
            rank = (
                similarity(current_album, title) if current_album else 0.0,
                1 if rg_type == "Album" and not secondary else 0,
                1 if track else 0,
                -int(year) if year else -9999,
            )
            out.append((rank, dict(album=title, albumartist=rg_artist, year=year, track=track,
                                   track_total=track_total, disc=disc,
                                   disc_total=int(rel.get("medium_count") or 0), release_id=rel.get("id") or "",
                                   kind=" + ".join([rg_type, *secondary]) if rg_type else "")))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def parse(data: dict, current_album: str = "") -> list[AcoustMatch]:
    """Antwort von /v2/lookup → Treffer (bester zuerst, jede Aufnahme nur einmal)."""
    if data.get("status") != "ok":
        err = (data.get("error") or {}).get("message", "unbekannter Fehler")
        raise OnlineError(_error_text(err))
    seen, out = set(), []
    for res in data.get("results") or []:
        score = float(res.get("score") or 0)
        for rec in res.get("recordings") or []:
            rid, title = rec.get("id") or "", rec.get("title") or ""
            if not title or rid in seen:
                continue
            seen.add(rid)
            rels = _releases(rec, current_album)
            best = rels[0][1] if rels else {}
            out.append(AcoustMatch(score, rid, title, _artists(rec.get("artists")), others=max(0, len(rels) - 1),
                                   **best))
    out.sort(key=lambda m: -m.score)
    return out


def _error_text(msg: str) -> str:
    low = msg.lower()
    if "api key" in low or "client" in low:
        return "AcoustID-Key ungültig – in Einstellungen → Online prüfen"
    if "fingerprint" in low:
        return "AcoustID kann den Fingerabdruck nicht lesen"
    return f"AcoustID: {msg}"


def _lookup(params: dict, key: str) -> dict:
    if not key:
        raise OnlineError("AcoustID-Key fehlt – kostenlos unter acoustid.org/new-application, dann in "
                          "Einstellungen → Online eintragen")
    try:
        return get_json(LOOKUP, {"client": key, "meta": META, **params}, limiter=LIMITER)
    except OnlineError as exc:
        if "lehnt die Anfrage ab" in str(exc) or "Fehler 400" in str(exc):
            raise OnlineError(_error_text(str(exc))) from exc
        raise


def lookup(fingerprint: str, duration: float, key: str, current_album: str = "") -> list[AcoustMatch]:
    data = _lookup({"duration": int(round(duration)), "fingerprint": fingerprint}, key)
    return parse(data, current_album)


def lookup_track(trackid: str, key: str, current_album: str = "") -> list[AcoustMatch]:
    """Nach AcoustID-Track-ID (für Tests und Aufzeichnungen)."""
    return parse(_lookup({"trackid": trackid}, key), current_album)
