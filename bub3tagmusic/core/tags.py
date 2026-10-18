"""Tags lesen und schreiben – für alle unterstützten Formate.

Jedes Format bekommt einen kleinen "Handler", der die einheitlichen
Feldnamen aus core/fields.py auf die echten Tag-Namen abbildet.

Grundregeln:
  * Es werden nur die Felder geschrieben, die sich geändert haben.
    Alle anderen Tags (auch unbekannte) bleiben unangetastet.
  * Audiodaten werden nie verändert – nur der Tag-Bereich.
  * Mehrfachwerte (z. B. zwei ARTIST-Einträge) werden als "A; B" angezeigt.
"""

from __future__ import annotations

import base64
import os
import struct

import mutagen
from mutagen import MutagenError
from mutagen.aiff import AIFF
from mutagen.apev2 import BINARY, APEValue, APEv2File
from mutagen.asf import ASF, ASFByteArrayAttribute
from mutagen.dsf import DSF
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, COMM, ID3, Frames
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from .covers import CoverData, image_info, sniff_mime
from .fields import FIELD_KEYS, join_number, split_number

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".flac", ".m4a", ".m4b", ".mp4", ".alac", ".ogg", ".oga", ".opus",
    ".wma", ".asf", ".wav", ".aif", ".aiff", ".aifc", ".ape", ".wv", ".dsf",
})

MULTI_SEP = "; "
FRONT_TYPES = (0, 3)  # "Sonstiges" und "Vorderseite" gelten als Albumcover


class TagWriteError(Exception):
    """Fehler mit verständlicher Meldung für die Oberfläche."""


def is_audio(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in AUDIO_EXTENSIONS


def _join(values) -> str:
    out = []
    for v in values or []:
        s = str(v).strip("\x00").strip()
        if s:
            out.append(s)
    return MULTI_SEP.join(out)


# ======================================================================
# ID3 (MP3, WAV, AIFF, DSF)
# ======================================================================
class ID3Handler:
    kind = "id3"
    TEXT = {
        "title": "TIT2", "artist": "TPE1", "albumartist": "TPE2", "album": "TALB",
        "year": "TDRC", "track": "TRCK", "disc": "TPOS", "composer": "TCOM",
    }

    def ensure_tags(self, f):
        if f.tags is None:
            f.add_tags()

    def tagtype(self, f) -> str:
        if f.tags is None:
            return "–"
        major = getattr(f.tags, "version", (2, 4, 0))[1]
        return f"ID3v2.{major}" if major >= 2 else "ID3v1"

    def read(self, f) -> dict:
        t = f.tags
        out = dict.fromkeys(FIELD_KEYS, "")
        if t is None:
            return out
        for key, fid in self.TEXT.items():
            fr = t.get(fid)
            if fr is not None:
                out[key] = _join(fr.text)
        fr = t.get("TCON")
        if fr is not None:
            out["genre"] = _join(fr.genres)
        out["comment"] = _join(self._comment_frame(t).text) if self._comment_frame(t) else ""
        return out

    @staticmethod
    def _comment_frame(t):
        comms = [fr for fr in t.getall("COMM") if not fr.desc.lower().startswith("itun")]
        for fr in comms:
            if fr.desc == "":
                return fr
        return comms[0] if comms else None

    def write(self, f, changes: dict) -> None:
        self.ensure_tags(f)
        t = f.tags
        for key, value in changes.items():
            value = value.strip()
            if key == "comment":
                for fr in list(t.getall("COMM")):
                    if fr.desc == "":
                        del t[fr.HashKey]
                if value:
                    t.add(COMM(encoding=3, lang="eng", desc="", text=[value]))
                continue
            fid = "TCON" if key == "genre" else self.TEXT[key]
            t.delall(fid)
            if key == "year":
                for old in ("TYER", "TDAT", "TIME"):
                    t.delall(old)
            if value:
                t.add(Frames[fid](encoding=3, text=[value]))

    def get_cover(self, f):
        if f.tags is None:
            return None, 0
        pics = f.tags.getall("APIC")
        if not pics:
            return None, 0
        front = next((p for p in pics if p.type == 3), pics[0])
        return CoverData(front.data, front.mime or sniff_mime(front.data)), len(pics)

    def set_cover(self, f, cover: CoverData) -> None:
        self.ensure_tags(f)
        for p in list(f.tags.getall("APIC")):
            if p.type in FRONT_TYPES:
                del f.tags[p.HashKey]
        f.tags.add(APIC(encoding=3, mime=cover.mime, type=3, desc="", data=cover.data))

    def remove_cover(self, f) -> None:
        if f.tags is not None:
            f.tags.delall("APIC")

    def save(self, f, opts: dict) -> None:
        version = 3 if int(opts.get("id3_version", 3)) == 3 else 4
        if isinstance(f, MP3):
            v1 = {"remove": 0, "keep": 1, "write": 2}.get(opts.get("id3v1", "keep"), 1)
            f.save(v2_version=version, v1=v1)
        else:
            try:
                f.save(v2_version=version)
            except TypeError:
                f.save()


# ======================================================================
# Vorbis-Kommentare (FLAC, OGG Vorbis, Opus, OGG-FLAC)
# ======================================================================
class VorbisHandler:
    kind = "vorbis"
    # erster Name = wird geschrieben, weitere = werden auch gelesen
    SIMPLE = {
        "title": ("TITLE",),
        "artist": ("ARTIST",),
        "albumartist": ("ALBUMARTIST", "ALBUM ARTIST", "ALBUM_ARTIST"),
        "album": ("ALBUM",),
        "year": ("DATE", "YEAR"),
        "genre": ("GENRE",),
        "composer": ("COMPOSER",),
        "comment": ("COMMENT", "DESCRIPTION"),
    }
    NUMBERS = {
        "track": ("TRACKNUMBER", ("TRACKTOTAL", "TOTALTRACKS")),
        "disc": ("DISCNUMBER", ("DISCTOTAL", "TOTALDISCS")),
    }

    def ensure_tags(self, f):
        if f.tags is None:
            f.add_tags()

    def tagtype(self, f) -> str:
        return "Vorbis"

    @staticmethod
    def _get(t, name) -> str:
        return _join(t.get(name, [])) if name in t else ""

    def read(self, f) -> dict:
        out = dict.fromkeys(FIELD_KEYS, "")
        t = f.tags
        if t is None:
            return out
        for key, names in self.SIMPLE.items():
            for name in names:
                if name in t:
                    out[key] = self._get(t, name)
                    break
        for key, (num_name, total_names) in self.NUMBERS.items():
            num = self._get(t, num_name)
            n, total = split_number(num)
            if not total:
                for tn in total_names:
                    if tn in t:
                        total = self._get(t, tn)
                        break
            out[key] = join_number(n, total)
        return out

    def write(self, f, changes: dict) -> None:
        self.ensure_tags(f)
        t = f.tags
        for key, value in changes.items():
            value = value.strip()
            if key in self.NUMBERS:
                num_name, total_names = self.NUMBERS[key]
                for name in (num_name, *total_names):
                    if name in t:
                        del t[name]
                n, total = split_number(value)
                if n:
                    t[num_name] = [n]
                if total:
                    t[total_names[0]] = [total]
                continue
            names = self.SIMPLE[key]
            # Primärnamen und den Namen, aus dem gelesen wurde, ersetzen
            source = next((nm for nm in names if nm in t), None)
            for name in {names[0], source} - {None}:
                if name in t:
                    del t[name]
            if value:
                t[names[0]] = [value]

    # --- Cover ---------------------------------------------------------
    def _ogg_pictures(self, f):
        pics = []
        if f.tags is None:
            return pics
        for raw in f.tags.get("METADATA_BLOCK_PICTURE", []):
            try:
                pics.append(Picture(base64.b64decode(raw)))
            except Exception:
                continue
        if not pics and "COVERART" in f.tags:
            try:
                data = base64.b64decode(f.tags["COVERART"][0])
                pic = Picture()
                pic.data, pic.type, pic.mime = data, 3, sniff_mime(data)
                pics.append(pic)
            except Exception:
                pass
        return pics

    def _pictures(self, f):
        return list(f.pictures) if isinstance(f, FLAC) else self._ogg_pictures(f)

    def get_cover(self, f):
        pics = self._pictures(f)
        if not pics:
            return None, 0
        front = next((p for p in pics if p.type == 3), pics[0])
        return CoverData(front.data, front.mime or sniff_mime(front.data)), len(pics)

    @staticmethod
    def _make_picture(cover: CoverData) -> Picture:
        pic = Picture()
        pic.type, pic.mime, pic.desc, pic.data = 3, cover.mime, "", cover.data
        info = image_info(cover.data)
        pic.width, pic.height = info["w"], info["h"]
        pic.depth = 24
        return pic

    def set_cover(self, f, cover: CoverData) -> None:
        pic = self._make_picture(cover)
        if isinstance(f, FLAC):
            f.metadata_blocks[:] = [
                b for b in f.metadata_blocks
                if not (isinstance(b, Picture) and b.type in FRONT_TYPES)
            ]
            f.add_picture(pic)
            return
        self.ensure_tags(f)
        keep = [p for p in self._ogg_pictures(f) if p.type not in FRONT_TYPES]
        for name in ("METADATA_BLOCK_PICTURE", "COVERART", "COVERARTMIME"):
            if name in f.tags:
                del f.tags[name]
        f.tags["METADATA_BLOCK_PICTURE"] = [
            base64.b64encode(p.write()).decode("ascii") for p in (*keep, pic)
        ]

    def remove_cover(self, f) -> None:
        if isinstance(f, FLAC):
            f.clear_pictures()
            return
        if f.tags is not None:
            for name in ("METADATA_BLOCK_PICTURE", "COVERART", "COVERARTMIME"):
                if name in f.tags:
                    del f.tags[name]

    def save(self, f, opts: dict) -> None:
        f.save()


# ======================================================================
# MP4 / M4A
# ======================================================================
class MP4Handler:
    kind = "mp4"
    TEXT = {
        "title": "\xa9nam", "artist": "\xa9ART", "albumartist": "aART", "album": "\xa9alb",
        "year": "\xa9day", "genre": "\xa9gen", "composer": "\xa9wrt", "comment": "\xa9cmt",
    }
    NUMBERS = {"track": "trkn", "disc": "disk"}

    def ensure_tags(self, f):
        if f.tags is None:
            f.add_tags()

    def tagtype(self, f) -> str:
        return "MP4"

    def read(self, f) -> dict:
        out = dict.fromkeys(FIELD_KEYS, "")
        t = f.tags
        if t is None:
            return out
        for key, atom in self.TEXT.items():
            if atom in t:
                out[key] = _join(t[atom])
        if not out["genre"] and "gnre" in t:
            try:
                from mutagen.id3 import TCON
                out["genre"] = _join(TCON(text=[f"({t['gnre'][0] - 1})"]).genres)
            except Exception:
                pass
        for key, atom in self.NUMBERS.items():
            if atom in t and t[atom]:
                n, total = (tuple(t[atom][0]) + (0, 0))[:2]
                out[key] = join_number(str(n) if n else "", str(total) if total else "")
        return out

    def write(self, f, changes: dict) -> None:
        self.ensure_tags(f)
        t = f.tags
        for key, value in changes.items():
            value = value.strip()
            if key in self.NUMBERS:
                atom = self.NUMBERS[key]
                if atom in t:
                    del t[atom]
                n, total = split_number(value)
                if not n and not total:
                    continue
                try:
                    t[atom] = [(int(n or 0), int(total or 0))]
                except ValueError:
                    label = "Track" if key == "track" else "Disc"
                    raise TagWriteError(f"{label} muss bei M4A eine Zahl sein (z. B. 3 oder 3/12).")
                continue
            atom = self.TEXT[key]
            if atom in t:
                del t[atom]
            if key == "genre" and "gnre" in t:
                del t["gnre"]
            if value:
                t[atom] = [value]

    def get_cover(self, f):
        if f.tags is None or not f.tags.get("covr"):
            return None, 0
        covers = f.tags["covr"]
        c = covers[0]
        mime = "image/png" if c.imageformat == MP4Cover.FORMAT_PNG else sniff_mime(bytes(c))
        return CoverData(bytes(c), mime), len(covers)

    def set_cover(self, f, cover: CoverData) -> None:
        self.ensure_tags(f)
        fmt = MP4Cover.FORMAT_PNG if cover.mime == "image/png" else MP4Cover.FORMAT_JPEG
        f.tags["covr"] = [MP4Cover(cover.data, imageformat=fmt)]

    def remove_cover(self, f) -> None:
        if f.tags is not None and "covr" in f.tags:
            del f.tags["covr"]

    def save(self, f, opts: dict) -> None:
        f.save()


# ======================================================================
# ASF / WMA
# ======================================================================
class ASFHandler:
    kind = "asf"
    TEXT = {
        "title": "Title", "artist": "Author", "albumartist": "WM/AlbumArtist",
        "album": "WM/AlbumTitle", "year": "WM/Year", "track": "WM/TrackNumber",
        "disc": "WM/PartOfSet", "genre": "WM/Genre", "composer": "WM/Composer",
        "comment": "Description",
    }

    def ensure_tags(self, f):
        if f.tags is None:
            f.add_tags()

    def tagtype(self, f) -> str:
        return "ASF"

    def read(self, f) -> dict:
        out = dict.fromkeys(FIELD_KEYS, "")
        t = f.tags
        if t is None:
            return out
        for key, name in self.TEXT.items():
            if name in t:
                out[key] = _join(str(getattr(v, "value", v)) for v in t[name])
        if not out["track"] and "WM/Track" in t:  # alte, nullbasierte Variante
            try:
                out["track"] = str(int(str(t["WM/Track"][0].value)) + 1)
            except Exception:
                pass
        return out

    def write(self, f, changes: dict) -> None:
        self.ensure_tags(f)
        t = f.tags
        for key, value in changes.items():
            value = value.strip()
            name = self.TEXT[key]
            if name in t:
                del t[name]
            if key == "track" and "WM/Track" in t:
                del t["WM/Track"]
            if value:
                t[name] = [value]

    @staticmethod
    def _parse_picture(blob: bytes):
        ptype = blob[0]
        size = struct.unpack("<I", blob[1:5])[0]
        pos = 5

        def wstr(p):
            end = p
            while blob[end:end + 2] != b"\x00\x00":
                end += 2
            return blob[p:end].decode("utf-16-le", "replace"), end + 2

        mime, pos = wstr(pos)
        _desc, pos = wstr(pos)
        return ptype, mime, blob[pos:pos + size]

    def _pictures(self, f):
        pics = []
        if f.tags is None:
            return pics
        for v in f.tags.get("WM/Picture", []):
            try:
                pics.append(self._parse_picture(bytes(v.value)))
            except Exception:
                continue
        return pics

    def get_cover(self, f):
        pics = self._pictures(f)
        if not pics:
            return None, 0
        ptype, mime, data = next((p for p in pics if p[0] == 3), pics[0])
        return CoverData(data, mime or sniff_mime(data)), len(pics)

    def set_cover(self, f, cover: CoverData) -> None:
        self.ensure_tags(f)
        keep = []
        for v in f.tags.get("WM/Picture", []):
            try:
                if self._parse_picture(bytes(v.value))[0] not in FRONT_TYPES:
                    keep.append(v)
            except Exception:
                keep.append(v)
        blob = (bytes([3]) + struct.pack("<I", len(cover.data))
                + cover.mime.encode("utf-16-le") + b"\x00\x00" + b"\x00\x00" + cover.data)
        f.tags["WM/Picture"] = keep + [ASFByteArrayAttribute(value=blob)]

    def remove_cover(self, f) -> None:
        if f.tags is not None and "WM/Picture" in f.tags:
            del f.tags["WM/Picture"]

    def save(self, f, opts: dict) -> None:
        f.save()


# ======================================================================
# APEv2 (APE, WavPack)
# ======================================================================
class APEHandler:
    kind = "ape"
    TEXT = {
        "title": ("Title",), "artist": ("Artist",), "albumartist": ("Album Artist", "AlbumArtist"),
        "album": ("Album",), "year": ("Year",), "track": ("Track",), "disc": ("Disc",),
        "genre": ("Genre",), "composer": ("Composer",), "comment": ("Comment",),
    }
    COVER_KEY = "Cover Art (Front)"

    def ensure_tags(self, f):
        if f.tags is None:
            f.add_tags()

    def tagtype(self, f) -> str:
        return "APEv2"

    def read(self, f) -> dict:
        out = dict.fromkeys(FIELD_KEYS, "")
        t = f.tags
        if t is None:
            return out
        for key, names in self.TEXT.items():
            for name in names:
                if name in t:
                    v = t[name]
                    try:
                        out[key] = _join(list(v))
                    except TypeError:
                        out[key] = str(v)
                    break
        return out

    def write(self, f, changes: dict) -> None:
        self.ensure_tags(f)
        t = f.tags
        for key, value in changes.items():
            value = value.strip()
            names = self.TEXT[key]
            source = next((nm for nm in names if nm in t), None)
            for name in {names[0], source} - {None}:
                if name in t:
                    del t[name]
            if value:
                t[names[0]] = value

    def get_cover(self, f):
        if f.tags is None:
            return None, 0
        keys = [k for k in f.tags.keys() if k.lower().startswith("cover art")]
        if not keys:
            return None, 0
        key = next((k for k in keys if k.lower() == self.COVER_KEY.lower()), keys[0])
        raw = bytes(f.tags[key].value)
        data = raw.split(b"\x00", 1)[1] if b"\x00" in raw[:256] else raw
        return CoverData(data, sniff_mime(data)), len(keys)

    def set_cover(self, f, cover: CoverData) -> None:
        self.ensure_tags(f)
        name = b"cover.png" if cover.mime == "image/png" else b"cover.jpg"
        f.tags[self.COVER_KEY] = APEValue(name + b"\x00" + cover.data, BINARY)

    def remove_cover(self, f) -> None:
        if f.tags is None:
            return
        for k in [k for k in f.tags.keys() if k.lower().startswith("cover art")]:
            del f.tags[k]

    def save(self, f, opts: dict) -> None:
        f.save()


# ======================================================================
# Verteiler
# ======================================================================
_ID3 = ID3Handler()
_VORBIS = VorbisHandler()
_MP4 = MP4Handler()
_ASF = ASFHandler()
_APE = APEHandler()

FORMAT_NAMES = {
    "MP3": "MP3", "FLAC": "FLAC", "OggVorbis": "OGG", "OggOpus": "Opus", "OggFLAC": "OGG-FLAC",
    "MP4": "M4A", "ASF": "WMA", "WAVE": "WAV", "AIFF": "AIFF", "DSF": "DSF",
    "MonkeysAudio": "APE", "WavPack": "WavPack",
}


def _handler(f):
    if isinstance(f, (MP3, WAVE, AIFF, DSF)):
        return _ID3
    if isinstance(f, (FLAC, OggVorbis, OggOpus, OggFLAC)):
        return _VORBIS
    if isinstance(f, MP4):
        return _MP4
    if isinstance(f, ASF):
        return _ASF
    if isinstance(f, APEv2File):
        return _APE
    if isinstance(getattr(f, "tags", None), ID3):
        return _ID3
    raise TagWriteError("Dieses Dateiformat wird nicht unterstützt.")


def _open(path: str):
    try:
        f = mutagen.File(path)
    except MutagenError as exc:
        raise TagWriteError(f"Datei kann nicht gelesen werden: {exc}") from exc
    except OSError as exc:
        raise TagWriteError(f"Datei kann nicht geöffnet werden: {exc.strerror or exc}") from exc
    if f is None:
        raise TagWriteError("Unbekanntes oder beschädigtes Audioformat.")
    return f


def read_file(path: str) -> dict:
    """Liest Tags + Audio-Infos. Gibt immer ein Dict zurück (Fehler im Feld 'error').

    Das Cover selbst wird NICHT im Ergebnis gespeichert (Speicherbedarf),
    nur eine kurze Beschreibung (Hash, Größe, Typ). Das Bild holt
    read_cover() bei Bedarf.
    """
    rec = {
        "path": path, "mtime": 0, "size": 0, "format": os.path.splitext(path)[1][1:].upper(),
        "tagtype": "", "tags": dict.fromkeys(FIELD_KEYS, ""), "length": 0.0, "bitrate": 0,
        "samplerate": 0, "channels": 0, "cover": None, "cover_count": 0, "error": "",
    }
    try:
        st = os.stat(path)
        rec["mtime"], rec["size"] = st.st_mtime_ns, st.st_size
        f = _open(path)
        h = _handler(f)
        rec["format"] = FORMAT_NAMES.get(type(f).__name__, rec["format"])
        rec["tagtype"] = h.tagtype(f)
        rec["tags"] = h.read(f)
        info = getattr(f, "info", None)
        if info is not None:
            rec["length"] = float(getattr(info, "length", 0) or 0)
            rec["bitrate"] = int((getattr(info, "bitrate", 0) or 0) // 1000)
            rec["samplerate"] = int(getattr(info, "sample_rate", 0) or 0)
            rec["channels"] = int(getattr(info, "channels", 0) or 0)
        cover, count = h.get_cover(f)
        if cover is not None:
            rec["cover"] = image_info(cover.data)
            rec["cover_count"] = count
    except TagWriteError as exc:
        rec["error"] = str(exc)
    except Exception as exc:  # nie wegen einer Datei abstürzen
        rec["error"] = f"Fehler beim Lesen: {exc}"
    return rec


def read_cover(path: str) -> CoverData | None:
    """Holt das Albumcover einer Datei (für Anzeige, Export, Rückgängig)."""
    try:
        f = _open(path)
        cover, _ = _handler(f).get_cover(f)
        return cover
    except Exception:
        return None


# Cover-Aktionen für write_file
COVER_KEEP = None
COVER_REMOVE = "remove"


def write_file(path: str, changes: dict, cover=COVER_KEEP, opts: dict | None = None) -> dict:
    """Schreibt geänderte Felder (und optional das Cover) und liest die Datei neu.

    changes: {feldname: neuer_wert}; leerer Wert = Feld löschen
    cover:   COVER_KEEP (None), COVER_REMOVE oder ein CoverData-Objekt
    """
    opts = opts or {}
    unknown = set(changes) - set(FIELD_KEYS)
    if unknown:
        raise TagWriteError(f"Unbekannte Felder: {', '.join(sorted(unknown))}")
    if not changes and cover is COVER_KEEP:
        return read_file(path)

    try:
        st = os.stat(path)
    except OSError as exc:
        raise TagWriteError(f"Datei nicht gefunden: {exc.strerror or exc}") from exc
    if not os.access(path, os.W_OK):
        raise TagWriteError("Keine Schreibrechte für diese Datei.")

    f = _open(path)
    h = _handler(f)
    try:
        if changes:
            h.write(f, changes)
        if cover == COVER_REMOVE:
            h.remove_cover(f)
        elif isinstance(cover, CoverData):
            h.set_cover(f, cover)
        h.save(f, opts)
    except TagWriteError:
        raise
    except MutagenError as exc:
        raise TagWriteError(f"Speichern fehlgeschlagen: {exc}") from exc
    except OSError as exc:
        raise TagWriteError(f"Speichern fehlgeschlagen: {exc.strerror or exc}") from exc

    if opts.get("keep_mtime"):
        try:
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        except OSError:
            pass
    return read_file(path)
