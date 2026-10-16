"""Painel lateral no estilo do XMind: abas "Estilo" (tópico) e "Mapa"."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from mindforge.layouts import LAYOUTS
from mindforge.model import ops
from mindforge.themes import SHAPES, visible_themes
from mindforge.view import style
from mindforge.view.icons import icon, shape_icon
from mindforge.view.painting import MARKER_LABELS
from mindforge.view.resources import marker_icon
from mindforge.view.widgets import (
    CardButton, Segmented, SkeletonPopup, SwatchButton, row, section_title, separator, thumbnail,
)

FONT_SIZES = [10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 28, 32, 40, 48]
GLOBAL_FONTS = ["Helvetica Neue", "Avenir Next", "Inter", "Roboto", "Open Sans", "Lato", "Montserrat",
                "Poppins", "Segoe UI", "Arial", "Verdana", "Georgia", "Times New Roman", "Menlo",
                "DejaVu Sans", "Noto Sans"]
LINE_WIDTHS = [("padrao", "Predefinição"), ("fina", "Fina"), ("grossa", "Grossa")]
LEVEL_NAMES = {"root": "Tema central", "main": "Tópico principal", "sub": "Subtópico",
               "floating": "Tópico flutuante"}
THEME_THUMB = QSize(74, 48)


def _scroll(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QScrollArea.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


class FormatPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.canvas = None
        self._note_tid: Optional[str] = None
        self._note_timer = QTimer(self)
        self._note_timer.setSingleShot(True)
        self._note_timer.setInterval(700)
        self._note_timer.timeout.connect(self._commit_note)
        self._theme_thumbs_key = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 8)
        outer.setSpacing(12)
        self.tabs = Segmented(["Estilo", "Mapa"])
        outer.addWidget(self.tabs)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.tabs.changed.connect(self.pages.setCurrentIndex)

        self._build_style_page()
        self._build_map_page()
        self.setMinimumWidth(286)
        self.setMaximumWidth(380)

    # ================================================================ Estilo
    def _build_style_page(self) -> None:
        self.style_stack = QStackedWidget()
        # estado vazio
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch(1)
        ic = QLabel()
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_icon = ic
        el.addWidget(ic)
        t = QLabel("Nenhum tópico selecionado")
        t.setObjectName("Heading")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(t)
        hint = QLabel("Clique em um tópico para editar o estilo.\n\n"
                      "Tab  cria subtópico\nEnter  cria tópico irmão\nF2 ou Espaço  edita o texto")
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(hint)
        el.addStretch(2)
        self.style_stack.addWidget(empty)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(10)
        self.heading = QLabel()
        self.heading.setObjectName("Heading")
        self.heading.setWordWrap(True)
        self.sub_heading = QLabel()
        self.sub_heading.setObjectName("Muted")
        lay.addWidget(self.heading)
        lay.addWidget(self.sub_heading)
        lay.addWidget(separator())

        # Forma
        lay.addWidget(section_title("Forma"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.shape_btns: dict[Optional[str], QToolButton] = {}
        shapes = [("padrao", "Automática (do tema)")] + list(SHAPES.items())
        for i, (key, label) in enumerate(shapes):
            b = QToolButton()
            b.setObjectName("ShapeButton")
            b.setCheckable(True)
            b.setToolTip(label)
            b.setIconSize(QSize(34, 22))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self.set_style("shape", None if k == "padrao" else k))
            grid.addWidget(b, i // 4, i % 4)
            self.shape_btns[key] = b
        lay.addLayout(grid)
        self._shape_order = [k for k, _ in shapes]

        lay.addWidget(separator())
        lay.addWidget(section_title("Cores"))
        self.fill_btn = SwatchButton(True)
        self.fill_btn.picked.connect(lambda v: self.set_style("fill", v))
        self.border_btn = SwatchButton(True)
        self.border_btn.picked.connect(lambda v: self.set_style("border", v))
        self.line_btn = SwatchButton(False)
        self.line_btn.picked.connect(lambda v: self.set_style("line_color", v))
        lay.addLayout(row("Preenchimento", self.fill_btn))
        lay.addLayout(row("Borda", self.border_btn))
        lay.addLayout(row("Linha do ramo", self.line_btn))

        lay.addWidget(separator())
        lay.addWidget(section_title("Texto"))
        self.size = QComboBox()
        self.size.addItem("Auto", None)
        for s in FONT_SIZES:
            self.size.addItem(f"{s} px", s)
        self.size.activated.connect(lambda _i: self.set_style("font_size", self.size.currentData()))
        self.bold = self._toggle("N", "Negrito", bold=True)
        self.bold.clicked.connect(lambda on: self.set_style("bold", bool(on)))
        self.italic = self._toggle("I", "Itálico", italic=True)
        self.italic.clicked.connect(lambda on: self.set_style("italic", bool(on)))
        self.text_btn = SwatchButton(False)
        self.text_btn.picked.connect(lambda v: self.set_style("text_color", v))
        h = QHBoxLayout()
        h.setSpacing(6)
        h.addWidget(self.size, 1)
        h.addWidget(self.bold)
        h.addWidget(self.italic)
        h.addWidget(self.text_btn)
        lay.addLayout(h)

        lay.addWidget(separator())
        lay.addWidget(section_title("Marcadores"))
        mg = QGridLayout()
        mg.setSpacing(6)
        self.marker_btns: dict[str, QToolButton] = {}
        for i, key in enumerate(ops.ALL_MARKERS):
            b = QToolButton()
            b.setObjectName("MarkerButton")
            b.setIcon(marker_icon(key))
            b.setIconSize(QSize(20, 20))
            b.setCheckable(True)
            b.setToolTip(MARKER_LABELS.get(key, key))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _on, k=key: self._toggle_marker(k))
            mg.addWidget(b, i // 4, i % 4)
            self.marker_btns[key] = b
        lay.addLayout(mg)

        lay.addWidget(separator())
        lay.addWidget(section_title("Nota"))
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Escreva uma nota para este tópico…")
        self.note.setMinimumHeight(110)
        self.note.textChanged.connect(lambda: self._note_timer.start())
        self.note.installEventFilter(self)
        lay.addWidget(self.note)
        self.reset_btn = QPushButton("Restaurar estilo padrão")
        self.reset_btn.setObjectName("LinkButton")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.clicked.connect(self._reset_style)
        lay.addWidget(self.reset_btn)
        lay.addStretch(1)
        self.style_stack.addWidget(_scroll(inner))
        self.pages.addWidget(self.style_stack)

    def _toggle(self, text: str, tip: str, bold: bool = False, italic: bool = False) -> QToolButton:
        b = QToolButton()
        b.setObjectName("StyleToggle")
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(True)
        b.setFixedSize(30, 28)
        f = b.font()
        f.setBold(bold)
        f.setItalic(italic)
        b.setFont(f)
        return b

    # ================================================================== Mapa
    def _build_map_page(self) -> None:
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(10)

        lay.addWidget(section_title("Esqueleto"))
        self.skeleton_btn = CardButton()
        self.skeleton_btn.clicked.connect(self._open_skeletons)
        lay.addWidget(self.skeleton_btn)

        lay.addWidget(separator())
        lay.addWidget(section_title("Tema de cores"))
        self.theme_grid = QGridLayout()
        self.theme_grid.setSpacing(6)
        self.theme_btns: dict[str, QToolButton] = {}
        for i, th in enumerate(visible_themes()):
            b = QToolButton()
            b.setObjectName("ThemeCard")
            b.setCheckable(True)
            b.setToolTip(th.label)
            b.setIconSize(THEME_THUMB)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=th.key: self._set_theme(k))
            self.theme_grid.addWidget(b, i // 3, i % 3)
            self.theme_btns[th.key] = b
        lay.addLayout(self.theme_grid)
        self.theme_name = QLabel()
        self.theme_name.setObjectName("Muted")
        lay.addWidget(self.theme_name)

        lay.addWidget(separator())
        self.bg_btn = SwatchButton(False)
        self.bg_btn.picked.connect(lambda v: self._set_setting("background", v))
        lay.addLayout(row("Cor de fundo", self.bg_btn))

        lay.addWidget(separator())
        lay.addWidget(section_title("Tipo de letra global"))
        self.font_combo = QComboBox()
        self.font_combo.addItem("Predefinição", None)
        families = set(QFontDatabase.families())
        for fam in GLOBAL_FONTS:
            if fam in families:
                self.font_combo.addItem(fam, fam)
        self.font_combo.activated.connect(lambda _i: self._set_setting("font", self.font_combo.currentData()))
        lay.addWidget(self.font_combo)

        lay.addWidget(section_title("Largura da linha de ramo"))
        self.line_combo = QComboBox()
        for key, label in LINE_WIDTHS:
            self.line_combo.addItem(label, key)
        self.line_combo.activated.connect(lambda _i: self._set_setting("line_width", self.line_combo.currentData()))
        lay.addWidget(self.line_combo)

        self.rainbow = QCheckBox("Ramo colorido")
        self.rainbow.clicked.connect(lambda on: self._set_setting("rainbow", bool(on)))
        lay.addWidget(self.rainbow)

        lay.addWidget(separator())
        lay.addWidget(section_title("Estilo do mapa"))
        self.compact = QCheckBox("Compactar mapa")
        self.compact.clicked.connect(lambda on: self._set_setting("compact", bool(on)))
        lay.addWidget(self.compact)
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
        self.refresh()

    def eventFilter(self, obj, ev):
        if obj is self.note and ev.type() == ev.Type.FocusOut:
            self._commit_note()
        return super().eventFilter(obj, ev)

    def _ids(self) -> list[str]:
        return self.canvas.mscene.selected_topic_ids() if self.canvas else []

    # ============================================================= refresh
    def refresh(self) -> None:
        if self.canvas is None:
            return
        self._refresh_map()
        m = self.canvas.doc.map
        ids = self._ids()
        cur = self.canvas.current()
        topic = m.find(cur) if cur else None
        if topic is None:
            self.style_stack.setCurrentIndex(0)
            self._set_note_text(None, "")
            return
        self.style_stack.setCurrentIndex(1)
        name = topic.text.split("\n")[0]
        self.heading.setText(name if len(name) <= 48 else name[:47] + "…")
        if len(ids) > 1:
            self.sub_heading.setText(f"{len(ids)} tópicos selecionados")
        else:
            level = "root" if topic is m.root else ("floating" if m.is_floating_root(topic)
                                                     else ("main" if topic.parent is m.root else "sub"))
            self.sub_heading.setText(LEVEL_NAMES[level])
        vis = self.canvas.mscene.visuals.get(topic.id)
        st = vis.style if vis else None
        current_shape = topic.style.get("shape") or "padrao"
        for k, b in self.shape_btns.items():
            b.setChecked(k == current_shape)
        if st:
            self.fill_btn.show_color(st.fill or "")
            has_border = bool(st.border) and (st.border_width > 0 or st.shape == "sublinhado")
            self.border_btn.show_color(st.border if has_border else "")
            self.text_btn.show_color(st.text_color)
            self.line_btn.show_color(st.line_color)
            self.bold.setChecked(st.bold)
            self.italic.setChecked(st.italic)
        fs = topic.style.get("font_size")
        idx = self.size.findData(int(fs)) if fs else 0
        if idx < 0:
            self.size.addItem(f"{int(fs)} px", int(fs))
            idx = self.size.count() - 1
        self.size.setCurrentIndex(idx)
        for k, b in self.marker_btns.items():
            b.setChecked(k in topic.markers)
        if not (self.note.hasFocus() and self._note_tid == topic.id):
            self._set_note_text(topic.id, topic.note)

    def _refresh_map(self) -> None:
        m = self.canvas.doc.map
        lay = LAYOUTS.get(m.layout)
        self.skeleton_btn.setText(f"  {lay.label if lay else m.layout}   ⌄")
        self.skeleton_btn.setIcon(QIcon(thumbnail(m.layout, "_esqueleto", QSize(96, 56))))
        key = (m.layout, tuple(sorted((k, v) for k, v in m.settings.items() if k != "background")))
        if key != self._theme_thumbs_key:
            self._theme_thumbs_key = key
            settings = {k: v for k, v in m.settings.items() if k in ("rainbow", "line_width")}
            for tkey, b in self.theme_btns.items():
                b.setIcon(QIcon(thumbnail(m.layout, tkey, THEME_THUMB, settings)))
        for tkey, b in self.theme_btns.items():
            b.setChecked(tkey == m.theme)
        th = next((t for t in visible_themes() if t.key == m.theme), None)
        self.theme_name.setText(th.label if th else "")
        self.bg_btn.show_color(self.canvas.mscene.background_color)
        for combo, value in ((self.font_combo, m.setting("font")), (self.line_combo, m.setting("line_width"))):
            i = combo.findData(value)
            if i < 0 and value:
                combo.addItem(str(value), value)
                i = combo.count() - 1
            combo.setCurrentIndex(max(0, i))
        self.rainbow.setChecked(bool(m.setting("rainbow")))
        self.compact.setChecked(bool(m.setting("compact")))

    def _set_note_text(self, tid: Optional[str], text: str) -> None:
        if self._note_timer.isActive():
            self._commit_note()
        self._note_tid = tid
        self.note.blockSignals(True)
        self.note.setPlainText(text)
        self.note.blockSignals(False)

    # =============================================================== ações
    def set_style(self, key: str, value) -> None:
        ids = self._ids()
        if not ids or self.canvas is None:
            return
        self.canvas.commit_edit(refocus=False)
        self.canvas.doc.apply("Formatar tópico", lambda m: ops.set_style(m, ids, key, value), select=ids)

    def _reset_style(self) -> None:
        ids = self._ids()
        if ids:
            self.canvas.doc.apply("Restaurar estilo", lambda m: ops.clear_style(m, ids), select=ids)

    def _toggle_marker(self, key: str) -> None:
        ids = self._ids()
        if ids:
            self.canvas.doc.apply("Marcador", lambda m: ops.toggle_marker(m, ids, key), select=ids)

    def _commit_note(self) -> None:
        self._note_timer.stop()
        tid = self._note_tid
        if self.canvas is None or tid is None or self.canvas.doc.map.find(tid) is None:
            return
        text = self.note.toPlainText()
        if self.canvas.doc.map.find(tid).note == text:
            return
        self.canvas.doc.apply("Editar nota", lambda m: ops.set_note(m, tid, text),
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
        self.canvas.doc.apply("Mudar esqueleto", lambda m: ops.set_layout(m, key))
        QTimer.singleShot(0, self.canvas.zoom_fit)

    def _set_theme(self, key: str) -> None:
        self.canvas.doc.apply("Mudar tema", lambda m: ops.set_theme(m, key))
        self.refresh()

    def _set_setting(self, key: str, value) -> None:
        self.canvas.commit_edit(refocus=False)
        self.canvas.doc.apply("Configurar mapa", lambda m: ops.set_map_setting(m, key, value))
        self.refresh()

    def focus_note(self) -> None:
        self.tabs.set_index(0)
        self.pages.setCurrentIndex(0)
        self.note.setFocus()
