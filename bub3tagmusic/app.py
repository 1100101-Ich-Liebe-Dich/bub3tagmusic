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


def _check_qt_version() -> None:
    """PySide6 6.11+ stürzt unter Python < 3.12 nach einer Weile ab (Qt-Fehler, nicht unserer)."""
    import PySide6
    major, minor = (int(x) for x in PySide6.__version__.split(".")[:2])
    if sys.version_info < (3, 12) and (major, minor) >= (6, 11):
        print(f"WARNUNG: PySide6 {PySide6.__version__} ist mit Python "
              f"{sys.version_info.major}.{sys.version_info.minor} instabil. Bitte ./install.sh erneut "
              f"ausführen (installiert dann PySide6 6.10).", file=sys.stderr)


def _load_qt_german(app) -> bool:
    """Qt-eigene Texte (Ja/Nein, Datei-Dialog …) auf Deutsch – passend zur Oberfläche."""
    from PySide6.QtCore import QLibraryInfo, QTranslator
    tr = QTranslator(app)
    if tr.load("qtbase_de", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(tr)
        return True
    return False


HELP = """BuB3TAGMUSIC – moderner Musik-Tagger für Linux (präsentiert von www.BAUENUNDBOOTEN.de)

Aufruf:  bub3tagmusic [ORDNER]
  ORDNER          Musik-Sammlung direkt öffnen
  --version       Version anzeigen
  --selftest [ORDNER]
                  Startet ohne Rückfragen, lädt (falls angegeben) das erste Album
                  aus ORDNER, beendet sich und meldet SELFTEST OK. Ändert keine Dateien
                  und nutzt eigene, temporäre Einstellungen.
"""


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        print(HELP)
        return 0
    if "--version" in argv:
        from . import APP_NAME, APP_VERSION
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    selftest = "--selftest" in argv
    if selftest:
        import tempfile
        tmp = tempfile.mkdtemp(prefix="bub3selftest_")
        os.environ["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")
        os.environ["XDG_CACHE_HOME"] = os.path.join(tmp, "cache")
    _check_qt_version()

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
    german = _load_qt_german(app)
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

    if getattr(win, "start_maximized", False) and not selftest:
        win.showMaximized()
    else:
        win.show()
    if selftest:
        return _selftest(app, win, args[0] if args else "", german)
    return app.exec()


def _selftest(app, win, folder: str, german: bool) -> int:
    """Für Build-Prüfungen: läuft komplett durch und beendet sich selbst."""
    import time

    import PySide6

    def wait(cond, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if cond():
                return True
            time.sleep(0.02)
        return False

    ok = True
    info = [f"Python {sys.version.split()[0]}", f"PySide6 {PySide6.__version__}",
            f"Plattform {app.platformName()}",
            f"Qt deutsch {'ja' if german else 'nein'}"]
    if folder:
        if not wait(lambda: win.tree.root_node is not None, 30):
            ok = False
            info.append("Ordnerbaum: Zeitüberschreitung")
        elif win.tree._albums:
            win.tree.select_paths([win.tree._albums[0]])
            if wait(lambda: len(win.session.items) > 0, 60):
                info.append(f"{len(win.tree._albums)} Alben, erstes Album {len(win.session.items)} Dateien")
                errors = [it for it in win.session.items if it.error]
                if errors:
                    ok = False
                    info.append(f"Lesefehler: {errors[0].error}")
            else:
                ok = False
                info.append("Album laden: Zeitüberschreitung")
    from .core.tools_external import find_tool, tool_version
    for tool in ("fpcalc", "rsgain"):
        path = find_tool(tool)
        where = "mitgeliefert" if path.startswith(os.environ.get("BUB3_BIN") or "/-/") else "System"
        info.append(f"{tool} {tool_version(tool)} ({where})" if path else f"{tool} fehlt")
    wait(lambda: False, 0.5)
    print("SELFTEST " + ("OK" if ok else "FEHLER") + " – " + ", ".join(info))
    win.session.revert()
    win.close()
    return 0 if ok else 1
