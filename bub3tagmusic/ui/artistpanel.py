"""Künstler-Ordner (Überordner ohne eigene Musik, darin die Alben).

Wird links ein solcher Ordner gewählt, zeigt die rechte Seite statt der Tag-Felder:
  * das Künstlerbild (folder.jpg in DIESEM Ordner) – reinziehen, laden, einfügen, online suchen
  * den Künstlernamen (vorbelegt mit dem Ordnernamen) für die Online-Suche
  * die Alben darin – mit Häkchen, ob sie schon ein cover.jpg haben
  * „Alle Alben laden“, um den ganzen Künstler auf einmal zu bearbeiten

Das alte Künstlerbild wird beim Ersetzen/Entfernen in den Papierkorb gelegt (wiederherstellbar).
"""

from __future__ import annotations

import os

from PySide6.QtCore import QFile, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QToolButton, QVBoxLayout,
                               QWidget)

from ..core.covers import find_folder_image, image_info, save_image_file
from ..core.settings import Settings
from ..core.tools import disc_from_folder
from . import icons
from .coverwidget import CoverView, image_bytes_from_mime


def is_artist_folder(node) -> bool:
    """Keine Musik direkt drin, aber Unterordner mit Musik – und keine reinen CD1/CD2-Unterordner."""
    if node is None or node.audio_count or not node.children:
        return False
    albums = [c for c in node.children if c.audio_count]
    if not albums:
        return False
    if all(disc_from_folder(c.name) is not None for c in node.children):
        return False                      # mehrteiliges Album (CD1, CD2 …), kein Künstler
    return True


class ArtistPanel(QWidget):
    message = Signal(str)
    featureRequested = Signal(str)        # z. B. "artist_image"
    loadAlbumsRequested = Signal(str)     # Ordner mit allen Alben laden

    IMAGE_SIZE = 248

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setObjectName("EditPanel")
        self.settings = settings
        self.folder = ""
        self.node = None
        self._icon_targets: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(objectName="EditPanelInner")
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(0)

        self.title = QLabel()
        self.title.setProperty("role", "heading")
        self.subtitle = QLabel()
        self.subtitle.setProperty("role", "faint")
        self.subtitle.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addSpacing(2)
        lay.addWidget(self.subtitle)
        lay.addSpacing(14)

        # --- Künstlerbild ------------------------------------------------------------------
        sec = QLabel("Künstlerbild")
        sec.setProperty("role", "section")
        lay.addWidget(sec)
        lay.addSpacing(6)
        row = QHBoxLayout()
        self.image = CoverView(self.IMAGE_SIZE)
        self.image.dropped.connect(self.set_image_bytes)
        self.image.clicked.connect(self._image_clicked)
        row.addWidget(self.image, 0, Qt.AlignmentFlag.AlignTop)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(6)
        self.image_info = QLabel()
        self.image_info.setProperty("role", "faint")
        self.image_info.setWordWrap(True)
        lay.addWidget(self.image_info)
        lay.addSpacing(10)

        lay.addWidget(self._label("Künstlername für die Suche"))
        lay.addSpacing(4)
        self.artist = QLineEdit()
        self.artist.setPlaceholderText("Name des Künstlers")
        self.artist.setToolTip("Vorbelegt mit dem Ordnernamen – bei Bedarf einfach korrigieren")
        self.artist.returnPressed.connect(lambda: self.featureRequested.emit("artist_image"))
        lay.addWidget(self.artist)
        lay.addSpacing(8)

        self.btn_search = QPushButton("Künstlerbild online suchen")
        self.btn_search.setProperty("kind", "primary")
        self.btn_search.setToolTip("TheAudioDB, Bandcamp, Discogs und Wikipedia durchsuchen (Strg+J)")
        self.btn_search.clicked.connect(lambda: self.featureRequested.emit("artist_image"))
        self._icon(self.btn_search, "magnifying-glass", "accent_text")
        lay.addWidget(self.btn_search)
        lay.addSpacing(6)
        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.btn_load = self._side("Bild laden …", "folder-open", self.load_image)
        self.btn_paste = self._side("Einfügen", "clipboard-text", self.paste_image)
        self.btn_remove = self._side("Entfernen", "trash", self.remove_image)
        for b in (self.btn_load, self.btn_paste, self.btn_remove):
            btns.addWidget(b)
        lay.addLayout(btns)
        lay.addSpacing(18)

        # --- Alben -------------------------------------------------------------------------
        self.albums_head = QLabel("Alben")
        self.albums_head.setProperty("role", "section")
        lay.addWidget(self.albums_head)
        lay.addSpacing(6)
        self.albums = QListWidget()
        self.albums.setMinimumHeight(120)
        self.albums.itemDoubleClicked.connect(self._album_open)
        lay.addWidget(self.albums, 1)
        lay.addSpacing(8)
        self.btn_all = QPushButton("Alle Alben laden und bearbeiten")
        self.btn_all.setToolTip("Lädt alle Alben dieses Künstlers in die Liste (Unterordner an)")
        self.btn_all.clicked.connect(lambda: self.loadAlbumsRequested.emit(self.folder))
        self._icon(self.btn_all, "tree-structure", "text")
        lay.addWidget(self.btn_all)
        lay.addSpacing(10)
        h = QLabel(f"Das Künstlerbild liegt als {settings.artist_image_name} in diesem Ordner, "
                   f"jedes Album darin hat sein eigenes {settings.album_cover_name}.")
        h.setProperty("role", "faint")
        h.setWordWrap(True)
        self._hint = h
        lay.addWidget(h)

    # --- Bausteine --------------------------------------------------------------------------
    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "fieldlabel")
        return lbl

    def _icon(self, w, name: str, role: str):
        w.setIcon(icons.icon(name, role))
        self._icon_targets.append((w, name, role))

    def _side(self, text: str, icon_name: str, slot) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setProperty("kind", "side")
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        self._icon(b, icon_name, "muted")
        return b

    def refresh_icons(self):
        for w, name, role in self._icon_targets:
            w.setIcon(icons.icon(name, role))
        self.refresh()

    # --- Inhalt ------------------------------------------------------------------------------
    @property
    def target(self) -> str:
        return os.path.join(self.folder, self.settings.artist_image_name) if self.folder else ""

    def artist_name(self) -> str:
        return self.artist.text().strip() or os.path.basename(self.folder)

    def set_folder(self, folder: str, node=None):
        if folder != self.folder:
            self.artist.setText(os.path.basename(folder.rstrip("/")))
        self.folder, self.node = folder, node
        self.refresh()

    def existing_image(self) -> str:
        """folder.jpg (oder wie in den Einstellungen benannt) – Groß-/Kleinschreibung egal."""
        if not self.folder:
            return ""
        return find_folder_image(self.folder, [self.settings.artist_image_name]) or ""

    def refresh(self):
        name = os.path.basename(self.folder.rstrip("/")) or self.folder
        self.title.setText(name)
        node = self.node
        albums = [c for c in (node.children if node else []) if c.audio_count]
        n_files = node.total_count if node else 0
        self.subtitle.setText(f"Künstler-Ordner · {len(albums)} {'Album' if len(albums) == 1 else 'Alben'} · "
                              f"{n_files:,} Musikdateien".replace(",", "."))
        path = self.existing_image()
        if path:
            pm = QPixmap(path)
            try:
                with open(path, "rb") as fh:
                    info = image_info(fh.read())
                size = f"{info['w']} × {info['h']} px · {max(1, info['bytes'] // 1024)} KB"
            except OSError:
                size = ""
            self.image.set_cover(pm if not pm.isNull() else None)
            self.image_info.setText(f"✓ {os.path.basename(path)} im Ordner" + (f" · {size}" if size else ""))
        else:
            self.image.set_cover(None, empty="Künstlerbild hierher ziehen")
            self.image_info.setText(f"Noch kein {self.settings.artist_image_name} – Bild reinziehen, laden "
                                    "oder online suchen.")
        self.btn_remove.setEnabled(bool(path))
        self.albums.clear()
        with_cover = 0
        for c in albums:
            has = bool(find_folder_image(c.path, [self.settings.album_cover_name]))
            with_cover += has
            it = QListWidgetItem(icons.icon("check-circle" if has else "circle", "done" if has else "faint"),
                                 f"{c.name}   ({c.audio_count})")
            it.setToolTip(f"{c.path}\n{self.settings.album_cover_name} {'vorhanden' if has else 'fehlt'}"
                          "\nDoppelklick öffnet das Album")
            it.setData(Qt.ItemDataRole.UserRole, c.path)
            self.albums.addItem(it)
        self.albums_head.setText(f"Alben  ·  {with_cover} von {len(albums)} mit {self.settings.album_cover_name}")
        self._hint.setText(f"Das Künstlerbild liegt als {self.settings.artist_image_name} in diesem Ordner, "
                           f"jedes Album darin hat sein eigenes {self.settings.album_cover_name}.")

    def _album_open(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.window().tree.select_paths([path])

    # --- Bild setzen / entfernen ------------------------------------------------------------
    def _replace_ok(self) -> bool:
        old = self.existing_image()
        if not old:
            return True
        r = QMessageBox.question(self, "Künstlerbild ersetzen?",
                                 f"In „{os.path.basename(self.folder)}“ gibt es schon {os.path.basename(old)}.\n\n"
                                 "Ersetzen? Das alte Bild kommt in den Papierkorb.")
        if r != QMessageBox.StandardButton.Yes:
            return False
        self._trash(old)
        return True

    @staticmethod
    def _trash(path: str) -> bool:
        ok = QFile.moveToTrash(path)
        ok = ok[0] if isinstance(ok, tuple) else ok
        if not ok:
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return True

    def set_image_bytes(self, data: bytes, ask: bool = True) -> bool:
        if not self.folder or not data:
            return False
        if ask and not self._replace_ok():
            return False
        target = self.existing_image() or self.target
        try:
            save_image_file(data, target)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Nicht gespeichert", f"{target}\n{getattr(exc, 'strerror', None) or exc}")
            return False
        self.message.emit(f"Künstlerbild gespeichert: {os.path.basename(self.folder)}/{os.path.basename(target)}")
        self.refresh()
        return True

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, f"Künstlerbild für „{os.path.basename(self.folder)}“",
                                              self.folder, "Bilder (*.jpg *.jpeg *.png *.webp)")
        if path:
            with open(path, "rb") as fh:
                self.set_image_bytes(fh.read())

    def paste_image(self) -> bool:
        data = image_bytes_from_mime(QApplication.clipboard().mimeData())
        if not data:
            self.message.emit("In der Zwischenablage ist kein Bild")
            return False
        return self.set_image_bytes(data)

    def remove_image(self):
        old = self.existing_image()
        if not old:
            return
        r = QMessageBox.question(self, "Künstlerbild entfernen?",
                                 f"{os.path.basename(old)} aus „{os.path.basename(self.folder)}“ in den Papierkorb legen?")
        if r != QMessageBox.StandardButton.Yes:
            return
        if self._trash(old):
            self.message.emit(f"{os.path.basename(old)} liegt im Papierkorb")
        self.refresh()

    def _image_clicked(self):
        if not self.image.has_image():
            self.load_image()
            return
        from .coverwidget import CoverPreview
        CoverPreview(self.image.pixmap(), self.image_info.text(), self).exec()
