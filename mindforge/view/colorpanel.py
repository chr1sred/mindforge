"""Interface dos temas de cores (1.3): seletor com abas, criar paleta, roda do Ramo colorido."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from mindforge import colorthemes as ct
from mindforge.i18n import ntr, tr
from mindforge.model.topic import MindMap, Topic
from mindforge.view.widgets import ColorPopup, Segmented

STRIP_SIZE = QSize(150, 26)
VARIANT_THUMB = QSize(84, 54)


# ------------------------------------------------------------ armazenamento
def palette_store():
    """Paletas do usuário: as do app; fora dele (testes, miniaturas), um arquivo na pasta de dados."""
    app = QApplication.instance()
    store = getattr(app, "palettes", None)
    if store is not None:
        return store
    global _fallback
    try:
        return _fallback
    except NameError:
        import os

        from PySide6.QtCore import QStandardPaths

        from mindforge.storage.palettes import PaletteStore
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        _fallback = PaletteStore(os.path.join(base, "temas.json"))
        return _fallback


def palette_name(p: ct.Palette) -> str:
    return p.name if p.group == "custom" else tr(p.name)


# ------------------------------------------------------------------ desenhos
def strip_pixmap(colors, size: QSize = STRIP_SIZE, radius: float = 5, dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(round(size.width() * dpr), round(size.height() * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0.5, 0.5, size.width() - 1, size.height() - 1), radius, radius)
    p.setClipPath(clip)
    cols = list(colors) or ["#CCCCCC"]
    w = size.width() / len(cols)
    for i, c in enumerate(cols):
        p.fillRect(QRectF(i * w, 0, w + 0.6, size.height()), QColor(c))
    p.setClipping(False)
    p.setPen(QPen(QColor(0, 0, 0, 40), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(clip)
    p.end()
    return pm


def wheel_pixmap(colors, size: int = 44, hub: str = "#2B2D33", dpr: float = 2.0,
                 hub_ratio: float = 0.17, outline: Optional[str] = None) -> QPixmap:
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    cols = list(colors) or ["#999999"]
    r = QRectF(1, 1, size - 2, size - 2)
    span = 360 / len(cols)
    p.setPen(Qt.PenStyle.NoPen)
    for i, c in enumerate(cols):
        p.setBrush(QColor(c))
        p.drawPie(r, int((90 - i * span) * 16), int(-span * 16))
    hr = size * hub_ratio
    if outline:     # separa o miolo do anel (miolo da mesma cor de um ramo)
        p.setBrush(QColor(outline))
        p.drawEllipse(QPointF(size / 2, size / 2), hr + 1.6, hr + 1.6)
    p.setBrush(QColor(hub))
    p.drawEllipse(QPointF(size / 2, size / 2), hr, hr)
    p.end()
    return pm


def quick_theme_pixmap(key: str, size: int = 30) -> QPixmap:
    """Círculo do tema rápido: miolo = cor do central, anel = cores dos ramos."""
    central, branches, bg = ct.quick_theme_colors(ct.QUICK_THEMES[key])
    return wheel_pixmap(branches, size, hub=central, hub_ratio=0.3, outline=bg)


def sample_for_preview() -> Topic:
    root = Topic(tr("Tema central"))
    for i in range(4):
        c = root.add_child(Topic(tr("Tópico {n}", n=i + 1)))
        for _j in range(2):
            c.add_child(Topic(tr("Subtópico")))
    return root


def preview_pixmap(colors, variant: int, size: QSize, layout: str = "mapa_mental") -> QPixmap:
    from mindforge.view.resources import render_thumbnail
    m = MindMap(sample_for_preview(), layout)
    m.settings["color_theme"] = {"id": "custom/preview", "name": "preview", "colors": list(colors)}
    if variant:
        m.settings["color_variant"] = variant
    return render_thumbnail(m, size)


_VARIANT_CACHE: dict = {}


def variant_thumbnail(colors, variant: int, layout: str, settings: dict, size: QSize) -> QPixmap:
    """Miniatura de uma variação: central + 4 principais, no esqueleto do mapa."""
    import json

    from mindforge.i18n import language
    from mindforge.view.resources import render_thumbnail
    key = (tuple(colors), variant, layout, json.dumps(settings, sort_keys=True, default=str),
           size.width(), size.height(), language())
    pm = _VARIANT_CACHE.get(key)
    if pm is None:
        root = Topic(tr("Tema central"))
        for i in range(4):          # só central + principais: a miniatura fica legível
            root.add_child(Topic(tr("Tópico {n}", n=i + 1)))
        m = MindMap(root, layout)
        m.settings = dict(settings)
        m.settings["color_theme"] = {"id": "custom/thumb", "name": "thumb", "colors": list(colors)}
        if variant:
            m.settings["color_variant"] = variant
        pm = render_thumbnail(m, size)
        if len(_VARIANT_CACHE) > 300:
            _VARIANT_CACHE.clear()
        _VARIANT_CACHE[key] = pm
    return pm


# ------------------------------------------------------------- botão do tema
class PaletteButton(QToolButton):
    """Botão do seletor: faixa com as 6 cores + nome + ⌄ (como no XMind)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(84, 22))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def show_palette(self, colors, name: str) -> None:
        self.setIcon(QIcon(strip_pixmap(colors, QSize(84, 22), 4)))
        label = name if len(name) <= 18 else name[:17] + "…"
        self.setText(f"  {label}   ⌄")
        self.setToolTip(name)


# ------------------------------------------------------------- popover
class PaletteItem(QToolButton):
    def __init__(self, palette: ct.Palette, selected: bool, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.setObjectName("PaletteItem")
        self.setCheckable(True)
        self.setChecked(selected)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIcon(QIcon(strip_pixmap(palette.colors)))
        self.setIconSize(STRIP_SIZE)
        self.setText(palette_name(palette))
        self.setToolTip(palette_name(palette))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class PalettePopup(QFrame):
    """Popover com as abas A Minha Cor / Colorido / Clássico."""
    picked = Signal(object)              # Palette
    create_requested = Signal()
    edit_requested = Signal(str)         # id da paleta personalizada
    make_default_requested = Signal()
    TABS = ("custom", "colorido", "classico")

    def __init__(self, parent: QWidget, current_id: Optional[str], is_default: bool):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.current_id = current_id
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        self.tabs = Segmented([tr("A Minha Cor"), tr("Colorido"), tr("Clássico")])
        lay.addWidget(self.tabs)
        self.stack = QStackedWidget()
        self.stack.setMinimumSize(360, 360)
        lay.addWidget(self.stack, 1)
        self._fill()
        group = (current_id or "").split("/", 1)[0]
        start = self.TABS.index(group) if group in self.TABS else 1
        self.tabs.set_index(start)
        self.stack.setCurrentIndex(start)
        self.tabs.changed.connect(self.stack.setCurrentIndex)
        foot = QHBoxLayout()
        self.default_btn = QPushButton(("✓ " if is_default else "") + tr("Usar como padrão para novos mapas"))
        self.default_btn.setObjectName("LinkButton")
        self.default_btn.setEnabled(not is_default)
        self.default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.default_btn.clicked.connect(self._make_default)
        foot.addWidget(self.default_btn)
        foot.addStretch(1)
        lay.addLayout(foot)

    def _page(self, palettes: list, empty_text: str = "") -> QWidget:
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(0, 0, 6, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for i, p in enumerate(palettes):
            b = PaletteItem(p, p.id == self.current_id)
            b.clicked.connect(lambda _c=False, pal=p: self._pick(pal))
            if p.group == "custom":
                b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                b.customContextMenuRequested.connect(lambda _pos, pal=p, btn=b: self._custom_menu(pal, btn))
            grid.addWidget(b, i // 2, i % 2)
        row = (len(palettes) + 1) // 2
        if empty_text:
            lab = QLabel(empty_text)
            lab.setObjectName("Muted")
            lab.setWordWrap(True)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lab, row, 0, 1, 2)
            row += 1
        grid.setRowStretch(row, 1)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(inner)
        return sa

    def _fill(self) -> None:
        store = palette_store()
        mine = QWidget()
        ml = QVBoxLayout(mine)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(8)
        ml.addWidget(self._page(store.palettes, "" if store.palettes else
                                tr("Você ainda não criou nenhuma paleta.")), 1)
        new = QPushButton(tr("Criar paleta…"))
        new.setEnabled(store.can_add())
        new.clicked.connect(self._create)
        ml.addWidget(new)
        self.stack.addWidget(mine)
        self.stack.addWidget(self._page(ct.COLORIDO))
        self.stack.addWidget(self._page(ct.CLASSICO))

    def _pick(self, p: ct.Palette) -> None:
        self.picked.emit(p)
        self.close()

    def _create(self) -> None:
        self.close()
        self.create_requested.emit()

    def _make_default(self) -> None:
        self.make_default_requested.emit()
        self.close()

    def _custom_menu(self, p: ct.Palette, btn: QWidget) -> None:
        store = palette_store()
        menu = QMenu(self)
        menu.addAction(tr("Editar…"), lambda: (self.close(), self.edit_requested.emit(p.id)))
        dup = menu.addAction(tr("Duplicar"), lambda: (store.duplicate(p.id), self._reload()))
        dup.setEnabled(store.can_add())
        menu.addAction(tr("Renomear…"), lambda: self._rename(p))
        menu.addSeparator()
        menu.addAction(tr("Excluir"), lambda: self._delete(p))
        menu.exec(btn.mapToGlobal(QPoint(10, btn.height() // 2)))

    def _reload(self) -> None:
        idx = self.stack.currentIndex()
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self._fill()
        self.stack.setCurrentIndex(idx)

    def _rename(self, p: ct.Palette) -> None:
        name, ok = QInputDialog.getText(self, tr("Renomear paleta"), tr("Nome:"), text=p.name)
        if ok and name.strip():
            palette_store().update(p.id, name, p.colors)
            self._reload()

    def _delete(self, p: ct.Palette) -> None:
        ans = QMessageBox.question(
            self, tr("Excluir paleta"),
            tr("Excluir a paleta “{nome}”? Os mapas que a usam continuam com as mesmas cores.", nome=p.name))
        if ans == QMessageBox.StandardButton.Yes:
            palette_store().delete(p.id)
            self._reload()


# ------------------------------------------------------- criar / editar paleta
class PaletteDialog(QDialog):
    """Criar novo tema de cores: 6 cores, nome e pré-visualização ao vivo."""
    PREVIEW = QSize(560, 250)

    def __init__(self, parent=None, palette: Optional[ct.Palette] = None):
        super().__init__(parent)
        self.editing = palette
        self.setWindowTitle(tr("Editar tema de cores") if palette else tr("Criar novo tema de cores"))
        self.colors: list[Optional[str]] = list(palette.colors) if palette else [None] * ct.N_COLORS
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        title = QLabel(self.windowTitle())
        title.setObjectName("Heading")
        lay.addWidget(title)
        hint = QLabel(tr("Escolha 6 cores para gerar um tema de cores personalizado."))
        hint.setObjectName("Muted")
        lay.addWidget(hint)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.slots: list[QToolButton] = []
        for i in range(ct.N_COLORS):
            b = QToolButton()
            b.setObjectName("ColorSlot")
            b.setFixedSize(46, 38)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tr("Cor {n} · clique direito: limpar", n=i + 1))
            b.clicked.connect(lambda _c=False, k=i: self._pick(k))
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _p, k=i: self._set(k, None))
            top.addWidget(b)
            self.slots.append(b)
        top.addSpacing(10)
        self.name = QLineEdit(palette.name if palette else palette_store().suggested_name())
        self.name.setMaxLength(60)
        self.name.setPlaceholderText(tr("Nome do tema"))
        self.name.textChanged.connect(lambda _t: self._validate())
        top.addWidget(self.name, 1)
        lay.addLayout(top)
        tools = QHBoxLayout()
        self.auto_btn = QPushButton(tr("Completar automaticamente"))
        self.auto_btn.setToolTip(tr("Escolha 1 ou 2 cores e o app sugere as outras em harmonia"))
        self.auto_btn.clicked.connect(self._auto)
        tools.addWidget(self.auto_btn)
        tools.addStretch(1)
        lay.addLayout(tools)
        self.preview = QLabel()
        self.preview.setObjectName("PreviewBox")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(self.PREVIEW)
        lay.addWidget(self.preview)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.save_btn = bb.button(QDialogButtonBox.StandardButton.Save)
        self.save_btn.setText(tr("Salvar"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._render_preview)
        self._refresh()

    # --------------------------------------------------------------- estado
    def _set(self, k: int, color: Optional[str]) -> None:
        self.colors[k] = color.upper() if color else None
        self._refresh()

    def _pick(self, k: int) -> None:
        pop = ColorPopup(self, self.colors[k], False, show_default=False)
        pop.picked.connect(lambda v, k=k: self._set(k, v) if v else None)
        pop.adjustSize()
        b = self.slots[k]
        g = b.mapToGlobal(QPoint(0, b.height() + 4))
        pop.move(g)
        pop.show()

    def _auto(self) -> None:
        chosen = [c for c in self.colors if c]
        self.colors = list(ct.auto_complete(chosen))
        self._refresh()

    def filled(self) -> list[str]:
        return [c for c in self.colors if c]

    def _refresh(self) -> None:
        for b, c in zip(self.slots, self.colors):
            if c:
                b.setIcon(QIcon(strip_pixmap([c], QSize(40, 32), 5)))
                b.setIconSize(QSize(40, 32))
                b.setText("")
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            else:
                b.setIcon(QIcon())
                b.setText("+")
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.auto_btn.setEnabled(0 < len(self.filled()) < ct.N_COLORS)
        self._validate()
        self._timer.start()

    def _validate(self) -> None:
        self.save_btn.setEnabled(len(self.filled()) == ct.N_COLORS and bool(self.name.text().strip()))

    def _render_preview(self) -> None:
        cols = self.filled()
        if len(cols) < ct.N_COLORS:
            self.preview.setPixmap(QPixmap())
            n = ct.N_COLORS - len(cols)
            self.preview.setText(ntr("Pré-visualizar tema de cores · falta {n} cor",
                                     "Pré-visualizar tema de cores · faltam {n} cores", n))
            return
        self.preview.setText("")
        self.preview.setPixmap(preview_pixmap(cols, 0, self.PREVIEW))

    def result_palette(self) -> tuple[str, list[str]]:
        return self.name.text().strip(), self.filled()


# ------------------------------------------------------------- roda de ramos
class WheelPopup(QFrame):
    picked = Signal(object)              # chave de BRANCH_PALETTES ou None ("Do tema")

    def __init__(self, parent: QWidget, current: Optional[str], theme_colors):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        grid = QGridLayout()
        grid.setSpacing(10)
        items = [(None, tr("Do tema"), theme_colors)] + \
                [(k, tr(label), cols) for k, (label, cols) in ct.BRANCH_PALETTES.items()]
        for i, (key, label, cols) in enumerate(items):
            b = QToolButton()
            b.setObjectName("WheelButton")
            b.setCheckable(True)
            b.setChecked(key == current)
            b.setIcon(QIcon(wheel_pixmap(cols, 44)))
            b.setIconSize(QSize(44, 44))
            b.setToolTip(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self._emit(k))
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)

    def _emit(self, key) -> None:
        self.picked.emit(key)
        self.close()


class WheelButton(QToolButton):
    picked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Swatch")
        self.setIconSize(QSize(22, 22))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.current: Optional[str] = None
        self.theme_colors: tuple = ()
        self.clicked.connect(self._open)

    def show_value(self, key: Optional[str], theme_colors) -> None:
        self.current = key
        self.theme_colors = tuple(theme_colors)
        cols = ct.BRANCH_PALETTES[key][1] if key in ct.BRANCH_PALETTES else self.theme_colors
        self.setIcon(QIcon(wheel_pixmap(cols, 22)))
        self.setToolTip(tr(ct.BRANCH_PALETTES[key][0]) if key in ct.BRANCH_PALETTES else tr("Do tema"))

    def _open(self) -> None:
        pop = WheelPopup(self.window(), self.current, self.theme_colors)
        pop.picked.connect(self.picked.emit)
        pop.adjustSize()
        g = self.mapToGlobal(QPoint(self.width(), self.height() + 4))
        pop.move(g.x() - pop.width(), g.y())
        pop.show()
