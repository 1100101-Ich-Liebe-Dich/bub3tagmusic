"""Was fehlt noch? Ordner ohne Bilder – Grundlage für „Fehlende Bilder finden“ und „Speichern & weiter“.

Ohne Qt. Arbeitet auf dem Ordnerbaum (scanner.FolderNode), den der Baum links schon kennt.
  * Album-Ordner  = Ordner mit Musik direkt darin. Fehlt dort das Albumcover (cover.jpg), zählt er.
    Bei CD1/CD2-Unterordnern reicht ein cover.jpg im übergeordneten Album-Ordner.
  * Künstler-Ordner = keine Musik direkt darin, aber Alben darunter. Fehlt folder.jpg, zählt er.
Grüne Haken (fertig) haben hiermit nichts zu tun – die gibt es nur fürs Speichern der Tags.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .covers import find_folder_image
from .tools import disc_from_folder

ALBUM, ARTIST = "album", "artist"


def is_artist_node(node) -> bool:
    """Keine Musik direkt drin, aber Unterordner mit Musik – und keine reinen CD1/CD2-Unterordner."""
    if node is None or node.audio_count or not node.children:
        return False
    if not any(c.audio_count for c in node.children):
        return False
    if all(disc_from_folder(c.name) is not None for c in node.children):
        return False                      # mehrteiliges Album (CD1, CD2 …), kein Künstler
    return True


def folders(root, kind: str):
    """Album- bzw. Künstler-Ordner in Baum-Reihenfolge."""
    if root is None:
        return
    for node in root.walk():
        if kind == ALBUM and node.audio_count:
            yield node
        elif kind == ARTIST and node is not root and is_artist_node(node):   # die Sammlung selbst ist kein Künstler
            yield node


def has_image(node, kind: str, album_name: str = "cover.jpg", artist_name: str = "folder.jpg") -> bool:
    if kind == ARTIST:
        return bool(find_folder_image(node.path, [artist_name]))
    if find_folder_image(node.path, [album_name]):
        return True
    if disc_from_folder(node.name) is not None:                 # CD1/CD2: Cover darf eine Ebene höher liegen
        return bool(find_folder_image(os.path.dirname(node.path), [album_name]))
    return False


@dataclass
class Missing:
    path: str
    kind: str              # ALBUM | ARTIST
    files: int = 0         # Musikdateien (Album) bzw. darunter (Künstler)


def missing_images(root, album_name: str = "cover.jpg", artist_name: str = "folder.jpg", *,
                   kinds=(ARTIST, ALBUM), progress=lambda done, total: None, cancelled=lambda: False) -> list[Missing]:
    """Alle Ordner ohne Bild – Künstler und Alben in Baum-Reihenfolge gemischt (Künstler vor seinen Alben)."""
    if root is None:
        return []
    nodes = [(n, k) for n in root.walk() for k in kinds
             if (k == ALBUM and n.audio_count) or (k == ARTIST and n is not root and is_artist_node(n))]
    out = []
    for i, (node, kind) in enumerate(nodes):
        if cancelled():
            break
        if i % 50 == 0:
            progress(i, len(nodes))
        if not has_image(node, kind, album_name, artist_name):
            out.append(Missing(node.path, kind, node.audio_count if kind == ALBUM else node.total_count))
    progress(len(nodes), len(nodes))
    return out


def next_missing(root, kind: str, after: str, album_name: str = "cover.jpg", artist_name: str = "folder.jpg",
                 skip: set[str] | None = None) -> str:
    """Nächster Ordner dieser Art ohne Bild nach `after` (Baum-Reihenfolge), sonst von vorn. '' = keiner mehr."""
    skip = skip or set()
    order = list(folders(root, kind))
    paths = [n.path for n in order]
    start = paths.index(after) + 1 if after in paths else 0
    for node in order[start:] + order[:start]:
        if node.path == after or node.path in skip:
            continue
        if not has_image(node, kind, album_name, artist_name):
            return node.path
    return ""
