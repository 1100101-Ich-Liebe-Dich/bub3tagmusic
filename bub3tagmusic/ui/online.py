"""Online-Dialoge (Phase 3): Album suchen, Cover suchen, Künstlerbild suchen.

Alle Abfragen laufen im Hintergrund. Nichts wird ohne Vorschau übernommen.
Album-Daten und eingebettete Cover landen wie jede Bearbeitung gelb in der Liste
(Strg+S speichert, Strg+Z nimmt alles in einem Schritt zurück). cover.jpg und
folder.jpg werden direkt in den Ordner geschrieben.
"""

from __future__ import annotations

import os
import re
import time

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
                               QSplitter,
                               QStyle, QStyledItemDelegate, QTableView, QVBoxLayout, QWidget)

from .. import features
from ..core.covers import find_folder_image, prepare_for_embedding, save_image_file
from ..core.fields import FIELD_BY_KEY
from ..core.model import FileItem
from ..online import artistimages, coversearch, deezer, discogs, itunes, lastfm, matching, musicbrainz
from ..online.base import AlbumMatch, CoverCandidate, search_text
from ..online.http import get_image
from . import icons, theme
from .tools import CHANGED, ERROR, UNCHANGED, WARN, Preview, PreviewModel, PreviewRow
from .widgets import FlowLayout, chip, hint, section
from .workers import ImageLoader, Job

_YEAR_PREFIX = re.compile(r"^\s*\(?\d{4}\)?\s*[-–.]?\s*")
_YEAR_SUFFIX = re.compile(r"\s*[\(\[]\d{4}[\)\]]\s*$")


def guess_search(items: list[FileItem]) -> tuple[str, str]:
    """Interpret + Album für die Suche: gemeinsame Tags, sonst Ordnernamen (Künstler/Jahr - Album)."""
    def common(key):
        values = {it.tags.get(key, "").strip() for it in items} - {""}
        return values.pop() if len(values) == 1 else ""
    artist = common("albumartist") or common("artist")
    album = common("album")
    dirs = {it.dir for it in items}
    if len(dirs) == 1:
        d = dirs.pop()
        if not album:
            album = _YEAR_SUFFIX.sub("", _YEAR_PREFIX.sub("", os.path.basename(d)))
        if not artist:
            artist = os.path.basename(os.path.dirname(d))
    # Alles in Klammern bleibt draußen: „Album (2020)“, „Album (EP)“, „Album [Deluxe]“ (1.1.5)
    return search_text(artist), search_text(album)


def rounded_pixmap(data: bytes | None, size: int, radius: int = 8) -> QPixmap:
    pm = QPixmap()
    if data:
        pm.loadFromData(data)
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    p.setClipPath(path)
    if pm.isNull():
        p.fillRect(0, 0, size, size, theme.qcolor("input"))
        icons.icon("disc", "faint").paint(p, QRect(size // 4, size // 4, size // 2, size // 2))
    else:
        scaled = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    p.end()
    return out


# ======================================================================
# Basis: Kopf, Suchzeile, Fuß – wie bei den Werkzeugen
# ======================================================================
class OnlineDialog(QDialog):
    feature_id = ""
    title = ""                     # leer = Titel aus features.py

    def __init__(self, win, items: list[FileItem], scope: str):
        super().__init__(win)
        self.win, self.session, self.settings = win, win.session, win.settings
        self.items = items
        self.feature = features.get(self.feature_id)
        self.opts: dict = dict(self.settings.tool_options.get(self.feature_id, {}))
        name = self.title or self.feature.title.replace(" …", "")
        self.setWindowTitle(name)
        self.resize(1100, 680)
        self.setMinimumSize(900, 540)
        self._loaders: list[ImageLoader] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head = QWidget(objectName="ToolHead")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(20, 14, 20, 14)
        hl.setSpacing(10)
        top = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.icon(self.feature.icon, "accent").pixmap(26, 26))
        top.addWidget(ic)
        top.addSpacing(6)
        tbox = QVBoxLayout()
        tbox.setSpacing(1)
        title = QLabel(name)
        title.setProperty("role", "heading")
        tbox.addWidget(title)
        self.scope_label = hint(scope, "muted")
        tbox.addWidget(self.scope_label)
        top.addLayout(tbox, 1)
        hl.addLayout(top)
        self.search_row = QHBoxLayout()
        self.search_row.setSpacing(8)
        hl.addLayout(self.search_row)
        root.addWidget(head)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self.body, 1)

        foot = QWidget(objectName="ToolFoot")
        fl = self.foot_layout = QHBoxLayout(foot)
        fl.setContentsMargins(20, 12, 20, 12)
        fl.setSpacing(10)
        self.status = QLabel()
        self.status.setObjectName("ToolSummary")
        self.status.setWordWrap(True)
        fl.addWidget(self.status, 1)
        self.foot_hint = hint("")
        self.foot_hint.setWordWrap(False)
        fl.addWidget(self.foot_hint)
        cancel = QPushButton("Schließen")
        cancel.clicked.connect(self.reject)
        fl.addWidget(cancel)
        self.apply_btn = QPushButton("Übernehmen")
        self.apply_btn.setProperty("kind", "primary")
        self.apply_btn.setMinimumWidth(170)
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        fl.addWidget(self.apply_btn)
        root.addWidget(foot)

    def search_field(self, placeholder: str, text: str, width: int = 0) -> QLineEdit:
        le = QLineEdit(text)
        le.setPlaceholderText(placeholder)
        le.returnPressed.connect(self.search)
        if width:
            le.setMinimumWidth(width)
        self.search_row.addWidget(le, 1)
        return le

    def search_button(self):
        b = QPushButton("Suchen")
        b.setIcon(icons.icon("magnifying-glass", "text"))
        b.clicked.connect(self.search)
        self.search_row.addWidget(b)
        self.search_btn = b

    def run(self, fn, *args, done=None, failed=None) -> Job:
        job = Job(fn, *args)
        if done:
            job.done.connect(done)
        job.failed.connect(failed or self.show_error)
        job.start()
        return job

    def load_images(self, jobs: list[tuple[int, str]], slot) -> None:
        for old in self._loaders:
            old.stop()
        loader = ImageLoader(jobs)
        loader.loaded.connect(slot)
        self._loaders = [loader]
        loader.start()

    def show_error(self, msg: str):
        self.set_status(msg, "danger")
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_status(self, text: str, role: str = ""):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {theme.tok(role)};" if role else "")

    def store_options(self):
        self.settings.tool_options[self.feature_id] = self.opts
        try:
            self.settings.save()
        except OSError:
            pass

    def _apply(self):
        self.store_options()
        self.apply()

    def apply(self):
        raise NotImplementedError

    def search(self):
        raise NotImplementedError

    def done(self, r):
        for loader in self._loaders:
            loader.stop()
        super().done(r)


# ======================================================================
# Album suchen (MusicBrainz / Discogs)
# ======================================================================
class _ResultDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 68)

    def paint(self, p: QPainter, option, index):
        m: AlbumMatch = index.data(Qt.ItemDataRole.UserRole)
        pm: QPixmap = index.data(Qt.ItemDataRole.DecorationRole)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        r = option.rect.adjusted(6, 3, -6, -3)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected or option.state & QStyle.StateFlag.State_MouseOver:
            path = QPainterPath()
            path.addRoundedRect(r, 8, 8)
            p.fillPath(path, theme.qcolor("selection" if selected else "hover"))
        if isinstance(pm, QPixmap) and not pm.isNull():
            p.drawPixmap(r.left() + 6, r.top() + 5, pm)
        x = r.left() + 64
        w = r.width() - 64 - 50
        p.setFont(theme.ui_font(13, QFont.Weight.DemiBold))
        p.setPen(theme.qcolor("text"))
        fm = p.fontMetrics()
        p.drawText(QRect(x, r.top() + 6, w, 18), Qt.AlignmentFlag.AlignLeft,
                   fm.elidedText(m.album, Qt.TextElideMode.ElideRight, w))
        p.setFont(theme.ui_font(12))
        p.setPen(theme.qcolor("muted"))
        fm = p.fontMetrics()
        p.drawText(QRect(x, r.top() + 25, w, 16), Qt.AlignmentFlag.AlignLeft,
                   fm.elidedText(m.albumartist, Qt.TextElideMode.ElideRight, w))
        p.setPen(theme.qcolor("faint"))
        details = index.data(Qt.ItemDataRole.UserRole + 1) or m.details      # bei „Alle Quellen“ mit Quelle
        p.drawText(QRect(x, r.top() + 42, w, 16), Qt.AlignmentFlag.AlignLeft,
                   fm.elidedText(details, Qt.TextElideMode.ElideRight, w))
        # Passt-Wert als kleine Pille
        score = max(0, min(100, m.score))
        role = "done" if score >= 85 else ("modified" if score >= 60 else "faint")
        pill = QRect(r.right() - 44, r.top() + 8, 38, 18)
        path = QPainterPath()
        path.addRoundedRect(pill, 9, 9)
        p.setPen(theme.qcolor(role))
        p.setFont(theme.ui_font(11, QFont.Weight.DemiBold))
        p.drawPath(path)
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, f"{score}")
        p.restore()


ALBUM_FIELDS = (
    ("title", "Titel"), ("artist", "Interpret"), ("album", "Album + Albuminterpret"),
    ("year", "Jahr"), ("track", "Track/Disc"), ("genre", "Genre"),
    ("label", "Label"), ("originalyear", "Original-Jahr"),
)
ALBUM_FIELDS_VERSION = 2          # 2 = Label + Original-Jahr (1.1) – bei alten Einstellungen einmal dazunehmen
ALBUM_SOURCES = ("MusicBrainz", "Discogs", "Deezer", "iTunes", "Last.fm")
ALL_SOURCES = "Alle"             # alle Quellen auf einmal (1.1.4)
SOURCE_HINTS = {
    "Deezer": "Deezer: Jahr oft das der Neuauflage · Cover gibt es hier nicht – dafür Cover suchen (Strg+K)",
    "Last.fm": "Last.fm: Titel, Längen und Genre – kein Jahr, kein Label, kein Cover",
    "iTunes": "",
    "Discogs": "",
    "MusicBrainz": "",
}


class AlbumSearchDialog(OnlineDialog):
    feature_id = "musicbrainz"
    title = "Album suchen"

    def __init__(self, win, items, scope, source: str | None = None):
        # Strg+L (ohne feste Quelle) nimmt die zuletzt benutzte – auch „Alle Quellen“
        self.source = source or dict(win.settings.tool_options.get("musicbrainz", {})).get("source", "MusicBrainz")
        if self.source not in (*ALBUM_SOURCES, ALL_SOURCES):
            self.source = "MusicBrainz"
        self._search_id = 0
        self._then_next = False
        self._lookups: dict[tuple[str, str], AlbumMatch] = {}
        self._current: AlbumMatch | None = None
        self._changes: list = []
        self._cover_all: list = []
        self._cover_bytes: bytes | None = None
        super().__init__(win, items, scope)
        artist, album = guess_search(items)
        self.opts["source"] = self.source

        self.artist = self.search_field("Interpret", artist)
        self.album = self.search_field("Album", album)
        self.src = {}
        for name in (*ALBUM_SOURCES, ALL_SOURCES):
            c = chip("Alle Quellen" if name == ALL_SOURCES else name, checkable=True,
                     tooltip="Alle Dienste gleichzeitig fragen – Treffer zeigen, woher sie kommen"
                     if name == ALL_SOURCES else "")
            c.setChecked(name == self.source)
            c.clicked.connect(lambda _=False, n=name: self._set_source(n))
            self.src[name] = c
            self.search_row.addWidget(c)
        self.search_button()

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget(objectName="ToolOptionsInner")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 10, 6, 10)
        self.results = QListWidget()
        self.results.setObjectName("ResultList")
        self.results.setItemDelegate(_ResultDelegate(self.results))
        self.results.setMouseTracking(True)
        self.results.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.currentRowChanged.connect(self._pick)
        ll.addWidget(self.results)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 14, 16, 8)
        rl.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(14)
        self.cover = QLabel()
        self.cover.setFixedSize(112, 112)
        top.addWidget(self.cover)
        info = QVBoxLayout()
        info.setSpacing(2)
        self.d_title = QLabel("")
        self.d_title.setProperty("role", "heading")
        self.d_title.setWordWrap(True)
        self.d_artist = QLabel("")
        self.d_artist.setProperty("role", "muted")
        self.d_details = hint("")
        info.addWidget(self.d_title)
        info.addWidget(self.d_artist)
        info.addWidget(self.d_details)
        info.addStretch(1)
        top.addLayout(info, 1)
        rl.addLayout(top)

        opts = QHBoxLayout()
        opts.setSpacing(8)
        opts.addWidget(QLabel("Zuordnung"))
        self.mode = QComboBox()
        for key, label in matching.MODES.items():
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(max(0, self.mode.findData(self.opts.get("mode", "auto"))))
        self.mode.currentIndexChanged.connect(lambda _i: (self.opts.__setitem__("mode", self.mode.currentData()),
                                                          self.refresh_preview()))
        opts.addWidget(self.mode)
        opts.addStretch(1)
        rl.addLayout(opts)

        fields_box = QWidget()
        flow = FlowLayout(fields_box, spacing=6)
        self.field_chips = {}
        chosen = set(self.opts.get("fields", [k for k, _ in ALBUM_FIELDS]))
        if self.opts.get("fields_v", 1) < ALBUM_FIELDS_VERSION:
            chosen |= {"label", "originalyear"}
            self.opts["fields_v"] = ALBUM_FIELDS_VERSION
        for key, label in ALBUM_FIELDS:
            c = chip(label, checkable=True)
            c.setChecked(key in chosen)
            c.toggled.connect(self._fields_changed)
            flow.addWidget(c)
            self.field_chips[key] = c
        self.cover_chip = chip("Cover", checkable=True, tooltip="Cover einbetten und als cover.jpg in den Ordner legen")
        self.cover_chip.setChecked(self.opts.get("cover", True))
        self.cover_chip.toggled.connect(self._fields_changed)
        flow.addWidget(self.cover_chip)
        self.clean_chip = chip("Ohne Remaster-Zusätze", checkable=True,
                               tooltip="„Titel (Remastered 2011)“ → „Titel“, „Album (Deluxe Edition)“ → „Album“.\n"
                                       "Live, Remix, Acoustic usw. bleiben stehen.")
        self.clean_chip.setChecked(self.opts.get("clean", True))
        self.clean_chip.toggled.connect(self._fields_changed)
        flow.addWidget(self.clean_chip)
        rl.addWidget(fields_box)

        self.model = PreviewModel(self)
        self.model.show_unchanged = True
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.view.setShowGrid(False)
        self.view.setWordWrap(False)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(28)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        rl.addWidget(self.view, 1)
        split.addWidget(right)
        split.setSizes([360, 740])
        self.body.addWidget(split)

        # Ordner für Ordner ohne das Fenster zu schließen (1.1.4). Der Hinweistext weicht den Knöpfen
        # (sonst wird die Statuszeile gequetscht) und steht stattdessen im Tooltip von „Übernehmen“.
        self.foot_hint.hide()
        self.apply_btn.setToolTip("Übernehmen und Fenster schließen – danach gelb markiert, Strg+S speichert, "
                                  "Strg+Z nimmt zurück")
        fl = self.foot_layout
        self.skip_btn = QPushButton("Nächster Ordner")
        self.skip_btn.setIcon(icons.icon("skip-forward", "text"))
        self.skip_btn.setToolTip("Nichts übernehmen – speichern, Ordner abhaken und im nächsten Ordner weitersuchen")
        self.skip_btn.clicked.connect(lambda: self._advance())
        fl.insertWidget(fl.indexOf(self.apply_btn), self.skip_btn)
        self.apply_btn.setProperty("kind", "")
        self.apply_btn.setMinimumWidth(130)
        self.next_btn = QPushButton("Übernehmen && weiter")
        self.next_btn.setProperty("kind", "primary")
        self.next_btn.setMinimumWidth(200)
        self.next_btn.setEnabled(False)
        self.next_btn.setToolTip("Übernehmen, speichern, Ordner abhaken und gleich im nächsten Ordner suchen "
                                 "(Strg+→ / Strg+Enter)")
        self.next_btn.clicked.connect(self._apply_next)
        fl.addWidget(self.next_btn)
        for keys in ("Ctrl+Right", "Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self, self._apply_next)
        if self.win.is_result_list:                  # Suchergebnis statt Ordner: es gibt kein „weiter“
            self.skip_btn.hide()
            self.next_btn.hide()
            self.apply_btn.setProperty("kind", "primary")
        self._show_details(None)
        if self.album.text().strip():
            QTimer.singleShot(0, self.search)
        else:
            self.set_status("Album und Interpret eingeben, dann Suchen")

    # --- Suche ----------------------------------------------------------------------
    def _set_source(self, name: str):
        self.source = name
        self.opts["source"] = name
        for n, c in self.src.items():
            c.setChecked(n == name)
        self.search()

    def done(self, r):
        self.store_options()                         # gewählte Quelle (auch „Alle Quellen“) für Strg+L merken
        super().done(r)

    def _source_call(self, source: str, artist: str, album: str):
        """(Funktion, Argumente) für die Suche bei einer Quelle – None, wenn ein Schlüssel fehlt."""
        s = self.settings
        if source == "Discogs":
            return (discogs.search_albums, (artist, album, s.discogs_token)) if s.discogs_token else None
        if source == "Last.fm":
            return (lastfm.search_albums, (artist, album, s.lastfm_key)) if s.lastfm_key else None
        if source == "Deezer":
            return deezer.search_albums, (artist, album)
        if source == "iTunes":
            return itunes.search_albums, (artist, album)
        return musicbrainz.search_albums, (artist, album, s.musicbrainz_contact)

    def _search_all(self, artist: str, album: str):
        self._search_id += 1
        sid = self._search_id
        calls, skipped = [], []
        for src in ALBUM_SOURCES:
            call = self._source_call(src, artist, album)
            (calls.append((src, call)) if call else skipped.append(src))
        self._all = {"left": len(calls), "total": len(calls), "found": [], "failed": [], "skipped": skipped}
        self.set_status(f"Suche bei {len(calls)} Quellen …")
        for src, (fn, args) in calls:              # alle gleichzeitig – jede Quelle hat ihre eigene Bremse
            self.run(fn, *args, done=lambda res, sid=sid: self._part(sid, res, ""),
                     failed=lambda msg, sid=sid, n=src: self._part(sid, [], f"{n}: {msg}"))

    def _part(self, sid: int, matches: list, error: str):
        if sid != self._search_id:                   # alte Suche – inzwischen neu gesucht
            return
        a = self._all
        a["left"] -= 1
        a["found"] += matches
        if error:
            a["failed"].append(error)
        if a["left"] > 0:
            self.set_status(f"Suche bei {a['total']} Quellen … ({a['total'] - a['left']} fertig, "
                            f"{len(a['found'])} Treffer)")
            return
        self._results(a["found"])

    def search(self):
        artist, album = self.artist.text().strip(), self.album.text().strip()
        if not album:
            self.set_status("Bitte ein Album eingeben")
            return
        self.results.clear()
        self._show_details(None)
        if self.source == ALL_SOURCES:
            self._search_all(artist, album)
            return
        self._search_id += 1
        self.set_status(f"Suche bei {self.source} …")
        if self.source == "Discogs":                 # ohne Token: verständliche Meldung von discogs.py
            fn, args = discogs.search_albums, (artist, album, self.settings.discogs_token)
        elif self.source == "Last.fm":
            fn, args = lastfm.search_albums, (artist, album, self.settings.lastfm_key)
        else:
            fn, args = self._source_call(self.source, artist, album)
        sid = self._search_id
        self.run(fn, *args, done=lambda res, sid=sid: sid == self._search_id and self._results(res))

    def _results(self, matches: list[AlbumMatch]):
        matches = matching.rank_for_files(matches, len(self.items))
        self.results.clear()
        every = self.source == ALL_SOURCES
        if every:
            matches = matching.mix_sources(matches)
        if not matches:
            if every:
                extra = "; ".join(self._all["failed"])
                self.set_status("Keine Quelle kennt dieses Album – Schreibweise prüfen" + (f" ({extra})" if extra else ""))
            else:
                self.set_status(f"{self.source} kennt dieses Album nicht – Schreibweise prüfen oder andere Quelle wählen")
            return
        jobs = []
        for i, m in enumerate(matches):
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, m)
            if every:                                    # woher kommt der Treffer?
                it.setData(Qt.ItemDataRole.UserRole + 1, " · ".join(p for p in (m.source, m.details) if p))
            it.setData(Qt.ItemDataRole.DecorationRole, rounded_pixmap(None, 52, 6))
            self.results.addItem(it)
            if m.cover_url:
                jobs.append((i, m.cover_url))
        self.load_images(jobs, self._thumb)
        if every:
            a = self._all
            srcs = len({m.source for m in matches})
            notes = [f"ohne Schlüssel übersprungen: {', '.join(a['skipped'])}"] if a["skipped"] else []
            notes += a["failed"]
            self.set_status(f"{len(matches)} Treffer aus {srcs} Quelle{'n' if srcs != 1 else ''}"
                            + "".join(f"  ·  {n}" for n in notes), "modified" if a["failed"] else "")
        else:
            self.set_status(f"{len(matches)} Treffer bei {self.source}")
        self.results.setCurrentRow(0)

    def _thumb(self, row: int, data: bytes):
        it = self.results.item(row)
        if it is not None:
            it.setData(Qt.ItemDataRole.DecorationRole, rounded_pixmap(data, 52, 6))

    def _pick(self, row: int):
        it = self.results.item(row)
        if it is None:
            return
        m: AlbumMatch = it.data(Qt.ItemDataRole.UserRole)
        key = (m.source, m.source_id)
        if key in self._lookups:
            self._show_details(self._lookups[key])
            return
        self.set_status(f"Lade Trackliste von {m.source} …")
        self._show_details(m, loading=True)
        if m.source == "Discogs":
            fn, args = discogs.get_album, (m.source_id, self.settings.discogs_token)
        elif m.source == "Deezer":
            fn, args = deezer.get_album, (m.source_id,)
        elif m.source == "iTunes":
            fn, args = itunes.get_album, (m.source_id,)
        elif m.source == "Last.fm":
            fn, args = lastfm.get_album, (m.source_id, self.settings.lastfm_key)
        else:
            fn, args = musicbrainz.get_album, (m.source_id, self.settings.musicbrainz_contact)
        self.run(fn, *args, done=lambda full, k=key, r=row: self._loaded(k, r, full))

    def _loaded(self, key, row, full: AlbumMatch):
        self._lookups[key] = full
        if self.results.currentRow() == row:
            self._show_details(full)

    # --- Details + Vorschau ---------------------------------------------------------
    def _show_details(self, m: AlbumMatch | None, loading: bool = False):
        self._current = None if (m is None or loading) else m
        self._cover_bytes = None
        if m is None:
            self.d_title.setText("")
            self.d_artist.setText("")
            self.d_details.setText("")
            self.cover.setPixmap(rounded_pixmap(None, 112))
            self.model.set_preview(Preview())
            self.apply_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return
        self.d_title.setText(m.album)
        self.d_artist.setText(m.albumartist)
        details = m.details
        if m.genre:
            details += f" · {m.genre}"
        if m.original_year and m.original_year != m.year:
            details += f" · erstmals {m.original_year}"
        note = SOURCE_HINTS.get(m.source, "") if not loading else "Trackliste wird geladen …"
        self.d_details.setText(details + (f"\n{note}" if note else ""))
        self.cover.setPixmap(rounded_pixmap(None, 112))
        if m.cover_url:
            self.run(get_image, m.cover_url, done=lambda data, mm=m: self._detail_cover(mm, data),
                     failed=lambda _msg: None)
        if not loading:
            self.refresh_preview()

    def _detail_cover(self, m, data):
        if self._current is m or (self._current and self._current.source_id == m.source_id):
            self.cover.setPixmap(rounded_pixmap(data, 112))

    def _fields_changed(self):
        self.opts["fields"] = [k for k, c in self.field_chips.items() if c.isChecked()]
        self.opts["cover"] = self.cover_chip.isChecked()
        self.opts["clean"] = self.clean_chip.isChecked()
        self.refresh_preview()

    def refresh_preview(self):
        m = self._current
        if m is None:
            return
        fields = {k for k, c in self.field_chips.items() if c.isChecked()}
        files = [matching.FileInfo(it.tags.get("track", ""), it.tags.get("disc", ""), it.rec.get("length", 0.0),
                                   it.tags.get("title", ""), it.name)
                 for it in self.items]
        assigned, used = matching.assign(files, m, self.mode.currentData())
        # Felder, die diese Quelle für dieses Album nicht kennt, gar nicht erst als Spalte zeigen
        provided = {"year": m.year, "genre": m.genre, "label": m.label, "originalyear": m.original_year}
        columns = [k for k in ("track", "disc", "title", "artist", "album", "year", "genre", "label",
                               "originalyear") if
                   (k in fields or (k == "disc" and "track" in fields and m.disc_total > 1)
                    or (k == "album" and "album" in fields)) and provided.get(k, True)]
        rows, changes, problems = [], [], 0
        for it, a in zip(self.items, assigned):
            if a.track_index is None:
                problems += 1
                rows.append(PreviewRow(it.name, [(it.tags.get(k, ""), None) for k in columns],
                                       "kein passender Track", ERROR, it.path))
                continue
            new = matching.tags_for(m, a.track_index, fields, clean=self.clean_chip.isChecked())
            diff = {k: v for k, v in new.items() if it.tags.get(k, "") != v}
            cells = [(diff[k], it.tags.get(k, "")) if k in diff else (new.get(k, it.tags.get(k, "")), None)
                     for k in columns]
            status, kind = (f"{len(diff)} Feld{'er' if len(diff) != 1 else ''}", CHANGED) if diff else \
                ("unverändert", UNCHANGED)
            if not a.length_ok:
                status, kind = f"Länge weicht ab ({a.length_diff:+.0f} s)".replace("+", "±"), WARN
                problems += 1
            elif a.title_score is not None and a.title_score < matching.TITLE_SURE:
                status, kind = f"Titel nur ähnlich ({a.title_score:.0%})", WARN
                problems += 1
            rows.append(PreviewRow(it.name, cells, status, kind, it.path))
            changes.append((it, diff))
        self._changes = [(it, d) for it, d in changes if d]
        cover = self.cover_chip.isChecked() and bool(m.cover_full_url)
        n = len(self._changes) if not cover else len(changes)
        self.model.set_preview(Preview([FIELD_BY_KEY[k].label for k in columns], rows,
                                       apply_count=n))
        self._fit()
        extra = []
        if len(self.items) != len(m.tracks):
            extra.append(f"{len(self.items)} Dateien, Album hat {len(m.tracks)} Tracks")
        if problems:
            extra.append(f"{problems} mit Hinweis")
        if self.cover_chip.isChecked() and not m.cover_full_url:
            extra.append("kein Cover bei diesem Treffer")
        self.set_status(f"Zuordnung: {matching.MODES[used]}" + "".join(f"  ·  {e}" for e in extra),
                        "modified" if problems else "")
        self._cover_all = [it for it, _ in changes] if cover else []
        self.apply_btn.setEnabled(n > 0)
        self.apply_btn.setText(f"Übernehmen ({n})" if n else "Übernehmen")
        self.next_btn.setEnabled(n > 0)

    WIDTHS = {"Datei": 190, "Track": 58, "Disc": 50, "Titel": 190, "Interpret": 130, "Album": 140,
              "Albuminterpret": 130, "Jahr": 54, "Genre": 110, "Label": 120, "Original-Jahr": 92}

    def _fit(self):
        hh = self.view.horizontalHeader()
        for c in range(self.model.columnCount() - 1):
            hh.resizeSection(c, self.WIDTHS.get(self.model.headerData(c, Qt.Orientation.Horizontal), 140))

    # --- Übernehmen -----------------------------------------------------------------
    def apply(self):
        m = self._current
        if m is None:
            return
        label = f"Album-Daten von {m.source} ({len(self._changes or self._cover_all)} Dateien)"
        if self._cover_all and m.cover_full_url:
            self.apply_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.set_status("Lade Cover in voller Größe …")
            self.run(coversearch.download_url, m.cover_full_url, done=lambda data: self._finish(label, data),
                     failed=lambda msg: (self.set_status(f"Cover nicht geladen ({msg}) – Tags werden trotzdem übernommen",
                                                         "modified"), self._finish(label, None)))
        else:
            self._finish(label, None)

    def _finish(self, label: str, cover_bytes: bytes | None):
        s = self.settings
        cover = None
        if cover_bytes:
            try:
                cover = prepare_for_embedding(cover_bytes, s.embed_max_size, s.embed_resize, s.jpeg_quality)
            except ValueError:
                cover = None
        if cover is not None:
            by_item = {id(it): d for it, d in self._changes}
            n = self.session.apply_changes([(it, by_item.get(id(it), {})) for it in self._cover_all], label, cover)
            saved = save_cover_files(self.items, cover, s.album_cover_name)
            extra = f", {s.album_cover_name} in {saved} Ordner" if saved else ""
        else:
            n = self.session.apply_changes(self._changes, label)
            extra = ""
        if self._then_next:
            self._then_next = False
            self._advance(f"{n} Datei(en) übernommen{extra}")
            return
        self.win.toast.show_message(f"{n} Datei(en) übernommen{extra} – Strg+S speichert")
        self.accept()

    # --- Übernehmen & weiter: speichern, abhaken, nächster Ordner, gleich wieder suchen ---------------
    def _apply_next(self):
        if not self.next_btn.isEnabled() or not self.next_btn.isVisible():
            return
        self._then_next = True
        self._apply()

    def _advance(self, done_text: str = ""):
        win = self.win
        if win.is_result_list:
            self.accept()
            return
        before = list(win._loaded_dirs)
        for b in (self.apply_btn, self.next_btn, self.skip_btn, self.search_btn):
            b.setEnabled(False)
        self.set_status((done_text + " · " if done_text else "") + "Speichere und gehe zum nächsten Ordner …")
        win.save_and_next()
        started = time.monotonic()

        def poll():
            if not self.isVisible():
                return
            busy = win._save_worker is not None or win._load_worker is not None
            if not busy and win._loaded_dirs != before and win.session.items:
                self._continue_here()
                return
            waited = time.monotonic() - started
            if (not busy and waited > 2.0) or waited > 60:     # kein offener Ordner mehr oder Fehler beim Speichern
                self.skip_btn.setEnabled(True)
                self.search_btn.setEnabled(True)
                self.apply_btn.setEnabled(False)
                self.next_btn.setEnabled(False)
                if win.session.modified_count():
                    self.set_status("Nicht alles gespeichert – bitte im Hauptfenster nachsehen", "danger")
                else:
                    self.set_status("Gespeichert – kein offener Ordner mehr. Geschafft! 🎉", "done")
                return
            QTimer.singleShot(100, poll)
        QTimer.singleShot(100, poll)

    def _continue_here(self):
        """Der nächste Ordner ist geladen: Dateien übernehmen, Suchbegriffe neu, gleich suchen."""
        items, scope = self.win.tool_items()
        self.items = items
        self.scope_label.setText(scope)
        self._changes, self._cover_all = [], []
        artist, album = guess_search(items)
        self.artist.setText(artist)
        self.album.setText(album)
        self.skip_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        self.results.clear()
        self._show_details(None)
        folder = os.path.basename(items[0].dir) if items else ""
        if album:
            self.search()
            self.setWindowTitle(f"Album suchen – {folder}")
        else:
            self.set_status(f"Weiter mit „{folder}“ – Album und Interpret eingeben, dann Suchen")


def save_cover_files(items: list[FileItem], cover, name: str, overwrite: bool = False) -> int:
    """cover.jpg (volle Größe) in jeden Album-Ordner – vorhandene nur mit overwrite."""
    saved = 0
    for d in sorted({it.dir for it in items}):
        target = os.path.join(d, name)
        if os.path.exists(target) and not overwrite:
            continue
        try:
            save_image_file(cover.full(), target)
            saved += 1
        except OSError:
            continue
    return saved


# ======================================================================
# Cover suchen / Künstlerbild suchen – gemeinsames Bildergitter
# ======================================================================
class ImageGridDialog(OnlineDialog):
    sources: tuple[str, ...] = ()
    tile = 150
    BIG = 240

    sources_version = 1          # höher setzen, wenn Quellen dazukommen → gespeicherte Auswahl einmal zurücksetzen

    def build_grid(self, side_title: str):
        self.src_chips = {}
        active = set(self.opts.get("sources", list(self.sources)))
        if self.opts.get("sources_v", 1) < self.sources_version:
            active = set(self.sources)               # neue Quellen sind sonst bei alten Einstellungen aus
            self.opts["sources_v"] = self.sources_version
            self.opts["sources"] = list(self.sources)
        for name in self.sources:
            c = chip(name, checkable=True)
            c.setChecked(name in active)
            c.toggled.connect(self._sources_changed)
            self.src_chips[name] = c
            self.search_row.addWidget(c)
        self.search_button()

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        self.grid = QListWidget()
        self.grid.setObjectName("ImageGrid")
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(self.tile, self.tile))
        self.grid.setGridSize(QSize(self.tile + 24, self.tile + 54))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setWordWrap(True)
        self.grid.setUniformItemSizes(True)
        self.grid.setSpacing(4)
        self.grid.currentRowChanged.connect(self._pick)
        self.grid.itemDoubleClicked.connect(lambda _it: self._apply())
        split.addWidget(self.grid)

        side_scroll = QScrollArea()
        side_scroll.setObjectName("ToolOptions")
        side_scroll.setWidgetResizable(True)
        side_scroll.setFrameShape(QFrame.Shape.NoFrame)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side_scroll.setMinimumWidth(300)
        side_scroll.setMaximumWidth(340)
        side = QWidget(objectName="ToolOptionsInner")
        side_scroll.setWidget(side)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(18, 16, 18, 16)
        sl.setSpacing(8)
        sl.addWidget(section(side_title))
        self.big = QLabel()
        self.big.setFixedSize(self.BIG, self.BIG)
        self.big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(self.big)
        self.big_info = QLabel("")
        self.big_info.setObjectName("CoverState")
        self.big_info.setWordWrap(True)
        sl.addWidget(self.big_info)
        self.big_sub = hint("")
        sl.addWidget(self.big_sub)
        self.side = sl
        split.addWidget(side_scroll)
        split.setStretchFactor(0, 1)
        self.body.addWidget(split)
        self._candidates: list[CoverCandidate] = []
        self._thumbs: dict[int, bytes] = {}
        self.big.setPixmap(rounded_pixmap(None, self.BIG, 12))

    def _sources_changed(self):
        self.opts["sources"] = [n for n, c in self.src_chips.items() if c.isChecked()]

    def active_sources(self) -> list[str]:
        return [n for n, c in self.src_chips.items() if c.isChecked()]

    def show_candidates(self, cands: list[CoverCandidate]):
        self._candidates = cands
        self._thumbs = {}
        self.grid.clear()
        placeholder = QIcon(rounded_pixmap(None, self.tile, 10))
        for c in cands:
            it = QListWidgetItem(placeholder, f"{c.size_text or '?'}\n{c.source}")
            it.setToolTip(c.description)
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.grid.addItem(it)
        self.load_images([(i, c.thumb_url or c.url) for i, c in enumerate(cands)], self._thumb)
        if cands:
            self.grid.setCurrentRow(0)
        self.apply_btn.setEnabled(bool(cands))

    def _thumb(self, i: int, data: bytes):
        self._thumbs[i] = data
        it = self.grid.item(i)
        if it is not None:
            it.setIcon(QIcon(rounded_pixmap(data, self.tile, 10)))
        if i == self.grid.currentRow():
            self._pick(i)

    def _pick(self, i: int):
        if not (0 <= i < len(self._candidates)):
            return
        c = self._candidates[i]
        self.big.setPixmap(rounded_pixmap(self._thumbs.get(i), self.BIG, 12))
        self.big_info.setText(c.description or c.source)
        self.big_sub.setText(f"{c.source} · {c.size_text}" if c.size_text else c.source)

    def current(self) -> CoverCandidate | None:
        i = self.grid.currentRow()
        return self._candidates[i] if 0 <= i < len(self._candidates) else None


class CoverSearchDialog(ImageGridDialog):
    feature_id = "cover_search"
    sources = coversearch.SOURCES
    sources_version = 2          # 1.1.2: TheAudioDB + Bandcamp statt Deezer

    def __init__(self, win, items, scope):
        super().__init__(win, items, scope)
        artist, album = guess_search(items)
        self.artist = self.search_field("Interpret", artist)
        self.album = self.search_field("Album", album)
        self.build_grid("Auswahl")
        s = self.settings
        self.chk_embed = chip("In die Dateien einbetten", checkable=True)
        self.chk_embed.setChecked(self.opts.get("embed", True))
        self.chk_file = chip(f"Als {s.album_cover_name} speichern", checkable=True)
        self.chk_file.setChecked(self.opts.get("file", True))
        for c in (self.chk_embed, self.chk_file):
            c.toggled.connect(self._targets_changed)
        box = QWidget()
        flow = FlowLayout(box, spacing=6)
        flow.addWidget(self.chk_embed)
        flow.addWidget(self.chk_file)
        self.side.addSpacing(6)
        self.side.addWidget(section("Übernehmen als"))
        self.side.addWidget(box)
        size_note = (f"Eingebettet wird auf {s.embed_max_size} px verkleinert, die Datei bleibt in voller Größe."
                     if s.embed_resize else "Eingebettet und gespeichert in voller Größe.")
        self.side.addWidget(hint(size_note))
        dirs = sorted({it.dir for it in items})
        existing = [d for d in dirs if find_folder_image(d, [s.album_cover_name])]
        if existing:
            self.side.addWidget(hint(f"{len(existing)} von {len(dirs)} Ordnern haben schon eine {s.album_cover_name} – "
                                     "sie wird ersetzt.", "muted"))
        self.side.addStretch(1)
        self.foot_hint.setText("Doppelklick übernimmt sofort")
        self.apply_btn.setText("Cover übernehmen")
        if self.album.text().strip() or self.artist.text().strip():
            QTimer.singleShot(0, self.search)

    def _targets_changed(self):
        self.opts["embed"], self.opts["file"] = self.chk_embed.isChecked(), self.chk_file.isChecked()
        self.apply_btn.setEnabled(bool(self._candidates) and (self.opts["embed"] or self.opts["file"]))

    def search(self):
        artist, album = self.artist.text().strip(), self.album.text().strip()
        if not album and not artist:
            self.set_status("Album oder Interpret eingeben")
            return
        sources = self.active_sources()
        if not sources:
            self.set_status("Mindestens eine Quelle auswählen")
            return
        self.set_status("Suche Cover bei " + ", ".join(sources) + " …")
        self.grid.clear()
        self._errors = []

        def run_search():
            return coversearch.search_covers(artist, album, sources, contact=self.settings.musicbrainz_contact,
                                             progress=lambda s, f, e: e and self._errors.append(f"{s}: {e}"))
        self.run(run_search, done=self._found)

    def _found(self, cands: list[CoverCandidate]):
        self.show_candidates(cands)
        self.set_status(*found_message(cands, self._errors, "Cover"))

    def apply(self):
        c = self.current()
        if c is None or not (self.chk_embed.isChecked() or self.chk_file.isChecked()):
            return
        self.apply_btn.setEnabled(False)
        self.set_status(f"Lade Cover von {c.source} …")
        self.run(coversearch.download, c, done=self._finish,
                 failed=lambda msg: (self.show_error(msg), self.apply_btn.setEnabled(True)))

    def _finish(self, data: bytes):
        s = self.settings
        try:
            cover = prepare_for_embedding(data, s.embed_max_size, s.embed_resize, s.jpeg_quality)
        except ValueError as exc:
            self.show_error(str(exc))
            return
        from ..core.covers import image_info
        info = image_info(data)
        parts = []
        if self.chk_embed.isChecked():
            n = self.session.apply_cover(self.items, cover, "Cover (online)")
            parts.append(f"bei {n} Datei(en) vorgemerkt")
        if self.chk_file.isChecked():
            saved = save_cover_files(self.items, cover, s.album_cover_name, overwrite=True)
            parts.append(f"{s.album_cover_name} in {saved} Ordner gespeichert")
        self.win.panel.refresh()
        self.win.toast.show_message(f"Cover {info['w']}×{info['h']}: " + ", ".join(parts))
        self.accept()


class ArtistImageDialog(ImageGridDialog):
    feature_id = "artist_image"
    sources = artistimages.SOURCES
    sources_version = 2          # 1.1.3: Bandcamp, Discogs, Wikipedia statt Deezer

    def __init__(self, win, items, scope, folder: str = "", artist: str = ""):
        """folder/artist: direkt für einen Künstler-Ordner (ohne geladene Dateien) – der Ordnername
        ist dann erst einmal der Künstlername."""
        super().__init__(win, items, scope or (f"Künstler-Ordner „{os.path.basename(folder)}“" if folder else ""))
        self.target_dir = folder or artist_folder(items)
        if not artist:
            artist, _album = guess_search(items) if items else ("", "")
        if self.target_dir and not artist:
            artist = os.path.basename(self.target_dir)
        self.artist = self.search_field("Künstler", artist)
        self.build_grid("Künstlerbild")
        dc = self.src_chips.get("Discogs")
        if dc is not None and not self.settings.discogs_token:        # ohne Token: Quelle aus, mit Hinweis
            dc.setChecked(False)
            dc.setEnabled(False)
            dc.setToolTip("Discogs braucht einen kostenlosen Token – Einstellungen → Online")
        tips = {"Bandcamp": "Band-Fotos – gut für kleine, unbekannte Künstler",
                "Wikipedia": "Freie Bilder von Wikimedia Commons (über MusicBrainz/Wikidata)",
                "TheAudioDB": "Porträt, Fanart und Breitbild"}
        for name, tip in tips.items():
            if name in self.src_chips:
                self.src_chips[name].setToolTip(tip)
        name = self.settings.artist_image_name
        if self.target_dir:
            where = f"Wird gespeichert als {name} in „{os.path.basename(self.target_dir)}“."
            if os.path.exists(os.path.join(self.target_dir, name)):
                where += f" Die vorhandene {name} wird ersetzt."
        else:
            where = "Die Auswahl liegt in mehreren Künstler-Ordnern – bitte Dateien von nur einem Künstler wählen."
        self.side.addSpacing(6)
        self.side.addWidget(hint(where, "muted"))
        self.side.addStretch(1)
        self.apply_btn.setText(f"Als {name} speichern")
        self.foot_hint.setText("Doppelklick speichert sofort")
        if self.target_dir and artist:
            QTimer.singleShot(0, self.search)

    def search(self):
        artist = self.artist.text().strip()
        if not artist:
            self.set_status("Künstler eingeben")
            return
        sources = self.active_sources()
        if not sources:
            self.set_status("Mindestens eine Quelle auswählen")
            return
        self.set_status("Suche Bilder bei " + ", ".join(sources) + " …")
        self.grid.clear()
        self._errors = []
        token, contact = self.settings.discogs_token, self.settings.musicbrainz_contact
        self.run(lambda: artistimages.search_artist_images(
            artist, sources, progress=lambda s, f, e: e and self._errors.append(f"{s}: {e}"),
            discogs_token=token, contact=contact), done=self._found)

    def _found(self, cands):
        self.show_candidates(cands)
        self.apply_btn.setEnabled(bool(cands) and bool(self.target_dir))
        self.set_status(*found_message(cands, self._errors, "Bilder"))

    def apply(self):
        c = self.current()
        if c is None or not self.target_dir:
            return
        self.apply_btn.setEnabled(False)
        self.set_status(f"Lade Bild von {c.source} …")
        self.run(get_image, c.url, done=self._finish,
                 failed=lambda msg: (self.show_error(msg), self.apply_btn.setEnabled(True)))

    def _finish(self, data: bytes):
        name = self.settings.artist_image_name
        target = os.path.join(self.target_dir, name)
        try:
            save_image_file(data, target)
        except OSError as exc:
            QMessageBox.warning(self, "Nicht gespeichert", f"{target}\n{exc.strerror or exc}")
            return
        self.win.toast.show_message(f"Künstlerbild gespeichert: {os.path.basename(self.target_dir)}/{name}")
        self.accept()


def found_message(cands: list, errors: list[str], what: str) -> tuple[str, str]:
    """Statuszeile nach einer Bildsuche: Treffer, Fehler einzelner Quellen, kein Internet."""
    if not cands and errors and all("Keine Verbindung" in e for e in errors):
        return "Keine Verbindung zum Internet – Netzwerk prüfen und nochmal suchen", "danger"
    if not cands:
        msg = f"Keine {what} gefunden – Schreibweise prüfen oder andere Quelle wählen"
        return msg + ("  ·  " + "; ".join(errors) if errors else ""), "modified"
    msg = f"{len(cands)} {what} gefunden"
    if errors:
        return msg + "  ·  nicht erreichbar: " + ", ".join(e.split(":")[0] for e in errors), "modified"
    return msg, ""


def artist_folder(items: list[FileItem]) -> str:
    """Künstler-Ordner = Eltern-Ordner der Album-Ordner (Musik/Künstler/Album/Lied.mp3)."""
    parents = {os.path.dirname(it.dir) for it in items}
    return parents.pop() if len(parents) == 1 else ""


ONLINE_DIALOGS = {
    "musicbrainz": lambda win, items, scope: AlbumSearchDialog(win, items, scope),   # zuletzt benutzte Quelle
    "album_mb": lambda win, items, scope: AlbumSearchDialog(win, items, scope, "MusicBrainz"),
    "album_all": lambda win, items, scope: AlbumSearchDialog(win, items, scope, ALL_SOURCES),
    "discogs": lambda win, items, scope: AlbumSearchDialog(win, items, scope, "Discogs"),
    "deezer": lambda win, items, scope: AlbumSearchDialog(win, items, scope, "Deezer"),
    "itunes": lambda win, items, scope: AlbumSearchDialog(win, items, scope, "iTunes"),
    "lastfm": lambda win, items, scope: AlbumSearchDialog(win, items, scope, "Last.fm"),
    "cover_search": CoverSearchDialog,
    "artist_image": ArtistImageDialog,
}
