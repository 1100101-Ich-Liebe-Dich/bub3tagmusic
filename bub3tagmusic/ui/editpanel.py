"""Bearbeitungsfeld rechts: Cover + Tag-Felder für die Auswahl.

Mehrfachauswahl:
  * Haben alle gewählten Dateien denselben Wert, steht er im Feld.
  * Sind die Werte verschieden, bleibt das Feld leer mit ‹verschieden›.
  * Wer etwas einträgt, ändert das Feld für ALLE gewählten Dateien.
  * Felder, die man nicht anfasst, bleiben unverändert.
  * Das × im Feld leert das Feld für alle gewählten Dateien.
"""

from __future__ import annotations

import os
from collections import OrderedDict

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QCompleter, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ..core.covers import (CoverData, find_folder_image, prepare_for_embedding, save_image_file,
                           sniff_mime)
from ..core.fields import COMMON_GENRES, FIELD_BY_KEY
from ..core.model import FileItem
from ..core.settings import Settings
from ..core.tags import COVER_REMOVE, read_cover
from . import icons
from .coverwidget import CoverPreview, CoverView, image_bytes_from_mime
from .session import Session

MIXED = "‹verschieden›"
MIXED_SHORT = "‹…›"


class FieldEdit(QLineEdit):
    """Eingabefeld, das weiß, ob es 'verschieden' ist und ob getippt wurde."""

    commitRequested = Signal(object)
    clearRequested = Signal(object)

    def __init__(self, key: str, clearable: bool = True, parent=None):
        super().__init__(parent)
        self.key = key
        self.clearable = clearable
        self.mixed = False
        self.dirty = False
        self._shown = ""
        self.textEdited.connect(self._on_edit)
        self.editingFinished.connect(lambda: self.dirty and self.commitRequested.emit(self))
        self._clear = QAction(icons.icon("x", "faint", "text"), "Feld leeren", self)
        self._clear.setToolTip("Feld für alle gewählten Dateien leeren")
        self._clear.triggered.connect(lambda: self.clearRequested.emit(self))
        self.addAction(self._clear, QLineEdit.ActionPosition.TrailingPosition)
        self._clear.setVisible(False)

    def refresh_icons(self):
        self._clear.setIcon(icons.icon("x", "faint", "text"))

    # Feste Mindestbreite: Das ×-Symbol (ein-/ausgeblendet) würde sie sonst ändern, das Fenster
    # teilt neu auf und die Liste wird neu vermessen – bei 50.000 Zeilen spürbar langsam.
    def minimumSizeHint(self):
        h = super().minimumSizeHint()
        return QSize(60, h.height())

    def show_value(self, value: str, mixed: bool, modified: bool):
        if self.dirty and self.hasFocus():
            return
        self.mixed, self.dirty, self._shown = mixed, False, value
        self.setText(value)
        self.setPlaceholderText((MIXED if self.clearable else MIXED_SHORT) if mixed else "")
        self._clear.setVisible(self.clearable and (bool(value) or mixed))
        # Eigener Name „edited“: QLineEdit hat schon eine Eigenschaft „modified“, die setText() still
        # zurücksetzt – dann blieb der gelbe Rahmen stehen, obwohl nichts mehr geändert war.
        if self.property("edited") != modified:
            self.setProperty("edited", modified)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    def _on_edit(self, text: str):
        self.dirty = True
        self._clear.setVisible(self.clearable and (bool(text) or self.mixed))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape and self.dirty:
            self.dirty = False
            self.setText(self._shown)
            self._clear.setVisible(self.clearable and (bool(self._shown) or self.mixed))
            return
        super().keyPressEvent(e)


class EditPanel(QWidget):
    message = Signal(str)                  # kurzer Hinweis (Toast)
    featureRequested = Signal(str)         # Platzhalter späterer Phasen
    saveNextRequested = Signal()

    COVER_SIZE = 156

    def __init__(self, session: Session, settings: Settings, parent=None):
        super().__init__(parent)
        self.setObjectName("EditPanel")
        self.session = session
        self.settings = settings
        self.items: list[FileItem] = []
        self.fields: dict[str, FieldEdit] = {}
        self._pixmaps: OrderedDict[str, QPixmap] = OrderedDict()
        self._shown_cover: CoverData | None = None
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

        # --- Kopf: was ist ausgewählt --------------------------------------------------
        self.title = QLabel("Keine Datei ausgewählt")
        self.title.setProperty("role", "heading")
        self.subtitle = QLabel("Wähle Dateien in der Liste – Strg+A wählt alle")
        self.subtitle.setProperty("role", "faint")
        self.subtitle.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addSpacing(2)
        lay.addWidget(self.subtitle)
        lay.addSpacing(14)

        # --- Cover ----------------------------------------------------------------------
        cover_row = QHBoxLayout()
        cover_row.setSpacing(12)
        self.cover = CoverView(self.COVER_SIZE)
        self.cover.dropped.connect(self._cover_from_bytes)
        self.cover.clicked.connect(self._cover_clicked)
        cover_row.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)

        side = QVBoxLayout()
        side.setSpacing(3)
        self.cover_state = QLabel("Kein Cover")
        self.cover_state.setObjectName("CoverState")
        self.cover_info = QLabel("")
        self.cover_info.setProperty("role", "faint")
        self.folder_info = QLabel("")
        self.folder_info.setProperty("role", "faint")
        for lbl in (self.cover_info, self.folder_info):     # lange Hinweise umbrechen statt das Feld zu sprengen
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        side.addWidget(self.cover_state)
        side.addWidget(self.cover_info)
        side.addWidget(self.folder_info)
        side.addStretch(1)

        self.btn_load = self._side_button("Bild laden …", "folder-open", self._cover_load)
        self.btn_folder = self._side_button("Aus Ordner", "folder-notch-open", self._cover_from_folder)
        self.btn_more = self._side_button("Weitere", "dots-three", None)
        more = QMenu(self.btn_more)
        self.act_paste = more.addAction("Aus Zwischenablage einfügen", self._cover_paste)
        self.act_paste.setShortcut(QKeySequence("Ctrl+Shift+V"))
        more.addSeparator()
        self.act_save_folder = more.addAction("", self._cover_save_to_folders)
        self.act_save_as = more.addAction("Speichern unter …", self._cover_save_as)
        self.act_artist = more.addAction("", self._artist_image)
        more.addSeparator()
        self.act_remove = more.addAction("Cover entfernen", self._cover_remove)
        more.addSeparator()
        self.act_online = more.addAction("Cover online suchen …\tStrg+K", lambda: self.featureRequested.emit("cover_search"))
        more.addAction("Künstlerbild online suchen …\tStrg+J", lambda: self.featureRequested.emit("artist_image"))
        self.btn_more.setMenu(more)
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        for b in (self.btn_load, self.btn_folder, self.btn_more):
            side.addWidget(b)
        cover_row.addLayout(side, 1)
        lay.addLayout(cover_row)
        lay.addSpacing(18)

        # --- Felder ---------------------------------------------------------------------
        sec = QLabel("Tags")
        sec.setProperty("role", "section")
        lay.addWidget(sec)
        lay.addSpacing(8)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)
        row = 0
        for key in ("title", "artist", "albumartist", "album"):
            self._add_field(grid, row, key)
            row += 1

        # Jahr / Track / Disc in einer Zeile
        lbl = self._label("Jahr")
        grid.addWidget(lbl, row, 0)
        nums = QHBoxLayout()
        nums.setSpacing(6)
        for key, width in (("year", 52), ("track", 56), ("disc", 44)):
            fe = self._make_field(key, clearable=False)
            fe.setMinimumWidth(width)
            fe.setToolTip({"year": "Jahr, z. B. 1999", "track": "Track, z. B. 3 oder 3/12",
                           "disc": "Disc, z. B. 1 oder 1/2"}[key])
            if key != "year":
                small = self._label(FIELD_BY_KEY[key].label)
                nums.addSpacing(4)
                nums.addWidget(small)
            nums.addWidget(fe, {"year": 4, "track": 4, "disc": 3}[key])
        grid.addLayout(nums, row, 1)
        row += 1

        # Genre mit Auswahlliste
        grid.addWidget(self._label("Genre"), row, 0)
        self.genre_box = QComboBox()
        self.genre_box.setEditable(True)
        self.genre_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        genre_edit = FieldEdit("genre")
        self._wire(genre_edit)
        self.genre_box.setLineEdit(genre_edit)
        self.genre_box.addItems(COMMON_GENRES)
        self.genre_box.setCurrentIndex(-1)
        self.genre_box.setMaxVisibleItems(14)
        comp = QCompleter(list(COMMON_GENRES), self.genre_box)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.genre_box.setCompleter(comp)
        self.genre_box.activated.connect(lambda _i: self._commit(genre_edit, force=True))
        self.fields["genre"] = genre_edit
        grid.addWidget(self.genre_box, row, 1)
        row += 1

        for key in ("composer", "comment"):
            self._add_field(grid, row, key)
            row += 1
        lay.addLayout(grid)
        lay.addSpacing(12)

        self.hint = QLabel("Enter übernimmt  ·  Esc verwirft das Getippte  ·  × leert das Feld für alle")
        self.hint.setProperty("role", "faint")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        lay.addStretch(1)

        # --- Fuß: Speichern & weiter ----------------------------------------------------
        foot = QWidget(objectName="EditFooter")
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(6)
        self.btn_next = QPushButton("Speichern && nächster Ordner")
        self.btn_next.setObjectName("NextButton")
        self.btn_next.setProperty("kind", "primary")
        self.btn_next.setMinimumHeight(40)
        self.btn_next.setToolTip("Speichert, hakt den Ordner als fertig ab und springt zum nächsten offenen Ordner (Strg+→)")
        self.btn_next.clicked.connect(self.saveNextRequested.emit)
        fl.addWidget(self.btn_next)
        k = QLabel("Strg+→  speichert, hakt ab und springt weiter")
        k.setProperty("role", "faint")
        k.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fl.addWidget(k)
        outer.addWidget(foot)

        self.setMinimumWidth(340)
        self._update_cover_menu_texts()
        self.set_items([])

    # --- Aufbau-Hilfen -------------------------------------------------------------------
    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "fieldlabel")
        return lbl

    def _side_button(self, text: str, icon_name: str, slot) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setProperty("kind", "side")
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setIcon(icons.icon(icon_name, "muted", "text"))
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_targets.append((b, icon_name))
        if slot:
            b.clicked.connect(slot)
        return b

    def _make_field(self, key: str, clearable: bool = True) -> FieldEdit:
        fe = FieldEdit(key, clearable)
        self._wire(fe)
        self.fields[key] = fe
        return fe

    def _wire(self, fe: FieldEdit):
        fe.commitRequested.connect(self._commit)
        fe.clearRequested.connect(self._clear_field)
        fe.returnPressed.connect(lambda fe=fe: (self._commit(fe), fe.selectAll()))

    def _add_field(self, grid: QGridLayout, row: int, key: str):
        grid.addWidget(self._label(FIELD_BY_KEY[key].label), row, 0)
        grid.addWidget(self._make_field(key), row, 1)

    def refresh_icons(self):
        for b, name in self._icon_targets:
            b.setIcon(icons.icon(name, "muted", "text"))
        for fe in self.fields.values():
            fe.refresh_icons()
        self.refresh()

    def _update_cover_menu_texts(self):
        self.act_save_folder.setText(f"Als {self.settings.album_cover_name} im Album-Ordner speichern")
        self.act_artist.setText(f"Künstlerbild festlegen ({self.settings.artist_image_name}) …")

    # --- Auswahl --------------------------------------------------------------------------
    def set_items(self, items: list[FileItem]):
        self.commit()
        self.items = items
        self.refresh()

    def refresh(self):
        items = self.items
        n = len(items)
        enabled = n > 0
        for key, fe in self.fields.items():
            fe.setEnabled(enabled)
        self.genre_box.setEnabled(enabled)
        for w in (self.btn_load, self.btn_folder, self.btn_more):
            w.setEnabled(enabled)
        self.cover.set_active(enabled)

        if not enabled:
            self.title.setText("Keine Datei ausgewählt")
            self.subtitle.setText("Wähle Dateien in der Liste – Strg+A wählt alle")
            for fe in self.fields.values():
                fe.show_value("", False, False)
            self._show_cover_none()
            return

        dirs = list(dict.fromkeys(it.dir for it in items))
        if n == 1:
            self.title.setText(items[0].tags.get("title") or items[0].name)
            self.subtitle.setText(items[0].name)
        else:
            self.title.setText(f"{n:,} Dateien ausgewählt".replace(",", "."))
            self.subtitle.setText(os.path.basename(dirs[0]) if len(dirs) == 1
                                  else f"aus {len(dirs):,} Ordnern".replace(",", "."))
        self.title.setToolTip(items[0].path if n == 1 else "")

        # Ein Durchgang pro Feld; geänderte Dateien nur einmal heraussuchen
        changed = [it for it in items if it.tags != it.orig]
        for key, fe in self.fields.items():
            values = {it.tags.get(key, "") for it in items}
            mixed = len(values) > 1
            modified = any(it.tags.get(key, "") != it.orig.get(key, "") for it in changed)
            fe.show_value("" if mixed else next(iter(values)), mixed, modified)
        self._refresh_cover(items, dirs)

    # --- Felder übernehmen ------------------------------------------------------------------
    def commit(self):
        """Getippte, noch nicht übernommene Werte anwenden (z. B. vor dem Speichern)."""
        for fe in self.fields.values():
            if fe.dirty:
                self._commit(fe)

    def _commit(self, fe: FieldEdit, force: bool = False):
        if not self.items:
            fe.dirty = False
            return
        if not fe.dirty and not force:
            return
        fe.dirty = False
        value = fe.text().strip()
        if fe.mixed and value == "" and not force:
            return  # nichts eingetragen – verschiedene Werte bleiben
        self.session.apply_fields(self.items, {fe.key: value})

    def _clear_field(self, fe: FieldEdit):
        if not self.items:
            return
        fe.dirty = False
        fe.setText("")
        self.session.apply_fields(self.items, {fe.key: ""}, f"{FIELD_BY_KEY[fe.key].label} geleert")
        self.message.emit(f"{FIELD_BY_KEY[fe.key].label} wird bei {len(self.items)} Datei(en) geleert")

    # --- Cover anzeigen -------------------------------------------------------------------------
    def _show_cover_none(self):
        self._shown_cover = None
        self.cover.set_cover(None, empty="Bild hierher ziehen")
        self.cover_state.setText("Kein Cover")
        self.cover_info.setText("")
        self.folder_info.setText("")

    def _pixmap_for(self, it: FileItem) -> tuple[QPixmap | None, CoverData | None]:
        state, key = it.cover_state()
        if state == "new":
            data = it.cover_action
        elif state == "disk":
            cached = self._pixmaps.get(key)
            if cached is not None:
                self._pixmaps.move_to_end(key)
                return cached, None
            data = read_cover(it.path)
        else:
            return None, None
        if data is None:
            return None, None
        pm = QPixmap()
        pm.loadFromData(data.data)
        if pm.isNull():
            return None, data
        if state == "disk":
            self._pixmaps[key] = pm
            while len(self._pixmaps) > 48:
                self._pixmaps.popitem(last=False)
        return pm, data

    def _refresh_cover(self, items: list[FileItem], dirs: list[str]):
        states = [it.cover_state() for it in items]
        keys = {k for _, k in states}
        kinds = {s for s, _ in states}
        first_with = next((it for it, (s, _) in zip(items, states) if s in ("disk", "new")), None)
        pm = None
        if first_with is not None:
            pm, data = self._pixmap_for(first_with)
            self._shown_cover = data
        else:
            self._shown_cover = None

        badge, role = "", "accent"
        if len(keys) > 1:
            with_cover = sum(1 for s, _ in states if s in ("disk", "new"))
            self.cover_state.setText("Verschiedene Cover")
            self.cover_info.setText(f"{with_cover} von {len(items)} mit Cover")
            badge, role = "verschieden", "modified"
        elif "new" in kinds:
            self.cover_state.setText("Neues Cover")
            self.cover_state.setToolTip("Wird beim Speichern eingebettet")
            self.cover_info.setText(self._describe(first_with))
            badge = "neu"
        elif "removed" in kinds:
            self.cover_state.setText("Wird entfernt")
            self.cover_info.setText("beim nächsten Speichern")
            badge, role = "entfernen", "danger"
        elif "disk" in kinds:
            self.cover_state.setText("Cover eingebettet")
            self.cover_info.setText(self._describe(first_with))
        else:
            self.cover_state.setText("Kein Cover")
            self.cover_info.setText("Reinziehen oder Strg+K (online)")
        self.cover.set_cover(pm, badge, role)

        # Ordnerbild (cover.jpg) prüfen
        name = self.settings.album_cover_name
        if len(dirs) == 1:
            found = find_folder_image(dirs[0], [name])
            self.folder_info.setText(f"✓ {name} im Ordner" if found else f"Kein {name} im Ordner")
        elif len(dirs) <= 300:
            have = sum(1 for d in dirs if find_folder_image(d, [name]))
            self.folder_info.setText(f"{have} von {len(dirs)} Ordnern mit {name}")
        else:
            self.folder_info.setText("")

    @staticmethod
    def _describe(it: FileItem | None) -> str:
        if it is None:
            return ""
        if isinstance(it.cover_action, CoverData):
            from ..core.covers import image_info
            info = image_info(it.cover_action.data)
        else:
            info = it.rec.get("cover") or {}
        if not info:
            return ""
        kind = info.get("mime", "").split("/")[-1].upper().replace("JPEG", "JPG")
        size = f"{info.get('w', 0)} × {info.get('h', 0)}" if info.get("w") else "?"
        return f"{size} px · {kind} · {max(1, info.get('bytes', 0) // 1024)} KB"

    # --- Cover-Aktionen -----------------------------------------------------------------------------
    def _prepare(self, data: bytes) -> CoverData | None:
        s = self.settings
        try:
            return prepare_for_embedding(data, s.embed_max_size, s.embed_resize, s.jpeg_quality)
        except ValueError as exc:
            QMessageBox.warning(self, "Bild nicht verwendbar", str(exc))
            return None

    def _cover_from_bytes(self, data: bytes):
        if not self.items:
            return
        cover = self._prepare(data)
        if cover is None:
            return
        n = self.session.apply_cover(self.items, cover, "Cover gesetzt")
        self.message.emit(f"Cover für {n} Datei(en) vorgemerkt – Strg+S speichert")

    def _cover_load(self):
        start = self.items[0].dir if self.items else ""
        path, _ = QFileDialog.getOpenFileName(self, "Cover laden", start,
                                              "Bilder (*.jpg *.jpeg *.png *.webp *.bmp *.gif)")
        if path:
            with open(path, "rb") as fh:
                self._cover_from_bytes(fh.read())

    def _cover_paste(self):
        data = image_bytes_from_mime(QApplication.clipboard().mimeData())
        if data:
            self._cover_from_bytes(data)
        else:
            self.message.emit("In der Zwischenablage ist kein Bild")

    def _cover_from_folder(self):
        by_dir: dict[str, list[FileItem]] = {}
        for it in self.items:
            by_dir.setdefault(it.dir, []).append(it)
        done, missing = 0, 0
        for d, its in by_dir.items():
            path = find_folder_image(d, self.settings.folder_image_candidates)
            if not path:
                missing += 1
                continue
            with open(path, "rb") as fh:
                cover = self._prepare(fh.read())
            if cover is not None:
                done += self.session.apply_cover(its, cover, "Cover aus Ordner")
        if done:
            extra = f" ({missing} Ordner ohne Bild)" if missing else ""
            self.message.emit(f"Ordnerbild bei {done} Datei(en) übernommen{extra}")
        else:
            names = ", ".join(self.settings.folder_image_candidates[:4])
            self.message.emit(f"Kein Ordnerbild gefunden ({names} …)")

    def _cover_remove(self):
        n = self.session.apply_cover(self.items, COVER_REMOVE, "Cover entfernt")
        self.message.emit(f"Cover wird bei {n} Datei(en) entfernt – Strg+S speichert" if n
                          else "Die Auswahl hat kein Cover")

    def _current_cover_for(self, its: list[FileItem]) -> CoverData | None:
        for it in its:
            if isinstance(it.cover_action, CoverData):
                return it.cover_action
            if it.cover_action != COVER_REMOVE and it.rec.get("cover"):
                c = read_cover(it.path)
                if c is not None:
                    return c
        return None

    def _cover_save_to_folders(self):
        name = self.settings.album_cover_name
        by_dir: dict[str, list[FileItem]] = {}
        for it in self.items:
            by_dir.setdefault(it.dir, []).append(it)
        existing = [d for d in by_dir if os.path.exists(os.path.join(d, name))]
        if existing:
            r = QMessageBox.question(
                self, "Datei ersetzen?",
                f"In {len(existing)} Ordner(n) gibt es schon eine {name}.\nErsetzen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                by_dir = {d: v for d, v in by_dir.items() if d not in existing}
        saved, errors = 0, []
        for d, its in by_dir.items():
            cover = self._current_cover_for(its)
            if cover is None:
                continue
            try:
                save_image_file(cover.full(), os.path.join(d, name))
                saved += 1
            except OSError as exc:
                errors.append(f"{d}: {exc.strerror or exc}")
        if errors:
            QMessageBox.warning(self, "Nicht alles gespeichert", "\n".join(errors[:20]))
        self.message.emit(f"{name} in {saved} Ordner(n) gespeichert" if saved else "Kein Cover zum Speichern")
        self.refresh()

    def _cover_save_as(self):
        cover = self._current_cover_for(self.items)
        if cover is None:
            self.message.emit("Kein Cover zum Speichern")
            return
        start = os.path.join(self.items[0].dir, "cover" + cover.ext)
        path, _ = QFileDialog.getSaveFileName(self, "Cover speichern unter", start, "Bilder (*.jpg *.png)")
        if path:
            data = cover.full()
            if path.lower().endswith(".png") and sniff_mime(data) != "image/png":
                pm = QPixmap()
                pm.loadFromData(data)
                pm.save(path, "PNG")
            else:
                save_image_file(data, path)
            self.message.emit(f"Gespeichert: {os.path.basename(path)}")

    def _artist_image(self):
        """Bild wählen und als folder.jpg in den Künstler-Ordner legen (Elternordner des Albums)."""
        if not self.items:
            return
        album_dirs = list(dict.fromkeys(it.dir for it in self.items))
        artist_dirs = list(dict.fromkeys(os.path.dirname(d) for d in album_dirs))
        if len(artist_dirs) != 1:
            self.message.emit("Bitte Dateien von nur einem Künstler auswählen")
            return
        target = os.path.join(artist_dirs[0], self.settings.artist_image_name)
        path, _ = QFileDialog.getOpenFileName(
            self, f"Künstlerbild für „{os.path.basename(artist_dirs[0])}“", artist_dirs[0],
            "Bilder (*.jpg *.jpeg *.png *.webp)")
        if not path:
            return
        if os.path.exists(target):
            r = QMessageBox.question(self, "Datei ersetzen?",
                                     f"{self.settings.artist_image_name} gibt es schon.\nErsetzen?")
            if r != QMessageBox.StandardButton.Yes:
                return
        with open(path, "rb") as fh:
            save_image_file(fh.read(), target)
        self.message.emit(f"Künstlerbild gespeichert: {os.path.basename(artist_dirs[0])}/"
                          f"{self.settings.artist_image_name}")

    def _cover_clicked(self):
        if not self.items:
            return
        if not self.cover.has_image():
            self._cover_load()
            return
        pm = self.cover.pixmap()
        first = next((it for it in self.items if it.has_cover()), None)
        CoverPreview(pm, self._describe(first), self).exec()

    # --- Tastatur: Bild einfügen mit Strg+V, wenn kein Feld den Fokus hat ------------------------
    def paste_cover_if_image(self) -> bool:
        data = image_bytes_from_mime(QApplication.clipboard().mimeData())
        if data and self.items:
            self._cover_from_bytes(data)
            return True
        return False
