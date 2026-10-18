"""Cover-Bilder: prüfen, verkleinern, als Datei speichern, im Ordner finden."""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass, field

try:
    from PIL import Image
except ImportError:  # Pillow ist optional, ohne wird nur nicht skaliert
    Image = None


@dataclass
class CoverData:
    data: bytes                      # was eingebettet wird (ggf. verkleinert)
    mime: str = "image/jpeg"
    # Originalbild in voller Größe – für cover.jpg im Ordner
    original: bytes | None = field(default=None, repr=False, compare=False)

    def full(self) -> bytes:
        return self.original or self.data

    @property
    def ext(self) -> str:
        return ".png" if self.mime == "image/png" else ".jpg"


def sniff_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return "application/octet-stream"


def short_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:16]


def image_info(data: bytes) -> dict:
    """Kleine Beschreibung für Liste/Cache – ohne das Bild selbst."""
    info = {"hash": short_hash(data), "bytes": len(data), "mime": sniff_mime(data), "w": 0, "h": 0}
    if Image is not None:
        try:
            with Image.open(io.BytesIO(data)) as im:  # liest nur den Kopf
                info["w"], info["h"] = im.size
        except Exception:
            pass
    return info


def prepare_for_embedding(data: bytes, max_size: int = 600, resize: bool = True,
                          quality: int = 90) -> CoverData:
    """Bild fürs Einbetten vorbereiten.

    JPEG/PNG bleiben unverändert, solange sie klein genug sind.
    Alles andere (WEBP, BMP, GIF, zu groß) wird zu JPEG umgewandelt.
    """
    mime = sniff_mime(data)
    if Image is None:
        if mime not in ("image/jpeg", "image/png"):
            raise ValueError("Dieses Bildformat braucht Pillow zum Umwandeln.")
        return CoverData(data, mime)

    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as exc:
        raise ValueError("Die Datei ist kein lesbares Bild.") from exc

    too_big = resize and max_size > 0 and max(im.size) > max_size
    if mime in ("image/jpeg", "image/png") and not too_big:
        return CoverData(data, mime)
    original = data

    if too_big:
        im.thumbnail((max_size, max_size), Image.LANCZOS)
    if im.mode not in ("RGB", "L"):
        background = Image.new("RGB", im.size, (255, 255, 255))
        rgba = im.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        im = background
    out = io.BytesIO()
    im.save(out, "JPEG", quality=quality, optimize=True)
    return CoverData(out.getvalue(), "image/jpeg", original=original)


def to_jpeg(data: bytes, quality: int = 92) -> bytes:
    """Für cover.jpg / folder.jpg: immer echtes JPEG in voller Größe."""
    if sniff_mime(data) == "image/jpeg" or Image is None:
        return data
    im = Image.open(io.BytesIO(data))
    if im.mode not in ("RGB", "L"):
        background = Image.new("RGB", im.size, (255, 255, 255))
        rgba = im.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        im = background
    out = io.BytesIO()
    im.save(out, "JPEG", quality=quality, optimize=True)
    return out.getvalue()


def find_folder_image(folder: str, candidates: list[str]) -> str | None:
    """Sucht cover.jpg, folder.jpg … (Groß-/Kleinschreibung egal)."""
    try:
        names = {entry.name.lower(): entry.name for entry in os.scandir(folder) if entry.is_file()}
    except OSError:
        return None
    for cand in candidates:
        real = names.get(cand.lower())
        if real:
            return os.path.join(folder, real)
    return None


def save_image_file(data: bytes, target: str, overwrite: bool = True) -> str:
    """Speichert ein Bild als Datei. .jpg-Ziele werden immer echtes JPEG."""
    if os.path.exists(target) and not overwrite:
        raise FileExistsError(target)
    if target.lower().endswith((".jpg", ".jpeg")):
        data = to_jpeg(data)
    tmp = target + ".bub3tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, target)
    return target
