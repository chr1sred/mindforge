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
from mindforge.templates import TEMPLATES, Template
from mindforge.themes import visible_themes
from mindforge.view.resources import render_thumbnail

THUMB = QSize(220, 140)


class TemplateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo mapa")
        self.resize(820, 600)
        lay = QVBoxLayout(self)
        title = QLabel("<b>Escolha uma estrutura para começar</b>")
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
        row.addWidget(QLabel("Tema:"))
        self.theme = QComboBox()
        for t in visible_themes():
            self.theme.addItem(t.label, t.key)
        row.addWidget(self.theme)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Criar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.theme.currentIndexChanged.connect(self._rebuild)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        self.list.currentItemChanged.connect(self._on_current)
        self._rebuild()

    def _rebuild(self) -> None:
        cur = self.list.currentRow()
        theme = self.theme.currentData()
        self.list.clear()
        for t in TEMPLATES:
            pm = render_thumbnail(t.create(theme), THUMB)
            name = t.name + ("  · exemplo" if t.sample else "")
            ic = QIcon(pm)
            ic.addPixmap(pm, QIcon.Mode.Selected)      # sem a "tinta" azul sobre a miniatura
            it = QListWidgetItem(ic, name)
            it.setData(Qt.ItemDataRole.UserRole, t.key)
            it.setToolTip(t.description)
            self.list.addItem(it)
        self.list.setCurrentRow(max(0, cur))

    def _on_current(self, item: Optional[QListWidgetItem], _prev=None) -> None:
        t = self.selected_template()
        self.desc.setText(t.description if t else "")

    def selected_template(self) -> Optional[Template]:
        it = self.list.currentItem()
        if it is None:
            return None
        key = it.data(Qt.ItemDataRole.UserRole)
        return next((t for t in TEMPLATES if t.key == key), None)

    def selected_theme(self) -> str:
        return self.theme.currentData()


class ExportDialog(QDialog):
    def __init__(self, parent=None, has_selection: bool = False, initial_fmt: str = "png"):
        super().__init__(parent)
        self.setWindowTitle("Exportar mapa")
        self.settings = QSettings()
        lay = QVBoxLayout(self)

        fmt_box = QGroupBox("Formato")
        fl = QHBoxLayout(fmt_box)
        self.fmt_group = QButtonGroup(self)
        self.rb = {}
        for i, (key, label) in enumerate((("png", "PNG (imagem)"), ("svg", "SVG (vetorial)"),
                                          ("pdf", "PDF (documento)"))):
            r = QRadioButton(label)
            self.fmt_group.addButton(r, i)
            self.rb[key] = r
            fl.addWidget(r)
        lay.addWidget(fmt_box)

        scope_box = QGroupBox("Conteúdo")
        sl = QVBoxLayout(scope_box)
        self.scope_all = QRadioButton("Mapa inteiro")
        self.scope_sel = QRadioButton("Somente o ramo selecionado")
        self.scope_all.setChecked(True)
        self.scope_sel.setEnabled(has_selection)
        sl.addWidget(self.scope_all)
        sl.addWidget(self.scope_sel)
        lay.addWidget(scope_box)

        self.stack = QStackedWidget()
        # PNG
        png = QWidget()
        pf = QFormLayout(png)
        self.png_transparent = QCheckBox("Fundo transparente")
        self.png_scale = QComboBox()
        for s in (1, 2, 3, 4):
            self.png_scale.addItem(f"{s}x" + ("  (recomendado)" if s == 2 else ""), s)
        pf.addRow(self.png_transparent)
        pf.addRow("Resolução:", self.png_scale)
        # SVG
        svg = QWidget()
        sf = QFormLayout(svg)
        self.svg_transparent = QCheckBox("Fundo transparente")
        self.svg_curves = QCheckBox("Converter textos em curvas (portabilidade total; texto não editável)")
        sf.addRow(self.svg_transparent)
        sf.addRow(self.svg_curves)
        # PDF
        pdf = QWidget()
        df = QFormLayout(pdf)
        self.pdf_page = QComboBox()
        for key, label in (("mapa", "Página do tamanho do mapa"), ("a4_paisagem", "A4 paisagem"),
                           ("a4_retrato", "A4 retrato"), ("a3_paisagem", "A3 paisagem")):
            self.pdf_page.addItem(label, key)
        self.pdf_bg = QCheckBox("Incluir cor de fundo do tema")
        df.addRow("Página:", self.pdf_page)
        df.addRow(self.pdf_bg)
        for w in (png, svg, pdf):
            self.stack.addWidget(w)
        lay.addWidget(self.stack)

        mrow = QFormLayout()
        self.margin = QSpinBox()
        self.margin.setRange(0, 400)
        self.margin.setSuffix(" px")
        mrow.addRow("Margem:", self.margin)
        lay.addLayout(mrow)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Exportar…")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
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

    def only_selection(self) -> bool:
        return self.scope_sel.isChecked() and self.scope_sel.isEnabled()


def ask_export_path(parent, fmt: str, base_name: str) -> Optional[str]:
    settings = QSettings()
    folder = settings.value("export/dir", os.path.expanduser("~"))
    filters = {"png": "Imagem PNG (*.png)", "svg": "Imagem SVG (*.svg)", "pdf": "Documento PDF (*.pdf)"}
    safe = "".join(c for c in base_name if c not in '\\/:*?"<>|\n').strip()[:60] or "mapa"
    path, _ = QFileDialog.getSaveFileName(parent, "Exportar como", os.path.join(folder, f"{safe}.{fmt}"),
                                          filters[fmt])
    if not path:
        return None
    if not path.lower().endswith("." + fmt):
        path += "." + fmt
    settings.setValue("export/dir", os.path.dirname(path))
    return path


MOD = "⌘" if sys.platform == "darwin" else "Ctrl"
SHIFT = "⇧" if sys.platform == "darwin" else "Shift"

SHORTCUTS = [
    ("Novo subtópico (filho)", "Tab"),
    ("Novo tópico irmão (abaixo)", "Enter"),
    ("Novo tópico irmão (acima)", f"{SHIFT}+Enter"),
    ("Inserir tópico pai", f"{MOD}+Enter"),
    ("Editar texto do tópico", "F2, Espaço ou comece a digitar"),
    ("Quebra de linha durante a edição", f"{SHIFT}+Enter"),
    ("Confirmar / cancelar edição", "Enter / Esc"),
    ("Excluir tópico (e ramo)", "Delete / Backspace"),
    ("Navegar entre tópicos", "← ↑ → ↓"),
    ("Mover tópico entre irmãos", f"{MOD}+↑ / {MOD}+↓"),
    ("Recolher / expandir ramo", f"{MOD}+/"),
    ("Desfazer / Refazer", f"{MOD}+Z / {MOD}+{SHIFT}+Z ou {MOD}+Y"),
    ("Copiar / Recortar / Colar ramo", f"{MOD}+C / {MOD}+X / {MOD}+V"),
    ("Duplicar tópico", f"{MOD}+D"),
    ("Selecionar todos os tópicos", f"{MOD}+A"),
    ("Relação entre tópicos", f"{MOD}+R, depois clique no destino"),
    ("Tópico flutuante", "Duplo clique no fundo"),
    ("Novo / Abrir / Salvar / Salvar como", f"{MOD}+N / {MOD}+O / {MOD}+S / {MOD}+{SHIFT}+S"),
    ("Exportar", f"{MOD}+E"),
    ("Buscar", f"{MOD}+F"),
    ("Zoom + / − / ajustar / 100%", f"{MOD}+= / {MOD}+- / {MOD}+0 / {MOD}+1"),
    ("Zoom com mouse / trackpad", f"{MOD}+roda ou pinça"),
    ("Mover a tela", "Espaço+arrastar, botão do meio ou rolagem"),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atalhos de teclado")
        self.resize(620, 640)
        lay = QVBoxLayout(self)
        table = QTableWidget(len(SHORTCUTS), 2)
        table.setHorizontalHeaderLabels(["Ação", "Atalho"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i, (a, k) in enumerate(SHORTCUTS):
            table.setItem(i, 0, QTableWidgetItem(a))
            table.setItem(i, 1, QTableWidgetItem(k))
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(table)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
