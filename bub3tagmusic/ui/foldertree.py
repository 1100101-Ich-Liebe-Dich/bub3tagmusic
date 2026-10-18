"""Ordnerbaum links: Sammlung, Künstler, Alben – mit Fertig-Status.

* Ein "Album-Ordner" ist jeder Ordner, der direkt Musikdateien enthält.
* Fertig-Status steht im Cache (nicht in den Musikdateien).
* Künstler-Ordner zeigen, wie viele ihrer Alben fertig sind (z. B. 2/5).
"""

from __future__ import annotations

import os

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPainter, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QMenu, QProgressBar, QStyle,
                               QStyledItemDelegate, QStyleOptionViewItem, QTreeView, QVBoxLayout, QWidget)

from ..core.cache import FOLDER_DONE, FOLDER_OPEN, Cache
from ..core.scanner import FolderNode
from . import icons, theme
from .workers import TreeScanWorker

PATH_ROLE = Qt.ItemDataRole.UserRole + 1
NODE_ROLE = Qt.ItemDataRole.UserRole + 2


class _Delegate(QStyledItemDelegate):
    def __init__(self, tree: "FolderTree"):
        super().__init__(tree.view)
        self.tree = tree

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 30)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        node: FolderNode = index.data(NODE_ROLE)
        widget = opt.widget
        style = widget.style() if widget else None
        opt.text = ""
        opt.icon = QIcon()  # Symbol und Text zeichnen wir selbst
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        if style:
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, widget)
        if node is None:
            return

        r = option.rect.adjusted(6, 0, -8, 0)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Status rechts
        done, total = self.tree.album_progress(node)
        status_w = 0
        if node.audio_count and not node.children:
            status_w = 18
            ic = icons.icon("check-circle-fill", "done") if done else None
            if ic is not None and not ic.isNull():
                ic.paint(painter, QRect(r.right() - 16, r.center().y() - 8, 16, 16))
            else:
                icons.dot_icon("faint", 9, ring=True).paint(
                    painter, QRect(r.right() - 12, r.center().y() - 4, 9, 9))
        elif total:
            text = "✓" if done == total else f"{done}/{total}"
            painter.setFont(theme.ui_font(11, QFont.Weight.Medium))
            painter.setPen(theme.qcolor("done" if done == total else "faint"))
            fm = painter.fontMetrics()
            status_w = fm.horizontalAdvance(text) + 4
            painter.drawText(QRect(r.right() - status_w, r.top(), status_w, r.height()),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, text)

        # Ordnersymbol + Name
        is_album = node.audio_count > 0 and not node.children
        icon_name = "disc" if is_album else ("folder-open" if self.tree.view.isExpanded(index) else "folder")
        ic = icons.icon(icon_name, "accent" if (option.state & QStyle.StateFlag.State_Selected) else "muted")
        ic.paint(painter, QRect(r.left(), r.center().y() - 8, 16, 16))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setFont(theme.ui_font(13, QFont.Weight.Medium if selected else QFont.Weight.Normal))
        painter.setPen(theme.qcolor("text"))
        text_rect = QRect(r.left() + 24, r.top(), r.width() - 24 - status_w - 8, r.height())
        name = painter.fontMetrics().elidedText(node.name, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
        painter.restore()


class FolderTree(QWidget):
    foldersSelected = Signal(list)       # gewählte Ordner (Pfade)
    artistImageRequested = Signal(str)   # Künstlerbild (folder.jpg) für diesen Ordner suchen
    rootChanged = Signal(str)
    progressChanged = Signal(int, int)   # fertig, gesamt (Alben)

    def __init__(self, cache: Cache, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.cache = cache
        self.root_path = ""
        self.root_node: FolderNode | None = None
        self.status: dict[str, int] = {}
        self._items: dict[str, QStandardItem] = {}
        self._albums: list[str] = []
        self._album_set: set[str] = set()
        self._token = 0
        self._worker: TreeScanWorker | None = None
        self._pending_select: list[str] = []
        self._progress_cache: dict[str, tuple[int, int]] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QWidget(objectName="SidebarHeader")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(14, 12, 14, 12)
        hl.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.root_label = QLabel("Keine Sammlung geöffnet")
        self.root_label.setProperty("role", "heading")
        self.root_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        top.addWidget(self.root_label, 1)
        hl.addLayout(top)
        self.progress_label = QLabel("Öffne deinen Musik-Ordner, um loszulegen")
        self.progress_label.setProperty("role", "faint")
        hl.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        hl.addWidget(self.progress_bar)
        lay.addWidget(head)

        self.model = QStandardItemModel(self)
        self.view = QTreeView()
        self.view.setModel(self.model)
        self.view.setHeaderHidden(True)
        self.view.setUniformRowHeights(True)
        self.view.setAnimated(False)
        self.view.setIndentation(14)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setItemDelegate(_Delegate(self))
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.setExpandsOnDoubleClick(True)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.selectionModel().selectionChanged.connect(self._on_selection)
        lay.addWidget(self.view, 1)

        self._debounce = QTimer(self, singleShot=True, interval=160)
        self._debounce.timeout.connect(self._emit_selection)
        self.setAcceptDrops(True)
        self.setMinimumWidth(200)

    # --- Sammlung ----------------------------------------------------------------
    def set_root(self, path: str, select: list[str] | None = None):
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return
        self.root_path = path
        self._pending_select = select if select is not None else self.selected_paths()
        self.root_label.setText(os.path.basename(path) or path)
        self.root_label.setToolTip(path)
        self.progress_label.setText("Ordner werden gezählt …")
        self._token += 1
        if self._worker is not None:
            self._worker.cancel()
        w = TreeScanWorker(path, self._token, self)
        w.done.connect(self._populate)
        w.finished.connect(w.deleteLater)
        self._worker = w
        w.start()
        self.rootChanged.emit(path)

    def reload(self):
        if self.root_path:
            self.set_root(self.root_path)

    def _populate(self, node: FolderNode, token: int):
        if token != self._token:
            return
        self._worker = None
        self.root_node = node
        self.status = self.cache.folder_status_all()
        self._progress_cache.clear()
        self.view.setUpdatesEnabled(False)
        self.view.selectionModel().blockSignals(True)
        self.model.clear()
        self._items.clear()
        self._albums = []

        def build(n: FolderNode) -> QStandardItem:
            it = QStandardItem(n.name)
            it.setData(n.path, PATH_ROLE)
            it.setData(n, NODE_ROLE)
            it.setToolTip(f"{n.path}\n{n.total_count} Musikdateien")
            self._items[n.path] = it
            if n.audio_count:
                self._albums.append(n.path)
            for c in n.children:
                it.appendRow(build(c))
            return it

        root_item = build(node)
        self.model.appendRow(root_item)
        self._album_set = set(self._albums)
        self.view.expand(root_item.index())
        self.view.selectionModel().blockSignals(False)
        self.view.setUpdatesEnabled(True)
        self._update_progress()

        if self._pending_select:
            paths = [p for p in self._pending_select if p in self._items]
            self._pending_select = []
            if paths:
                self.select_paths(paths, emit=True)
        if node.total_count == 0:
            self.progress_label.setText("Keine Musikdateien in diesem Ordner gefunden")

    # --- Fortschritt -------------------------------------------------------------
    def album_progress(self, node: FolderNode) -> tuple[int, int]:
        cached = self._progress_cache.get(node.path)
        if cached is not None:
            return cached
        done = total = 0
        for n in node.walk():
            if n.audio_count:
                total += 1
                if self.status.get(n.path) == FOLDER_DONE:
                    done += 1
        self._progress_cache[node.path] = (done, total)
        return done, total

    def _update_progress(self):
        self._progress_cache.clear()
        total = len(self._albums)
        done = sum(1 for p in self._albums if self.status.get(p) == FOLDER_DONE)
        if total:
            self.progress_label.setText(f"{done:,} von {total:,} Alben fertig".replace(",", "."))
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)
        self.view.viewport().update()
        self.progressChanged.emit(done, total)

    # --- Status ------------------------------------------------------------------
    def node_for(self, path: str):
        it = self._items.get(path)
        return it.data(NODE_ROLE) if it is not None else None

    def albums_in(self, paths: list[str]) -> list[str]:
        """Alle Album-Ordner in/unter den angegebenen Ordnern."""
        out = []
        for p in paths:
            it = self._items.get(p)
            node = it.data(NODE_ROLE) if it else None
            if node is None:
                if p in self._album_set or os.path.isdir(p):
                    out.append(p)
                continue
            out.extend(n.path for n in node.walk() if n.audio_count)
        return list(dict.fromkeys(out))

    def mark(self, paths: list[str], status: int):
        albums = self.albums_in(paths)
        if not albums:
            return
        self.cache.set_folder_status(albums, status)
        for p in albums:
            self.status[p] = status
        self._update_progress()

    def is_done(self, path: str) -> bool:
        return self.status.get(path) == FOLDER_DONE

    # --- Auswahl / Navigation ------------------------------------------------------
    def selected_paths(self) -> list[str]:
        idxs = self.view.selectionModel().selectedRows() if self.view.selectionModel() else []
        return [i.data(PATH_ROLE) for i in idxs if i.data(PATH_ROLE)]

    def select_paths(self, paths: list[str], emit: bool = True):
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        sel = QItemSelection()
        first = None
        for p in paths:
            it = self._items.get(p)
            if it is None:
                continue
            idx = it.index()
            first = first or idx
            parent = idx.parent()
            while parent.isValid():
                self.view.expand(parent)
                parent = parent.parent()
            sel.select(idx, idx)
        if first is None:
            return
        sm = self.view.selectionModel()
        sm.blockSignals(True)
        sm.select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        sm.setCurrentIndex(first, QItemSelectionModel.SelectionFlag.NoUpdate)
        sm.blockSignals(False)
        self.view.scrollTo(first, QAbstractItemView.ScrollHint.EnsureVisible)
        self.view.viewport().update()
        if emit:
            self._debounce.stop()
            self._emit_selection()

    def neighbour_album(self, current: list[str], step: int = 1, only_open: bool = True) -> str | None:
        """Nächster (step=1) oder vorheriger (step=-1) Album-Ordner in Baum-Reihenfolge."""
        if not self._albums:
            return None
        positions = [self._albums.index(p) for p in self.albums_in(current) if p in self._album_set]
        if not positions:
            # Auswahl ist z. B. der Sammlungs-Ordner selbst: ab Anfang suchen
            start = -1 if step > 0 else len(self._albums)
        else:
            start = max(positions) if step > 0 else min(positions)
        i = start + step
        while 0 <= i < len(self._albums):
            p = self._albums[i]
            if not only_open or self.status.get(p) != FOLDER_DONE:
                return p
            i += step
        return None

    def _on_selection(self, *_):
        self._debounce.start()

    def _emit_selection(self):
        self.foldersSelected.emit(self.selected_paths())

    # --- Kontextmenü -----------------------------------------------------------------
    def _context_menu(self, pos):
        paths = self.selected_paths()
        if not paths:
            return
        menu = QMenu(self)
        menu.addAction(icons.icon("check-circle"), "Als fertig markieren", lambda: self.mark(paths, FOLDER_DONE))
        menu.addAction(icons.icon("circle"), "Als offen markieren", lambda: self.mark(paths, FOLDER_OPEN))
        menu.addSeparator()
        if len(paths) == 1:
            menu.addAction(icons.icon("folder-open"), "Im Dateimanager öffnen",
                           lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(paths[0])))
            menu.addAction(icons.icon("house-line"), "Als Sammlung öffnen", lambda: self.set_root(paths[0], []))
            menu.addAction(icons.icon("user-circle"), "Künstlerbild für diesen Ordner suchen …",
                           lambda: self.artistImageRequested.emit(paths[0]))
        menu.addSeparator()
        menu.addAction("Alles aufklappen", self.view.expandAll)
        menu.addAction("Alles zuklappen", lambda: (self.view.collapseAll(),
                                                   self.view.expand(self.model.index(0, 0))))
        menu.addAction(icons.icon("arrows-clockwise"), "Ordner neu zählen", self.reload)
        menu.exec(self.view.viewport().mapToGlobal(pos))

    # --- Ordner per Drag & Drop öffnen ---------------------------------------------
    def dragEnterEvent(self, e):
        urls = e.mimeData().urls() if e.mimeData().hasUrls() else []
        if urls and urls[0].isLocalFile() and os.path.isdir(urls[0].toLocalFile()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        path = e.mimeData().urls()[0].toLocalFile()
        if os.path.isdir(path):
            self.set_root(path, [])
            e.acceptProposedAction()
