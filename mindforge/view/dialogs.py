"""Diálogos: novo mapa (modelos), exportação e atalhos de teclado."""
from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QRadioButton,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from mindforge.export import ExportOptions
from mindforge.i18n import N_, tr
from mindforge.templates import TEMPLATES, Template
from mindforge.view.resources import render_thumbnail

THUMB = QSize(220, 140)


class TemplateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Novo mapa"))
        self.resize(820, 600)
        lay = QVBoxLayout(self)
        title = QLabel(tr("<b>Escolha uma estrutura para começar</b>"))
        lay.addWidget(title)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 24, THUMB.height() + 44))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setWordWrap(True)
        self.list.setSpacing(4)
        lay.addWidget(self.list, 1)
        self.desc = QLabel()
        self.desc.setStyleSheet("color: palette(mid);")
        lay.addWidget(self.desc)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Tema de cores:")))
        self.theme = QComboBox()
        self.theme.setIconSize(QSize(60, 14))
        self._fill_themes()
        row.addWidget(self.theme)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Criar"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.theme.currentIndexChanged.connect(self._rebuild)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        self.list.currentItemChanged.connect(self._on_current)
        self._rebuild()

    def _fill_themes(self) -> None:
        from mindforge import colorthemes as ct
        from mindforge.view.colorpanel import palette_name, palette_store, strip_pixmap
        dp, _dv = ct.default_for_new_maps()
        dpal = ct.palette_from_setting(dp)
        self.theme.addItem(QIcon(strip_pixmap(dpal.colors, QSize(60, 14), 3)),
                           tr("Padrão ({nome})", nome=palette_name(dpal)), None)
        for p in (*palette_store().palettes, *ct.COLORIDO, *ct.CLASSICO):
            self.theme.addItem(QIcon(strip_pixmap(p.colors, QSize(60, 14), 3)), palette_name(p), p.as_setting())

    def _rebuild(self) -> None:
        cur = self.list.currentRow()
        pal = self.theme.currentData()
        self.list.clear()
        for t in TEMPLATES:
            pm = render_thumbnail(t.create(palette=pal, variant=None if pal is None else 0), THUMB)
            name = tr(t.name) + (tr("  · exemplo") if t.sample else "")
            ic = QIcon(pm)
            ic.addPixmap(pm, QIcon.Mode.Selected)      # sem a "tinta" azul sobre a miniatura
            it = QListWidgetItem(ic, name)
            it.setData(Qt.ItemDataRole.UserRole, t.key)
            it.setToolTip(tr(t.description))
            self.list.addItem(it)
        self.list.setCurrentRow(max(0, cur))

    def _on_current(self, item: Optional[QListWidgetItem], _prev=None) -> None:
        t = self.selected_template()
        self.desc.setText(tr(t.description) if t else "")

    def selected_template(self) -> Optional[Template]:
        it = self.list.currentItem()
        if it is None:
            return None
        key = it.data(Qt.ItemDataRole.UserRole)
        return next((t for t in TEMPLATES if t.key == key), None)

    def selected_palette(self) -> Optional[dict]:
        """Paleta escolhida (None = tema padrão para novos mapas)."""
        return self.theme.currentData()


class ExportDialog(QDialog):
    def __init__(self, parent=None, has_selection: bool = False, initial_fmt: str = "png",
                 dark_background: bool = False):
        super().__init__(parent)
        self.dark_background = dark_background
        self.setWindowTitle(tr("Exportar mapa"))
        self.settings = QSettings()
        lay = QVBoxLayout(self)

        fmt_box = QGroupBox(tr("Formato"))
        fl = QHBoxLayout(fmt_box)
        self.fmt_group = QButtonGroup(self)
        self.rb = {}
        for i, (key, label) in enumerate((("png", tr("PNG (imagem)")), ("svg", tr("SVG (vetorial)")),
                                          ("pdf", tr("PDF (documento)")))):
            r = QRadioButton(label)
            self.fmt_group.addButton(r, i)
            self.rb[key] = r
            fl.addWidget(r)
        lay.addWidget(fmt_box)

        scope_box = QGroupBox(tr("Conteúdo"))
        sl = QVBoxLayout(scope_box)
        self.scope_all = QRadioButton(tr("Mapa inteiro"))
        self.scope_sel = QRadioButton(tr("Somente o ramo selecionado"))
        self.scope_all.setChecked(True)
        self.scope_sel.setEnabled(has_selection)
        sl.addWidget(self.scope_all)
        sl.addWidget(self.scope_sel)
        lay.addWidget(scope_box)

        self.stack = QStackedWidget()
        # PNG
        png = QWidget()
        pf = QFormLayout(png)
        self.png_transparent = QCheckBox(tr("Fundo transparente"))
        self.png_scale = QComboBox()
        for s in (1, 2, 3, 4):
            self.png_scale.addItem(f"{s}x" + (tr("  (recomendado)") if s == 2 else ""), s)
        pf.addRow(self.png_transparent)
        self.png_warn = self._dark_warning()
        pf.addRow(self.png_warn)
        self.png_transparent.toggled.connect(lambda on: self.png_warn.setVisible(on and self.dark_background))
        pf.addRow(tr("Resolução:"), self.png_scale)
        # SVG
        svg = QWidget()
        sf = QFormLayout(svg)
        self.svg_transparent = QCheckBox(tr("Fundo transparente"))
        self.svg_curves = QCheckBox(tr("Converter textos em curvas (portabilidade total; texto não editável)"))
        sf.addRow(self.svg_transparent)
        self.svg_warn = self._dark_warning()
        sf.addRow(self.svg_warn)
        self.svg_transparent.toggled.connect(lambda on: self.svg_warn.setVisible(on and self.dark_background))
        sf.addRow(self.svg_curves)
        # PDF
        pdf = QWidget()
        df = QFormLayout(pdf)
        self.pdf_page = QComboBox()
        for key, label in (("mapa", tr("Página do tamanho do mapa")), ("a4_paisagem", tr("A4 paisagem")),
                           ("a4_retrato", tr("A4 retrato")), ("a3_paisagem", tr("A3 paisagem"))):
            self.pdf_page.addItem(label, key)
        self.pdf_bg = QCheckBox(tr("Incluir cor de fundo do tema"))
        df.addRow(tr("Página:"), self.pdf_page)
        df.addRow(self.pdf_bg)
        for w in (png, svg, pdf):
            self.stack.addWidget(w)
        lay.addWidget(self.stack)

        mrow = QFormLayout()
        self.margin = QSpinBox()
        self.margin.setRange(0, 400)
        self.margin.setSuffix(" px")
        mrow.addRow(tr("Margem:"), self.margin)
        lay.addLayout(mrow)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Exportar…"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.fmt_group.idToggled.connect(lambda i, on: on and self.stack.setCurrentIndex(i))
        self._load(initial_fmt)

    def _load(self, initial_fmt: str) -> None:
        s = self.settings
        fmt = s.value("export/fmt", initial_fmt) or "png"
        self.rb.get(fmt, self.rb["png"]).setChecked(True)
        self.stack.setCurrentIndex(["png", "svg", "pdf"].index(fmt if fmt in self.rb else "png"))
        self.png_transparent.setChecked(s.value("export/png_transparent", True, type=bool))
        idx = self.png_scale.findData(int(s.value("export/png_scale", 2)))
        self.png_scale.setCurrentIndex(max(0, idx))
        self.svg_transparent.setChecked(s.value("export/svg_transparent", True, type=bool))
        self.svg_curves.setChecked(s.value("export/svg_curves", False, type=bool))
        self.pdf_page.setCurrentIndex(max(0, self.pdf_page.findData(s.value("export/pdf_page", "mapa"))))
        self.pdf_bg.setChecked(s.value("export/pdf_bg", True, type=bool))
        self.margin.setValue(int(s.value("export/margin", 32)))

    def fmt(self) -> str:
        return ["png", "svg", "pdf"][max(0, self.fmt_group.checkedId())]

    def options(self) -> ExportOptions:
        f = self.fmt()
        s = self.settings
        s.setValue("export/fmt", f)
        s.setValue("export/png_transparent", self.png_transparent.isChecked())
        s.setValue("export/png_scale", self.png_scale.currentData())
        s.setValue("export/svg_transparent", self.svg_transparent.isChecked())
        s.setValue("export/svg_curves", self.svg_curves.isChecked())
        s.setValue("export/pdf_page", self.pdf_page.currentData())
        s.setValue("export/pdf_bg", self.pdf_bg.isChecked())
        s.setValue("export/margin", self.margin.value())
        return ExportOptions(
            fmt=f,
            scale=float(self.png_scale.currentData()),
            transparent=self.png_transparent.isChecked() if f == "png" else self.svg_transparent.isChecked(),
            margin=float(self.margin.value()),
            text_as_paths=self.svg_curves.isChecked(),
            pdf_page=self.pdf_page.currentData(),
            pdf_background=self.pdf_bg.isChecked(),
        )

    def _dark_warning(self) -> QLabel:
        lab = QLabel(tr("⚠ Este mapa tem fundo escuro e textos claros: com fundo transparente, eles podem "
                        "sumir em documentos brancos. Desmarque para incluir o fundo."))
        lab.setWordWrap(True)
        lab.setObjectName("Warning")
        lab.setVisible(False)
        return lab

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.png_warn.setVisible(self.png_transparent.isChecked() and self.dark_background)
        self.svg_warn.setVisible(self.svg_transparent.isChecked() and self.dark_background)

    def only_selection(self) -> bool:
        return self.scope_sel.isChecked() and self.scope_sel.isEnabled()


def ask_export_path(parent, fmt: str, base_name: str) -> Optional[str]:
    settings = QSettings()
    folder = settings.value("export/dir", os.path.expanduser("~"))
    filters = {"png": tr("Imagem PNG (*.png)"), "svg": tr("Imagem SVG (*.svg)"), "pdf": tr("Documento PDF (*.pdf)")}
    safe = "".join(c for c in base_name if c not in '\\/:*?"<>|\n').strip()[:60] or tr("mapa")
    path, _ = QFileDialog.getSaveFileName(parent, tr("Exportar como"), os.path.join(folder, f"{safe}.{fmt}"),
                                          filters[fmt])
    if not path:
        return None
    if not path.lower().endswith("." + fmt):
        path += "." + fmt
    settings.setValue("export/dir", os.path.dirname(path))
    return path


MOD = "⌘" if sys.platform == "darwin" else "Ctrl"
SHIFT = "⇧" if sys.platform == "darwin" else "Shift"

# (ação, tecla). Teclas usam {mod}/{shift}; textos entre as teclas também são traduzidos.
SHORTCUTS = [
    (N_("Novo subtópico (filho)"), "Tab"),
    (N_("Novo tópico irmão (abaixo)"), "Enter"),
    (N_("Novo tópico irmão (acima)"), "{shift}+Enter"),
    (N_("Inserir tópico pai"), "{mod}+Enter"),
    (N_("Editar texto do tópico"), N_("F2, Espaço ou comece a digitar")),
    (N_("Quebra de linha durante a edição"), "{shift}+Enter"),
    (N_("Confirmar / cancelar edição"), "Enter / Esc"),
    (N_("Excluir tópico (e ramo)"), "Delete / Backspace"),
    (N_("Navegar entre tópicos"), "← ↑ → ↓"),
    (N_("Mover tópico entre irmãos"), "{mod}+↑ / {mod}+↓"),
    (N_("Recolher / expandir ramo"), N_("{mod}+/ ou clique no ⊖ / no número")),
    (N_("Expandir o ramo inteiro"), N_("Alt+clique no número")),
    (N_("Desfazer / Refazer"), N_("{mod}+Z / {mod}+{shift}+Z ou {mod}+Y")),
    (N_("Copiar / Recortar / Colar ramo"), "{mod}+C / {mod}+X / {mod}+V"),
    (N_("Duplicar tópico"), "{mod}+D"),
    (N_("Selecionar todos os tópicos"), "{mod}+A"),
    (N_("Relação entre tópicos"), N_("{mod}+R, depois clique no destino")),
    (N_("Tópico flutuante"), N_("Duplo clique no fundo")),
    (N_("Novo / Abrir / Salvar / Salvar como"), "{mod}+N / {mod}+O / {mod}+S / {mod}+{shift}+S"),
    (N_("Exportar"), "{mod}+E"),
    (N_("Buscar"), "{mod}+F"),
    (N_("Zoom + / − / ajustar / 100%"), "{mod}+= / {mod}+- / {mod}+0 / {mod}+1"),
    (N_("Zoom com mouse / trackpad"), N_("{mod}+roda ou pinça")),
    (N_("Mover a tela"), N_("Botão direito+arrastar, Espaço+arrastar, botão do meio ou rolagem")),
]


def shortcut_rows() -> list[tuple[str, str]]:
    """Linhas da tabela de atalhos já traduzidas e com as teclas do sistema."""
    return [(tr(a), tr(k).format(mod=MOD, shift=SHIFT)) for a, k in SHORTCUTS]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Atalhos de teclado"))
        self.resize(620, 640)
        lay = QVBoxLayout(self)
        table = QTableWidget(len(SHORTCUTS), 2)
        table.setHorizontalHeaderLabels([tr("Ação"), tr("Atalho")])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i, (a, k) in enumerate(shortcut_rows()):
            table.setItem(i, 0, QTableWidgetItem(a))
            table.setItem(i, 1, QTableWidgetItem(k))
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(table)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText(tr("Fechar"))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class SettingsDialog(QDialog):
    """Ajustes do aplicativo. Hoje: idioma da interface (troca imediata)."""

    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        from mindforge.i18n import LANGUAGES
        self.setWindowTitle(tr("Ajustes"))
        self.setMinimumWidth(360)
        lay = QVBoxLayout(self)
        box = QGroupBox("Idioma / Language")
        bl = QVBoxLayout(box)
        self._radios: dict[str, QRadioButton] = {}
        for code, label in LANGUAGES.items():
            rb = QRadioButton(label)
            rb.setChecked(code == current)
            bl.addWidget(rb)
            self._radios[code] = rb
        lay.addWidget(box)
        note = QLabel(tr("A interface muda na hora. O conteúdo dos mapas não é traduzido."))
        note.setWordWrap(True)
        note.setObjectName("Muted")
        lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("OK"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def selected_language(self) -> str:
        for code, rb in self._radios.items():
            if rb.isChecked():
                return code
        return next(iter(self._radios))
