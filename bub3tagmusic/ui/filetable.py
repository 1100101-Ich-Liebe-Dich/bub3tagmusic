"""Dateiliste: schnelles Tabellenmodell für zehntausende Einträge.

Sortieren und Filtern passieren direkt im Modell über eine Liste von
Zeilen-Indizes (statt QSortFilterProxyModel) – das ist bei 50.000 Zeilen
um ein Vielfaches schneller.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QAction, QFont, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QMenu, QStyle, QStyledItemDelegate,
                               QTableView)

from ..core import filters
from ..core.fields import FIELD_BY_KEY, number_sort_key
from ..core.model import FileItem
from ..core.scanner import natural_key
from . import icons, theme
from .session import Session


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    width: int
    kind: str = "tag"          # tag | file | info | state
    align: str = "left"


COLUMNS: tuple[Column, ...] = (
    Column("state", "", 30, "state", "center"),
    Column("filename", "Dateiname", 210, "file"),
    Column("title", "Titel", 200),
    Column("artist", "Interpret", 160),
    Column("album", "Album", 170),
    Column("albumartist", "Albuminterpret", 160),
    Column("year", "Jahr", 62, align="right"),
    Column("track", "Track", 62, align="right"),
    Column("disc", "Disc", 52, align="right"),
    Column("genre", "Genre", 110),
    Column("composer", "Komponist", 150),
    Column("comment", "Kommentar", 180),
    Column("cover", "Cover", 92, "info"),
    Column("length", "Länge", 62, "info", "right"),
    Column("bitrate", "kbit/s", 64, "info", "right"),
    Column("samplerate", "Hz", 70, "info", "right"),
    Column("format", "Format", 70, "info"),
    Column("tagtype", "Tag", 76, "info"),
    Column("rg_track", "RG Track", 84, "info", "right"),
    Column("rg_album", "RG Album", 84, "info", "right"),
    Column("folder", "Ordner", 220, "file"),
)
COLUMN_INDEX = {c.key: i for i, c in enumerate(COLUMNS)}
# Später dazugekommene Spalten: bei vorhandenen Einstellungen erst einmal ausgeblendet
NEW_HIDDEN = {"rg_track", "rg_album"}


def fmt_length(sec: float) -> str:
    if not sec:
        return ""
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class FileTableModel(QAbstractTableModel):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._rows: list[int] = []          # sichtbare Zeilen → Index in session.items
        self._pos: dict[int, int] = {}      # id(item) → Zeile
        self._filter = ""
        self._words: list[str] = []
        self._quick: set[str] = set()       # Schnellfilter (Phase 4)
        self._sort: tuple[int, Qt.SortOrder] | None = None
        session.itemsReplaced.connect(self._reset)
        session.itemsChanged.connect(self._items_changed)

    # --- Grundfunktionen -----------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def item(self, row: int) -> FileItem:
        return self.session.items[self._rows[row]]

    def row_of(self, item: FileItem) -> int:
        return self._pos.get(id(item), -1)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        col = COLUMNS[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return col.label
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self._align(col)
        if role == Qt.ItemDataRole.ToolTipRole and col.key == "state":
            return "Status: gelber Punkt = ungespeichert, rot = Fehler"
        return None

    def flags(self, index):
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if COLUMNS[index.column()].kind == "tag":
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    @staticmethod
    def _align(col: Column):
        a = {"left": Qt.AlignmentFlag.AlignLeft, "right": Qt.AlignmentFlag.AlignRight,
             "center": Qt.AlignmentFlag.AlignHCenter}[col.align]
        return a | Qt.AlignmentFlag.AlignVCenter

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        it = self.item(index.row())
        col = COLUMNS[index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self._text(it, col)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self._align(col)
        if role == Qt.ItemDataRole.ForegroundRole:
            if col.kind == "tag" and it.is_field_modified(col.key):
                return theme.qcolor("modified")
            if col.key == "cover":
                state = it.cover_state()[0]
                if state in ("new", "removed"):
                    return theme.qcolor("modified")
                if state == "none":
                    return theme.qcolor("faint")
            if col.kind == "info" or col.key == "folder":
                return theme.qcolor("muted")
            return None
        if role == Qt.ItemDataRole.DecorationRole and col.key == "state":
            if it.error:
                return icons.dot_icon("danger", 9)
            if it.is_modified():
                return icons.dot_icon("modified", 9)
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            if it.error:
                return it.error
            if col.key in ("filename", "folder"):
                return it.path
            if col.kind == "tag" and it.is_field_modified(col.key):
                old = it.orig.get(col.key, "") or "(leer)"
                return f"Vorher: {old}"
            if col.key == "cover":
                cov = it.rec.get("cover")
                if cov:
                    return f"{cov['w']} × {cov['h']} px · {cov['mime'].split('/')[-1].upper()} · {cov['bytes'] // 1024} KB"
        return None

    @staticmethod
    def _text(it: FileItem, col: Column) -> str:
        if col.kind == "tag":
            return it.tags.get(col.key, "")
        k = col.key
        if k == "filename":
            return it.name
        if k == "folder":
            return it.dir
        if k == "cover":
            state = it.cover_state()[0]
            if state == "new":
                return "neu"
            if state == "removed":
                return "entfernen"
            cov = it.rec.get("cover")
            return f"{cov['w']}×{cov['h']}" if cov and cov.get("w") else ("ja" if cov else "–")
        r = it.rec
        if k == "length":
            return fmt_length(r.get("length", 0))
        if k == "bitrate":
            return str(r.get("bitrate") or "")
        if k == "samplerate":
            return str(r.get("samplerate") or "")
        if k == "format":
            return r.get("format", "")
        if k == "tagtype":
            return r.get("tagtype", "")
        if k == "rg_track":
            return (r.get("rg") or {}).get("track", "")
        if k == "rg_album":
            return (r.get("rg") or {}).get("album", "")
        return ""

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        col = COLUMNS[index.column()]
        if col.kind != "tag":
            return False
        it = self.item(index.row())
        value = str(value).strip()
        if it.tags.get(col.key, "") == value:
            return False
        label = f"{FIELD_BY_KEY[col.key].label} geändert (1 Datei)"
        self.session.apply_fields([it], {col.key: value}, label)
        return True

    # --- Sortieren / Filtern ---------------------------------------------------
    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        """column < 0 = Ladereihenfolge (Ordner, dann Dateiname)."""
        self._sort = None if column < 0 else (column, order)
        self.layoutAboutToBeChanged.emit()
        old = self.persistentIndexList()
        old_items = [(idx, self.item(idx.row())) for idx in old if idx.isValid() and idx.row() < len(self._rows)]
        self._apply_sort()
        self._rebuild_pos()
        new = []
        for idx, it in old_items:
            r = self.row_of(it)
            new.append(self.index(r, idx.column()) if r >= 0 else QModelIndex())
        self.changePersistentIndexList([i for i, _ in old_items], new)
        self.layoutChanged.emit()

    def _apply_sort(self):
        items = self.session.items
        if self._sort is None:
            self._rows.sort()
            return
        column, order = self._sort
        col = COLUMNS[column]
        if col.key in ("track", "disc", "year"):
            key = lambda i: number_sort_key(items[i].tags.get(col.key, ""))  # noqa: E731
        elif col.key == "length":
            key = lambda i: items[i].rec.get("length", 0)  # noqa: E731
        elif col.key in ("rg_track", "rg_album"):
            def key(i, k=col.key[3:]):  # noqa: E306
                v = (items[i].rec.get("rg") or {}).get(k, "")
                try:
                    return (0, float(v.split()[0]))
                except (ValueError, IndexError):
                    return (1, 0.0)
        elif col.key in ("bitrate", "samplerate"):
            key = lambda i: items[i].rec.get(col.key, 0) or 0  # noqa: E731
        elif col.key == "cover":
            key = lambda i: ((items[i].rec.get("cover") or {}).get("w", 0))  # noqa: E731
        elif col.key == "state":
            key = lambda i: (not items[i].is_modified(), i)  # noqa: E731
        elif col.key in ("filename", "folder"):
            key = lambda i: natural_key(items[i].path)  # noqa: E731
        else:
            key = lambda i: (self._text(items[i], col).casefold() or "￿", i)  # noqa: E731
        self._rows.sort(key=key, reverse=order == Qt.SortOrder.DescendingOrder)

    def set_filter(self, text: str):
        self._filter = text.strip().casefold()
        self._words = filters.text_words(text)
        self._reset()

    def set_quick_filters(self, keys) -> None:
        self._quick = set(keys)
        self._reset()

    @property
    def is_filtered(self) -> bool:
        return bool(self._words or self._quick)

    def _matches(self, it: FileItem) -> bool:
        if self._quick and not filters.item_passes(it, self._quick):
            return False
        return filters.text_passes(self._words, it.name, it.tags)

    def _reset(self):
        self.beginResetModel()
        items = self.session.items
        if self.is_filtered:
            self._rows = [i for i, it in enumerate(items) if self._matches(it)]
        else:
            self._rows = list(range(len(items)))
        if self._sort is not None:
            self._apply_sort()
        self._rebuild_pos()
        self.endResetModel()

    def _rebuild_pos(self):
        items = self.session.items
        self._pos = {id(items[i]): row for row, i in enumerate(self._rows)}

    def _items_changed(self, changed: list):
        if not self._rows:
            return
        if len(changed) > 200:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, len(COLUMNS) - 1))
            return
        last = len(COLUMNS) - 1
        for it in changed:
            r = self.row_of(it)
            if r >= 0:
                self.dataChanged.emit(self.index(r, 0), self.index(r, last))

    def visible_items(self) -> list[FileItem]:
        items = self.session.items
        return [items[i] for i in self._rows]


class _Delegate(QStyledItemDelegate):
    """Etwas Luft links/rechts und ein Akzentstrich an ausgewählten Zeilen."""

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)
        if index.column() == 0 and option.state & QStyle.StateFlag.State_Selected:
            painter.save()
            painter.fillRect(QRect(option.rect.left(), option.rect.top() + 4, 3, option.rect.height() - 8),
                             theme.qcolor("selection_line"))
            painter.restore()


class FileTable(QTableView):
    selectionChangedSignal = Signal()
    openFolderRequested = Signal()

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.model_ = FileTableModel(session, self)
        self.setModel(self.model_)
        self.setItemDelegate(_Delegate(self))
        self.empty_title = "Wähle links einen Ordner"
        self.empty_hint = "Mit gedrückter Strg-Taste mehrere Ordner wählen"

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                             | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSortingEnabled(False)
        self.setCornerButtonEnabled(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)

        vh = self.verticalHeader()
        vh.setVisible(False)
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(32)

        hh = self.horizontalHeader()
        hh.setSectionsMovable(True)
        hh.setHighlightSections(False)
        hh.setStretchLastSection(False)
        hh.setSortIndicatorShown(True)
        hh.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self._header_clicked)
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._header_menu)
        hh.setMinimumSectionSize(28)
        for i, c in enumerate(COLUMNS):
            hh.resizeSection(i, c.width)
        hh.setSectionResizeMode(COLUMN_INDEX["state"], QHeaderView.ResizeMode.Fixed)

        self.selectionModel().selectionChanged.connect(lambda *_: self.selectionChangedSignal.emit())
        self.model_.modelReset.connect(self.selectionChangedSignal.emit)

    # --- Spalten ---------------------------------------------------------------
    def apply_column_settings(self, hidden: list[str], widths: dict[str, int]):
        hh = self.horizontalHeader()
        for i, c in enumerate(COLUMNS):
            hh.setSectionHidden(i, c.key in hidden or (c.key in NEW_HIDDEN and c.key not in widths))
            if c.key in widths and c.key != "state":
                hh.resizeSection(i, max(30, int(widths[c.key])))

    def column_settings(self) -> tuple[list[str], dict[str, int]]:
        hh = self.horizontalHeader()
        hidden = [c.key for i, c in enumerate(COLUMNS) if hh.isSectionHidden(i)]
        widths = {c.key: hh.sectionSize(i) for i, c in enumerate(COLUMNS) if not hh.isSectionHidden(i)}
        return hidden, widths

    def _header_menu(self, pos: QPoint):
        hh = self.horizontalHeader()
        menu = QMenu(self)
        menu.addSection("Spalten anzeigen")
        for i, c in enumerate(COLUMNS):
            if c.key in ("state", "filename"):
                continue
            act = QAction(c.label, menu, checkable=True)
            act.setChecked(not hh.isSectionHidden(i))
            act.toggled.connect(lambda on, i=i: hh.setSectionHidden(i, not on))
            menu.addAction(act)
        menu.addSeparator()
        menu.addAction("Sortierung aufheben", self.reset_sort)
        menu.exec(hh.mapToGlobal(pos))

    def _header_clicked(self, section: int):
        hh = self.horizontalHeader()
        cur = self.model_._sort
        if cur and cur[0] == section:
            if cur[1] == Qt.SortOrder.AscendingOrder:
                order = Qt.SortOrder.DescendingOrder
            else:
                self.reset_sort()
                return
        else:
            order = Qt.SortOrder.AscendingOrder
        hh.setSortIndicator(section, order)
        self.model_.sort(section, order)

    def reset_sort(self):
        self.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.model_.sort(-1)

    # --- Auswahl ---------------------------------------------------------------
    def selected_items(self) -> list[FileItem]:
        """Über Auswahl-Bereiche statt selectedRows() – bei 50.000 Zeilen viel schneller."""
        rows: set[int] = set()
        for rng in self.selectionModel().selection():
            rows.update(range(rng.top(), rng.bottom() + 1))
        n = self.model_.rowCount()
        return [self.model_.item(r) for r in sorted(rows) if r < n]

    def select_items(self, items: list[FileItem]):
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        sel = QItemSelection()
        last = len(COLUMNS) - 1
        for it in items:
            r = self.model_.row_of(it)
            if r >= 0:
                sel.select(self.model_.index(r, 0), self.model_.index(r, last))
        self.selectionModel().select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    # --- Leerer Zustand ----------------------------------------------------------
    def set_empty_text(self, title: str, hint: str = ""):
        self.empty_title, self.empty_hint = title, hint
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.model_.rowCount() > 0:
            return
        p = QPainter(self.viewport())
        r = self.viewport().rect()
        f = theme.ui_font(16, QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(theme.qcolor("muted"))
        title_rect = QRect(r.left(), r.center().y() - 30, r.width(), 28)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.empty_title)
        if self.empty_hint:
            p.setFont(theme.ui_font(13))
            p.setPen(theme.qcolor("faint"))
            p.drawText(QRect(r.left(), r.center().y() + 2, r.width(), 22), Qt.AlignmentFlag.AlignCenter,
                       self.empty_hint)
        p.end()
