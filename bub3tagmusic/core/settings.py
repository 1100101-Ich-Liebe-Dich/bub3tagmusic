"""Einstellungen als JSON unter ~/.config/bub3tagmusic/settings.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .. import APP_ID


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    path = Path(base) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(Path.home(), ".cache")
    path = Path(base) / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Settings:
    # --- Tags ---------------------------------------------------------
    id3_version: int = 3                 # 3 = ID3v2.3 (kompatibel), 4 = ID3v2.4
    id3v1: str = "keep"                  # keep | remove | write
    keep_mtime: bool = False             # Änderungsdatum der Datei beibehalten

    # --- Cover --------------------------------------------------------
    album_cover_name: str = "cover.jpg"  # Albumcover im Album-Ordner
    artist_image_name: str = "folder.jpg"  # Künstlerbild im Künstler-Ordner
    folder_image_candidates: list[str] = field(default_factory=lambda: [
        "cover.jpg", "cover.jpeg", "cover.png", "folder.jpg", "folder.jpeg",
        "folder.png", "front.jpg", "front.png", "album.jpg", "albumart.jpg",
    ])
    embed_resize: bool = True            # beim Einbetten verkleinern
    embed_max_size: int = 600            # Kantenlänge in Pixel
    jpeg_quality: int = 90

    # --- Oberfläche ---------------------------------------------------
    theme: str = "dark"                  # dark | light
    recursive: bool = False              # Unterordner mitladen
    select_all_on_load: bool = True      # nach dem Laden alle Dateien auswählen
    show_filter_bar: bool = True         # Schnellfilter-Leiste über der Liste (Phase 4)
    last_root: str = ""
    last_selection: list[str] = field(default_factory=list)
    hidden_columns: list[str] = field(default_factory=lambda: [
        "albumartist", "composer", "comment", "tagtype", "samplerate", "folder", "rg_track", "rg_album",
    ])
    column_widths: dict[str, int] = field(default_factory=dict)
    window_geometry: str = ""
    splitter_state: str = ""

    # --- Werkzeuge (Phase 2): letzte Einstellungen je Werkzeug ---------
    tool_options: dict = field(default_factory=dict)

    # --- Online (Phase 3) ---------------------------------------------
    discogs_token: str = ""
    acoustid_key: str = ""               # Phase 4
    musicbrainz_contact: str = ""        # E-Mail für den User-Agent (MusicBrainz-Regel)

    # ------------------------------------------------------------------
    @classmethod
    def path(cls) -> Path:
        return config_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        try:
            data = json.loads(cls.path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return s
        known = {f.name for f in fields(cls)}
        for key, value in data.items():
            if key in known:
                setattr(s, key, value)
        return s

    def save(self) -> None:
        tmp = self.path().with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path())

    def write_options(self) -> dict:
        """Nur die Werte, die beim Schreiben von Dateien gebraucht werden."""
        return {
            "id3_version": self.id3_version,
            "id3v1": self.id3v1,
            "keep_mtime": self.keep_mtime,
        }
