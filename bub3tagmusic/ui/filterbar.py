"""Schnellfilter-Leiste über der Dateiliste (Phase 4).

Chips zum An- und Abschalten („Ohne Cover“, „Ohne Jahr“ …), kombinierbar,
mit der Anzahl passender Dateien. Rechts: dieselben Filter in der ganzen
Sammlung suchen (liest aus dem Zwischenspeicher, nur Neues wird eingelesen).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from ..core.filters import QUICK_FILTERS
from . import icons
from .widgets import FlowLayout, chip


class FilterBar(QWidget):
    changed = Signal()
    collectionRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FilterBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 6, 10, 6)
        outer.setSpacing(8)

        self._icon = QLabel()
        self._icon.setToolTip("Schnellfilter – mehrere gleichzeitig möglich")
        outer.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)

        holder = QWidget()
        self.flow = FlowLayout(holder, spacing=6)
        self.flow.setContentsMargins(0, 0, 0, 0)
        self.chips: dict[str, QToolButton] = {}
        self._labels: dict[str, str] = {}
        for f in QUICK_FILTERS:
            b = chip(f.label, checkable=True, tooltip=f.tooltip)
            b.toggled.connect(lambda _on: self._changed())
            self.flow.addWidget(b)
            self.chips[f.key] = b
            self._labels[f.key] = f.label
        self.clear_btn = chip("Aufheben", tooltip="Alle Schnellfilter ausschalten")
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.hide()
        self.flow.addWidget(self.clear_btn)
        outer.addWidget(holder, 1)

        self.search_btn = QToolButton()
        self.search_btn.setText("Ganze Sammlung")
        self.search_btn.setProperty("kind", "text")
        self.search_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setToolTip("Mit diesen Filtern (und dem Suchtext) die ganze Sammlung durchsuchen – "
                                   "die Treffer kommen in die Liste")
        self.search_btn.clicked.connect(self.collectionRequested.emit)
        outer.addWidget(self.search_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.refresh_icons()
        self._update_buttons()

    # ------------------------------------------------------------------
    def refresh_icons(self):
        self._icon.setPixmap(icons.icon("funnel", "faint").pixmap(16, 16))
        self._icon.setContentsMargins(0, 5, 0, 0)
        self.search_btn.setIcon(icons.icon("magnifying-glass", "muted"))

    def active(self) -> set[str]:
        return {k for k, b in self.chips.items() if b.isChecked()}

    def set_active(self, keys) -> None:
        for k, b in self.chips.items():
            b.blockSignals(True)
            b.setChecked(k in keys)
            b.blockSignals(False)
        self._changed()

    def clear(self):
        self.set_active(set())

    def set_counts(self, counts: dict[str, int]) -> None:
        for k, b in self.chips.items():
            n = counts.get(k)
            b.setText(self._labels[k] if n is None else f"{self._labels[k]}  {n:,}".replace(",", "."))
            b.adjustSize()
        self.flow.invalidate()

    def set_search_enabled(self, on: bool, tip: str = "") -> None:
        self.search_btn.setEnabled(on)
        if tip:
            self.search_btn.setToolTip(tip)

    def _changed(self):
        self._update_buttons()
        self.changed.emit()

    def _update_buttons(self):
        self.clear_btn.setVisible(bool(self.active()))
        self.flow.invalidate()
