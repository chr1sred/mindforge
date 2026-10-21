"""Janela principal: menus, barra de ferramentas, painel, busca e arquivo."""
from __future__ import annotations

import os
import unicodedata
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QSizePolicy, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from mindforge import APP_NAME, FILE_EXTENSION, __version__
from mindforge.document import Document
from mindforge.export import ExportError, export_file
from mindforge.i18n import N_, ntr, tr
from mindforge.layouts import LAYOUTS
from mindforge.model import ops
from mindforge.storage import MindForgeFileError, save_map
from mindforge.view.canvas import MindCanvas
from mindforge.view.dialogs import ExportDialog, ShortcutsDialog, ask_export_path
from mindforge.view import style
from mindforge.view.format_panel import FormatPanel
from mindforge.view.icons import icon
from mindforge.view.resources import app_icon

if TYPE_CHECKING:
    from mindforge.app import MindForgeApp

def file_filter() -> str:
    return tr("Mapas {app} (*{ext})", app=APP_NAME, ext=FILE_EXTENSION)
AUTOSAVE_MS = 60_000


def _norm(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if not unicodedata.combining(c)).casefold()


class FindBar(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.win = window
        self.setObjectName("FindBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.matches: list[str] = []
        self.pos = -1
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.addWidget(QLabel(tr("Buscar:")))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(tr("Texto do tópico ou da nota (ignora acentos)"))
        self.edit.setClearButtonEnabled(True)
        self.edit.textChanged.connect(self._search)
        self.edit.returnPressed.connect(self.next)
        self.edit.installEventFilter(self)
        lay.addWidget(self.edit, 1)
        self.count = QLabel()
        lay.addWidget(self.count)
        for text, slot, tip in (("◀", self.prev, tr("Anterior (Shift+Enter)")), ("▶", self.next, tr("Próximo (Enter)")),
                                ("✕", self.close_bar, tr("Fechar (Esc)"))):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            b.setAutoRaise(True)
            lay.addWidget(b)
        self.hide()

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == ev.Type.KeyPress:
            if ev.key() == Qt.Key.Key_Escape:
                self.close_bar()
                return True
            if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and \
                    ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.prev()
                return True
        return super().eventFilter(obj, ev)

    def open_bar(self) -> None:
        self.show()
        self.edit.setFocus()
        self.edit.selectAll()
        self._search()

    def close_bar(self) -> None:
        self.hide()
        self.win.canvas.setFocus()

    def _search(self) -> None:
        q = _norm(self.edit.text().strip())
        m = self.win.doc.map
        self.matches = [t.id for t in m.all_topics()
                        if q and (q in _norm(t.text) or q in _norm(t.note))]
        self.pos = -1
        self._update_label()

    def _update_label(self) -> None:
        if not self.edit.text().strip():
            self.count.setText("")
        elif not self.matches:
            self.count.setText(tr("nenhum resultado"))
        else:
            self.count.setText(tr("{i} de {n}", i=self.pos + 1 if self.pos >= 0 else 0, n=len(self.matches)))

    def _go(self, step: int) -> None:
        if not self.matches:
            self._search()
        if not self.matches:
            return
        self.pos = (self.pos + step) % len(self.matches)
        self.win.canvas.reveal(self.matches[self.pos])
        self._update_label()

    def next(self) -> None:
        self._go(1)

    def prev(self) -> None:
        self._go(-1)


class MainWindow(QMainWindow):
    def __init__(self, app: "MindForgeApp", doc: Document):
        super().__init__()
        self.app = app
        self.doc = doc
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowIcon(app_icon())
        self.resize(1280, 820)

        self.canvas = MindCanvas(doc)
        self.find_bar = FindBar(self)
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self.canvas, 1)
        cl.addWidget(self.find_bar)
        self.setCentralWidget(central)

        self.panel = FormatPanel()
        self.dock = QDockWidget(tr("Formatar"), self)
        self.dock.setObjectName("dock_formatar")
        self.dock.setWidget(self.panel)
        self.dock.setTitleBarWidget(QWidget())          # painel "embutido", sem barra de título
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.resizeDocks([self.dock], [310], Qt.Orientation.Horizontal)
        self.panel.set_canvas(self.canvas)

        self._tb_buttons: list[QToolButton] = []
        self._build_canvas_shortcuts()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self.refresh_chrome()

        self.canvas.status_message.connect(lambda msg: self.statusBar().showMessage(msg, 6000))
        self.canvas.zoom_changed.connect(lambda z: self.zoom_btn.setText(f"{round(z * 100)}%"))
        self.canvas.context_menu_requested.connect(self._context_menu)
        doc.modified_changed.connect(lambda _m: self._update_title())
        doc.changed.connect(self._on_doc_changed)
        self._update_title()
        self._on_doc_changed()

        self._autosave_rev = -1
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(AUTOSAVE_MS)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()
        self.canvas.setFocus()

    # ================================================================== ações
    def _act(self, text: str, slot: Callable, shortcuts=(), tip: str = "",
             checkable: bool = False) -> QAction:
        a = QAction(text, self)
        # sem heurística do macOS: em inglês, textos como "Settings…"/"About" seriam movidos sozinhos
        a.setMenuRole(QAction.MenuRole.NoRole)
        if shortcuts:
            a.setShortcuts([QKeySequence(s) if isinstance(s, str) else QKeySequence(s) for s in shortcuts])
        if tip:
            a.setStatusTip(tip)
            a.setToolTip(tip)
        a.setCheckable(checkable)
        a.triggered.connect(lambda _c=False: slot())
        self.addAction(a)
        return a

    def _canvas_act(self, shortcuts, slot: Callable) -> QAction:
        """Atalho que só vale com o mapa em foco (não interfere em campos de texto)."""
        a = QAction(self.canvas)
        a.setShortcuts([QKeySequence(s) for s in shortcuts])
        a.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        a.triggered.connect(lambda _c=False: slot())
        self.canvas.addAction(a)
        return a

    def _build_canvas_shortcuts(self) -> None:
        c = self.canvas
        self._canvas_act(["Tab"], c.add_child)
        self._canvas_act(["Return", "Enter"], lambda: c.add_sibling(False))
        self._canvas_act(["Shift+Return", "Shift+Enter"], lambda: c.add_sibling(True))
        self._canvas_act(["Ctrl+Return", "Ctrl+Enter"], c.add_parent)
        self._canvas_act(["F2"], lambda: c.start_edit())
        self._canvas_act(["Delete", "Backspace"], c.delete_selected)
        self._canvas_act(["Left"], lambda: c.navigate("left"))
        self._canvas_act(["Right"], lambda: c.navigate("right"))
        self._canvas_act(["Up"], lambda: c.navigate("up"))
        self._canvas_act(["Down"], lambda: c.navigate("down"))
        self._canvas_act(["Ctrl+Up"], lambda: c.move_sibling(-1))
        self._canvas_act(["Ctrl+Down"], lambda: c.move_sibling(1))
        self._canvas_act(["Ctrl+/"], lambda: c.toggle_collapse())
        self._canvas_act(["Ctrl+C"], c.copy)
        self._canvas_act(["Ctrl+X"], c.cut)
        self._canvas_act(["Ctrl+V"], c.paste)
        self._canvas_act(["Ctrl+D"], c.duplicate)
        self._canvas_act(["Ctrl+A"], c.select_all)
        self._canvas_act(["Ctrl+R"], c.start_relation)
        self._canvas_act(["Ctrl+Alt+C"], c.copy_style)
        self._canvas_act(["Ctrl+Alt+V"], lambda: c.paste_style())
        self._canvas_act(["Ctrl+Alt+R"], c.reset_style)
        self._canvas_act(["Ctrl+B"], lambda: c.toggle_text_format("bold"))
        self._canvas_act(["Ctrl+I"], lambda: c.toggle_text_format("italic"))
        self._canvas_act(["Ctrl+Shift+X"], lambda: c.toggle_text_format("strike"))

    def _build_menus(self) -> None:
        c = self.canvas
        mb = self.menuBar()
        # ---------------------------------------------------------- Arquivo
        m = mb.addMenu(tr("&Arquivo"))
        self.a_new = self._act(tr("Novo…"), self.app.new_from_template, ["Ctrl+N"], tr("Novo mapa a partir de um modelo"))
        self.a_open = self._act(tr("Abrir…"), self.open_dialog, ["Ctrl+O"], tr("Abrir mapa"))
        m.addAction(self.a_new)
        m.addAction(self.a_open)
        self.recent_menu = m.addMenu(tr("Abrir recente"))
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        self.a_save = self._act(tr("Salvar"), self.save, ["Ctrl+S"], tr("Salvar mapa"))
        self.a_save_as = self._act(tr("Salvar como…"), self.save_as, ["Ctrl+Shift+S"])
        m.addAction(self.a_save)
        m.addAction(self.a_save_as)
        m.addSeparator()
        self.a_export = self._act(tr("Exportar (PNG, SVG, PDF)…"), self.export, ["Ctrl+E"])
        m.addAction(self.a_export)
        m.addSeparator()
        m.addAction(self._act(tr("Fechar janela"), self.close, ["Ctrl+W"]))
        quit_a = self._act(tr("Sair"), self.app.quit_all, ["Ctrl+Q"])
        quit_a.setMenuRole(QAction.MenuRole.QuitRole)
        m.addAction(quit_a)

        # ----------------------------------------------------------- Editar
        e = mb.addMenu(tr("&Editar"))
        self.a_undo = self._act(tr("Desfazer"), self.undo, ["Ctrl+Z"])
        self.a_redo = self._act(tr("Refazer"), self.redo, ["Ctrl+Shift+Z", "Ctrl+Y"])
        st = self.doc.undo_stack
        st.canUndoChanged.connect(self.a_undo.setEnabled)
        st.canRedoChanged.connect(self.a_redo.setEnabled)
        st.undoTextChanged.connect(self._on_undo_text)
        st.redoTextChanged.connect(self._on_redo_text)
        # estado inicial vem da pilha (a janela pode ser recriada com histórico, ex.: troca de idioma)
        self.a_undo.setEnabled(st.canUndo())
        self.a_redo.setEnabled(st.canRedo())
        self._on_undo_text(st.undoText())
        self._on_redo_text(st.redoText())
        e.addAction(self.a_undo)
        e.addAction(self.a_redo)
        e.addSeparator()
        for text, slot in ((tr("Recortar  (Ctrl+X)"), c.cut), (tr("Copiar  (Ctrl+C)"), c.copy),
                           (tr("Colar  (Ctrl+V)"), c.paste), (tr("Duplicar  (Ctrl+D)"), c.duplicate),
                           (tr("Excluir  (Delete)"), c.delete_selected),
                           (tr("Selecionar todos  (Ctrl+A)"), c.select_all)):
            e.addAction(self._act(_mac(text), slot))
        e.addSeparator()
        e.addAction(self._act(_mac(tr("Editar texto  (F2 / Espaço)")), lambda: c.start_edit()))
        stm = e.addMenu(tr("Estilo"))
        for text, slot in ((tr("Copiar estilo  (Ctrl+Alt+C)"), c.copy_style),
                           (tr("Colar estilo  (Ctrl+Alt+V)"), lambda: c.paste_style()),
                           (tr("Repor estilo  (Ctrl+Alt+R)"), c.reset_style)):
            stm.addAction(self._act(_mac(text), slot))
        fmt = e.addMenu(tr("Formatar texto"))
        for text, kind in ((tr("Negrito  (Ctrl+B)"), "bold"), (tr("Itálico  (Ctrl+I)"), "italic"),
                           (tr("Tachado  (Ctrl+Shift+X)"), "strike")):
            fmt.addAction(self._act(_mac(text), lambda k=kind: c.toggle_text_format(k)))
        self.a_find = self._act(tr("Buscar…"), self.find_bar.open_bar, ["Ctrl+F"])
        e.addAction(self.a_find)

        # ----------------------------------------------------------- Inserir
        i = mb.addMenu(tr("&Inserir"))
        i.addAction(self._act(tr("Subtópico  (Tab)"), c.add_child))
        i.addAction(self._act(tr("Tópico irmão  (Enter)"), lambda: c.add_sibling(False)))
        i.addAction(self._act(_mac(tr("Tópico irmão acima  (Shift+Enter)")), lambda: c.add_sibling(True)))
        i.addAction(self._act(_mac(tr("Tópico pai  (Ctrl+Enter)")), c.add_parent))
        i.addAction(self._act(tr("Tópico flutuante  (duplo clique no fundo)"), lambda: c.add_floating()))
        i.addSeparator()
        i.addAction(self._act(_mac(tr("Relação  (Ctrl+R)")), c.start_relation))
        i.addAction(self._act(tr("Nota"), self._focus_note, ["Ctrl+Shift+N"]))
        mk = i.addMenu(tr("Marcador"))
        from mindforge.view.painting import MARKER_LABELS
        from mindforge.view.resources import marker_icon
        for key in ops.ALL_MARKERS:
            a = self._act(tr(MARKER_LABELS[key]), lambda k=key: self.panel._toggle_marker(k))
            a.setIcon(marker_icon(key))
            mk.addAction(a)

        # --------------------------------------------------------- Organizar
        o = mb.addMenu(tr("&Organizar"))
        o.addAction(self._act(_mac(tr("Mover para cima  (Ctrl+↑)")), lambda: c.move_sibling(-1)))
        o.addAction(self._act(_mac(tr("Mover para baixo  (Ctrl+↓)")), lambda: c.move_sibling(1)))
        o.addSeparator()
        o.addAction(self._act(_mac(tr("Recolher/expandir ramo  (Ctrl+/)")), lambda: c.toggle_collapse()))
        o.addAction(self._act(tr("Expandir tudo"), lambda: c.set_collapsed_all(False), ["Ctrl+Shift+E"]))
        o.addAction(self._act(tr("Recolher tudo"), lambda: c.set_collapsed_all(True), ["Ctrl+Shift+C"]))
        o.addSeparator()
        self.layout_menu = o.addMenu(tr("Esqueleto"))
        for key, lay in LAYOUTS.items():
            a = self._act(tr(lay.label), lambda k=key: self._set_layout(k), checkable=True)
            a.setData(key)
            self.layout_menu.addAction(a)
        self.theme_menu = o.addMenu(tr("Tema de cores"))
        self.theme_menu.aboutToShow.connect(self._fill_theme_menu)
        self.quick_menu = o.addMenu(tr("Temas rápidos"))
        self.quick_menu.aboutToShow.connect(self._fill_quick_menu)

        # -------------------------------------------------------- Visualizar
        v = mb.addMenu(tr("&Visualizar"))
        v.addAction(self._act(tr("Aumentar zoom"), c.zoom_in, ["Ctrl+=", "Ctrl++"]))
        v.addAction(self._act(tr("Diminuir zoom"), c.zoom_out, ["Ctrl+-"]))
        v.addAction(self._act(tr("Ajustar à tela"), c.zoom_fit, ["Ctrl+0"]))
        v.addAction(self._act(tr("Tamanho real (100%)"), c.zoom_reset, ["Ctrl+1"]))
        v.addSeparator()
        tv = self.dock.toggleViewAction()
        tv.setText(tr("Painel Estilo/Mapa"))
        tv.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.addAction(tv)
        v.addAction(tv)
        self.a_fullscreen = self._act(tr("Tela cheia"), self.toggle_fullscreen,
                                      [QKeySequence(QKeySequence.StandardKey.FullScreen)])
        v.addAction(self.a_fullscreen)

        # ------------------------------------------------------------- Ajuda
        h = mb.addMenu(tr("Aj&uda"))
        h.addAction(self._act(tr("Atalhos de teclado"), lambda: ShortcutsDialog(self).exec(), ["F1"]))
        about = self._act(tr("Sobre o {app}", app=APP_NAME), self._about)
        about.setMenuRole(QAction.MenuRole.AboutRole)
        h.addAction(about)
        # No macOS o papel "Preferências" leva o item para o menu do app, logo abaixo de "Sobre".
        self.a_settings = self._act(tr("Ajustes…"), self.show_settings,
                                    [QKeySequence(QKeySequence.StandardKey.Preferences)])
        self.a_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        h.addAction(self.a_settings)

    def _tb_button(self, tb: QToolBar, icon_name: str, text: str, tip: str,
                   slot: Optional[Callable] = None, menu: Optional[QMenu] = None) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(_mac(tip))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(22, 22))
        b.setAutoRaise(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setProperty("icon_name", icon_name)
        if menu is not None:
            b.setMenu(menu)
            b.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup if slot
                           else QToolButton.ToolButtonPopupMode.InstantPopup)
        if slot is not None:
            b.clicked.connect(lambda _c=False: slot())
        tb.addWidget(b)
        self._tb_buttons.append(b)
        return b

    def _build_toolbar(self) -> None:
        tb = QToolBar(tr("Ferramentas"))
        tb.setObjectName("TopBar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.toggleViewAction().setVisible(False)
        self.addToolBar(tb)
        c = self.canvas

        topic_menu = QMenu(self)
        topic_menu.addAction(tr("Tópico irmão  (Enter)"), lambda: c.add_sibling(False))
        topic_menu.addAction(tr("Subtópico  (Tab)"), c.add_child)
        topic_menu.addAction(_mac(tr("Tópico antes  (Shift+Enter)")), lambda: c.add_sibling(True))
        topic_menu.addAction(_mac(tr("Tópico pai  (Ctrl+Enter)")), c.add_parent)
        topic_menu.addSeparator()
        topic_menu.addAction(tr("Tópico flutuante"), lambda: c.add_floating())
        self._tb_button(tb, "add_topic", tr("Tópico"), tr("Inserir tópico (Enter)"), lambda: c.add_sibling(False), topic_menu)
        self._tb_button(tb, "subtopic", tr("Subtópico"), tr("Inserir subtópico (Tab)"), c.add_child)
        self._tb_button(tb, "relation", tr("Relação"), tr("Relação entre tópicos (Ctrl+R)"), c.start_relation)
        from mindforge.view.painting import MARKER_LABELS
        from mindforge.view.resources import marker_icon
        mk_menu = QMenu(self)
        for key in ops.ALL_MARKERS:
            mk_menu.addAction(marker_icon(key), tr(MARKER_LABELS[key]), lambda k=key: self.panel._toggle_marker(k))
        self._tb_button(tb, "marker", tr("Marcador"), tr("Adicionar marcador ao tópico"), None, mk_menu)
        self._tb_button(tb, "note", tr("Nota"), tr("Nota do tópico (Ctrl+Shift+N)"), self._focus_note)
        self.brush_btn = self._tb_button(
            tb, "brush", tr("Estilo"),
            tr("Pincel de estilo: copia o estilo do tópico e aplica no próximo clicado. "
               "Duplo clique: aplica em vários (Esc encerra)"), self._brush_clicked)
        self.brush_btn.setCheckable(True)
        self._brush_clicked_at = 0.0
        c.brush_changed.connect(lambda mode: self.brush_btn.setChecked(mode is not None))

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._tb_button(tb, "undo", tr("Desfazer"), tr("Desfazer (Ctrl+Z)"), self.undo)
        self._tb_button(tb, "redo", tr("Refazer"), tr("Refazer (Ctrl+Shift+Z)"), self.redo)
        tb.addSeparator()
        self._tb_button(tb, "search", tr("Buscar"), tr("Buscar (Ctrl+F)"), self.find_bar.open_bar)
        self._tb_button(tb, "export", tr("Exportar"), tr("Exportar PNG, SVG ou PDF (Ctrl+E)"), self.export)
        self._tb_button(tb, "fullscreen", tr("Tela cheia"), tr("Tela cheia"), self.toggle_fullscreen)
        self.panel_btn = self._tb_button(tb, "panel", tr("Painel"), tr("Mostrar/ocultar painel (Ctrl+Shift+F)"),
                                         lambda: self.dock.setVisible(not self.dock.isVisible()))
        self.panel_btn.setCheckable(True)
        self.panel_btn.setChecked(True)
        self.dock.visibilityChanged.connect(self.panel_btn.setChecked)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.count_label = QLabel()
        sb.addPermanentWidget(self.count_label)
        c = self.canvas
        out_b = QToolButton()
        out_b.setText("−")
        out_b.setToolTip(_mac(tr("Diminuir zoom (Ctrl+-)")))
        out_b.clicked.connect(c.zoom_out)
        self.zoom_btn = QToolButton()
        self.zoom_btn.setText("100%")
        self.zoom_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        zm = QMenu(self)
        for z in (50, 75, 100, 125, 150, 200, 300):
            zm.addAction(f"{z}%", lambda z=z: c.set_zoom(z / 100, True))
        zm.addSeparator()
        zm.addAction(_mac(tr("Ajustar à tela  (Ctrl+0)")), c.zoom_fit)
        self.zoom_btn.setMenu(zm)
        self.zoom_btn.setMinimumWidth(52)
        in_b = QToolButton()
        in_b.setText("+")
        in_b.setToolTip(_mac(tr("Aumentar zoom (Ctrl+=)")))
        in_b.clicked.connect(c.zoom_in)
        self.fit_btn = QToolButton()
        self.fit_btn.setToolTip(_mac(tr("Ajustar à tela (Ctrl+0)")))
        self.fit_btn.clicked.connect(c.zoom_fit)
        for w in (out_b, self.zoom_btn, in_b, self.fit_btn):
            sb.addPermanentWidget(w)

    def refresh_chrome(self) -> None:
        """Reaplica ícones após troca do modo claro/escuro."""
        col = style.chrome().text
        for b in self._tb_buttons:
            b.setIcon(icon(b.property("icon_name"), col))
        if hasattr(self, "fit_btn"):
            self.fit_btn.setIcon(icon("fit", col, 16))
        self.panel.refresh_chrome()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ================================================================ estado
    def _on_doc_changed(self) -> None:
        n = self.doc.map.count()
        self.count_label.setText(ntr("{n} tópico", "{n} tópicos", n))
        for a in self.layout_menu.actions():
            a.setChecked(a.data() == self.doc.map.layout)

    def _update_title(self) -> None:
        name = os.path.basename(self.doc.path) if self.doc.path else tr("Sem título")
        self.setWindowTitle(f"{name}[*] — {APP_NAME}")
        self.setWindowModified(self.doc.is_modified())
        if self.doc.path:
            self.setWindowFilePath(self.doc.path)

    def _set_layout(self, key: str) -> None:
        self.canvas.commit_edit()
        self.doc.apply(N_("Mudar estrutura"), lambda m: ops.set_layout(m, key))
        QTimer.singleShot(0, self.canvas.zoom_fit)

    def _fill_quick_menu(self) -> None:
        from mindforge import colorthemes as ct
        from mindforge.view.colorpanel import quick_theme_pixmap
        menu = self.quick_menu
        menu.clear()
        active = ct.active_quick_theme(self.doc.map)
        for key, q in ct.QUICK_THEMES.items():
            a = menu.addAction(QIcon(quick_theme_pixmap(key, 18)), tr(q.label))
            a.setCheckable(True)
            a.setChecked(key == active)
            a.setMenuRole(QAction.MenuRole.NoRole)
            a.triggered.connect(lambda _c=False, k=key: self.panel._apply_quick_theme(k))

    def _fill_theme_menu(self) -> None:
        from mindforge import colorthemes as ct
        from mindforge.view.colorpanel import palette_name, palette_store, strip_pixmap
        menu = self.theme_menu
        menu.clear()
        cur = ct.current_palette(self.doc.map)
        groups = ((tr("A Minha Cor"), palette_store().palettes), (tr("Colorido"), ct.COLORIDO),
                  (tr("Clássico"), ct.CLASSICO))
        for title, pals in groups:
            if not pals:
                continue
            menu.addSection(title)
            for p in pals:
                a = menu.addAction(QIcon(strip_pixmap(p.colors, QSize(60, 14), 3)), palette_name(p))
                a.setCheckable(True)
                a.setChecked(cur is not None and cur.id == p.id)
                a.setMenuRole(QAction.MenuRole.NoRole)
                a.triggered.connect(lambda _c=False, pal=p: self.panel._apply_colors(
                    pal.as_setting(), None if ct.current_palette(self.doc.map) else 0))
        menu.addSeparator()
        new = menu.addAction(tr("Criar novo tema de cores…"), lambda: self.panel._edit_palette(None))
        new.setMenuRole(QAction.MenuRole.NoRole)

    def _focus_note(self) -> None:
        self.dock.show()
        self.panel.focus_note()

    def _on_undo_text(self, t: str) -> None:
        try:
            self.a_undo.setText(tr("Desfazer {acao}", acao=tr(t)).strip() if t else tr("Desfazer"))
        except RuntimeError:
            pass

    def _on_redo_text(self, t: str) -> None:
        try:
            self.a_redo.setText(tr("Refazer {acao}", acao=tr(t)).strip() if t else tr("Refazer"))
        except RuntimeError:
            pass

    def undo(self) -> None:
        self.canvas.commit_edit()
        self.doc.undo_stack.undo()

    def redo(self) -> None:
        self.canvas.commit_edit()
        self.doc.undo_stack.redo()

    def _context_menu(self, tid, global_pos) -> None:
        c = self.canvas
        menu = QMenu(self)
        if tid:
            menu.addAction(tr("Novo subtópico  (Tab)"), c.add_child)
            menu.addAction(tr("Novo tópico irmão  (Enter)"), lambda: c.add_sibling(False))
            menu.addAction(tr("Editar texto  (F2)"), lambda: c.start_edit(tid))
            menu.addAction(tr("Nota…"), self._focus_note)
            menu.addSeparator()
            menu.addAction(tr("Recolher / expandir"), lambda: c.toggle_collapse())
            menu.addAction(tr("Relação a partir daqui"), c.start_relation)
            menu.addSeparator()
            menu.addAction(tr("Copiar"), c.copy)
            menu.addAction(tr("Recortar"), c.cut)
            menu.addAction(tr("Colar como subtópico"), c.paste)
            menu.addAction(tr("Duplicar"), c.duplicate)
            t = self.doc.map.find(tid)
            if t is not None and t.parent is not None:
                menu.addAction(tr("Tornar tópico flutuante"), lambda: self._detach(tid))
            menu.addSeparator()
            menu.addAction(_mac(tr("Copiar estilo  (Ctrl+Alt+C)")), c.copy_style)
            pst = menu.addAction(_mac(tr("Colar estilo  (Ctrl+Alt+V)")), lambda: c.paste_style())
            pst.setEnabled(c.has_copied_style())
            menu.addAction(_mac(tr("Repor estilo  (Ctrl+Alt+R)")), c.reset_style)
            menu.addSeparator()
            menu.addAction(tr("Excluir"), c.delete_selected)
        elif c.mscene.selected_relation_ids():
            rid = c.mscene.selected_relation_ids()[0]
            rel = next((r for r in self.doc.map.relations if r.id == rid), None)
            menu.addAction(tr("Editar rótulo…"), lambda: c.edit_relation_label(rid))
            menu.addAction(tr("Inverter direção"), lambda: c.relation_action(rid, "reverse"))
            ends = menu.addMenu(tr("Pontas"))
            for key, label in (("end", tr("Seta no fim")), ("both", tr("Setas nos dois lados")),
                               ("none", tr("Sem seta"))):
                a = ends.addAction(label, lambda k=key: c.relation_action(rid, "arrows", k))
                a.setCheckable(True)
                a.setChecked(rel is not None and rel.arrows == key)
            st = menu.addAction(tr("Endireitar curva"), lambda: c.relation_action(rid, "straighten"))
            st.setEnabled(rel is not None and rel.is_custom_shape())
            menu.addSeparator()
            menu.addAction(tr("Excluir relação"), c.delete_selected)
        else:
            pos = c.mapToScene(c.mapFromGlobal(global_pos))
            menu.addAction(tr("Novo tópico flutuante aqui"), lambda: c.add_floating(pos))
            menu.addAction(tr("Colar"), c.paste)
            menu.addSeparator()
            menu.addAction(tr("Ajustar à tela"), c.zoom_fit)
            menu.addAction(tr("Expandir tudo"), lambda: c.set_collapsed_all(False))
        menu.exec(global_pos)

    def _brush_clicked(self) -> None:
        """Clique: pincel para 1 tópico. Duplo clique: pincel travado. Clique com o pincel ativo: desliga."""
        import time
        c = self.canvas
        now = time.monotonic()
        quick = now - self._brush_clicked_at < QApplication.doubleClickInterval() / 1000.0
        self._brush_clicked_at = now
        if c.brush_mode == "once" and quick:
            c.brush_mode = "sticky"                 # 2º clique do duplo clique: trava
            c.start_brush(sticky=True)
        elif c.brush_mode is not None:
            c.end_brush()
        else:
            c.start_brush(sticky=False)
        self.brush_btn.setChecked(c.brush_mode is not None)
        c.setFocus()

    def _detach(self, tid: str) -> None:
        it = self.canvas.mscene.topic_items.get(tid)
        p = it.pos() if it else None
        x, y = (p.x() + 40, p.y() + 40) if p is not None else (0, 0)
        self.doc.apply(N_("Tornar flutuante"), lambda m: ops.detach_to_floating(m, tid, x, y), select=[tid])

    def _about(self) -> None:
        QMessageBox.about(self, tr("Sobre o {app}", app=APP_NAME),
                          f"<b>{APP_NAME} {__version__}</b><br>" +
                          tr("Editor de mapas mentais.<br><br>Feito em Python + PySide6 (Qt)."))

    # =============================================================== arquivo
    def open_dialog(self) -> None:
        folder = QSettings().value("files/dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, tr("Abrir mapa"), folder, file_filter())
        if path:
            QSettings().setValue("files/dir", os.path.dirname(path))
            self.app.open_path(path, self)

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        files = self.app.recent_files()
        if not files:
            a = self.recent_menu.addAction(tr("(nenhum)"))
            a.setEnabled(False)
            return
        for p in files:
            ra = self.recent_menu.addAction(os.path.basename(p), lambda p=p: self.app.open_path(p, self))
            ra.setMenuRole(QAction.MenuRole.NoRole)     # "setup.mfmap" não pode virar "Preferências" no Mac
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(tr("Limpar lista"), self.app.clear_recent)

    def save(self) -> bool:
        self.canvas.commit_edit()
        self.panel._commit_note()
        if not self.doc.path:
            return self.save_as()
        return self._write(self.doc.path)

    def save_as(self) -> bool:
        self.canvas.commit_edit()
        self.panel._commit_note()
        folder = QSettings().value("files/dir", os.path.expanduser("~"))
        base = self.doc.path or os.path.join(folder, _safe_name(self.doc.map.root.text) + FILE_EXTENSION)
        path, _ = QFileDialog.getSaveFileName(self, tr("Salvar mapa como"), base, file_filter())
        if not path:
            return False
        if not path.lower().endswith(FILE_EXTENSION):
            path += FILE_EXTENSION
        QSettings().setValue("files/dir", os.path.dirname(path))
        return self._write(path)

    def _write(self, path: str) -> bool:
        try:
            save_map(self.doc.map, path)
        except MindForgeFileError as exc:
            QMessageBox.critical(self, tr("Erro ao salvar"), str(exc))
            return False
        self.doc.mark_saved(path)
        self.app.recovery.remove(self.doc.uid)
        self.app.add_recent(path)
        self._update_title()
        self.statusBar().showMessage(tr("Salvo em {path}", path=path), 5000)
        return True

    def export(self) -> None:
        c = self.canvas
        c.commit_edit()
        sel = ops.top_level_selection(self.doc.map, c.mscene.selected_topic_ids())
        from mindforge.themes import is_dark
        dlg = ExportDialog(self, has_selection=bool(sel),
                           dark_background=is_dark(self.canvas.mscene.background_color))
        if not dlg.exec():
            return
        opt = dlg.options()
        opt.title = self.doc.map.root.text.split("\n")[0]
        if dlg.only_selection():
            ids = set()
            for t in sel:
                ids.update(x.id for x in t.walk_visible())
            opt.only_ids = ids
        base = (sel[0].text if dlg.only_selection() and sel else self.doc.map.root.text).split("\n")[0]
        path = ask_export_path(self, opt.fmt, base)
        if not path:
            return
        try:
            res = export_file(c.mscene, path, opt)
        except ExportError as exc:
            QMessageBox.warning(self, tr("Exportação"), str(exc))
            return
        except Exception as exc:  # erro inesperado: nunca derrubar o app
            QMessageBox.critical(self, tr("Exportação"), tr("Falha inesperada ao exportar:\n{erro}", erro=exc))
            return
        msg = tr("Exportado: {arquivo}", arquivo=os.path.basename(path))
        if opt.fmt == "png":
            msg += f" ({res.width}×{res.height} px)"
        self.statusBar().showMessage(msg, 8000)
        if res.notes:
            QMessageBox.information(self, tr("Exportação"), "\n".join(res.notes))

    # ============================================================ autosave
    def autosave(self) -> None:
        if self.doc.is_modified() and self.doc.revision != self._autosave_rev:
            try:
                self.app.recovery.write(self.doc.uid, self.doc.map, self.doc.path)
                self._autosave_rev = self.doc.revision
            except OSError:
                pass

    def maybe_save(self) -> bool:
        self.canvas.commit_edit()
        self.panel._commit_note()
        if not self.doc.is_modified():
            return True
        self.raise_()
        self.activateWindow()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(APP_NAME)
        name = os.path.basename(self.doc.path) if self.doc.path else tr("Sem título")
        box.setText(tr("Deseja salvar as alterações em “{nome}”?", nome=name))
        box.setInformativeText(tr("Se não salvar, as alterações serão perdidas."))
        save = box.addButton(tr("Salvar"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("Não salvar"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self.save()
        return clicked is discard

    def show_settings(self) -> None:
        from mindforge.i18n import language
        from mindforge.view.dialogs import SettingsDialog
        dlg = SettingsDialog(language(), self)
        if dlg.exec():
            code = dlg.selected_language()
            if code != language():
                # adiado: a janela atual (dona do diálogo) será recriada
                QTimer.singleShot(0, lambda: self.app.set_language(code))

    # ------------------------------------------------- troca de idioma
    def view_state(self) -> dict:
        """Estado visual para recriar a janela sem o usuário perceber."""
        self.canvas.commit_edit()
        self.panel._commit_note()
        return {
            "geometry": self.saveGeometry(),
            "pos": self.pos(),
            "size": self.size(),
            "max": self.isMaximized(),
            "state": self.saveState(),
            "full": self.isFullScreen(),
            "zoom": self.canvas.zoom,
            "h": self.canvas.horizontalScrollBar().value(),
            "v": self.canvas.verticalScrollBar().value(),
            "sel": list(self.canvas.mscene.selected_topic_ids()),
            "dock": self.dock.isVisible(),
            "autosave_rev": self._autosave_rev,
        }

    def restore_view_state(self, st: dict) -> None:
        self.restoreGeometry(st["geometry"])
        if not st["max"]:
            self.resize(st["size"])
            self.move(st["pos"])
        self.restoreState(st["state"])
        self.dock.setVisible(st["dock"])
        self._autosave_rev = st["autosave_rev"]
        if st["sel"]:
            self.canvas.mscene.select_ids(st["sel"])
        self.canvas.set_zoom(st["zoom"])
        # as barras só aceitam o valor depois que o layout da janela nova assentou
        QTimer.singleShot(0, lambda: (self.canvas.horizontalScrollBar().setValue(st["h"]),
                                      self.canvas.verticalScrollBar().setValue(st["v"])))

    def close_for_rebuild(self) -> None:
        """Fecha sem perguntar nada: o documento continua aberto na janela nova."""
        self._rebuilding = True
        self.close()

    def closeEvent(self, e: QCloseEvent) -> None:
        if getattr(self, "_rebuilding", False):
            self.autosave_timer.stop()
            self.app.window_closed(self)
            e.accept()
            return
        if not self.maybe_save():
            e.ignore()
            return
        self.autosave_timer.stop()
        self.app.recovery.remove(self.doc.uid)
        self.app.window_closed(self)
        e.accept()


def _safe_name(text: str) -> str:
    s = "".join(ch for ch in text.split("\n")[0] if ch not in '\\/:*?"<>|').strip()
    return s[:60] or "mapa"


def _mac(text: str) -> str:
    """No macOS, exibe ⌘/⇧ no lugar de Ctrl/Shift nas dicas."""
    import sys
    if sys.platform == "darwin":
        return text.replace("Ctrl+", "⌘").replace("Alt+", "⌥").replace("Shift+", "⇧")
    return text
