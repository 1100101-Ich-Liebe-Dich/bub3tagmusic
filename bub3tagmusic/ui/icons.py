"""Icons (Phosphor über qtawesome), passend zum aktiven Theme eingefärbt."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from . import theme

try:
    import qtawesome as qta
except ImportError:  # ohne qtawesome läuft alles, nur ohne Symbole
    qta = None


def icon(name: str, role: str = "text", active_role: str | None = None) -> QIcon:
    return _icon(name, theme.current(), role, active_role or role)


@lru_cache(maxsize=512)
def _icon(name: str, _theme: str, role: str, active_role: str) -> QIcon:
    if qta is None:
        return QIcon()
    try:
        return qta.icon(
            f"ph.{name}",
            color=theme.tok(role),
            color_active=theme.tok(active_role),
            color_disabled=theme.tok("faint"),
        )
    except Exception:
        return QIcon()


@lru_cache(maxsize=64)
def _dot(color: str, size: int, ring: bool) -> QPixmap:
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    if ring:
        pen = p.pen()
        pen.setColor(c)
        pen.setWidthF(1.4)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(1.5, 1.5, size - 3, size - 3))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()
    return pm


def dot_icon(role: str, size: int = 10, ring: bool = False) -> QIcon:
    return QIcon(_dot(theme.tok(role), size, ring))
