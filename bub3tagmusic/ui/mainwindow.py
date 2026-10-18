"""Hauptfenster: verbindet Ordnerbaum, Dateiliste, Bearbeitungsfeld und Arbeiter."""

from __future__ import annotations

import os

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QMenu, QMessageBox, QProgressBar, QPushButton, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, PRESENTER, PRESENTER_URL, features
from ..core import filters
from ..core.cache import FOLDER_DONE, FOLDER_OPEN, Cache
from ..core.settings import Settings, cache_dir
from ..core.undo import EditStep, RenameStep, SaveStep
from . import icons, theme
from .dialogs import (AboutDialog, ComingSoonDialog, ErrorListDialog, SettingsDialog, ShortcutsDialog, Toast,
                      open_url)
from .editpanel import EditPanel
from .filterbar import FilterBar
from .filetable import FileTable
from .foldertree import FolderTree
from .session import Session
from .extras import EXTRA_DIALOGS
from .online import ONLINE_DIALOGS
from .tools import TOOL_DIALOGS
from .workers import LoadWorker, RenameWorker, SaveWorker

# Fertige Funktionen späterer Phasen hier eintragen: feature-id → Methodenname.
# Werkzeuge mit Vorschau-Dialog stehen stattdessen in ui/tools.py → TOOL_DIALOGS.
FEATURE_HANDLERS: dict[str, str] = {
    "filters": "toggle_filter_bar",
    "export": "export_list",
}


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.cache = Cache(cache_dir() / "cache.sqlite")
        self.session = Session(self)
        self._icon_targets: list[tuple[object, str, str]] = []
        self._load_token = 0
        self._load_worker: LoadWorker | None = None
        self._save_worker: SaveWorker | None = None
        self._loaded_dirs: list[str] = []
        self._search: tuple[set, str] | None = None     # Liste = Suchergebnis aus der ganzen Sammlung
        self._result_files: list[str] | None = None     # Liste = feste Dateiliste (z. B. Duplikate)
        self._result_label = ""
        self._after_load_select_all = settings.select_all_on_load

        self.setWindowTitle(APP_NAME)
        self.setAcceptDrops(True)
        self.resize(1360, 820)
        self.setMinimumSize(980, 600)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        self.tree = FolderTree(self.cache)
        self.table = FileTable(self.session)
        self.panel = EditPanel(self.session, settings)

        self.table_area = QWidget(objectName="TableArea")
        tl = QVBoxLayout(self.table_area)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        self.filterbar = FilterBar()
        self.filterbar.setVisible(settings.show_filter_bar)
        tl.addWidget(self.filterbar)
        tl.addWidget(self.table)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.table_area)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([270, 760, 390])
        root.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

        self.toast = Toast(self.table_area)
        self._build_statusbar()
        self._build_actions()

        # Signale
        self.tree.foldersSelected.connect(self._on_folders_selected)
        self.tree.progressChanged.connect(lambda *_: self._update_status())
        self.table.selectionChangedSignal.connect(self._sel_timer_start)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        self.session.stateChanged.connect(self._update_status)
        self.session.itemsChanged.connect(self._on_items_changed)
        self.panel.message.connect(self.toast.show_message)
        self.panel.featureRequested.connect(self.run_feature)
        self.panel.saveNextRequested.connect(self.save_and_next)
        self.filterbar.changed.connect(self._quick_filters_changed)
        self.filterbar.collectionRequested.connect(self.search_collection)
        self.table.model_.modelReset.connect(self._update_status)
        self._count_timer = QTimer(self, singleShot=True, interval=350)
        self._count_timer.timeout.connect(self._update_filter_counts)
        self.session.itemsReplaced.connect(self._count_timer.start)
        self.session.itemsChanged.connect(lambda _i: self._count_timer.start())

        self._sel_timer = QTimer(self, singleShot=True, interval=40)
        self._sel_timer.timeout.connect(self._on_table_selection)

        self._restore_state()
        self._update_status()
        self._update_empty_text()

    # ==================================================================
    # Aufbau
    # ==================================================================
    def _icon(self, target, name: str, role: str = "text"):
        target.setIcon(icons.icon(name, role))
        self._icon_targets.append((target, name, role))

    def _tool(self, text: str, icon_name: str, tip: str = "", checkable=False, text_beside=True) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip or text)
        b.setCheckable(checkable)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text_beside
                             else Qt.ToolButtonStyle.ToolButtonIconOnly)
        if text_beside:
            b.setProperty("kind", "text")
        self._icon(b, icon_name, "muted" if not checkable else "muted")
        return b

    def _build_topbar(self) -> QWidget:
        bar = QWidget(objectName="TopBar")
        bar.setFixedHeight(58)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(4)

        mark = QLabel(APP_NAME)
        mark.setObjectName("Wordmark")
        mark.setToolTip(f"präsentiert von {PRESENTER}")
        h.addWidget(mark)
        h.addSpacing(18)

        self.btn_open = self._tool("Sammlung öffnen", "folder-open", "Musik-Ordner öffnen (Strg+O)")
        self.btn_open.clicked.connect(self.open_collection)
        h.addWidget(self.btn_open)

        self.btn_recursive = self._tool("Unterordner", "tree-structure",
                                        "Unterordner mitladen (Strg+R) – z. B. alle Alben eines Künstlers auf einmal",
                                        checkable=True)
        self.btn_recursive.setChecked(self.settings.recursive)
        self.btn_recursive.toggled.connect(self._toggle_recursive)
        h.addWidget(self.btn_recursive)

        self.btn_reload = self._tool("", "arrows-clockwise", "Neu einlesen (F5)", text_beside=False)
        self.btn_reload.clicked.connect(self.reload)
        h.addWidget(self.btn_reload)
        h.addSpacing(14)

        self.filter = QLineEdit()
        self.filter.setObjectName("FilterField")
        self.filter.setPlaceholderText("Liste filtern …  (Strg+F)")
        self.filter.setClearButtonEnabled(True)
        self.filter.setMinimumWidth(180)
        self.filter.setMaximumWidth(320)
        self._filter_icon = self.filter.addAction(icons.icon("magnifying-glass", "faint"),
                                                  QLineEdit.ActionPosition.LeadingPosition)
        self._icon_targets.append((self._filter_icon, "magnifying-glass", "faint"))
        self._filter_timer = QTimer(self, singleShot=True, interval=180)
        self._filter_timer.timeout.connect(lambda: self.table.model_.set_filter(self.filter.text()))
        self.filter.textChanged.connect(lambda _t: (self._filter_timer.start(), self._update_search_button()))
        h.addWidget(self.filter, 1)
        h.addSpacing(10)

        # Menüs der späteren Phasen – aus features.py gebaut
        for group in ("tools", "online", "extras"):
            title = features.GROUP_TITLES[group]
            icon_name = {"tools": "wrench", "online": "globe", "extras": "lightning"}[group]
            b = self._tool(title, icon_name, f"{title} (Phase {features.by_group(group)[0].phase})")
            b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            b.setMenu(self._feature_menu(group))
            h.addWidget(b)

        h.addSpacing(10)
        sep = QWidget()
        sep.setFixedSize(1, 24)
        sep.setStyleSheet(f"background: {theme.tok('line')};")
        self._sep = sep
        h.addWidget(sep)
        h.addSpacing(10)

        self.btn_undo = self._tool("", "arrow-counter-clockwise", "Rückgängig (Strg+Z)", text_beside=False)
        self.btn_undo.clicked.connect(self.undo)
        h.addWidget(self.btn_undo)

        self.btn_save = QPushButton("Speichern")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setToolTip("Alle Änderungen speichern (Strg+S)")
        self.btn_save.setMinimumWidth(132)
        self._icon(self.btn_save, "floppy-disk", "text")
        self.btn_save.clicked.connect(lambda: self.save())
        h.addSpacing(4)
        h.addWidget(self.btn_save)
        h.addSpacing(4)

        self.btn_menu = self._tool("", "gear-six", "Einstellungen und mehr", text_beside=False)
        self.btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_menu.setMenu(self._main_menu())
        h.addWidget(self.btn_menu)
        return bar

    def _feature_menu(self, group: str) -> QMenu:
        m = QMenu(self)
        for f in features.by_group(group):
            right = (f.shortcut.replace("Ctrl", "Strg") if f.shortcut else "") if f.ready else f"Phase {f.phase}"
            act = m.addAction(icons.icon(f.icon, "muted"), f"{f.title}\t{right}" if right else f.title)
            act.setToolTip(f.description)
            act.triggered.connect(lambda _=False, fid=f.id: self.run_feature(fid))
            self._icon_targets.append((act, f.icon, "muted"))
        return m

    def _main_menu(self) -> QMenu:
        m = QMenu(self)

        def add(text, slot, icon_name=None):
            a = m.addAction(text, slot)
            if icon_name:
                self._icon(a, icon_name, "muted")
            return a

        add("Einstellungen …", self.open_settings, "sliders-horizontal")
        add("Hell / Dunkel umschalten", self.toggle_theme, "sun")
        add("Tastenkürzel", lambda: ShortcutsDialog(self).exec(), "keyboard")
        m.addSeparator()
        add("Gewählte Ordner als fertig markieren", lambda: self._mark_tree(FOLDER_DONE), "check-circle")
        add("Gewählte Ordner als offen markieren", lambda: self._mark_tree(FOLDER_OPEN), "circle")
        add("Zwischenspeicher leeren", self._clear_cache, "trash")
        self._act_desktop = None
        if os.environ.get("APPIMAGE"):
            self._act_desktop = add("Ins Startmenü eintragen", self._toggle_desktop_entry, "list-plus")
            m.aboutToShow.connect(self._update_desktop_action)
        m.addSeparator()
        add(f"Über {APP_NAME}", lambda: AboutDialog(self).exec(), "info")
        add(PRESENTER, lambda: open_url(PRESENTER_URL), "anchor")
        return m

    def _build_statusbar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.lbl_count = QLabel()
        self.lbl_sel = QLabel()
        self.lbl_mod = QLabel()
        sb.addWidget(self.lbl_count)
        sb.addWidget(self.lbl_sel)
        sb.addWidget(self.lbl_mod)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        self.progress.hide()
        self.lbl_progress = QLabel()
        self.lbl_progress.hide()
        sb.addWidget(self.lbl_progress)
        sb.addWidget(self.progress)
        link = QLabel(f'präsentiert von <a href="{PRESENTER_URL}" style="text-decoration:none; '
                      f'color:{theme.tok("muted")}; font-weight:600">{PRESENTER}</a>')
        link.setOpenExternalLinks(True)
        self._presenter_label = link
        sb.addPermanentWidget(link)

    def _build_actions(self):
        def act(keys, slot, ctx=Qt.ShortcutContext.WindowShortcut):
            a = QAction(self)
            a.setShortcut(QKeySequence(keys))
            a.setShortcutContext(ctx)
            a.triggered.connect(slot)
            self.addAction(a)
            return a

        act("Ctrl+O", self.open_collection)
        act("Ctrl+S", lambda: self.save())
        act("Ctrl+Right", self.save_and_next)
        act("Ctrl+Left", self.previous_folder)
        act("Ctrl+Z", self.undo)
        act("Ctrl+D", self.toggle_done)
        act("Ctrl+R", lambda: self.btn_recursive.toggle())
        act("F5", self.reload)
        act("Ctrl+F", lambda: (self.filter.setFocus(), self.filter.selectAll()))
        act("Ctrl+E", self._focus_title)
        act("Ctrl+,", self.open_settings)
        act("F1", lambda: ShortcutsDialog(self).exec())
        act("Ctrl+Shift+V", lambda: self.panel.paste_cover_if_image() or
            self.toast.show_message("In der Zwischenablage ist kein Bild"))
        for f in features.FEATURES:
            if f.shortcut:
                act(f.shortcut, lambda fid=f.id: self.run_feature(fid))

    # ==================================================================
    # Sammlung & Laden
    # ==================================================================
    def open_collection(self):
        start = self.tree.root_path or self.settings.last_root or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Musik-Sammlung öffnen", start)
        if path:
            if not self._confirm_unsaved():
                return
            self.session.clear()
            self._loaded_dirs = []
            self.tree.set_root(path, [])
            self.settings.last_root = path
            self._update_empty_text()

    def reload(self):
        if self._result_files is not None:
            self._load([], files=self._result_files, label=self._result_label)
            return
        if self._search is not None:
            self.search_collection(self._search)
            return
        if self._loaded_dirs:
            self._load(self._loaded_dirs, force=True)
        self.tree.reload()

    def _toggle_recursive(self, on: bool):
        self.settings.recursive = on
        if self._loaded_dirs:
            if not self._confirm_unsaved():
                self.btn_recursive.blockSignals(True)
                self.btn_recursive.setChecked(not on)
                self.btn_recursive.blockSignals(False)
                self.settings.recursive = not on
                return
            self._load(self._loaded_dirs, force=True)
        self.toast.show_message("Unterordner werden mitgeladen" if on else "Nur der gewählte Ordner")

    def _on_folders_selected(self, paths: list[str]):
        if not paths or (paths == self._loaded_dirs and not self.is_result_list):
            return
        if not self._confirm_unsaved():
            self.tree.select_paths(self._loaded_dirs, emit=False)
            return
        self._load(paths)

    @property
    def is_result_list(self) -> bool:
        """Liste zeigt ein Suchergebnis statt gewählter Ordner (kein „nächster Ordner“)."""
        return self._search is not None or self._result_files is not None

    def show_files(self, paths: list[str], label: str):
        """Bestimmte Dateien in die Liste holen (z. B. aus der Duplikat-Suche)."""
        if not self._confirm_unsaved():
            return False
        self.tree.select_paths([], emit=False)
        self._load([], files=list(paths), label=label)
        return True

    def _load(self, paths: list[str], force: bool = False, keep=None, search: tuple | None = None,
              files: list[str] | None = None, label: str = ""):
        self.panel.set_items([])
        self._load_token += 1
        if self._load_worker is not None:
            self._load_worker.cancel()
        self._search = search
        self._result_files = files
        self._result_label = label if files is not None else ""
        self._loaded_dirs = [] if (search or files is not None) else list(paths)
        self.session.clear()
        self.table.set_empty_text("Durchsuche die Sammlung …" if search else "Wird geladen …", "")
        w = LoadWorker(paths, True if search else self.settings.recursive, self.cache, self._load_token, self,
                       keep=keep, files=files)
        w.progress.connect(self._load_progress)
        w.done.connect(self._loaded)
        w.finished.connect(w.deleteLater)
        self._load_worker = w
        QTimer.singleShot(250, lambda t=self._load_token: self._show_progress(t))
        w.start()
        names = ", ".join(os.path.basename(p) for p in paths[:3]) + (" …" if len(paths) > 3 else "")
        if search:
            names = "Sammlung: " + filters.describe(*search)
        elif files is not None:
            names = label
        self.setWindowTitle(f"{names} – {APP_NAME}")

    def _show_progress(self, token):
        if token == self._load_token and self._load_worker is not None:
            self.progress.setRange(0, 0)
            self.progress.show()
            self.lbl_progress.setText("Durchsuche …" if self._search else "Lese Tags …")
            self.lbl_progress.show()

    def _load_progress(self, done: int, total: int, token: int):
        if token != self._load_token:
            return
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        verb = "Durchsuche" if self._search else "Lese Tags"
        self.lbl_progress.setText(f"{verb} … {done:,} / {total:,}".replace(",", "."))

    def _loaded(self, recs: list, token: int):
        if token != self._load_token:
            return
        self._load_worker = None
        self.progress.hide()
        self.lbl_progress.hide()
        self.session.set_records(recs)
        self._update_empty_text()
        if self._search is not None:
            self.toast.show_message(f"{len(recs):,} Treffer in der Sammlung".replace(",", ".") if recs
                                    else "Keine passende Datei in der Sammlung")
            if recs:
                self.table.selectRow(0)
        elif self._result_files is not None:
            if recs:
                self.table.selectRow(0)
        elif recs and self._after_load_select_all:
            self.table.selectAll()
        elif recs:
            self.table.selectRow(0)
        errors = [(r["path"], r["error"]) for r in recs if r.get("error")]
        if errors:
            self.toast.show_message(f"{len(errors)} Datei(en) konnten nicht gelesen werden (roter Punkt)")

    def _update_empty_text(self):
        self._update_search_button()
        if self._result_files is not None:
            self.table.set_empty_text("Keine Dateien", "Die Dateien gibt es nicht mehr – links einen Ordner wählen")
        elif self._search is not None:
            self.table.set_empty_text("Nichts gefunden",
                                      "In der ganzen Sammlung passt keine Datei zu: " + filters.describe(*self._search))
        elif not self.tree.root_path:
            self.table.set_empty_text("Öffne deine Musik-Sammlung",
                                      "Oben auf „Sammlung öffnen“ klicken, Strg+O drücken oder einen Ordner ins Fenster ziehen")
        elif not self._loaded_dirs:
            self.table.set_empty_text("Wähle links einen Ordner",
                                      "Strg+Klick wählt mehrere · „Unterordner“ lädt alles darunter mit")
        else:
            hint = "" if self.settings.recursive else "Tipp: Mit „Unterordner“ (Strg+R) werden auch Unterordner geladen"
            self.table.set_empty_text("Hier liegen keine Musikdateien", hint)

    # ==================================================================
    # Auswahl / Status
    # ==================================================================
    def _sel_timer_start(self):
        self._sel_timer.start()

    def _on_table_selection(self):
        self.panel.set_items(self.table.selected_items())
        self._update_status()

    def _on_items_changed(self, items: list):
        panel_ids = {id(i) for i in self.panel.items}
        if any(id(i) in panel_ids for i in items):
            self.panel.refresh()

    def _update_status(self):
        n = len(self.session.items)
        sel = len(self.panel.items)
        mod = self.session.modified_count()
        shown = self.table.model_.rowCount()
        if not n:
            count = "Keine Dateien geladen"
        elif self.table.model_.is_filtered:
            count = f"{shown:,} von {n:,} Dateien (gefiltert)"
        else:
            count = f"{n:,} Dateien"
        if self._search is not None and n:
            count = "Sammlung: " + count
        elif self._result_files is not None and n:
            count = f"{self._result_label}: {count}"
        self.lbl_count.setText(count.replace(",", "."))
        self.lbl_count.adjustSize()
        self.lbl_sel.setText(f"{sel:,} ausgewählt".replace(",", ".") if sel else "")
        self.lbl_mod.setStyleSheet(f"color: {theme.tok('modified')}; font-weight: 600;")
        self.lbl_mod.setText(f"{mod:,} ungespeichert".replace(",", ".") if mod else "")
        self.lbl_mod.adjustSize()
        self.btn_save.setProperty("kind", "primary" if mod else "")
        self.btn_save.style().unpolish(self.btn_save)
        self.btn_save.style().polish(self.btn_save)
        self.btn_save.setText(f"Speichern ({mod:,})".replace(",", ".") if mod else "Speichern")
        self.btn_save.updateGeometry()
        self._icon_refresh_one(self.btn_save, "floppy-disk", "accent_text" if mod else "text")
        step = self.session.undo.peek()
        self.btn_undo.setEnabled(step is not None)
        self.btn_undo.setToolTip(f"Rückgängig: {step.label} (Strg+Z)" if step else "Nichts rückgängig zu machen")

    def _icon_refresh_one(self, target, name, role):
        for i, (t, n, r) in enumerate(self._icon_targets):
            if t is target:
                self._icon_targets[i] = (t, name, role)
        target.setIcon(icons.icon(name, role))

    def _focus_title(self):
        fe = self.panel.fields["title"]
        if fe.isEnabled():
            fe.setFocus()
            fe.selectAll()

    # ==================================================================
    # Speichern
    # ==================================================================
    def save(self, then=None, quiet: bool = False):
        self.panel.commit()
        if self._save_worker is not None:
            return
        jobs = self.session.save_jobs()
        if not jobs:
            if not quiet:
                self.toast.show_message("Nichts zu speichern")
            if then:
                then()
            return
        self._run_save(jobs, f"{len(jobs)} Datei(en) gespeichert", then, record_undo=True)

    def _run_save(self, jobs, label, then=None, record_undo=True):
        w = SaveWorker(jobs, self.settings.write_options(), self.cache, capture_undo=record_undo, parent=self)
        self._save_worker = w
        self.table.setEnabled(False)
        self.panel.setEnabled(False)
        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self.progress.show()
        self.lbl_progress.setText("Speichere …")
        self.lbl_progress.show()
        w.progress.connect(lambda d, t: (self.progress.setValue(d),
                                         self.lbl_progress.setText(f"Speichere … {d} / {t}")))

        def finished(results):
            self._save_worker = None
            self.progress.hide()
            self.lbl_progress.hide()
            self.table.setEnabled(True)
            self.panel.setEnabled(True)
            ok, errors = self.session.finish_save(results, label, record_undo=record_undo)
            self.panel.refresh()
            if errors:
                self.toast.show_message(f"{ok} gespeichert, {len(errors)} mit Fehler")
                ErrorListDialog("Nicht alles gespeichert", errors, self).exec()
                return
            self.toast.show_message(label if record_undo else f"Rückgängig gemacht: {ok} Datei(en)")
            if then:
                then()

        w.done.connect(finished)
        w.finished.connect(w.deleteLater)
        w.start()

    def save_and_next(self):
        if self.is_result_list:            # Suchergebnis: kein „nächster Ordner“
            self.save()
            return
        self.save(then=self._mark_and_advance, quiet=True)

    def _mark_and_advance(self):
        loaded = self.session.dirs()
        position = loaded or self._loaded_dirs or self.tree.selected_paths()
        if loaded:
            self.tree.mark(loaded, FOLDER_DONE)
        nxt = self.tree.neighbour_album(position, +1, only_open=True)
        if nxt is None:
            nxt = self.tree.neighbour_album([], +1, only_open=True)  # von vorn
        if nxt is None:
            self.toast.show_message("Geschafft – alle Alben sind als fertig markiert")
            return
        self.tree.select_paths([nxt])
        if loaded:
            self.toast.show_message(f"✓ {os.path.basename(loaded[0])} fertig – weiter mit {os.path.basename(nxt)}")

    def previous_folder(self):
        position = self.session.dirs() or self._loaded_dirs
        prev = self.tree.neighbour_album(position, -1, only_open=False)
        if prev:
            self.tree.select_paths([prev])

    def toggle_done(self):
        paths = self.session.dirs() or self.tree.selected_paths()
        if not paths:
            return
        albums = self.tree.albums_in(paths)
        all_done = albums and all(self.tree.is_done(p) for p in albums)
        self.tree.mark(paths, FOLDER_OPEN if all_done else FOLDER_DONE)
        self.toast.show_message("Als offen markiert" if all_done else "Als fertig markiert")

    def _mark_tree(self, status):
        paths = self.tree.selected_paths()
        if paths:
            self.tree.mark(paths, status)

    # ==================================================================
    # Werkzeuge (Phase 2)
    # ==================================================================
    def tool_items(self):
        """Auswahl – oder, wenn nichts ausgewählt ist, alle Dateien der Liste."""
        items = self.table.selected_items()
        if items:
            n = len(items)
            return items, f"Gilt für {n:,} ausgewählte Datei{'en' if n != 1 else ''}".replace(",", ".")
        items = self.table.model_.visible_items()
        return items, f"Gilt für alle {len(items):,} Dateien in der Liste".replace(",", ".")

    def open_tool(self, feature_id: str):
        if self._save_worker is not None:
            return
        self.panel.commit()
        items, scope = self.tool_items()
        if not items:
            self.toast.show_message("Erst links einen Ordner öffnen")
            return
        TOOL_DIALOGS[feature_id](self, items, scope).exec()

    def open_online(self, feature_id: str):
        if self._save_worker is not None:
            return
        self.panel.commit()
        items, scope = self.tool_items()
        if not items:
            self.toast.show_message("Erst links einen Ordner öffnen")
            return
        ONLINE_DIALOGS[feature_id](self, items, scope).exec()

    def open_extra(self, feature_id: str):
        if self._save_worker is not None:
            return
        self.panel.commit()
        items, scope = self.tool_items()
        if not items and not (feature_id == "duplicates" and self.tree.root_path):
            self.toast.show_message("Erst links einen Ordner öffnen")
            return
        EXTRA_DIALOGS[feature_id](self, items, scope).exec()

    def run_rename(self, pairs, label: str, record_undo: bool = True):
        if not pairs or self._save_worker is not None:
            return
        w = RenameWorker(pairs, self.cache, self)
        self._save_worker = w
        self.table.setEnabled(False)
        self.panel.setEnabled(False)
        self.lbl_progress.setText("Benenne um …")
        self.lbl_progress.show()

        def finished(results):
            self._save_worker = None
            self.lbl_progress.hide()
            self.table.setEnabled(True)
            self.panel.setEnabled(True)
            ok, errors = self.session.finish_rename(results, label, record_undo=record_undo)
            self.panel.refresh()
            moved = [(r["old"].rstrip("/"), r["new"].rstrip("/")) for r in results
                     if not r["error"] and os.path.isdir(r["new"])]
            if moved:
                self._folders_renamed(moved)
            if errors:
                self.toast.show_message(f"{ok} umbenannt, {len(errors)} mit Fehler")
                ErrorListDialog("Nicht alles umbenannt", errors, self).exec()
            else:
                self.toast.show_message(label if record_undo else f"Zurückbenannt: {ok} Datei(en)")

        w.done.connect(finished)
        w.finished.connect(w.deleteLater)
        w.start()

    def _folders_renamed(self, moved: list[tuple[str, str]]):
        """Nach Ordner-Umbenennen: geladene Ordner, Sammlung und Baum auf die neuen Pfade setzen."""
        def remap(path: str) -> str:
            for old, new in moved:
                if path == old:
                    return new
                if path.startswith(old + "/"):
                    return new + path[len(old):]
            return path

        self._loaded_dirs = [remap(p) for p in self._loaded_dirs]
        root = remap(self.tree.root_path) if self.tree.root_path else ""
        if root:
            self.settings.last_root = root
            self.tree.set_root(root, list(self._loaded_dirs))

    def _table_menu(self, pos):
        items = self.table.selected_items()
        if not items:
            return
        m = QMenu(self)
        for group in ("tools", "online"):
            for f in features.by_group(group):
                if f.ready:
                    a = m.addAction(icons.icon(f.icon, "muted"),
                                    f"{f.title}\t{f.shortcut.replace('Ctrl', 'Strg')}" if f.shortcut else f.title)
                    a.triggered.connect(lambda _=False, fid=f.id: self.run_feature(fid))
            m.addSeparator()
        m.addSeparator()
        modified = [it for it in items if it.is_modified()]
        if modified:
            m.addAction(icons.icon("arrow-counter-clockwise", "muted"),
                        f"Änderungen verwerfen ({len(modified)})", lambda: self.session.revert(modified))
        if len({it.dir for it in items}) == 1:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            m.addAction(icons.icon("folder-open", "muted"), "Ordner im Dateimanager öffnen",
                        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(items[0].dir)))
        m.exec(self.table.viewport().mapToGlobal(pos))

    # ==================================================================
    # Rückgängig
    # ==================================================================
    def undo(self):
        if self._save_worker is not None:
            return
        step = self.session.undo.peek()
        if step is None:
            self.toast.show_message("Nichts rückgängig zu machen")
            return
        if isinstance(step, EditStep):
            self.session.undo.pop()
            self.session.undo_edit(step)
            self.panel.refresh()
            self.toast.show_message(f"Rückgängig: {step.label}")
            return
        if isinstance(step, SaveStep):
            n = len(step.entries)
            r = QMessageBox.question(
                self, "Speichern rückgängig machen?",
                f"„{step.label}“ rückgängig machen?\n\nDie vorherigen Werte von {n} Datei(en) "
                f"werden zurück in die Dateien geschrieben.")
            if r != QMessageBox.StandardButton.Yes:
                return
            self.session.undo.pop()
            self._run_save(self.session.undo_jobs(step), step.label, record_undo=False)
            return
        if isinstance(step, RenameStep):
            n = len(step.pairs)
            r = QMessageBox.question(
                self, "Umbenennen rückgängig machen?",
                f"„{step.label}“ rückgängig machen?\n\n{n} Datei(en) bekommen wieder ihren alten Namen.")
            if r != QMessageBox.StandardButton.Yes:
                return
            self.session.undo.pop()
            self.run_rename([(new, old) for old, new in reversed(step.pairs)], step.label, record_undo=False)

    # ==================================================================
    # Ungespeicherte Änderungen
    # ==================================================================
    def _confirm_unsaved(self) -> bool:
        """True = weitermachen (gespeichert oder verworfen), False = abbrechen."""
        self.panel.commit()
        mod = self.session.modified_count()
        if not mod:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Ungespeicherte Änderungen")
        box.setText(f"{mod} Datei(en) haben ungespeicherte Änderungen.")
        box.setInformativeText("Jetzt speichern?")
        b_save = box.addButton("Speichern", QMessageBox.ButtonRole.AcceptRole)
        b_drop = box.addButton("Verwerfen", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        b_save.setProperty("kind", "primary")
        box.setDefaultButton(b_save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is b_save:
            self._save_blocking()
            return self.session.modified_count() == 0
        if clicked is b_drop:
            self.session.revert()
            return True
        return False

    def _save_blocking(self):
        """Speichern und warten (für Ordnerwechsel / Schließen)."""
        from PySide6.QtCore import QEventLoop
        loop = QEventLoop()
        self.save(then=loop.quit, quiet=True)
        if self._save_worker is not None:
            self._save_worker.done.connect(lambda *_: QTimer.singleShot(0, loop.quit))
            loop.exec()

    # ==================================================================
    # Schnellfilter (Phase 4)
    # ==================================================================
    def _quick_filters_changed(self):
        self.table.model_.set_quick_filters(self.filterbar.active())
        self._update_search_button()
        self._update_status()

    def _update_filter_counts(self):
        if self.filterbar.isVisible():
            self.filterbar.set_counts(filters.count_items(self.session.items) if self.session.items else {})

    def _update_search_button(self):
        keys = {k for k in self.filterbar.active() if filters.FILTER_BY_KEY[k].collection}
        ok = bool(self.tree.root_path) and bool(keys or self.filter.text().strip())
        self.filterbar.set_search_enabled(ok)

    def toggle_filter_bar(self):
        on = not self.filterbar.isVisible()
        self.filterbar.setVisible(on)
        self.settings.show_filter_bar = on
        if on:
            self._update_filter_counts()
        else:
            self.filterbar.clear()
        self.toast.show_message("Schnellfilter eingeblendet" if on else "Schnellfilter ausgeblendet")

    def export_list(self):
        if not self.session.items:
            self.toast.show_message("Erst links einen Ordner öffnen")
            return
        from .export import ExportDialog
        ExportDialog(self).exec()

    def search_collection(self, search: tuple | None = None):
        """Gewählte Schnellfilter + Suchtext in der ganzen Sammlung (Zwischenspeicher + neue Dateien)."""
        root = self.tree.root_path
        if not root:
            self.toast.show_message("Erst eine Sammlung öffnen")
            return
        if search is None:
            if self.filterbar.chips["modified"].isChecked():
                self.filterbar.chips["modified"].setChecked(False)   # gibt es in der Sammlung nicht
            keys = {k for k in self.filterbar.active() if filters.FILTER_BY_KEY[k].collection}
            search = (keys, self.filter.text().strip())
        keys, text = search
        if not keys and not text:
            self.toast.show_message("Erst einen Schnellfilter wählen oder einen Suchtext eingeben")
            return
        if not self._confirm_unsaved():
            return
        words = filters.text_words(text)

        def keep(rec, keys=frozenset(keys), words=words):
            return (filters.record_passes(rec, keys)
                    and filters.text_passes(words, os.path.basename(rec["path"]), rec.get("tags") or {}))

        self.tree.select_paths([], emit=False)
        self._load([root], keep=keep, search=(set(keys), text))

    # ==================================================================
    # Spätere Phasen
    # ==================================================================
    def run_feature(self, feature_id: str):
        if feature_id in TOOL_DIALOGS:
            self.open_tool(feature_id)
            return
        if feature_id in ONLINE_DIALOGS:
            self.open_online(feature_id)
            return
        if feature_id in EXTRA_DIALOGS:
            self.open_extra(feature_id)
            return
        handler = FEATURE_HANDLERS.get(feature_id)
        if handler:
            getattr(self, handler)()
            return
        ComingSoonDialog(features.get(feature_id), self).exec()

    # ==================================================================
    # Einstellungen / Theme
    # ==================================================================
    def open_settings(self):
        old_theme = self.settings.theme
        if SettingsDialog(self.settings, self).exec():
            if self.settings.theme != old_theme:
                self.apply_theme(self.settings.theme)
            self._after_load_select_all = self.settings.select_all_on_load
            self.panel._update_cover_menu_texts()
            self.panel.refresh()
            self.toast.show_message("Einstellungen gespeichert")

    def toggle_theme(self):
        self.apply_theme("light" if theme.current() == "dark" else "dark")
        self.settings.theme = theme.current()

    def apply_theme(self, name: str):
        theme.apply(QApplication.instance(), name)
        for target, icon_name, role in self._icon_targets:
            target.setIcon(icons.icon(icon_name, role))
        self._sep.setStyleSheet(f"background: {theme.tok('line')};")
        self._presenter_label.setText(
            f'präsentiert von <a href="{PRESENTER_URL}" style="text-decoration:none; '
            f'color:{theme.tok("muted")}; font-weight:600">{PRESENTER}</a>')
        self.panel.refresh_icons()
        self.filterbar.refresh_icons()
        self.tree.view.viewport().update()
        self.table.viewport().update()
        self._update_status()

    def _clear_cache(self):
        self.cache.clear_files()
        self.toast.show_message("Zwischenspeicher geleert – Tags werden neu gelesen")

    # ==================================================================
    # Fensterzustand
    # ==================================================================
    def _restore_state(self):
        s = self.settings
        self.start_maximized = False
        if s.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(s.window_geometry.encode()))
        else:
            self._fit_to_screen()
        if s.splitter_state:
            self.splitter.restoreState(QByteArray.fromBase64(s.splitter_state.encode()))
        self.table.apply_column_settings(s.hidden_columns, s.column_widths)
        if s.last_root and os.path.isdir(s.last_root):
            self.tree.set_root(s.last_root, [p for p in s.last_selection if os.path.isdir(p)])

    def _fit_to_screen(self):
        """Erster Start: Fenster passend zum Bildschirm – kleine Bildschirme maximiert."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        if avail.width() < 1440 or avail.height() < 900:
            self.start_maximized = True
            self.resize(min(1360, avail.width()), min(820, avail.height()))
            return
        w, h = min(1440, int(avail.width() * 0.9)), min(900, int(avail.height() * 0.9))
        self.resize(w, h)
        self.move(avail.left() + (avail.width() - w) // 2, avail.top() + (avail.height() - h) // 2)

    # --- Startmenü (nur im AppImage) ------------------------------------------
    @staticmethod
    def _desktop_entry_path() -> str:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        return os.path.join(base, "applications", "bub3tagmusic.desktop")

    def _toggle_desktop_entry(self):
        path = self._desktop_entry_path()
        base = os.path.dirname(os.path.dirname(path))
        icon = os.path.join(base, "icons", "hicolor", "scalable", "apps", "bub3tagmusic.svg")
        if os.path.exists(path):
            for p in (path, icon):
                try:
                    os.remove(p)
                except OSError:
                    pass
            self.toast.show_message("Aus dem Startmenü entfernt")
        else:
            appimage = os.environ.get("APPIMAGE", "")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            os.makedirs(os.path.dirname(icon), exist_ok=True)
            import shutil
            shutil.copyfile(os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources",
                                         "bub3tagmusic.svg"), icon)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(
                    "[Desktop Entry]\nType=Application\nName=BuB3TAGMUSIC\nGenericName=Musik-Tagger\n"
                    "Comment=Musik-Tags und Cover bearbeiten – präsentiert von www.BAUENUNDBOOTEN.de\n"
                    f'Exec="{appimage}" %f\nIcon=bub3tagmusic\nTerminal=false\n'
                    "Categories=AudioVideo;Audio;Qt;\nKeywords=tag;tagger;mp3;flac;cover;id3;musik;\n"
                    "StartupWMClass=bub3tagmusic\n")
            self.toast.show_message("Im Startmenü eingetragen – bitte die AppImage-Datei nicht mehr verschieben")
        self._update_desktop_action()

    def _update_desktop_action(self):
        if self._act_desktop is not None:
            self._act_desktop.setText("Aus dem Startmenü entfernen" if os.path.exists(self._desktop_entry_path())
                                      else "Ins Startmenü eintragen")

    def _store_state(self):
        s = self.settings
        s.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        s.splitter_state = bytes(self.splitter.saveState().toBase64()).decode()
        s.hidden_columns, s.column_widths = self.table.column_settings()
        s.last_root = self.tree.root_path or s.last_root
        s.last_selection = self._loaded_dirs[:20]
        s.theme = theme.current()
        s.save()

    def closeEvent(self, e: QCloseEvent):
        if not self._confirm_unsaved():
            e.ignore()
            return
        self._store_state()
        if self._load_worker is not None:
            self._load_worker.cancel()
            self._load_worker.wait(2000)
        e.accept()

    # ==================================================================
    # Ordner ins Fenster ziehen = Sammlung öffnen
    # ==================================================================
    def dragEnterEvent(self, e):
        urls = e.mimeData().urls() if e.mimeData().hasUrls() else []
        if urls and urls[0].isLocalFile() and os.path.isdir(urls[0].toLocalFile()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        path = e.mimeData().urls()[0].toLocalFile()
        if os.path.isdir(path) and self._confirm_unsaved():
            self.session.clear()
            self._loaded_dirs = []
            self.tree.set_root(path, [])
            self.settings.last_root = path
            self._update_empty_text()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast.show_message(self.toast.text())
