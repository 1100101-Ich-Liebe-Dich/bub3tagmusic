"""Cover-Anzeige mit Drag & Drop."""

from __future__ import annotations

import os

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from . import icons, theme

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


def image_bytes_from_mime(mime) -> bytes | None:
    """Bild aus Drag & Drop oder Zwischenablage holen (Datei oder Bilddaten)."""
    if mime.hasUrls():
        for url in mime.urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if path.lower().endswith(IMAGE_EXTS) and os.path.isfile(path):
                    with open(path, "rb") as fh:
                        return fh.read()
    if mime.hasImage():
        img = mime.imageData()
        if isinstance(img, QImage) and not img.isNull():
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            return bytes(ba.data())
    return None


class CoverView(QWidget):
    dropped = Signal(bytes)
    clicked = Signal()

    def __init__(self, size: int = 148, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pm: QPixmap | None = None
        self._badge = ""
        self._badge_role = "accent"
        self._empty = "Bild hierher ziehen"
        self._drag = False
        self._enabled = True

    def set_cover(self, pm: QPixmap | None, badge: str = "", badge_role: str = "accent", empty: str = ""):
        self._pm = pm
        self._badge, self._badge_role = badge, badge_role
        self._empty = empty or "Bild hierher ziehen"
        self.update()

    def set_active(self, on: bool):
        self._enabled = on
        self.setAcceptDrops(on)
        self.update()

    def has_image(self) -> bool:
        return self._pm is not None and not self._pm.isNull()

    def pixmap(self) -> QPixmap | None:
        return self._pm

    def sizeHint(self):
        return QSize(self.width(), self.height())

    # --- Zeichnen ------------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)

        if self.has_image():
            p.save()
            p.setClipPath(path)
            p.fillRect(r, theme.qcolor("sunken"))
            pm = self._pm.scaled(self.size() * self.devicePixelRatioF(), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(self.devicePixelRatioF())
            w, h = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
            p.drawPixmap(QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), pm, QRectF(pm.rect()))
            p.restore()
            p.setPen(QPen(theme.qcolor("line"), 1))
            p.drawPath(path)
        else:
            p.fillPath(path, theme.qcolor("input"))
            pen = QPen(theme.qcolor("accent" if self._drag else "line_strong"), 1.4, Qt.PenStyle.DashLine)
            pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.drawPath(path)
            ic = icons.icon("image", "faint")
            ic.paint(p, int(r.center().x() - 14), int(r.center().y() - 30), 28, 28)
            p.setPen(theme.qcolor("faint" if self._enabled else "line_strong"))
            p.setFont(theme.ui_font(12))
            p.drawText(QRectF(r.left() + 8, r.center().y() + 2, r.width() - 16, 40),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                       self._empty)

        if self._drag and self.has_image():
            p.fillPath(path, QColor(0, 0, 0, 110))
            p.setPen(QPen(theme.qcolor("accent"), 2))
            p.drawPath(path)
            p.setPen(QColor("white"))
            p.setFont(theme.ui_font(13, QFont.Weight.DemiBold))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Loslassen zum\nErsetzen")

        if self._badge:
            p.setFont(theme.ui_font(11, QFont.Weight.DemiBold))
            fm = p.fontMetrics()
            bw = fm.horizontalAdvance(self._badge) + 14
            br = QRectF(r.left() + 6, r.bottom() - 26, bw, 20)
            bp = QPainterPath()
            bp.addRoundedRect(br, 6, 6)
            p.fillPath(bp, theme.qcolor(self._badge_role))
            p.setPen(theme.qcolor("accent_text") if self._badge_role == "accent" else QColor("#14100A"))
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, self._badge)
        p.end()

    # --- Maus / Drag & Drop ---------------------------------------------------------
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def dragEnterEvent(self, e):
        if self._enabled and image_bytes_from_mime(e.mimeData()) is not None:
            self._drag = True
            self.update()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._drag = False
        self.update()

    def dropEvent(self, e):
        self._drag = False
        self.update()
        data = image_bytes_from_mime(e.mimeData())
        if data:
            e.acceptProposedAction()
            self.dropped.emit(data)


class CoverPreview(QDialog):
    """Großansicht beim Klick aufs Cover."""

    def __init__(self, pm: QPixmap, info: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cover")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 12)
        screen = self.screen().availableGeometry() if self.screen() else None
        max_side = int(min(screen.width(), screen.height()) * 0.7) if screen else 700
        shown = pm
        if max(pm.width(), pm.height()) > max_side:
            shown = pm.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        img = QLabel()
        img.setPixmap(shown)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(img)
        cap = QLabel(info)
        cap.setProperty("role", "muted")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(cap)
