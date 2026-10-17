"""Painel lateral no estilo do XMind: abas tr("Estilo") (tópico) e tr("Mapa").

A aba Estilo é dividida em seções recolhíveis (Forma, Limite, Texto, Ramo,
Marcadores, Nota). Com vários tópicos selecionados, valores diferentes
aparecem como "—" e qualquer alteração vale para todos.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QCompleter, QGridLayout, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

from mindforge import colorthemes as ct
from mindforge.i18n import N_, ntr, tr
from mindforge.layouts import LAYOUTS
from mindforge.model import ops
from mindforge.themes import (
    BORDER_STYLES, BRANCH_STYLES, LEVELS, LINE_ENDS, LINE_PATTERNS, SHAPES, TEXT_CASES,
)
from mindforge.view import style
from mindforge.view.icons import branch_style_icon, icon, line_end_icon, pattern_icon, shape_icon
from mindforge.view.colorpanel import (
    PaletteButton, PaletteDialog, PalettePopup, WheelButton, palette_name, palette_store,
    variant_thumbnail,
)
from mindforge.view.painting import MARKER_LABELS, default_family, ensure_fonts, font_available
from mindforge.view.resources import marker_icon
from mindforge.view.widgets import (
    CardButton, CollapsibleSection, IconPickerButton, Segmented, SkeletonPopup, SwatchButton, row,
    section_title, separator, set_combo, thumbnail,
)

FONT_SIZES = [10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 28, 32, 40, 48, 64]
GLOBAL_FONTS = ["Inter", "Helvetica Neue", "Avenir Next", "Roboto", "Open Sans", "Lato", "Montserrat",
                "Poppins", "Segoe UI", "Arial", "Verdana", "Georgia", "Times New Roman", "Menlo",
                "DejaVu Sans", "Noto Sans"]
MAP_LINE_WIDTHS = [("padrao", N_("Predefinição")), ("fina", N_("Fina")), ("grossa", N_("Grossa"))]
LEVEL_NAMES = {"root": N_("Tema central"), "main": N_("Tópico principal"), "sub": N_("Subtópico"),
               "floating": N_("Tópico flutuante")}
THEME_THUMB = QSize(82, 54)
WEIGHT_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}


@lru_cache(maxsize=1)
def font_families() -> tuple[str, ...]:
    ensure_fonts()
    fams = [f for f in QFontDatabase.families()
            if not f.startswith((".", "@")) and not QFontDatabase.isPrivateFamily(f)]
    return tuple(sorted(set(fams), key=str.casefold))


@lru_cache(maxsize=256)
def font_weights(family: str) -> tuple[tuple[int, str], ...]:
    """Pesos reais disponíveis na fonte (sem os itálicos)."""
    out: dict[int, str] = {}
    for st in QFontDatabase.styles(family):
        if QFontDatabase.italic(family, st):
            continue
        w = int(round(QFontDatabase.weight(family, st) / 100.0) * 100)
        out.setdefault(w, st)
    if not out:
        out = {400: "Regular", 700: "Bold"}
    return tuple(sorted(out.items()))


def _scroll(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QScrollArea.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


def _combo(items: list[tuple], default: Optional[str] = N_("Padrão")) -> QComboBox:
    c = QComboBox()
    if default:
        c.addItem(tr(default), None)
    for item in items:
        if len(item) == 3:
            c.addItem(item[2], tr(item[1]), item[0])
        else:
            c.addItem(tr(item[1]), item[0])
    return c


class FormatPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.canvas = None
        self._refreshing = False
        self._note_tid: Optional[str] = None
        self._note_timer = QTimer(self)
        self._note_timer.setSingleShot(True)
        self._note_timer.setInterval(700)
        self._note_timer.timeout.connect(self._commit_note)
        self._theme_thumbs_key = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 8)
        outer.setSpacing(12)
        self.tabs = Segmented([tr("Estilo"), tr("Mapa")])
        outer.addWidget(self.tabs)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.tabs.changed.connect(self.pages.setCurrentIndex)

        self._build_style_page()
        self._build_map_page()
        self.setMinimumWidth(296)
        self.setMaximumWidth(400)

    # ================================================================ Estilo
    def _build_style_page(self) -> None:
        self.style_stack = QStackedWidget()
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch(1)
        self._empty_icon = QLabel()
        self._empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(self._empty_icon)
        t = QLabel(tr("Nenhum tópico selecionado"))
        t.setObjectName("Heading")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(t)
        hint = QLabel(tr("Clique em um tópico para editar o estilo.\n\n"
                         "Tab  cria subtópico\nEnter  cria tópico irmão\nF2 ou Espaço  edita o texto"))
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(hint)
        el.addStretch(2)
        self.style_stack.addWidget(empty)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)

        # -------------------------------------------------- cabeçalho
        self.heading = QLabel()
        self.heading.setObjectName("Heading")
        self.heading.setWordWrap(True)
        self.sub_heading = QLabel()
        self.sub_heading.setObjectName("Muted")
        lay.addWidget(self.heading)
        lay.addWidget(self.sub_heading)
        hb = QHBoxLayout()
        self.level_btn = QPushButton(tr("Aplicar ao nível"))
        self.level_btn.setToolTip(tr("Copia este estilo para todos os tópicos do mesmo nível"))
        self.level_btn.clicked.connect(self._apply_to_level)
        self.reset_btn = QPushButton(tr("Repor estilo"))
        self.reset_btn.setToolTip(tr("Volta ao estilo padrão do tema"))
        self.reset_btn.clicked.connect(self._reset_style)
        hb.addWidget(self.level_btn)
        hb.addWidget(self.reset_btn)
        lay.addLayout(hb)
        lay.addWidget(separator())

        # -------------------------------------------------- Forma
        sec = CollapsibleSection(tr("Forma"), "forma")
        grid = QGridLayout()
        grid.setSpacing(6)
        self.shape_btns: dict[str, QToolButton] = {}
        shapes = [("padrao", N_("Automática (do tema)"))] + list(SHAPES.items())
        for i, (key, label) in enumerate(shapes):
            b = QToolButton()
            b.setObjectName("ShapeButton")
            b.setCheckable(True)
            b.setToolTip(tr(label))
            b.setIconSize(QSize(34, 22))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self.set_style("shape", None if k == "padrao" else k))
            grid.addWidget(b, i // 5, i % 5)
            self.shape_btns[key] = b
        sec.add(grid)
        self.fill_btn = SwatchButton(True)
        self.fill_btn.picked.connect(lambda v: self.set_style("fill", v))
        sec.add(row(tr("Preenchimento"), self.fill_btn))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 2000)
        self.width_spin.setSpecialValueText(tr("Auto"))
        self.width_spin.setSuffix(" px")
        self.width_spin.setSingleStep(10)
        self.width_spin.setToolTip(tr("Largura fixa do tópico (o texto quebra para caber). 0 = automática"))
        self.width_spin.editingFinished.connect(self._on_width)
        self.width_fit = QPushButton(tr("Ajustar"))
        self.width_fit.setToolTip(tr("Volta à largura automática"))
        self.width_fit.clicked.connect(lambda: self.set_style("width", None))
        sec.add(row(tr("Largura"), self.width_spin, self.width_fit))
        lay.addWidget(sec)
        self._sections = [sec]

        # -------------------------------------------------- Limite
        sec = CollapsibleSection(tr("Limite"), "limite")
        self.border_style = _combo([(k, v) for k, v in BORDER_STYLES.items()])
        self.border_style.activated.connect(lambda _i: self.set_style("border_style", self.border_style.currentData()))
        self.border_level = _combo(list(LEVELS.items()))
        self.border_level.activated.connect(lambda _i: self.set_style("border_level", self.border_level.currentData()))
        self.border_btn = SwatchButton(True)
        self.border_btn.picked.connect(lambda v: self.set_style("border", v))
        sec.add(row(tr("Estilo"), self.border_style))
        sec.add(row(tr("Espessura"), self.border_level))
        sec.add(row(tr("Cor"), self.border_btn))
        lay.addWidget(sec)
        self._sections.append(sec)

        # -------------------------------------------------- Texto
        sec = CollapsibleSection(tr("Texto"), "texto")
        self.font_combo = QComboBox()
        self.font_combo.setEditable(True)
        self.font_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.font_combo.setMaxVisibleItems(18)
        self._fonts_filled = False
        self.font_combo.activated.connect(self._on_font_activated)
        self.font_combo.lineEdit().editingFinished.connect(self._on_font_typed)
        sec.add(self.font_combo)
        self.font_warning = QLabel(tr("Fonte não instalada neste computador — usando substituta."))
        self.font_warning.setObjectName("Muted")
        self.font_warning.setWordWrap(True)
        self.font_warning.hide()
        sec.add(self.font_warning)
        h = QHBoxLayout()
        h.setSpacing(6)
        self.weight_combo = QComboBox()
        self.weight_combo.activated.connect(lambda _i: self.set_styles(
            {"font_weight": self.weight_combo.currentData(), "bold": None}))
        self.size_combo = QComboBox()
        self.size_combo.setEditable(True)
        self.size_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.size_combo.addItem(tr("Auto"), None)
        for s in FONT_SIZES:
            self.size_combo.addItem(str(s), s)
        self.size_combo.activated.connect(lambda _i: self.set_style("font_size", self.size_combo.currentData()))
        self.size_combo.lineEdit().editingFinished.connect(self._on_size_typed)
        self.size_combo.setFixedWidth(82)
        h.addWidget(self.weight_combo, 1)
        h.addWidget(self.size_combo)
        sec.add(h)
        h = QHBoxLayout()
        h.setSpacing(6)
        self.bold = self._toggle(tr("N"), tr("Negrito"), bold=True)      # "N" de Negrito; "B" em inglês
        self.bold.clicked.connect(lambda on: self.set_styles({"font_weight": 700 if on else 400, "bold": None}))
        self.italic = self._toggle("I", tr("Itálico"), italic=True)
        self.italic.clicked.connect(lambda on: self.set_style("italic", bool(on)))
        self.strike = self._toggle("S", tr("Riscado"), strike=True)
        self.strike.clicked.connect(lambda on: self.set_style("strike", bool(on)))
        self.case_btn = QToolButton()
        self.case_btn.setObjectName("StyleToggle")
        self.case_btn.setText("Tt")
        self.case_btn.setToolTip(tr("Maiúsculas e minúsculas"))
        self.case_btn.setFixedSize(38, 28)
        self.case_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        cm = QMenu(self.case_btn)
        self.case_actions = {}
        for key, label in TEXT_CASES.items():
            a = cm.addAction(tr(label), lambda k=key: self.set_style("text_case", None if k == "normal" else k))
            a.setCheckable(True)
            self.case_actions[key] = a
        self.case_btn.setMenu(cm)
        self.text_btn = SwatchButton(False)
        self.text_btn.picked.connect(lambda v: self.set_style("text_color", v))
        for w in (self.bold, self.italic, self.strike, self.case_btn):
            h.addWidget(w)
        h.addStretch(1)
        h.addWidget(self.text_btn)
        sec.add(h)
        h = QHBoxLayout()
        h.setSpacing(6)
        self.align_group = QButtonGroup(self)
        self.align_group.setExclusive(True)
        self.align_btns: dict[str, QToolButton] = {}
        for key, tip in (("left", tr("Alinhar à esquerda")), ("center", tr("Centralizar")), ("right", tr("Alinhar à direita"))):
            b = QToolButton()
            b.setObjectName("StyleToggle")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setFixedHeight(28)
            b.setSizePolicy(b.sizePolicy().horizontalPolicy().Expanding, b.sizePolicy().verticalPolicy())
            b.clicked.connect(lambda _c=False, k=key: self.set_style("align", k))
            self.align_group.addButton(b)
            self.align_btns[key] = b
            h.addWidget(b)
        sec.add(h)
        lay.addWidget(sec)
        self._sections.append(sec)

        # -------------------------------------------------- Ramo
        sec = CollapsibleSection(tr("Ramo"), "ramo")
        self.branch_btn = IconPickerButton(self._branch_items, 2, QSize(44, 28), tr("Padrão do esqueleto"))
        self.branch_btn.picked.connect(lambda k: self.set_style("branch_style", k, branch=True))
        self.pattern_combo = QComboBox()
        self.pattern_combo.setIconSize(QSize(56, 14))
        self.pattern_combo.activated.connect(lambda _i: self.set_style(
            "line_pattern", self.pattern_combo.currentData(), branch=True))
        self.end_btn = IconPickerButton(self._end_items, 2, QSize(44, 20), tr("Padrão"))
        self.end_btn.picked.connect(lambda k: self.set_style("line_end", k, branch=True))
        self.line_level = _combo(list(LEVELS.items()))
        self.line_level.activated.connect(lambda _i: self.set_style(
            "line_level", self.line_level.currentData(), branch=True))
        self.line_btn = SwatchButton(False)
        self.line_btn.picked.connect(lambda v: self.set_style("line_color", v, branch=True))
        self.branch_desc = QCheckBox(tr("Aplicar também aos descendentes"))
        self.branch_hint = QLabel()
        self.branch_hint.setObjectName("Muted")
        self.branch_hint.setWordWrap(True)
        sec.add(row(tr("Estilo"), self.branch_btn))
        sec.add(row(tr("Linha"), self.pattern_combo))
        sec.add(row(tr("Fim"), self.end_btn))
        sec.add(row(tr("Espessura"), self.line_level))
        sec.add(row(tr("Cor"), self.line_btn))
        sec.add(self.branch_desc)
        sec.add(self.branch_hint)
        lay.addWidget(sec)
        self._sections.append(sec)

        # -------------------------------------------------- Marcadores
        sec = CollapsibleSection(tr("Marcadores"), "marcadores")
        mg = QGridLayout()
        mg.setSpacing(6)
        self.marker_btns: dict[str, QToolButton] = {}
        for i, key in enumerate(ops.ALL_MARKERS):
            b = QToolButton()
            b.setObjectName("MarkerButton")
            b.setIcon(marker_icon(key))
            b.setIconSize(QSize(20, 20))
            b.setCheckable(True)
            b.setToolTip(tr(MARKER_LABELS.get(key, key)))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _on, k=key: self._toggle_marker(k))
            mg.addWidget(b, i // 4, i % 4)
            self.marker_btns[key] = b
        sec.add(mg)
        lay.addWidget(sec)
        self._sections.append(sec)

        # -------------------------------------------------- Nota
        sec = CollapsibleSection(tr("Nota"), "nota")
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText(tr("Escreva uma nota para este tópico…"))
        self.note.setMinimumHeight(110)
        self.note.textChanged.connect(lambda: self._note_timer.start())
        self.note.installEventFilter(self)
        sec.add(self.note)
        lay.addWidget(sec)
        self._sections.append(sec)
        lay.addStretch(1)
        self.style_stack.addWidget(_scroll(inner))
        self.pages.addWidget(self.style_stack)

    def _toggle(self, text: str, tip: str, bold: bool = False, italic: bool = False,
                strike: bool = False) -> QToolButton:
        b = QToolButton()
        b.setObjectName("StyleToggle")
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(True)
        b.setFixedSize(32, 28)
        f = b.font()
        f.setBold(bold)
        f.setItalic(italic)
        f.setStrikeOut(strike)
        b.setFont(f)
        return b

    def _branch_items(self) -> list:
        col = style.chrome().text
        return [(k, branch_style_icon(k, col), tr(v)) for k, v in BRANCH_STYLES.items()]

    def _end_items(self) -> list:
        col = style.chrome().text
        return [(k, line_end_icon(k, col), tr(v)) for k, v in LINE_ENDS.items()]

    # ================================================================== Mapa
    def _build_map_page(self) -> None:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)

        lay.addWidget(section_title(tr("Esqueleto")))
        self.skeleton_btn = CardButton()
        self.skeleton_btn.clicked.connect(self._open_skeletons)
        lay.addWidget(self.skeleton_btn)

        lay.addWidget(separator())
        lay.addWidget(section_title(tr("Tema de cores")))
        th_row = QHBoxLayout()
        th_row.setSpacing(6)
        self.palette_btn = PaletteButton()
        self.palette_btn.clicked.connect(self._open_palettes)
        th_row.addWidget(self.palette_btn, 1)
        self.palette_add = QToolButton()
        self.palette_add.setObjectName("Card")
        self.palette_add.setText("+")
        self.palette_add.setToolTip(tr("Criar novo tema de cores"))
        self.palette_add.setFixedWidth(40)
        self.palette_add.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.palette_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.palette_add.clicked.connect(lambda: self._edit_palette(None))
        th_row.addWidget(self.palette_add)
        lay.addLayout(th_row)
        # as 6 variações do tema (miniaturas), como no XMind
        self.theme_grid = QGridLayout()
        self.theme_grid.setSpacing(6)
        self.variant_btns: list[QToolButton] = []
        for i, label in enumerate(ct.VARIANTS):
            b = QToolButton()
            b.setObjectName("ThemeCard")
            b.setCheckable(True)
            b.setToolTip(tr(label))
            b.setIconSize(THEME_THUMB)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=i: self._set_variant(k))
            self.theme_grid.addWidget(b, i // 3, i % 3)
            self.variant_btns.append(b)
        lay.addLayout(self.theme_grid)
        self.theme_name = QLabel()
        self.theme_name.setObjectName("Muted")
        lay.addWidget(self.theme_name)

        lay.addWidget(separator())
        self.bg_btn = SwatchButton(False)
        self.bg_btn.picked.connect(lambda v: self._set_setting("background", v))
        lay.addLayout(row(tr("Cor de fundo"), self.bg_btn))

        lay.addWidget(separator())
        lay.addWidget(section_title(tr("Tipo de letra global")))
        self.map_font = QComboBox()
        self.map_font.addItem(tr("Predefinição (Inter)"), None)
        for fam in GLOBAL_FONTS[1:]:
            if font_available(fam):
                self.map_font.addItem(fam, fam)
        self.map_font.activated.connect(lambda _i: self._set_setting("font", self.map_font.currentData()))
        lay.addWidget(self.map_font)

        lay.addWidget(section_title(tr("Ramos")))
        self.map_branch = IconPickerButton(self._branch_items, 2, QSize(44, 28), tr("Padrão do esqueleto"))
        self.map_branch.picked.connect(lambda k: self._set_setting("branch_style", k))
        lay.addLayout(row(tr("Estilo de ramo padrão"), self.map_branch))
        self.map_line = QComboBox()
        for key, label in MAP_LINE_WIDTHS:
            self.map_line.addItem(tr(label), key)
        self.map_line.activated.connect(lambda _i: self._set_setting("line_width", self.map_line.currentData()))
        lay.addLayout(row(tr("Largura da linha"), self.map_line))
        self.rainbow = QCheckBox(tr("Ramo colorido"))
        self.rainbow.clicked.connect(lambda on: self._set_setting("rainbow", bool(on)))
        self.wheel_btn = WheelButton()
        self.wheel_btn.picked.connect(lambda k: self._set_setting("branch_palette", k))
        self.static_btn = SwatchButton(False)
        self.static_btn.setToolTip(tr("Cor única dos ramos"))
        self.static_btn.picked.connect(lambda v: self._set_setting("static_color", v))
        rb_row = QHBoxLayout()
        rb_row.addWidget(self.rainbow)
        rb_row.addStretch(1)
        rb_row.addWidget(self.wheel_btn)
        rb_row.addWidget(self.static_btn)
        lay.addLayout(rb_row)

        lay.addWidget(separator())
        lay.addWidget(section_title(tr("Estilo do mapa")))
        self.compact = QCheckBox(tr("Compactar mapa"))
        self.compact.clicked.connect(lambda on: self._set_setting("compact", bool(on)))
        lay.addWidget(self.compact)
        self.fish_align = QCheckBox(tr("Alinhar tópicos principais (espinha de peixe)"))
        self.fish_align.setToolTip(tr("Todas as espinhas com o mesmo comprimento, em fileiras retas"))
        self.fish_align.clicked.connect(lambda on: self._set_setting("fishbone_align", bool(on)))
        lay.addWidget(self.fish_align)
        lay.addStretch(1)
        self.pages.addWidget(_scroll(inner))

    # ============================================================ conexão
    def set_canvas(self, canvas) -> None:
        self.canvas = canvas
        canvas.current_changed.connect(self.refresh)
        canvas.doc.changed.connect(self.refresh)
        self.refresh_chrome()

    def refresh_chrome(self) -> None:
        """Atualiza ícones quando muda o modo claro/escuro."""
        c = style.chrome()
        for key, b in self.shape_btns.items():
            b.setIcon(shape_icon(key, c.text, c.surface_hover))
        self._empty_icon.setPixmap(icon("topic", c.muted, 44).pixmap(44, 44))
        for key, b in self.align_btns.items():
            b.setIcon(icon(f"align_{key}", c.text, 18))
        self.pattern_combo.clear()
        self.pattern_combo.addItem(tr("Padrão"), None)
        for key, label in LINE_PATTERNS.items():
            self.pattern_combo.addItem(pattern_icon(key, c.text), "" if key != "nenhum" else tr(label), key)
        for sec in self._sections:
            sec._apply()
        self.refresh()

    def eventFilter(self, obj, ev):
        if obj is self.note and ev.type() == ev.Type.FocusOut:
            self._commit_note()
        return super().eventFilter(obj, ev)

    def _ids(self) -> list[str]:
        return self.canvas.mscene.selected_topic_ids() if self.canvas else []

    def _ensure_fonts_listed(self) -> None:
        if self._fonts_filled:
            return
        self._fonts_filled = True
        self.font_combo.blockSignals(True)
        self.font_combo.addItem(tr("Padrão ({fonte})", fonte=default_family()), None)
        for fam in font_families():
            self.font_combo.addItem(fam, fam)
        comp = QCompleter([self.font_combo.itemText(i) for i in range(self.font_combo.count())], self.font_combo)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.font_combo.setCompleter(comp)
        self.font_combo.blockSignals(False)

    # ============================================================= refresh
    def refresh(self) -> None:
        if self.canvas is None or self._refreshing:
            return
        self._refreshing = True
        try:
            self._refresh_map()
            self._refresh_style()
        finally:
            self._refreshing = False

    def _values(self, fn: Callable) -> tuple[object, bool]:
        """(valor do tópico atual, há valores diferentes na seleção?)."""
        m = self.canvas.doc.map
        vis = self.canvas.mscene.visuals
        cur = self.canvas.current()
        vals = []
        for tid in self._ids():
            t = m.find(tid)
            if t is not None and tid in vis:
                vals.append(fn(t, vis[tid].style))
        t = m.find(cur)
        current = fn(t, vis[cur].style) if t is not None and cur in vis else (vals[0] if vals else None)
        return current, len(set(map(repr, vals))) > 1

    def _refresh_style(self) -> None:
        m = self.canvas.doc.map
        ids = self._ids()
        cur = self.canvas.current()
        topic = m.find(cur) if cur else None
        if topic is None or cur not in self.canvas.mscene.visuals:
            self.style_stack.setCurrentIndex(0)
            self._set_note_text(None, "")
            return
        self.style_stack.setCurrentIndex(1)
        name = topic.text.split("\n")[0]
        self.heading.setText(name if len(name) <= 48 else name[:47] + "…")
        level = self.canvas.mscene.visuals[cur].level
        if len(ids) > 1:
            self.sub_heading.setText(ntr("{n} tópico selecionado", "{n} tópicos selecionados", len(ids)))
        else:
            self.sub_heading.setText(tr(LEVEL_NAMES.get(level, "")))
        self.level_btn.setEnabled(len(ids) == 1)

        # Forma
        shape, mixed = self._values(lambda t, s: t.style.get("shape") or "padrao")
        for k, b in self.shape_btns.items():
            b.setChecked(not mixed and k == shape)
        fill, mixed = self._values(lambda t, s: s.fill or "")
        self.fill_btn.show_color(None if mixed else fill)
        width, mixed = self._values(lambda t, s: int(t.style.get("width") or 0))
        self.width_spin.blockSignals(True)
        self.width_spin.setValue(0 if mixed else int(width))
        self.width_spin.blockSignals(False)

        # Limite
        v, mixed = self._values(lambda t, s: t.style.get("border_style"))
        set_combo(self.border_style, v, mixed)
        v, mixed = self._values(lambda t, s: t.style.get("border_level"))
        set_combo(self.border_level, v, mixed)
        v, mixed = self._values(lambda t, s: (s.border or "") if s.border_width > 0 else "")
        self.border_btn.show_color(None if mixed else v)

        # Texto
        self._ensure_fonts_listed()
        fam, mixed = self._values(lambda t, s: t.style.get("font_family"))
        set_combo(self.font_combo, fam, mixed)
        if not mixed and fam and self.font_combo.findData(fam) < 0:
            self.font_combo.setEditText(fam)
        self.font_warning.setVisible(bool(fam) and not mixed and not font_available(fam))
        real_family = fam if fam and font_available(fam) else (m.setting("font") or default_family())
        self.weight_combo.blockSignals(True)
        self.weight_combo.clear()
        for w, label in font_weights(real_family):
            self.weight_combo.addItem(label or WEIGHT_NAMES.get(w, str(w)), w)
        self.weight_combo.blockSignals(False)
        wv, mixed = self._values(lambda t, s: s.weight)
        if not mixed and self.weight_combo.findData(wv) < 0:
            self.weight_combo.addItem(WEIGHT_NAMES.get(wv, str(wv)), wv)
        set_combo(self.weight_combo, wv, mixed)
        fs, mixed = self._values(lambda t, s: t.style.get("font_size"))
        self.size_combo.blockSignals(True)
        if mixed:
            self.size_combo.setEditText("—")
        elif fs is None:
            real, _ = self._values(lambda t, s: int(round(s.font_size)))
            self.size_combo.setCurrentIndex(0)
            self.size_combo.setEditText(f"{real}")
        else:
            self.size_combo.setEditText(str(int(fs)))
        self.size_combo.blockSignals(False)
        for btn, fn in ((self.bold, lambda t, s: s.bold), (self.italic, lambda t, s: s.italic),
                        (self.strike, lambda t, s: s.strike)):
            v, mixed = self._values(fn)
            btn.setChecked(bool(v) and not mixed)
        case, mixed = self._values(lambda t, s: s.text_case)
        for k, a in self.case_actions.items():
            a.setChecked(not mixed and k == case)
        tc, mixed = self._values(lambda t, s: s.text_color)
        self.text_btn.show_color(None if mixed else tc)
        al, mixed = self._values(lambda t, s: s.resolved_align)
        self.align_group.setExclusive(False)
        for k, b in self.align_btns.items():
            b.setChecked(not mixed and k == al)
        self.align_group.setExclusive(True)

        # Ramo
        groups = {g.parent: g for g in self.canvas.mscene.layout_result.groups}
        styled = [tid for tid in ids if tid in groups and groups[tid].style != "indent"]
        any_group = any(tid in groups for tid in ids)
        self.branch_btn.setEnabled(bool(styled))
        if not any_group:
            self.branch_hint.setText(tr("As opções valem para as linhas que saem deste tópico "
                                        "para os subtópicos dele."))
        elif not styled:
            self.branch_hint.setText(tr("Neste esqueleto o formato das linhas destes subtópicos é fixo; "
                                        "linha, fim, espessura e cor continuam valendo."))
        else:
            self.branch_hint.setText("")
        self.branch_hint.setVisible(bool(self.branch_hint.text()))
        col = style.chrome().text
        bs, mixed = self._values(lambda t, s: t.style.get("branch_style"))
        if bs:
            self.branch_btn.show_value(bs, branch_style_icon(bs, col), mixed)
        else:
            default = (groups[cur].style if cur in groups and groups[cur].style != "indent"
                       else (m.setting("branch_style") or LAYOUTS[m.layout].default_branch))
            self.branch_btn.show_value(None, branch_style_icon(m.setting("branch_style") or default, col), mixed)
        lp, mixed = self._values(lambda t, s: t.style.get("line_pattern"))
        set_combo(self.pattern_combo, lp, mixed)
        le, mixed = self._values(lambda t, s: s.line_end)
        self.end_btn.show_value(le, line_end_icon(le or "nenhum", col), mixed)
        ll, mixed = self._values(lambda t, s: t.style.get("line_level"))
        set_combo(self.line_level, ll, mixed)
        lc, mixed = self._values(lambda t, s: s.line_color)
        self.line_btn.show_color(None if mixed else lc)

        # Marcadores e nota
        for k, b in self.marker_btns.items():
            b.setChecked(k in topic.markers)
        if not (self.note.hasFocus() and self._note_tid == topic.id):
            self._set_note_text(topic.id, topic.note)

    def _refresh_map(self) -> None:
        m = self.canvas.doc.map
        lay = LAYOUTS.get(m.layout)
        self.skeleton_btn.setText(f"  {tr(lay.label) if lay else m.layout}   ⌄")
        self.skeleton_btn.setIcon(QIcon(thumbnail(m.layout, "_esqueleto", QSize(96, 56))))
        pal = ct.current_palette(m)
        legacy = pal is None
        shown = pal or ct.legacy_palette(m.theme)
        self.palette_btn.show_palette(shown.colors, palette_name(shown) if not legacy else tr(shown.name))
        variant = int(m.setting("color_variant") or 0)
        key = (m.layout, shown.colors, tuple(sorted((k, str(v)) for k, v in m.settings.items()
                                                    if k in ("rainbow", "line_width", "branch_style",
                                                             "branch_palette", "static_color"))))
        if key != self._theme_thumbs_key:
            self._theme_thumbs_key = key
            settings = {k: v for k, v in m.settings.items()
                        if k in ("rainbow", "line_width", "branch_style", "branch_palette", "static_color")}
            for i, b in enumerate(self.variant_btns):
                b.setIcon(QIcon(variant_thumbnail(shown.colors, i, m.layout, settings, THEME_THUMB)))
        for i, b in enumerate(self.variant_btns):
            b.setChecked(not legacy and i == variant)
        self.theme_name.setText(tr("{tema} · {variacao}", tema=palette_name(shown), variacao=tr(ct.VARIANTS[variant]))
                                if not legacy else tr("Tema anterior: escolha uma variação para atualizar"))
        self.bg_btn.show_color(self.canvas.mscene.background_color)
        set_combo(self.map_font, m.setting("font"))
        set_combo(self.map_line, m.setting("line_width"))
        col = style.chrome().text
        mb = m.setting("branch_style")
        self.map_branch.show_value(mb, branch_style_icon(mb or (lay.default_branch if lay else "colchete_curvo"), col))
        rainbow = bool(m.setting("rainbow"))
        self.rainbow.setChecked(rainbow)
        theme = ct.effective_theme(m)
        self.wheel_btn.setVisible(rainbow)
        self.wheel_btn.show_value(m.setting("branch_palette"), theme.palette)
        self.static_btn.setVisible(not rainbow)
        self.static_btn.show_color(m.setting("static_color") or theme.mono)
        self.compact.setChecked(bool(m.setting("compact")))
        self.fish_align.setChecked(bool(m.setting("fishbone_align")))
        self.fish_align.setVisible(m.layout == "espinha_peixe")

    def _set_note_text(self, tid: Optional[str], text: str) -> None:
        if self._note_timer.isActive():
            self._commit_note()
        self._note_tid = tid
        self.note.blockSignals(True)
        self.note.setPlainText(text)
        self.note.blockSignals(False)

    # =============================================================== ações
    def set_style(self, key: str, value, branch: bool = False) -> None:
        self.set_styles({key: value}, branch)

    def set_styles(self, values: dict, branch: bool = False) -> None:
        ids = self._ids()
        if not ids or self.canvas is None or self._refreshing:
            return
        self.canvas.commit_edit(refocus=False)
        sel = list(ids)
        if branch and self.branch_desc.isChecked():
            ids = ops.with_descendants(self.canvas.doc.map, ids)
        self.canvas.doc.apply(N_("Formatar tópico"), lambda m: ops.set_styles(m, ids, values), select=sel)

    def _on_width(self) -> None:
        v = self.width_spin.value()
        self.set_style("width", v if v >= 40 else None)

    def _on_size_typed(self) -> None:
        txt = self.size_combo.currentText().strip().replace("px", "").strip()
        if txt.lower() == "auto":
            self.set_style("font_size", None)
            return
        try:
            v = max(6, min(200, int(float(txt.replace(",", ".")))))
        except ValueError:
            self.refresh()
            return
        self.set_style("font_size", v)

    def _on_font_activated(self, index: int) -> None:
        self.set_style("font_family", self.font_combo.itemData(index))

    def _on_font_typed(self) -> None:
        txt = self.font_combo.currentText().strip()
        i = self.font_combo.findText(txt, Qt.MatchFlag.MatchFixedString)
        if i >= 0:
            data = self.font_combo.itemData(i)
            m = self.canvas.doc.map if self.canvas else None
            t = m.find(self.canvas.current()) if m else None
            if t is not None and t.style.get("font_family") == data:
                return
            self.set_style("font_family", data)
        else:
            self.refresh()

    def _reset_style(self) -> None:
        ids = self._ids()
        if ids:
            self.canvas.doc.apply(N_("Repor estilo"), lambda m: ops.clear_style(m, ids), select=ids)

    def _apply_to_level(self) -> None:
        cur = self.canvas.current() if self.canvas else None
        if cur:
            self.canvas.doc.apply(N_("Aplicar estilo ao nível"), lambda m: ops.apply_style_to_level(m, cur),
                                  select=[cur])

    def _toggle_marker(self, key: str) -> None:
        ids = self._ids()
        if ids:
            self.canvas.doc.apply(N_("Marcador"), lambda m: ops.toggle_marker(m, ids, key), select=ids)

    def _commit_note(self) -> None:
        self._note_timer.stop()
        tid = self._note_tid
        if self.canvas is None or tid is None or self.canvas.doc.map.find(tid) is None:
            return
        text = self.note.toPlainText()
        if self.canvas.doc.map.find(tid).note == text:
            return
        self.canvas.doc.apply(N_("Editar nota"), lambda m: ops.set_note(m, tid, text),
                              merge_key=f"note:{tid}")

    def _open_skeletons(self) -> None:
        pop = SkeletonPopup(self.window(), self.canvas.doc.map.layout)
        pop.picked.connect(self._set_layout)
        pop.adjustSize()
        g = self.skeleton_btn.mapToGlobal(QPoint(0, 0))
        pop.move(g.x() - pop.width() - 12, max(0, g.y() - 40))
        pop.show()

    def _set_layout(self, key: str) -> None:
        self.canvas.commit_edit(refocus=False)
        self.canvas.doc.apply(N_("Mudar esqueleto"), lambda m: ops.set_layout(m, key))
        QTimer.singleShot(0, self.canvas.zoom_fit)

    # ------------------------------------------------------- temas de cores
    def _apply_colors(self, palette_setting: Optional[dict], variant: Optional[int]) -> None:
        def fn(m):
            ops.set_color_theme(m, palette_setting, variant)
            m.settings.pop("background", None)      # o fundo faz parte do tema (ex.: Noturno)
        self.canvas.commit_edit()
        self.canvas.doc.apply(N_("Mudar tema de cores"), fn)

    def _open_palettes(self) -> None:
        m = self.canvas.doc.map
        pal = ct.current_palette(m)
        dp, dv = ct.default_for_new_maps()
        is_default = pal is not None and list(pal.colors) == dp["colors"] and \
            int(m.setting("color_variant") or 0) == dv
        pop = PalettePopup(self.window(), pal.id if pal else None, is_default)
        pop.picked.connect(lambda p: self._apply_colors(p.as_setting(), None if ct.current_palette(
            self.canvas.doc.map) else 0))
        pop.create_requested.connect(lambda: self._edit_palette(None))
        pop.edit_requested.connect(self._edit_palette)
        pop.make_default_requested.connect(self._make_default)
        pop.adjustSize()
        g = self.palette_btn.mapToGlobal(QPoint(0, self.palette_btn.height() + 4))
        pop.move(g.x() + self.palette_btn.width() - pop.width(), g.y())
        pop.show()

    def _edit_palette(self, pid: Optional[str]) -> None:
        store = palette_store()
        current = store.find(pid) if pid else None
        if current is None and not store.can_add():
            QMessageBox.information(self, tr("A Minha Cor"),
                                    tr("Limite de {n} paletas atingido. Exclua alguma para criar outra.",
                                       n=ct.MAX_CUSTOM))
            return
        dlg = PaletteDialog(self.window(), current)
        if not dlg.exec():
            return
        name, colors = dlg.result_palette()
        try:
            p = store.update(current.id, name, colors) if current else store.add(name, colors)
        except (ValueError, KeyError, OSError) as exc:
            QMessageBox.warning(self, tr("A Minha Cor"), str(exc))
            return
        m = self.canvas.doc.map
        cur = ct.current_palette(m)
        # paleta nova: aplica no mapa; edição: atualiza o mapa se ele usa essa paleta
        if current is None or (cur is not None and cur.id == p.id):
            self._apply_colors(p.as_setting(), None if cur else 0)

    def _make_default(self) -> None:
        m = self.canvas.doc.map
        pal = ct.current_palette(m)
        if pal is None:
            return
        v = int(m.setting("color_variant") or 0)
        try:
            palette_store().set_default(pal.as_setting(), v)
        except OSError as exc:
            QMessageBox.warning(self, tr("A Minha Cor"), str(exc))
            return
        ct.set_default_for_new_maps(pal.as_setting(), v)
        self.canvas.status_message.emit(tr("“{nome}” será o tema dos novos mapas.", nome=palette_name(pal)))

    def _set_variant(self, i: int) -> None:
        m = self.canvas.doc.map
        pal = ct.current_palette(m) or ct.legacy_palette(m.theme)
        self._apply_colors(pal.as_setting(), i)

    def _set_theme(self, key: str) -> None:
        self.canvas.doc.apply(N_("Mudar tema"), lambda m: ops.set_theme(m, key))
        self.refresh()

    def _set_setting(self, key: str, value) -> None:
        self.canvas.commit_edit(refocus=False)
        self.canvas.doc.apply(N_("Configurar mapa"), lambda m: ops.set_map_setting(m, key, value))
        self.refresh()

    def focus_note(self) -> None:
        self.tabs.set_index(0)
        self.pages.setCurrentIndex(0)
        self.note.setFocus()
