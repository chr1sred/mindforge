"""Idiomas (1.3): catálogo completo, interface sem texto vazado e troca imediata."""
import ast
import os
import re

import pytest
import shiboken6
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QMenu, QWidget

from mindforge import i18n
from mindforge.i18n.en_us import EN

ROOT = os.path.join(os.path.dirname(__file__), "..", "mindforge")
FUNCS = {"tr": 1, "ntr": 2, "N_": 1}
PT_WORDS = re.compile(r"[ãõçáéíóúâêôà]|\b(de|do|da|para|tópico|não|ou|com|em|ramo|mapa)\b", re.I)


def _keys() -> dict[str, str]:
    out = {}
    for r, _d, files in os.walk(ROOT):
        if "i18n" in r:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(r, f)
            for n in ast.walk(ast.parse(open(p, encoding="utf-8").read())):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS:
                    for a in n.args[:FUNCS[n.func.id]]:
                        if isinstance(a, ast.Constant) and isinstance(a.value, str):
                            out.setdefault(a.value, f"{os.path.relpath(p, ROOT)}:{n.lineno}")
    return out


# --------------------------------------------------------------- catálogo
def test_toda_chave_tem_traducao():
    missing = {k: where for k, where in _keys().items() if k not in EN}
    assert not missing, "Sem tradução em en_us.py:\n" + "\n".join(f"{w}: {k!r}" for k, w in missing.items())


def test_marcadores_iguais_na_traducao():
    for k, v in EN.items():
        assert set(re.findall(r"\{(\w*)\}", k)) == set(re.findall(r"\{(\w*)\}", v)), k


def test_atalhos_preservados_na_traducao():
    """Os atalhos entre parênteses precisam sobreviver (no Mac viram ⌘/⇧)."""
    for k, v in EN.items():
        for sc in re.findall(r"(?:Ctrl|Shift)\+\S+", k):
            assert sc in v, (k, sc)


def test_tr_ntr_e_fallback():
    i18n.set_language("en_US")
    try:
        assert i18n.tr("Salvar") == "Save"
        assert i18n.tr("Salvo em {path}", path="/x") == "Saved to /x"
        assert i18n.ntr("{n} tópico", "{n} tópicos", 1) == "1 topic"
        assert i18n.ntr("{n} tópico", "{n} tópicos", 3) == "3 topics"
        assert i18n.tr("texto sem tradução") == "texto sem tradução"
    finally:
        i18n.set_language("pt_BR")
    assert i18n.tr("Salvar") == "Salvar"
    assert i18n.ntr("{n} tópico", "{n} tópicos", 2) == "2 tópicos"


def test_idioma_inicial_segue_o_sistema(monkeypatch):
    from PySide6.QtCore import QLocale
    monkeypatch.delenv("MINDFORGE_IDIOMA", raising=False)
    old = QLocale()
    try:
        QLocale.setDefault(QLocale("pt_BR"))
        monkeypatch.setattr(QLocale, "system", staticmethod(lambda: QLocale("pt_BR")))
        assert i18n.system_language() == "pt_BR"
        monkeypatch.setattr(QLocale, "system", staticmethod(lambda: QLocale("de_DE")))
        assert i18n.system_language() == "en_US"
    finally:
        QLocale.setDefault(old)


def test_idioma_salvo_tem_prioridade(qapp, monkeypatch):
    from PySide6.QtCore import QSettings
    monkeypatch.delenv("MINDFORGE_IDIOMA", raising=False)
    QSettings().setValue("ui/language", "en_US")
    try:
        assert qapp.initial_language() == "en_US"
    finally:
        QSettings().remove("ui/language")


# ------------------------------------------------------------ interface
def _texts(root):
    # No macOS, o Qt gerencia a barra de menus nativa e recicla objetos internos (menus/ações
    # movidos para o menu do app); por isso objetos já destruídos pelo Qt são ignorados aqui.
    out = []
    for w in [root, *root.findChildren(QWidget)]:
        if not shiboken6.isValid(w):
            continue
        for attr in ("text", "toolTip", "statusTip", "windowTitle", "placeholderText", "title"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    v = f()
                except TypeError:
                    continue
                if isinstance(v, str) and v:
                    out.append(v)
        if isinstance(w, QComboBox):
            out += [w.itemText(i) for i in range(w.count())]
        for a in w.actions():
            if not shiboken6.isValid(a):
                continue
            out += [t for t in (a.text(), a.toolTip(), a.statusTip()) if t]
            sub = a.menu()
            if sub is not None and shiboken6.isValid(sub):
                out += _texts(sub)
    return out


ALLOWED = {"Português (PT-BR)", "Idioma / Language"}


def _leaks(widget):
    content = set()
    win = widget.window() if hasattr(widget, "window") else widget
    doc = getattr(win, "doc", None)
    if doc is not None:     # o conteúdo do mapa não é traduzido
        stack = [doc.map.root, *doc.map.floating]
        while stack:
            t = stack.pop()
            content.add(t.text)
            stack += t.children
    return sorted({t for t in _texts(widget)
                   if PT_WORDS.search(t) and t not in ALLOWED and t.split("\n")[0] not in content})


def test_interface_inglesa_sem_portugues(qapp):
    from mindforge.document import Document
    from mindforge.templates import get_template
    from mindforge.view.dialogs import ExportDialog, SettingsDialog, ShortcutsDialog, TemplateDialog
    qapp._apply_language("en_US", persist=False)
    w = qapp.new_window(Document(get_template("mapa_direita").create()))
    QTest.qWaitForWindowExposed(w)
    try:
        assert w.doc.map.root.text == "Central Topic"
        assert w.menuBar().actions()[0].text() == "&File"
        w.canvas.mscene.select_ids([w.doc.map.root.children[0].id])
        QTest.qWait(30)
        assert _leaks(w) == []
        from mindforge import colorthemes as ct
        from mindforge.view.colorpanel import PaletteDialog, PalettePopup, WheelPopup
        w.panel._refresh_map()
        assert _leaks(w.panel) == []
        extra = (PalettePopup(w, "colorido/aurora", False), PaletteDialog(w), WheelPopup(w, None, ct.DEFAULT_PALETTE.colors))
        for dlg in (TemplateDialog(w), ExportDialog(w, True, dark_background=True), ShortcutsDialog(w),
                    SettingsDialog("en_US", w), *extra):
            assert _leaks(dlg) == [], type(dlg).__name__
            dlg.deleteLater()
    finally:
        w.doc.mark_saved()
        w.close()
        QTest.qWait(10)


def test_novos_topicos_no_idioma_atual(qapp):
    from mindforge.document import Document
    from mindforge.model import ops
    from mindforge.templates import get_template
    qapp._apply_language("en_US", persist=False)
    m = get_template("mapa_mental").create()
    assert m.root.text == "Central Topic" and m.root.children[0].text == "Main Topic 1"
    c = ops.add_child(m, m.root.id)
    assert c.text == "Main Topic"
    assert ops.add_child(m, c.id).text == "Subtopic"
    assert ops.add_floating(m, 0, 0).text == "Floating Topic"
    del Document


# ---------------------------------------------------------------- troca
def test_troca_de_idioma_preserva_documento_e_desfazer(qapp):
    from mindforge.document import Document
    from mindforge.model import ops
    from mindforge.templates import get_template
    w = qapp.new_window(Document(get_template("mapa_direita").create()))
    QTest.qWaitForWindowExposed(w)
    doc = w.doc
    tid = doc.map.root.children[0].id
    doc.apply("Mover tópico", lambda m: ops.add_child(m, tid))
    n_before = len(doc.map.root.children[0].children)
    assert w.a_undo.text() == "Desfazer Mover tópico"
    w.canvas.mscene.select_ids([tid])
    count = len(qapp.windows)

    qapp.set_language("en_US")
    QTest.qWait(50)
    try:
        assert len(qapp.windows) == count
        nw = next(x for x in qapp.windows if x.doc is doc)
        assert nw is not w
        assert nw.menuBar().actions()[0].text() == "&File"
        assert nw.a_undo.isEnabled() and nw.a_undo.text() == "Undo Move topic"
        assert nw.doc.is_modified()                       # não perdeu o "não salvo"
        assert nw.canvas.mscene.selected_topic_ids() == [tid]
        nw.undo()
        assert len(doc.map.root.children[0].children) == n_before - 1
        nw.redo()
        assert len(doc.map.root.children[0].children) == n_before
        # o mapa em si não é traduzido
        assert doc.map.root.text == "Tema central"
    finally:
        qapp.set_language("pt_BR")
        QTest.qWait(20)
        for x in [x for x in qapp.windows if x.doc is doc]:
            x.doc.mark_saved()
            x.close()
        QTest.qWait(10)


def test_ajustes_no_menu(window):
    a = window.a_settings
    from PySide6.QtGui import QAction
    assert a.menuRole() == QAction.MenuRole.PreferencesRole
    # o menu que contém a ação (no macOS o Qt ainda a leva para o menu do app)
    menus = [o for o in a.associatedObjects() if isinstance(o, QMenu)]
    assert len(menus) == 1
    help_menu = menus[0]
    assert help_menu.title() == "Aj&uda"
    acts = [x for x in help_menu.actions() if not x.isSeparator()]
    # logo depois de "Sobre"
    assert acts[-1] is a and acts[-2].menuRole() == QAction.MenuRole.AboutRole


@pytest.mark.parametrize("lang", ["pt_BR", "en_US"])
def test_atalhos_funcionam_nos_dois_idiomas(qapp, lang):
    from PySide6.QtCore import Qt
    from mindforge.document import Document
    from mindforge.templates import get_template
    qapp._apply_language(lang, persist=False)
    w = qapp.new_window(Document(get_template("mapa_direita").create()))
    QTest.qWaitForWindowExposed(w)
    w.activateWindow()
    w.canvas.setFocus()
    QTest.qWait(120)
    try:
        root = w.doc.map.root
        w.canvas.mscene.select_ids([root.id])
        n = len(root.children)
        QTest.keyClick(w.canvas, Qt.Key.Key_Tab)
        QTest.keyClick(w.canvas, Qt.Key.Key_Escape)
        assert len(root.children) == n + 1
        assert root.children[-1].text == ("Main Topic" if lang == "en_US" else "Tópico principal")
    finally:
        w.doc.mark_saved()
        w.close()
        QTest.qWait(10)
