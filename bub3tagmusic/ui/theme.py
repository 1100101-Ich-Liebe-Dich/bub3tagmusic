"""Farben, Schrift und Stylesheet.

Zwei Themes:
  * "dark"  – Nachtwache: tiefes Hafenblau, Bojen-Orange als Akzent
  * "light" – Seekarte:   helles Kartenpapier, gleiche Akzentfarbe

Alle Farben stehen nur hier. Widgets holen sie über `tok("name")`.
"""

from __future__ import annotations

import os

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "fonts")
UI_FONT = "Inter"
WORDMARK_FONT = "Big Shoulders Stencil ExtraBold"

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#121B24",
        "panel": "#172230",
        "raised": "#1E2B39",
        "sunken": "#101820",
        "input": "#0F171F",
        "hover": "#223243",
        "line": "#263544",
        "line_soft": "#1A2633",
        "line_strong": "#36495C",
        "text": "#E4EBF1",
        "muted": "#8A9BAB",
        "faint": "#5A6B7B",
        "accent": "#FF8A2A",
        "accent_hover": "#FF9D4D",
        "accent_text": "#1C1004",
        "accent_soft": "#3A2A1D",
        "selection": "#24384D",
        "selection_line": "#FF8A2A",
        "done": "#3FCB8D",
        "modified": "#F4C453",
        "danger": "#FF6B6B",
        "scroll": "#2E3F51",
    },
    "light": {
        "bg": "#E8EDF1",
        "panel": "#F5F8FA",
        "raised": "#FFFFFF",
        "sunken": "#FFFFFF",
        "input": "#FFFFFF",
        "hover": "#E5ECF2",
        "line": "#D4DDE5",
        "line_soft": "#EBF0F4",
        "line_strong": "#B9C6D2",
        "text": "#13212C",
        "muted": "#566879",
        "faint": "#8C9AA7",
        "accent": "#E26C0B",
        "accent_hover": "#F07B19",
        "accent_text": "#FFFFFF",
        "accent_soft": "#FBE6D3",
        "selection": "#DCE8F3",
        "selection_line": "#E26C0B",
        "done": "#1C9A62",
        "modified": "#B97F00",
        "danger": "#D33A3A",
        "scroll": "#C3CFDA",
    },
}

_current = "dark"


def current() -> str:
    return _current


def tok(name: str) -> str:
    return THEMES[_current][name]


def qcolor(name: str) -> QColor:
    return QColor(tok(name))


def load_fonts() -> None:
    if not os.path.isdir(FONT_DIR):
        return
    for fn in sorted(os.listdir(FONT_DIR)):
        if fn.lower().endswith((".ttf", ".otf")):
            QFontDatabase.addApplicationFont(os.path.join(FONT_DIR, fn))


def ui_font(size_px: int = 13, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(UI_FONT)
    f.setPixelSize(size_px)
    f.setWeight(weight)
    return f


def wordmark_font(size_px: int = 26) -> QFont:
    f = QFont(WORDMARK_FONT)
    f.setPixelSize(size_px)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
    return f


def _arrow_files(t: dict[str, str], name: str) -> dict[str, str]:
    """Kleine Pfeil-Symbole für Auswahllisten und Zahlenfelder in Theme-Farbe.

    Sobald ein Stylesheet Comboboxen/Spinboxen gestaltet, zeichnet Qt die Pfeile
    nicht mehr selbst – deshalb liegen sie als SVG im Cache.
    """
    from ..core.settings import cache_dir
    folder = cache_dir() / "theme"
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    shapes = {"down": "M2 4 L6 8 L10 4", "up": "M2 8 L6 4 L10 8"}
    for key, d in shapes.items():
        for role in ("muted", "faint"):
            path = folder / f"chevron-{key}-{name}-{role}.svg"
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
                   f'<path d="{d}" fill="none" stroke="{t[role]}" stroke-width="1.6" '
                   f'stroke-linecap="round" stroke-linejoin="round"/></svg>')
            try:
                if not path.exists() or path.read_text() != svg:
                    path.write_text(svg)
            except OSError:
                pass
            out[f"{key}_{role}"] = path.as_posix()
    return out


def apply(app: QApplication, name: str) -> None:
    global _current
    _current = name if name in THEMES else "dark"
    t = dict(THEMES[_current])
    try:
        t.update({f"arrow_{k}": v for k, v in _arrow_files(t, _current).items()})
    except Exception:
        pass

    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["bg"],
        QPalette.ColorRole.WindowText: t["text"],
        QPalette.ColorRole.Base: t["input"],
        QPalette.ColorRole.AlternateBase: t["panel"],
        QPalette.ColorRole.Text: t["text"],
        QPalette.ColorRole.Button: t["raised"],
        QPalette.ColorRole.ButtonText: t["text"],
        QPalette.ColorRole.Highlight: t["accent"],
        QPalette.ColorRole.HighlightedText: t["accent_text"],
        QPalette.ColorRole.ToolTipBase: t["raised"],
        QPalette.ColorRole.ToolTipText: t["text"],
        QPalette.ColorRole.PlaceholderText: t["faint"],
        QPalette.ColorRole.Link: t["accent"],
        QPalette.ColorRole.Mid: t["line"],
        QPalette.ColorRole.Midlight: t["line_soft"],
        QPalette.ColorRole.Dark: t["line_strong"],
        QPalette.ColorRole.Light: t["raised"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["faint"]))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(t))


def stylesheet(t: dict[str, str]) -> str:
    return f"""
* {{ font-family: "{UI_FONT}"; font-size: 13px; }}
QMainWindow, QDialog {{ background: {t['bg']}; }}
QWidget {{ color: {t['text']}; }}
QLabel {{ background: transparent; }}
QLabel[role="muted"] {{ color: {t['muted']}; }}
QLabel[role="faint"] {{ color: {t['faint']}; font-size: 12px; }}
QLabel[role="heading"] {{ font-size: 15px; font-weight: 600; }}
QLabel[role="section"] {{ color: {t['muted']}; font-size: 12px; font-weight: 600; }}
QLabel[role="fieldlabel"] {{ color: {t['muted']}; font-size: 12px; }}
QLabel[role="link"] {{ color: {t['muted']}; font-size: 12px; }}
QLabel#Wordmark {{ font-family: "{WORDMARK_FONT}"; font-size: 30px; color: {t['text']}; letter-spacing: 0.5px; }}
QLabel#AboutMark {{ font-family: "{WORDMARK_FONT}"; font-size: 52px; color: {t['text']}; letter-spacing: 0.5px; }}
QLabel#CoverState {{ font-weight: 600; }}

#TopBar {{ background: {t['panel']}; border-bottom: 1px solid {t['line']}; }}
#Sidebar, #EditPanel, #EditPanelInner {{ background: {t['panel']}; }}
#SidebarHeader {{ background: {t['panel']}; border-bottom: 1px solid {t['line_soft']}; }}
#TableArea {{ background: {t['sunken']}; }}
#FilterBar {{ background: {t['sunken']}; border-bottom: 1px solid {t['line_soft']}; }}
#EditFooter {{ background: {t['panel']}; border-top: 1px solid {t['line']}; }}

QSplitter::handle {{ background: {t['line']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}

/* Ordnerbaum */
QTreeView {{ background: {t['panel']}; border: none; outline: 0; padding: 4px 6px; }}
QTreeView::item {{ height: 30px; border-radius: 6px; padding-left: 2px; }}
QTreeView::item:hover {{ background: {t['hover']}; }}
QTreeView::item:selected {{ background: {t['selection']}; color: {t['text']}; }}

/* Dateiliste */
QTableView {{
    background: {t['sunken']}; alternate-background-color: {t['sunken']};
    border: none; outline: 0; gridline-color: transparent;
    selection-background-color: {t['selection']}; selection-color: {t['text']};
}}
QTableView::item {{ padding: 0 8px; border-bottom: 1px solid {t['line_soft']}; }}
QTableView::item:selected {{ background: {t['selection']}; color: {t['text']}; }}
QTableView QLineEdit {{ border-radius: 0; padding: 0 6px; border: 1px solid {t['accent']}; }}
QHeaderView {{ background: {t['sunken']}; border: none; }}
QHeaderView::section {{
    background: {t['sunken']}; color: {t['muted']}; border: none;
    border-bottom: 1px solid {t['line']}; padding: 0 8px; height: 34px;
    font-size: 12px; font-weight: 600;
}}
QHeaderView::section:hover {{ color: {t['text']}; }}
QTableCornerButton::section {{ background: {t['sunken']}; border: none; }}

/* Eingabefelder */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
    background: {t['input']}; border: 1px solid {t['line']}; border-radius: 7px;
    padding: 5px 8px; selection-background-color: {t['accent']}; selection-color: {t['accent_text']};
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {t['line_strong']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border-color: {t['accent']}; }}
QLineEdit[edited="true"], QComboBox[edited="true"] {{ border-color: {t['modified']}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {t['faint']}; background: {t['panel']}; border-color: {t['line_soft']}; }}
QLineEdit#FilterField {{ border-radius: 9px; padding: 6px 10px; background: {t['input']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url("{t.get('arrow_down_muted', '')}"); width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: url("{t.get('arrow_down_faint', '')}"); }}
QSpinBox {{ padding-right: 22px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; background: transparent; margin-right: 2px;
}}
QSpinBox::up-button {{ subcontrol-position: top right; margin-top: 2px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; margin-bottom: 2px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {t['hover']}; border-radius: 4px; }}
QSpinBox::up-arrow {{ image: url("{t.get('arrow_up_muted', '')}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url("{t.get('arrow_down_muted', '')}"); width: 10px; height: 10px; }}
QComboBox QLineEdit {{ border: none; padding: 0; margin: 0; background: transparent; border-radius: 0; }}
QComboBox QAbstractItemView {{
    background: {t['raised']}; border: 1px solid {t['line']}; outline: 0;
    selection-background-color: {t['hover']}; selection-color: {t['text']}; padding: 4px;
}}

/* Buttons */
QPushButton {{
    background: {t['raised']}; border: 1px solid {t['line']}; border-radius: 8px;
    padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background: {t['hover']}; border-color: {t['line_strong']}; }}
QPushButton:pressed {{ background: {t['line']}; }}
QPushButton:disabled {{ color: {t['faint']}; background: {t['panel']}; border-color: {t['line_soft']}; }}
QPushButton[kind="primary"] {{
    background: {t['accent']}; color: {t['accent_text']}; border: 1px solid {t['accent']}; font-weight: 600;
}}
QPushButton[kind="primary"]:hover {{ background: {t['accent_hover']}; border-color: {t['accent_hover']}; }}
QPushButton[kind="primary"]:disabled {{ background: {t['accent_soft']}; color: {t['faint']}; border-color: {t['accent_soft']}; }}
QPushButton#NextButton {{ padding: 10px 14px; font-size: 14px; }}
QPushButton[kind="ghost"] {{ background: transparent; border: 1px solid transparent; }}
QPushButton[kind="ghost"]:hover {{ background: {t['hover']}; }}
QPushButton::menu-indicator {{ image: none; width: 0; }}

QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 6px; }}
QToolButton:hover {{ background: {t['hover']}; }}
QToolButton:pressed {{ background: {t['line']}; }}
QToolButton:checked {{ background: {t['accent_soft']}; border-color: {t['accent_soft']}; color: {t['accent']}; }}
QToolButton:disabled {{ color: {t['faint']}; }}
QToolButton[popupMode="2"] {{ padding-right: 8px; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QToolButton[kind="text"] {{ padding: 6px 10px; font-weight: 500; }}
QToolButton[kind="side"] {{
    background: {t['raised']}; border: 1px solid {t['line']}; border-radius: 7px;
    padding: 5px 8px; font-weight: 500; text-align: left;
}}
QToolButton[kind="side"]:hover {{ background: {t['hover']}; border-color: {t['line_strong']}; }}
QToolButton[kind="side"]:disabled {{ background: {t['panel']}; border-color: {t['line_soft']}; }}

/* Menüs */
QMenu {{ background: {t['raised']}; border: 1px solid {t['line']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t['hover']}; }}
QMenu::item:disabled {{ color: {t['faint']}; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::separator {{ height: 1px; background: {t['line']}; margin: 6px 6px; }}
QMenu::section {{ color: {t['muted']}; }}

/* Scrollbalken */
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['scroll']}; border-radius: 4px; min-height: 36px; margin: 2px 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t['scroll']}; border-radius: 4px; min-width: 36px; margin: 2px 2px; }}
QScrollBar::handle:hover {{ background: {t['line_strong']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

/* Statusleiste */
QStatusBar {{ background: {t['panel']}; border-top: 1px solid {t['line']}; color: {t['muted']}; min-height: 30px; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {t['muted']}; font-size: 12px; padding: 0 6px; }}
QProgressBar {{ background: {t['line']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}

QToolTip {{ background: {t['raised']}; color: {t['text']}; border: 1px solid {t['line']}; padding: 6px 8px; border-radius: 6px; }}

/* Dialoge */
QTabWidget::pane {{ border: 1px solid {t['line']}; border-radius: 10px; background: {t['panel']}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {t['muted']}; padding: 8px 14px; border: none; margin-right: 2px; }}
QTabBar::tab:selected {{ color: {t['text']}; border-bottom: 2px solid {t['accent']}; }}
QTabBar::tab:hover {{ color: {t['text']}; }}
QListWidget {{ background: {t['input']}; border: 1px solid {t['line']}; border-radius: 8px; outline: 0; }}
QListWidget::item {{ padding: 6px; border-bottom: 1px solid {t['line_soft']}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
#Toast {{ background: {t['raised']}; border: 1px solid {t['line_strong']}; border-radius: 10px; padding: 9px 14px; color: {t['text']}; font-weight: 500; }}
QToolButton[kind="chip"] {{
    background: {t['raised']}; border: 1px solid {t['line']}; border-radius: 11px;
    padding: 3px 10px; font-size: 12px; color: {t['muted']};
}}
QToolButton[kind="chip"]:hover {{ border-color: {t['line_strong']}; color: {t['text']}; }}
QToolButton[kind="chip"]:checked {{ background: {t['accent_soft']}; border-color: {t['accent']}; color: {t['text']}; }}
#ToolHead {{ background: {t['panel']}; border-bottom: 1px solid {t['line']}; }}
#ToolOptions, #ToolOptionsInner {{ background: {t['panel']}; border-right: 1px solid {t['line']}; }}
#ToolOptionsInner {{ border: none; }}
#ToolFoot {{ background: {t['panel']}; border-top: 1px solid {t['line']}; }}
#ToolSummary {{ font-weight: 600; }}
#ToolMessage {{ background: {t['accent_soft']}; color: {t['text']}; padding: 9px 14px; border-bottom: 1px solid {t['line']}; }}
QPlainTextEdit {{ background: {t['input']}; }}
QListWidget#ResultList {{ background: {t['panel']}; border: none; outline: 0; }}
QListWidget#ResultList::item {{ border: none; }}
QListWidget#ImageGrid {{ background: {t['sunken']}; border: none; outline: 0; padding: 10px; }}
QListWidget#ImageGrid::item {{ border-radius: 10px; padding: 6px; color: {t['muted']}; border: none; }}
QListWidget#ImageGrid::item:hover {{ background: {t['hover']}; }}
QListWidget#ImageGrid::item:selected {{ background: {t['selection']}; color: {t['text']}; border: 1px solid {t['accent']}; }}
#Card {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 12px; }}
"""
