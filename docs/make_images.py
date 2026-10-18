"""Bilder für die GitHub-Seite erzeugen (README, Release, Vorschaubild).

Aufruf:  QT_QPA_PLATFORM=offscreen python3 docs/make_images.py
Braucht ffmpeg (für die Demo-Sammlung) und Pillow. Ändert nichts außerhalb von docs/.

Erzeugt eine kleine, ansehnliche Demo-Sammlung in einem Temp-Ordner, startet BuB3TAGMUSIC
unsichtbar und fotografiert die wichtigsten Ansichten im Standard-Theme „Bauen & Booten“.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
WORK = tempfile.mkdtemp(prefix="bub3docs_")
os.environ["XDG_CONFIG_HOME"] = os.path.join(WORK, "config")
os.environ["XDG_CACHE_HOME"] = os.path.join(WORK, "cache")
os.environ["XDG_DATA_HOME"] = os.path.join(WORK, "data")

W, H = 1440, 860
BG, PANEL, AMBER, GREEN, TEXT, BODY, FAINT = "#1C1F1C", "#171A17", "#E5A00D", "#7A8B76", "#E4ECE0", "#B4C6AF", "#7F8B7B"


# ----------------------------------------------------------------------
# Demo-Sammlung
# ----------------------------------------------------------------------
ADJ = ["Rostiger", "Leiser", "Letzter", "Blauer", "Alter", "Kalter", "Stiller", "Weiter", "Später", "Grauer",
       "Neuer", "Ferner", "Dunkler", "Heller", "Wilder", "Langer", "Schwerer", "Fremder", "Erster", "Rauer"]
NOUN = ["Anker", "Kai", "Leuchtturm", "Hafen", "Wind", "Kutter", "Lotse", "Steg", "Mast", "Deich", "Nebel",
        "Kurs", "Bug", "Strom", "Sund", "Tampen"]
PICK = {}


def build_collection() -> str:
    from make_testfiles import make, make_collection

    from bub3tagmusic.core.tags import read_file, write_file
    templates = make(os.path.join(WORK, "formats"), seconds=1.0)
    music = os.path.join(WORK, "Musik")
    make_collection(music, 24, templates)
    titles = iter(f"{a} {n}" for n in NOUN for a in ADJ)          # 320 verschiedene Titel
    albums = sorted(d for d, _s, f in os.walk(music) if any(x[:2].isdigit() for x in f))
    for folder in albums:
        for name in sorted(os.listdir(folder)):
            if not name[:2].isdigit():
                continue
            path = os.path.join(folder, name)
            n = int(name[:2])
            title = next(titles)
            new = os.path.join(folder, f"{n:02d} - {title}{os.path.splitext(name)[1]}")
            os.rename(path, new)
            if read_file(new)["tags"]["artist"]:
                write_file(new, {"title": title})
            else:                                                   # kaum getaggtes Album
                write_file(new, {"title": f"{n:02d} - {title}"})
    tagged = [a for a in albums if read_file(os.path.join(a, sorted(os.listdir(a))[0]))["tags"].get("artist")]
    # ein Album mit „verwilderten“ Tags für die Aktionen
    messy = PICK["messy"] = tagged[4]
    for name in sorted(os.listdir(messy)):
        p = os.path.join(messy, name)
        if name[:2].isdigit():
            t = read_file(p)["tags"]
            write_file(p, {"title": "  " + t["title"].upper() + "  ( )", "albumartist": ""})
            os.rename(p, os.path.join(messy, name.replace(" - ", "_").replace(" ", "_")))
    # Duplikate: drei Lieder liegen zusätzlich auf einem „Best Of“
    src = tagged[0]
    band = os.path.basename(os.path.dirname(src))
    best = os.path.join(os.path.dirname(src), "2010 - Best Of")
    os.makedirs(best, exist_ok=True)
    for i, name in enumerate(sorted(f for f in os.listdir(src) if f[:2].isdigit())[:3], 1):
        dst = os.path.join(best, f"{i:02d} - {name[5:]}")
        shutil.copyfile(os.path.join(src, name), dst)
        write_file(dst, {"album": "Best Of", "year": "2010", "track": f"{i}/3", "albumartist": band})
    return music


# ----------------------------------------------------------------------
def save(img, name: str):
    """QImage/QPixmap → PNG, mit Pillow verkleinert gespeichert."""
    from PIL import Image
    tmp = os.path.join(WORK, name)
    img.save(tmp)
    im = Image.open(tmp).convert("RGB")
    im.save(os.path.join(HERE, name), optimize=True)
    print("  ", name, im.size)


def main():
    from PySide6.QtWidgets import QApplication
    music = build_collection()
    app = QApplication(sys.argv[:1])
    from bub3tagmusic.app import prepare_app
    from bub3tagmusic.core.settings import Settings
    from bub3tagmusic.ui import theme
    prepare_app(app)
    s = Settings()
    theme.apply(app, "bub")
    from bub3tagmusic.ui.mainwindow import MainWindow

    def pump(sec=0.3):
        t0 = time.time()
        while time.time() - t0 < sec:
            app.processEvents()
            time.sleep(0.01)

    def wait(cond, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout and not cond():
            pump(0.05)

    win = MainWindow(s)
    win.resize(W, H)
    win.show()
    win.tree.set_root(music, [])
    wait(lambda: win.tree.root_node is not None)
    albums = win.tree._albums

    def load(paths, recursive=False):
        win.btn_recursive.setChecked(recursive)
        win.tree.select_paths(paths)
        wait(lambda: win._load_worker is None and win.session.items)
        pump(0.6)

    # 1) Hauptfenster: Album mit Cover, alle Dateien ausgewählt
    with_cover = next(a for a in albums if os.path.exists(os.path.join(a, "cover.jpg")))
    win.tree.mark([albums[0], albums[1], albums[2]], 1)
    load([with_cover])
    win.session.apply_fields(win.session.items[:2], {"comment": "Remaster 2024"})
    pump(0.6)
    save(win.grab(), "screenshot-dark.png")
    win.session.revert()
    pump()

    # 2) Helles Theme
    win.apply_theme("bub_light")
    pump(0.4)
    save(win.grab(), "screenshot-light.png")

    # 3) Alle Themes als Collage
    shots = {}
    for key in theme.THEME_INFO:
        win.apply_theme(key)
        pump(0.4)
        shots[key] = win.grab().toImage()
    win.apply_theme("bub")
    pump(0.3)
    themes_collage(shots)

    # 4) Schnellfilter über die ganze Sammlung
    win.filterbar.chips["no_cover"].setChecked(True)
    pump(0.2)
    win.search_collection()
    wait(lambda: win._load_worker is None and win._search is not None)
    pump(0.6)
    save(win.grab(), "screenshot-filter.png")
    win.filterbar.clear()

    # 5) Werkzeug „Tags aus Dateiname“ auf einem kaum getaggten Album
    from bub3tagmusic.core.tags import read_file
    bare = next(a for a in albums
                if not read_file(os.path.join(a, sorted(f for f in os.listdir(a) if f[:2].isdigit())[0]))
                ["tags"]["artist"])
    load([bare])
    from bub3tagmusic.ui.tools import TOOL_DIALOGS
    items, scope = win.tool_items()
    d = TOOL_DIALOGS["tags_from_filename"](win, items, scope)
    d.resize(1180, 680)
    d.show()
    d.pattern.combo.setEditText("%artist%/%year% - %album%/%track% - %title%")
    pump(0.8)
    d.refresh()
    d.pattern.combo.lineEdit().setCursorPosition(0)
    d.apply_btn.setFocus()
    pump(0.3)
    save(d.grab(), "screenshot-werkzeug.png")
    d.reject()

    # 6) Aktionen auf dem verwilderten Album
    load([PICK["messy"]])
    from bub3tagmusic.ui.extras import EXTRA_DIALOGS
    items, scope = win.tool_items()
    d = EXTRA_DIALOGS["actions"](win, items, scope)
    d.resize(1180, 680)
    d.show()
    names = [d.combo.itemText(i) for i in range(d.combo.count())]
    d.combo.setCurrentIndex(names.index("Album fertig machen"))
    pump(0.8)
    d.refresh()
    pump(0.3)
    save(d.grab(), "screenshot-aktionen.png")
    d.reject()

    # 7) Duplikate (nach Tags, ganze Sammlung)
    d = EXTRA_DIALOGS["duplicates"](win, win.session.items, "")
    d.resize(1180, 680)
    d.show()
    d.rb_all.setChecked(True)
    d.cb_sound.setChecked(False)
    d.search()
    wait(lambda: d.task is not None and not d.task.isRunning(), 60)
    pump(0.5)
    save(d.grab(), "screenshot-duplikate.png")
    d.reject()

    # 8) ReplayGain (nur messen) – wenn rsgain da ist
    from bub3tagmusic.core.tools_external import find_tool
    if find_tool("rsgain"):
        load([with_cover])
        items, scope = win.tool_items()
        d = EXTRA_DIALOGS["replaygain"](win, items, scope)
        d.resize(1180, 640)
        d.show()
        d.start()
        wait(lambda: d.task is not None and not d.task.isRunning() and d.results, 60)
        pump(0.5)
        top = d.tree.topLevelItem(0)
        if top is not None:
            top.setExpanded(True)
        pump(0.2)
        save(d.grab(), "screenshot-replaygain.png")
        d.reject()

    # 9) HTML-Export (im Browser fotografiert, falls Playwright da ist)
    load([with_cover])
    from bub3tagmusic.core import export
    from bub3tagmusic.ui.export import table_snapshot
    headers, rows, numeric = table_snapshot(win.table)
    html = os.path.join(WORK, "export.html")
    export.write_html(html, headers, rows, title=os.path.basename(with_cover), numeric=numeric,
                      dark=theme.THEMES["bub"], light=theme.THEMES["bub_light"])
    browser_shot(html, "screenshot-export.png")

    banner()
    social_preview()
    win.session.revert()
    win.close()
    shutil.rmtree(WORK, ignore_errors=True)


# ----------------------------------------------------------------------
def themes_collage(shots: dict):
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from bub3tagmusic.ui import theme
    tw, th = 560, int(560 * H / W)
    pad, label_h = 24, 34
    cols = 3
    rows = (len(shots) + cols - 1) // cols
    img = QImage(cols * tw + (cols + 1) * pad, rows * (th + label_h) + (rows + 1) * pad, QImage.Format.Format_RGB32)
    img.fill(QColor(BG))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    font = theme.ui_font(17)
    font.setBold(True)
    p.setFont(font)
    for i, (key, shot) in enumerate(shots.items()):
        r, c = divmod(i, cols)
        if r == rows - 1 and len(shots) % cols:          # letzte Reihe mittig
            c += (cols - len(shots) % cols) / 2
        x = int(pad + c * (tw + pad))
        y = pad + r * (th + label_h + pad)
        p.drawImage(QRect(x, y, tw, th), shot.scaled(tw, th, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
        p.setPen(QColor(GREEN))
        p.drawRect(QRect(x, y, tw - 1, th - 1))
        p.setPen(QColor(AMBER if key == "bub" else BODY))
        p.drawText(QRect(x, y + th + 6, tw, label_h - 6), Qt.AlignmentFlag.AlignHCenter, theme.label(key))
    p.end()
    save(img, "themes.png")


def _icon_pixmap(size: int):
    from PySide6.QtGui import QIcon
    return QIcon(os.path.join(ROOT, "bub3tagmusic", "resources", "bub3tagmusic.svg")).pixmap(size, size)


def _brand_canvas(w: int, h: int):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(BG))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # feine Seekarten-Linien in Erdgrün
    pen = QPen(QColor(GREEN))
    pen.setWidthF(1.0)
    col = QColor(GREEN)
    for i, r in enumerate(range(80, int(w * 1.2), 46)):
        col.setAlphaF(max(0.02, 0.10 - i * 0.004))
        pen.setColor(col)
        p.setPen(pen)
        p.drawEllipse(QPointF(w * 0.86, h * 0.5), r, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(AMBER))
    p.drawRect(0, h - 6, w, 6)
    return img, p


def banner():
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont

    from bub3tagmusic.ui import theme
    w, h = 1280, 360
    img, p = _brand_canvas(w, h)
    p.drawPixmap(70, 92, _icon_pixmap(150))
    mark = QFont(theme.WORDMARK_FONT)
    mark.setPixelSize(118)
    mark.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
    p.setFont(mark)
    p.setPen(QColor(AMBER))
    p.drawText(QRect(260, 70, 1000, 130), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "BuB3TAGMUSIC")
    p.setFont(theme.ui_font(30, QFont.Weight.DemiBold))
    p.setPen(QColor(TEXT))
    p.drawText(QRect(266, 200, 1000, 44), Qt.AlignmentFlag.AlignLeft, "Moderner, schneller Musik-Tagger für Linux")
    p.setFont(theme.ui_font(21))
    p.setPen(QColor(BODY))
    p.drawText(QRect(266, 252, 1000, 34), Qt.AlignmentFlag.AlignLeft,
               "präsentiert von www.BAUENUNDBOOTEN.de")
    p.end()
    save(img, "banner.png")


def social_preview():
    """1280 × 640 – für GitHub → Settings → Social preview."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage

    from bub3tagmusic.ui import theme
    w, h = 1280, 640
    img, p = _brand_canvas(w, h)
    p.drawPixmap(64, 64, _icon_pixmap(96))
    mark = QFont(theme.WORDMARK_FONT)
    mark.setPixelSize(84)
    p.setFont(mark)
    p.setPen(QColor(AMBER))
    p.drawText(QRect(180, 58, 1050, 110), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "BuB3TAGMUSIC")
    p.setFont(theme.ui_font(26, QFont.Weight.DemiBold))
    p.setPen(QColor(TEXT))
    p.drawText(QRect(184, 160, 1050, 40), Qt.AlignmentFlag.AlignLeft, "Moderner, schneller Musik-Tagger für Linux")
    shot = QImage(os.path.join(HERE, "screenshot-dark.png"))
    if not shot.isNull():
        sw = 1100
        sh = int(sw * shot.height() / shot.width())
        p.setPen(QColor(GREEN))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawImage(QRect(90, 236, sw, sh), shot.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation))
        p.drawRect(QRect(90, 236, sw - 1, sh - 1))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(AMBER))
    p.drawRect(0, h - 6, w, 6)
    p.end()
    save(img, "social-preview.png")


def browser_shot(html: str, name: str):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("   (Playwright fehlt – Export-Bild übersprungen)")
        return
    exe = None
    for cand in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",):
        if os.path.exists(cand):
            exe = cand
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        page = b.new_page(viewport={"width": 1200, "height": 640}, color_scheme="dark")
        page.goto("file://" + html)
        page.wait_for_timeout(300)
        tmp = os.path.join(WORK, name)
        page.screenshot(path=tmp)
        b.close()
    from PIL import Image
    Image.open(tmp).convert("RGB").save(os.path.join(HERE, name), optimize=True)
    print("  ", name)


if __name__ == "__main__":
    main()
