"""Componentes de interface reutilizáveis (estilo XMind)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QToolButton, QVBoxLayout, QWidget,
)

from mindforge.layouts import LAYOUTS
from mindforge.model.topic import MindMap, Topic
from mindforge.view import style

PRESET_COLORS = [
    "#FFFFFF", "#F2F3F5", "#D9DCE1", "#9AA4B2", "#5D6472", "#24364F", "#111111", "#7C4A2D",
    "#E5534B", "#F0883E", "#D4A72C", "#3FA66B", "#1B9AAA", "#2F80ED", "#8250DF", "#D63F8C",
    "#FFADAD", "#FFC89A", "#E9D985", "#B5E3A3", "#A0E7D9", "#9BD5F0", "#BDB2FF", "#FFC6FF",
]

# Sentinelas do seletor de cor
NO_COLOR = ""          # "Sem cor"
THEME_DEFAULT = None   # "Padrão do tema"


def swatch_pixmap(color: Optional[str], w: int = 22, h: int = 16, radius: float = 4) -> QPixmap:
    pm = QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(style.chrome().border))
    if color:
        p.setBrush(QColor(color))
        p.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)
    else:
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)
        p.setPen(QColor("#E5534B"))
        p.drawLine(3, h - 3, w - 3, 3)
    p.end()
    return pm


class ColorPopup(QFrame):
    picked = Signal(object)       # str | "" (sem cor) | None (padrão do tema)

    def __init__(self, parent: QWidget, current: Optional[str], allow_none: bool):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, col in enumerate(PRESET_COLORS):
            b = QToolButton()
            b.setIcon(QIcon(swatch_pixmap(col, 22, 22, 11)))
            b.setIconSize(QSize(22, 22))
            b.setAutoRaise(True)
            b.setToolTip(col)
            b.setCheckable(True)
            b.setChecked(bool(current) and current.upper() == col)
            b.clicked.connect(lambda _c=False, c=col: self._emit(c))
            grid.addWidget(b, i // 8, i % 8)
        lay.addLayout(grid)
        row = QHBoxLayout()
        if allow_none:
            none = QPushButton("Sem cor")
            none.clicked.connect(lambda: self._emit(NO_COLOR))
            row.addWidget(none)
        default = QPushButton("Padrão do tema")
        default.clicked.connect(lambda: self._emit(THEME_DEFAULT))
        row.addWidget(default)
        more = QPushButton("Mais cores…")
        more.clicked.connect(self._custom)
        row.addWidget(more)
        lay.addLayout(row)
        self._current = current

    def _emit(self, value) -> None:
        self.picked.emit(value)
        self.close()

    def _custom(self) -> None:
        self.hide()
        c = QColorDialog.getColor(QColor(self._current or "#FFFFFF"), self.parentWidget(), "Escolher cor")
        if c.isValid():
            self.picked.emit(c.name().upper())
        self.close()


class SwatchButton(QToolButton):
    picked = Signal(object)

    def __init__(self, allow_none: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("Swatch")
        self.allow_none = allow_none
        self.color: Optional[str] = None
        self.setIconSize(QSize(30, 16))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._open)

    def show_color(self, color: Optional[str]) -> None:
        self.color = color
        self.setIcon(QIcon(swatch_pixmap(color or None, 30, 16)))

    def _open(self) -> None:
        pop = ColorPopup(self.window(), self.color, self.allow_none)
        pop.picked.connect(self.picked.emit)
        pop.adjustSize()
        g = self.mapToGlobal(QPoint(self.width(), self.height() + 4))
        pop.move(g.x() - pop.width(), g.y())
        pop.show()


def section_title(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("SectionTitle")
    return lab


def separator() -> QFrame:
    f = QFrame()
    f.setObjectName("Separator")
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def row(label: str, *widgets: QWidget) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(6)
    lab = QLabel(label)
    lab.setObjectName("RowLabel")
    h.addWidget(lab)
    h.addStretch(1)
    for w in widgets:
        h.addWidget(w)
    return h


class Segmented(QFrame):
    changed = Signal(int)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        for i, t in enumerate(labels):
            b = QPushButton(t)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(b, i)
            lay.addWidget(b)
        self.group.button(0).setChecked(True)
        self.group.idClicked.connect(self.changed.emit)

    def set_index(self, i: int) -> None:
        self.group.button(i).setChecked(True)


# ------------------------------------------------------------- miniaturas
def sample_map(layout: str, theme: str) -> MindMap:
    root = Topic("Tema central")
    n = 4 if layout != "espinha_peixe" else 4
    for i in range(n):
        c = root.add_child(Topic(f"Tópico {i + 1}"))
        for j in range(2):
            c.add_child(Topic("Subtópico"))
    return MindMap(root, layout, theme)


_THUMBS: dict[tuple, QPixmap] = {}


def thumbnail(layout: str, theme: str, size: QSize, settings: Optional[dict] = None) -> QPixmap:
    key = (layout, theme, size.width(), size.height(), tuple(sorted((settings or {}).items())))
    pm = _THUMBS.get(key)
    if pm is None:
        from mindforge.view.resources import render_thumbnail
        m = sample_map(layout, theme)
        m.settings = dict(settings or {})
        pm = render_thumbnail(m, size)
        _THUMBS[key] = pm
    return pm


SKELETON_GROUPS = [
    ("Mapa de ideias", ["mapa_mental"]),
    ("Gráfico de lógica", ["mapa_direita", "mapa_esquerda"]),
    ("Estrutura", ["organograma", "arvore"]),
    ("Linha do tempo", ["linha_tempo"]),
    ("Espinha de peixe", ["espinha_peixe"]),
]


class SkeletonPopup(QFrame):
    picked = Signal(str)
    THUMB = QSize(150, 92)

    def __init__(self, parent: QWidget, current: str):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 18)
        lay.setSpacing(8)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        r = 0
        for title, keys in SKELETON_GROUPS:
            grid.addWidget(section_title(title), r, 0, 1, 3)
            r += 1
            for i, key in enumerate(keys):
                b = QToolButton()
                b.setObjectName("ThemeCard")
                b.setCheckable(True)
                b.setChecked(key == current)
                b.setIcon(QIcon(thumbnail(key, "_esqueleto", self.THUMB)))
                b.setIconSize(self.THUMB)
                b.setToolTip(LAYOUTS[key].label)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _c=False, k=key: self._pick(k))
                grid.addWidget(b, r, i)
            r += 1
        lay.addLayout(grid)

    def _pick(self, key: str) -> None:
        self.picked.emit(key)
        self.close()


class CardButton(QToolButton):
    """Botão "cartão" com miniatura + título + seta (como o seletor de esqueleto do XMind)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(88, 52))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# --------------------------------------------------------- seções recolhíveis
class CollapsibleSection(QWidget):
    """Seção do painel com título clicável (▾/▸) que recolhe o conteúdo; lembra o estado."""

    def __init__(self, title: str, key: str, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import QSettings
        self._settings_key = f"painel/secao/{key}"
        self._open = QSettings().value(self._settings_key, True, type=bool)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.header = QToolButton()
        self.header.setObjectName("SectionHeader")
        self.header.setText(title)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.clicked.connect(self.toggle)
        head.addWidget(self.header)
        head.addStretch(1)
        self.extra = QHBoxLayout()
        self.extra.setSpacing(4)
        head.addLayout(self.extra)
        lay.addLayout(head)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 4)
        self.body_layout.setSpacing(8)
        lay.addWidget(self.body)
        self._apply()

    def toggle(self) -> None:
        from PySide6.QtCore import QSettings
        self._open = not self._open
        QSettings().setValue(self._settings_key, self._open)
        self._apply()

    def _apply(self) -> None:
        self.body.setVisible(self._open)
        from mindforge.view.icons import icon
        self.header.setIcon(icon("chevron" if self._open else "chevron_right", style.chrome().muted, 12))

    def add(self, item) -> None:
        if isinstance(item, QWidget):
            self.body_layout.addWidget(item)
        else:
            self.body_layout.addLayout(item)


# ------------------------------------------------------------- grade de ícones
class IconGridPopup(QFrame):
    picked = Signal(object)

    def __init__(self, parent: QWidget, items: list, current, columns: int = 2,
                 icon_size: QSize = QSize(44, 28), default_label: Optional[str] = None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (key, ic, tip) in enumerate(items):
            b = QToolButton()
            b.setObjectName("ShapeButton")
            b.setIcon(ic)
            b.setIconSize(icon_size)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setChecked(key == current)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self._emit(k))
            grid.addWidget(b, i // columns, i % columns)
        lay.addLayout(grid)
        if default_label:
            d = QPushButton(default_label)
            d.clicked.connect(lambda: self._emit(None))
            lay.addWidget(d)

    def _emit(self, key) -> None:
        self.picked.emit(key)
        self.close()


class IconPickerButton(QToolButton):
    """Botão que mostra o ícone da opção atual e abre uma grade de opções."""
    picked = Signal(object)

    def __init__(self, items_factory, columns: int = 2, icon_size: QSize = QSize(44, 28),
                 default_label: Optional[str] = "Padrão", parent=None):
        super().__init__(parent)
        self.setObjectName("Swatch")
        self.items_factory = items_factory
        self.columns = columns
        self.grid_icon = icon_size
        self.default_label = default_label
        self.current = None
        self.setIconSize(QSize(34, 20))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._open)

    def show_value(self, key, ic: Optional[QIcon], mixed: bool = False) -> None:
        self.current = key
        if mixed or ic is None:
            self.setIcon(QIcon())
            self.setText("—")
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        else:
            self.setText("")
            self.setIcon(ic)
            self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

    def _open(self) -> None:
        pop = IconGridPopup(self.window(), self.items_factory(), self.current, self.columns,
                            self.grid_icon, self.default_label)
        pop.picked.connect(self.picked.emit)
        pop.adjustSize()
        g = self.mapToGlobal(QPoint(self.width(), self.height() + 4))
        pop.move(g.x() - pop.width(), g.y())
        pop.show()


def set_combo(combo, value, mixed: bool = False) -> None:
    """Seleciona ``value`` num QComboBox (por data); com valores mistos mostra '—'."""
    combo.blockSignals(True)
    try:
        if mixed:
            combo.setPlaceholderText("—")
            combo.setCurrentIndex(-1)
        else:
            i = combo.findData(value)
            if i < 0 and value is not None and not combo.isEditable():
                combo.addItem(str(value), value)
                i = combo.count() - 1
            combo.setCurrentIndex(max(0, i) if not combo.isEditable() or i >= 0 else 0)
    finally:
        combo.blockSignals(False)
