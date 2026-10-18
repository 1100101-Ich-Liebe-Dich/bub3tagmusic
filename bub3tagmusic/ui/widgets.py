"""Kleine wiederverwendbare Bausteine für Dialoge: Fließ-Layout, Chips, Feld-Auswahl, Muster-Feld."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QLabel, QLayout, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
                               QWidgetItem)

from ..core.fields import FIELDS


class FlowLayout(QLayout):
    """Ordnet Widgets nebeneinander an und bricht um, wenn der Platz endet."""

    def __init__(self, parent=None, spacing: int = 6):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def addWidget(self, w):
        self.addChildWidget(w)
        self.addItem(QWidgetItem(w))

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, test=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        return size

    def _layout(self, rect: QRect, test: bool) -> int:
        x, y, line_h = rect.x(), rect.y(), 0
        for it in self._items:
            w = it.widget()
            if w is not None and w.isHidden():
                continue
            hint = it.sizeHint()
            if x + hint.width() > rect.right() + 1 and line_h > 0:
                x = rect.x()
                y += line_h + self._spacing
                line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


def chip(text: str, checkable: bool = False, tooltip: str = "") -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setProperty("kind", "chip")
    b.setCheckable(checkable)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "section")
    return lbl


def hint(text: str, role: str = "faint") -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", role)
    lbl.setWordWrap(True)
    return lbl


class FieldPicker(QWidget):
    """Felder als anklickbare Chips (für Schreibweise, Ersetzen, Aufräumen)."""

    changed = Signal()

    def __init__(self, keys: list[str], selected: list[str], parent=None):
        super().__init__(parent)
        lay = FlowLayout(self, spacing=6)
        self._chips: dict[str, QToolButton] = {}
        labels = {f.key: f.label for f in FIELDS}
        for key in keys:
            c = chip(labels.get(key, key), checkable=True)
            c.setChecked(key in selected)
            c.toggled.connect(lambda _on: self.changed.emit())
            lay.addWidget(c)
            self._chips[key] = c
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def selected(self) -> list[str]:
        return [k for k, c in self._chips.items() if c.isChecked()]

    def set_all(self, on: bool):
        for c in self._chips.values():
            c.blockSignals(True)
            c.setChecked(on)
            c.blockSignals(False)
        self.changed.emit()


class PatternBox(QWidget):
    """Eingabe für Muster: Vorlagen + zuletzt benutzte, darunter Platzhalter zum Anklicken."""

    changed = Signal(str)

    def __init__(self, presets: tuple[str, ...], history: list[str], current: str,
                 keys: list[str], parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setMaxVisibleItems(16)
        # lange Muster dürfen das Feld nicht breiter machen als die Spalte
        self.combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(12)
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        seen = []
        for p in list(history) + list(presets):
            if p and p not in seen:
                seen.append(p)
        self.combo.addItems(seen)
        self.combo.setEditText(current or (seen[0] if seen else ""))
        self.combo.lineEdit().textChanged.connect(self.changed.emit)
        lay.addWidget(self.combo)

        chips = QWidget()
        flow = FlowLayout(chips, spacing=5)
        labels = {f.key: f.label for f in FIELDS}
        for key in keys:
            c = chip(f"%{key}%", tooltip=labels.get(key, "Teil überspringen"))
            c.clicked.connect(lambda _=False, k=key: self.insert(f"%{k}%"))
            flow.addWidget(c)
        lay.addWidget(chips)

    def text(self) -> str:
        return self.combo.currentText().strip()

    def insert(self, token: str):
        le = self.combo.lineEdit()
        le.insert(token)
        le.setFocus()

    @staticmethod
    def remember(history: list[str], pattern: str, limit: int = 12) -> list[str]:
        pattern = pattern.strip()
        if not pattern:
            return history
        return ([pattern] + [h for h in history if h != pattern])[:limit]
