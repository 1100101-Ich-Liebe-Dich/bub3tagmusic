"""Dialoge: Einstellungen, Tastenkürzel, Über, Fehlerliste, "Kommt bald" + Toast."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QPushButton, QRadioButton, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)

from .. import APP_NAME, APP_PHASE, APP_VERSION, PRESENTER, PRESENTER_URL
from ..core.settings import Settings
from ..features import Feature
from . import icons, theme


def _muted(text: str, role: str = "muted", wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


# ======================================================================
class ComingSoonDialog(QDialog):
    def __init__(self, feature: Feature, parent=None):
        super().__init__(parent)
        self.setWindowTitle(feature.title.replace(" …", ""))
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.icon(feature.icon, "accent").pixmap(28, 28))
        head.addWidget(ic)
        title = QLabel(feature.title.replace(" …", ""))
        title.setProperty("role", "heading")
        head.addWidget(title, 1)
        lay.addLayout(head)
        badge = QLabel(f"Kommt in Phase {feature.phase}")
        badge.setStyleSheet(f"color: {theme.tok('accent')}; font-weight: 600;")
        lay.addWidget(badge)
        lay.addWidget(_muted(feature.description))
        if feature.shortcut:
            lay.addWidget(_muted(f"Geplantes Tastenkürzel: {feature.shortcut.replace('Ctrl', 'Strg')}", "faint"))
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)
        lay.addSpacing(6)
        lay.addWidget(btns)


# ======================================================================
class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 14)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # --- Tags ---------------------------------------------------------------------
        t = QWidget()
        f = QFormLayout(t)
        f.setContentsMargins(18, 18, 18, 18)
        f.setVerticalSpacing(12)
        self.id3_23 = QRadioButton("ID3v2.3 – läuft überall (empfohlen)")
        self.id3_24 = QRadioButton("ID3v2.4 – neuer, aber manche Autoradios kennen es nicht")
        grp = QButtonGroup(self)
        grp.addButton(self.id3_23)
        grp.addButton(self.id3_24)
        (self.id3_23 if settings.id3_version == 3 else self.id3_24).setChecked(True)
        box = QVBoxLayout()
        box.addWidget(self.id3_23)
        box.addWidget(self.id3_24)
        f.addRow("MP3-Tags", box)
        self.id3v1 = QComboBox()
        self.id3v1.addItem("Vorhandene aktualisieren", "keep")
        self.id3v1.addItem("Entfernen", "remove")
        self.id3v1.addItem("Immer schreiben", "write")
        self.id3v1.setCurrentIndex(max(0, self.id3v1.findData(settings.id3v1)))
        f.addRow("Alte ID3v1-Tags", self.id3v1)
        self.keep_mtime = QCheckBox("Änderungsdatum der Dateien beibehalten")
        self.keep_mtime.setChecked(settings.keep_mtime)
        f.addRow("", self.keep_mtime)
        tabs.addTab(t, "Tags")

        # --- Cover --------------------------------------------------------------------
        c = QWidget()
        f = QFormLayout(c)
        f.setContentsMargins(18, 18, 18, 18)
        f.setVerticalSpacing(12)
        self.album_name = QLineEdit(settings.album_cover_name)
        f.addRow("Albumcover-Datei", self.album_name)
        self.artist_name = QLineEdit(settings.artist_image_name)
        f.addRow("Künstlerbild-Datei", self.artist_name)
        self.candidates = QLineEdit(", ".join(settings.folder_image_candidates))
        self.candidates.setToolTip("Diese Dateien werden bei „Aus Ordner“ gesucht – in dieser Reihenfolge")
        f.addRow("Ordnerbilder suchen", self.candidates)
        self.resize = QCheckBox("Beim Einbetten verkleinern auf")
        self.resize.setChecked(settings.embed_resize)
        self.size = QSpinBox()
        self.size.setRange(200, 3000)
        self.size.setSingleStep(100)
        self.size.setSuffix(" px")
        self.size.setValue(settings.embed_max_size)
        row = QHBoxLayout()
        row.addWidget(self.resize)
        row.addWidget(self.size)
        row.addStretch(1)
        f.addRow("Eingebettetes Cover", row)
        self.quality = QSpinBox()
        self.quality.setRange(60, 100)
        self.quality.setValue(settings.jpeg_quality)
        f.addRow("JPEG-Qualität", self.quality)
        f.addRow("", _muted("Die Datei im Ordner (cover.jpg) wird immer in voller Größe gespeichert.", "faint"))
        tabs.addTab(c, "Cover")

        # --- Online -------------------------------------------------------------------
        o = QWidget()
        f = QFormLayout(o)
        f.setContentsMargins(18, 18, 18, 18)
        f.setVerticalSpacing(12)
        f.addRow(_muted("MusicBrainz, Cover-Suche (Cover Art Archive, iTunes, Deezer) und Künstlerbilder "
                        "brauchen keine Zugangsdaten. Nur Discogs braucht einen kostenlosen Token.", "faint"))
        self.discogs = QLineEdit(settings.discogs_token)
        self.discogs.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.discogs.setPlaceholderText("persönlicher Token von discogs.com/settings/developers")
        f.addRow("Discogs-Token", self.discogs)
        self.mb = QLineEdit(settings.musicbrainz_contact)
        self.mb.setPlaceholderText("E-Mail oder Website (MusicBrainz bittet darum)")
        f.addRow("MusicBrainz-Kontakt", self.mb)
        self.acoustid = QLineEdit(settings.acoustid_key)
        self.acoustid.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        f.addRow("AcoustID-Key", self.acoustid)
        tabs.addTab(o, "Online")

        # --- Darstellung --------------------------------------------------------------
        d = QWidget()
        f = QFormLayout(d)
        f.setContentsMargins(18, 18, 18, 18)
        self.theme_box = QComboBox()
        for key in theme.THEME_INFO:
            self.theme_box.addItem(theme.label(key), key)
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(settings.theme)))
        f.addRow("Theme", self.theme_box)
        self.select_all = QCheckBox("Nach dem Öffnen eines Ordners alle Dateien auswählen")
        self.select_all.setChecked(settings.select_all_on_load)
        self.select_all.setToolTip("Praktisch zum albumweisen Taggen: Album, Interpret, Jahr … gleich für alle setzen")
        f.addRow("Arbeitsweise", self.select_all)
        tabs.addTab(d, "Darstellung")

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        btns.button(QDialogButtonBox.StandardButton.Save).setProperty("kind", "primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _save(self):
        s = self.s
        s.id3_version = 3 if self.id3_23.isChecked() else 4
        s.id3v1 = self.id3v1.currentData()
        s.keep_mtime = self.keep_mtime.isChecked()
        s.album_cover_name = self.album_name.text().strip() or "cover.jpg"
        s.artist_image_name = self.artist_name.text().strip() or "folder.jpg"
        cands = [x.strip() for x in self.candidates.text().split(",") if x.strip()]
        s.folder_image_candidates = cands or Settings().folder_image_candidates
        s.embed_resize = self.resize.isChecked()
        s.embed_max_size = self.size.value()
        s.jpeg_quality = self.quality.value()
        s.discogs_token = self.discogs.text().strip()
        s.musicbrainz_contact = self.mb.text().strip()
        s.acoustid_key = self.acoustid.text().strip()
        s.theme = self.theme_box.currentData()
        s.select_all_on_load = self.select_all.isChecked()
        s.save()
        self.accept()


# ======================================================================
SHORTCUTS = (
    ("Arbeiten", (
        ("Strg+→", "Speichern, Ordner abhaken, nächster offener Ordner"),
        ("Strg+←", "Vorheriger Ordner"),
        ("Strg+S", "Speichern"),
        ("Strg+Z", "Rückgängig (auch schon Gespeichertes)"),
        ("Strg+D", "Ordner als fertig / offen markieren"),
        ("Strg+R", "Unterordner mitladen an/aus"),
    )),
    ("Auswahl & Bearbeiten", (
        ("Strg+A", "Alle Dateien in der Liste auswählen"),
        ("Strg+E", "Zum Feld Titel springen"),
        ("F2", "Zelle in der Liste bearbeiten"),
        ("Enter", "Feld übernehmen"),
        ("Esc", "Getipptes verwerfen"),
        ("Strg+Shift+V", "Bild aus Zwischenablage als Cover"),
    )),
    ("Werkzeuge", (
        ("Alt+1", "Tags aus Dateiname"),
        ("Alt+2", "Dateinamen aus Tags (umbenennen)"),
        ("Alt+3", "Tracks nummerieren"),
        ("Alt+4", "Groß-/Kleinschreibung"),
        ("Alt+5", "Suchen & Ersetzen"),
        ("Alt+6", "Ordner umbenennen"),
        ("Alt+7", "Aktionen (mehrere Schritte auf einmal)"),
    )),
    ("Ansicht", (
        ("Strg+O", "Sammlung öffnen"),
        ("Strg+F", "Liste filtern"),
        ("F5", "Ordner neu einlesen"),
        ("Strg+L", "Album online suchen (MusicBrainz / Discogs)"),
        ("Strg+K", "Cover online suchen"),
        ("Strg+J", "Künstlerbild online suchen"),
        ("Strg+Shift+L", "Unbekannte Dateien erkennen (AcoustID)"),
        ("Strg+Shift+E", "Liste exportieren (CSV / HTML)"),
        ("Strg+,", "Einstellungen"),
        ("F1", "Diese Übersicht"),
    )),
)


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tastenkürzel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(14)
        g = QGridLayout()
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(6)
        g.setColumnStretch(1, 1)
        row = 0
        for group, rows in SHORTCUTS:
            h = QLabel(group)
            h.setProperty("role", "section")
            if row:
                g.setRowMinimumHeight(row, 10)
                row += 1
            g.addWidget(h, row, 0, 1, 2)
            row += 1
            for keys, what in rows:
                k = QLabel(keys)
                k.setStyleSheet(f"background: {theme.tok('raised')}; border: 1px solid {theme.tok('line')};"
                                f"border-radius: 5px; padding: 2px 7px; font-weight: 600;")
                g.addWidget(k, row, 0, Qt.AlignmentFlag.AlignLeft)
                g.addWidget(QLabel(what), row, 1)
                row += 1
        lay.addLayout(g)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.button(QDialogButtonBox.StandardButton.Close).setText("Schließen")
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)


# ======================================================================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Über {APP_NAME}")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 18)
        lay.setSpacing(6)
        mark = QLabel(APP_NAME)
        mark.setObjectName("AboutMark")
        lay.addWidget(mark)
        lay.addWidget(_muted(f"Version {APP_VERSION}" + (f"  ·  Phase {APP_PHASE}" if APP_PHASE < 5 else "")))
        lay.addSpacing(8)
        lay.addWidget(QLabel("Moderner, schneller Musik-Tagger für Linux."))
        link = QLabel(f'präsentiert von <a href="{PRESENTER_URL}" style="color:{theme.tok("accent")};'
                      f'text-decoration:none; font-weight:600">{PRESENTER}</a>')
        link.setOpenExternalLinks(True)
        lay.addWidget(link)
        lay.addSpacing(10)
        lay.addWidget(_muted("Gebaut mit Python, Qt 6 (PySide6), mutagen und Pillow. "
                             "Icons: Phosphor. Schriften: Inter und Big Shoulders Stencil (SIL OFL).", "faint"))
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.button(QDialogButtonBox.StandardButton.Close).setText("Schließen")
        btns.rejected.connect(self.reject)
        lay.addSpacing(8)
        lay.addWidget(btns)


# ======================================================================
class ErrorListDialog(QDialog):
    def __init__(self, title: str, errors: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(620, 360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        h = QLabel(f"{len(errors)} Datei(en) konnten nicht verarbeitet werden")
        h.setProperty("role", "heading")
        lay.addWidget(h)
        lay.addWidget(_muted("Alle anderen Dateien wurden normal verarbeitet.", "faint"))
        lst = QListWidget()
        for path, msg in errors:
            lst.addItem(f"{path}\n    {msg}")
        lay.addWidget(lst, 1)
        row = QHBoxLayout()
        copy = QPushButton("Liste kopieren")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(
            "\n".join(f"{p}\t{m}" for p, m in errors)))
        row.addWidget(copy)
        row.addStretch(1)
        close = QPushButton("Schließen")
        close.setProperty("kind", "primary")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)


# ======================================================================
class Toast(QLabel):
    """Kurze Bestätigung unten in der Mitte, blendet sich selbst aus."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setFont(theme.ui_font(13, QFont.Weight.Medium))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self._fade_out)
        self._fading = False
        self._anim.finished.connect(lambda: self._fading and self.hide())
        self.hide()

    def show_message(self, text: str, ms: int = 2600):
        self.setText(text)
        self.adjustSize()
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 22)
        self.raise_()
        self._anim.stop()
        self._fading = False
        self._anim.setStartValue(self._fx.opacity() if self.isVisible() else 0.0)
        self._anim.setEndValue(1.0)
        self.show()
        self._anim.start()
        self._timer.start(ms)

    def _fade_out(self):
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._fading = True
        self._anim.start()


def open_url(url: str):
    QDesktopServices.openUrl(QUrl(url))
