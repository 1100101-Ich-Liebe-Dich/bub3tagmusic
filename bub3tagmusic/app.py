"""Programmstart."""

from __future__ import annotations

import os
import sys


def prepare_app(app) -> None:
    """Stil, Schriften und Theme – auch von den Tests genutzt."""
    from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleFactory

    from .ui import theme

    class Style(QProxyStyle):
        def drawPrimitive(self, element, option, painter, widget=None):
            # Keine gestrichelten Fokus-Rahmen – Auswahl und Rahmenfarbe zeigen den Fokus
            if element == QStyle.PrimitiveElement.PE_FrameFocusRect:
                return
            super().drawPrimitive(element, option, painter, widget)

    app.setStyle(Style(QStyleFactory.create("Fusion")))
    theme.load_fonts()
    app.setFont(theme.ui_font(13))


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    from . import APP_ID, APP_NAME, APP_VERSION
    from .core.settings import Settings
    from .ui import theme

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("BAUENUNDBOOTEN")
    app.setDesktopFileName(APP_ID)
    prepare_app(app)
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "bub3tagmusic.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    settings = Settings.load()
    theme.apply(app, settings.theme)

    from .ui.mainwindow import MainWindow
    win = MainWindow(settings)

    # Ordner als Argument: bub3tagmusic ~/Musik
    args = [a for a in argv[1:] if not a.startswith("-")]
    if args and os.path.isdir(args[0]):
        win.tree.set_root(os.path.abspath(args[0]), [])
        settings.last_root = os.path.abspath(args[0])
        win._update_empty_text()

    win.show()
    return app.exec()
