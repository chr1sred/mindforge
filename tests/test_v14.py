"""Testes da versão 1.4: cores consistentes, Temas rápidos, formatação rápida e relações."""
import random
import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from mindforge import colorthemes as ct
from mindforge.document import Document
from mindforge.layouts import LAYOUTS
from mindforge.model import ops
from mindforge.model.topic import MindMap, Topic
from mindforge.view.scene import MindScene


def _mapa(layout="mapa_mental", n=5):
    m = MindMap(Topic("Raiz"), layout)
    ct.apply_default(m, ct.CATALOG["colorido/arco_iris"].as_setting(), 0)
    for i in range(n):
        t = ops.add_child(m, m.root.id, f"Principal {i}")
        for j in range(2):
            s = ops.add_child(m, t.id, f"Sub {i}.{j}")
            ops.add_child(m, s.id, f"Neto {i}.{j}")
    return m


def _cena(m):
    s = MindScene(Document(m))
    s.sync()
    return s


def _cores(s, m):
    return {t.id: (s.visuals[t.id].style.fill, s.visuals[t.id].style.text_color,
                   s.visuals[t.id].style.line_color, s.visuals[t.id].branch) for t in m.all_topics()}


# ------------------------------------------------- trocar tema recolore tudo
def test_trocar_tema_recolore_todos_os_niveis_em_todos_os_esqueletos(qapp):
    for layout in LAYOUTS:
        m = _mapa(layout)
        m.settings["branch_palette"] = "neon"          # roda escolhida antes: não pode "prender" as cores
        m.settings["background"] = "#FFEEDD"
        antes = _cores(_cena(m), m)
        ops.apply_color_theme(m, ct.CATALOG["classico/terra"].as_setting(), None)
        assert "branch_palette" not in m.settings and "background" not in m.settings
        s = _cena(m)
        depois = _cores(s, m)
        th = ct.build_theme(ct.CATALOG["classico/terra"].colors, 0)
        for t in m.all_topics():
            assert depois[t.id] != antes[t.id], (layout, t.text)
        for i, t in enumerate(m.root.children):
            assert s.visuals[t.id].branch == th.palette[i % len(th.palette)], layout


def test_cor_estatica_e_limpa_ao_trocar_tema(qapp):
    m = _mapa()
    m.settings["rainbow"] = False
    m.settings["static_color"] = "#E5534B"
    ops.apply_color_theme(m, ct.CATALOG["colorido/oceano"].as_setting(), 2)
    s = _cena(m)
    assert {s.visuals[t.id].branch for t in m.root.children} == {ct.build_theme(
        ct.CATALOG["colorido/oceano"].colors, 2).mono}


def test_espinha_de_peixe_principais_preenchidos_e_variacoes_funcionam(qapp):
    estilos = []
    for v in range(len(ct.VARIANTS)):
        m = _mapa("espinha_peixe")
        ops.apply_color_theme(m, ct.CATALOG["colorido/aurora"].as_setting(), v)
        s = _cena(m)
        st = s.visuals[m.root.children[0].id].style
        assert st.shape == "capsula"
        sub = s.visuals[m.root.children[0].children[0].id].style
        assert sub.shape == "nenhuma" and not sub.fill
        estilos.append((st.fill, st.border, st.text_color, s.background_color))
    contraste = estilos[0]
    assert contraste[0] == ct.build_theme(ct.CATALOG["colorido/aurora"].colors, 0).palette[0]   # preenchido
    assert not contraste[1]                                                                    # sem contorno
    assert len(set(estilos)) >= 5          # as variações mudam o visual da espinha de peixe


# ------------------------------------------------- cores manuais
def test_cores_manuais_contagem_e_repor(qapp):
    m = _mapa()
    a, b = m.root.children[0], m.root.children[1]
    ops.set_styles(m, [a.id], {"fill": "#123456", "font_size": 30})
    ops.set_styles(m, [b.id], {"text_color": "#FF0000"})
    assert sorted(ops.topics_with_manual_colors(m)) == sorted([a.id, b.id])
    ops.clear_colors(m)
    assert ops.topics_with_manual_colors(m) == []
    assert a.style == {"font_size": 30}            # fonte/tamanho continuam


def test_painel_aviso_de_cores_manuais(window):
    p = window.panel
    doc = window.doc
    t = doc.map.root.children[0]
    doc.apply("x", lambda m: ops.set_styles(m, [t.id], {"fill": "#123456"}))
    QTest.qWait(20)
    assert not p.manual_row.isHidden()
    assert "1" in p.manual_label.text()
    p.manual_reset.click()
    QTest.qWait(20)
    assert "fill" not in doc.map.find(t.id).style
    assert p.manual_row.isHidden()
    window.undo()
    assert doc.map.find(t.id).style.get("fill") == "#123456"


# ------------------------------------------------- temas rápidos
def test_temas_rapidos_pintam_o_mapa_inteiro(qapp):
    assert len(ct.QUICK_THEMES) == 12
    for key, q in ct.QUICK_THEMES.items():
        assert q.palette_id in ct.CATALOG
        m = _mapa("organograma")
        t = m.root.children[0]
        ops.set_styles(m, [t.id], {"fill": "#123456", "font_size": 28})
        m.settings.update({"branch_palette": "terra", "background": "#000000"})
        ops.apply_color_theme(m, ct.CATALOG[q.palette_id].as_setting(), q.variant, reset_manual_colors=True)
        assert ct.active_quick_theme(m) == key
        assert m.layout == "organograma"
        assert t.style == {"font_size": 28}         # só as cores saem
        s = _cena(m)
        assert s.visuals[t.id].style.fill != "#123456" or q.variant in (4,)


def test_circulo_do_tema_rapido_tem_central_e_ramos():
    for q in ct.QUICK_THEMES.values():
        central, branches, bg = ct.quick_theme_colors(q)
        assert ct.is_hex(central) and len(branches) >= 3 and ct.is_hex(bg)


def test_painel_e_menu_de_temas_rapidos(window):
    p = window.panel
    doc = window.doc
    p.quick_btns["noite"].click()
    QTest.qWait(20)
    assert ct.active_quick_theme(doc.map) == "noite"
    assert p.quick_btns["noite"].isChecked() and not p.quick_btns["classico"].isChecked()
    from mindforge.themes import is_dark
    assert is_dark(window.canvas.mscene.background_color)
    window._fill_quick_menu()
    acts = [a for a in window.quick_menu.actions() if a.isCheckable()]
    assert len(acts) == 12 and sum(a.isChecked() for a in acts) == 1
    next(a for a in acts if a.text() == "Pastel").trigger()
    assert ct.active_quick_theme(doc.map) == "pastel"
    window.undo()
    assert ct.active_quick_theme(doc.map) == "noite"
    # escolher a roda depois tira a marcação do tema rápido
    p.wheel_btn.picked.emit("neon")
    assert ct.active_quick_theme(doc.map) is None


# ------------------------------------------------- formatação rápida
def _key(w, key, mods=Qt.KeyboardModifier.ControlModifier):
    QTest.keyClick(w.canvas, key, mods)
    QTest.qWait(10)


def test_atalhos_negrito_italico_tachado_na_selecao(window):
    c = window.canvas
    doc = window.doc
    a, b = doc.map.root.children[0], doc.map.root.children[1]
    c.select_ids([a.id, b.id])
    s = c.mscene
    assert s.visuals[a.id].style.bold      # principais já são semibold (600)
    # seleção mista → liga em todos; de novo → desliga
    doc.apply("x", lambda m: ops.set_styles(m, [a.id], {"italic": True}))
    c.select_ids([a.id, b.id])
    _key(window, Qt.Key.Key_I)
    assert s.visuals[a.id].style.italic and s.visuals[b.id].style.italic
    _key(window, Qt.Key.Key_I)
    assert not s.visuals[a.id].style.italic and not s.visuals[b.id].style.italic
    _key(window, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert s.visuals[a.id].style.strike and s.visuals[b.id].style.strike
    _key(window, Qt.Key.Key_B)
    assert not s.visuals[a.id].style.bold
    _key(window, Qt.Key.Key_B)
    assert s.visuals[a.id].style.bold
    n = doc.undo_stack.count()
    window.undo()
    assert doc.undo_stack.index() == n - 1 and not s.visuals[a.id].style.bold   # 1 desfazer por atalho


def test_atalhos_durante_a_edicao_nao_saem_da_edicao(window):
    c = window.canvas
    doc = window.doc
    t = doc.map.root.children[0]
    c.select_id(t.id)
    c.start_edit(t.id)
    ed = c.editor
    ed.textCursor().insertText("Novo texto")
    QTest.qWait(10)
    QTest.keyClick(c, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(20)
    assert c.editor is ed                                   # continua editando
    assert c.mscene.visuals[t.id].style.italic
    assert ed.font().italic()                               # o editor mostra o itálico
    assert ed.toPlainText() == "Novo texto"                 # o texto digitado não se perde
    QTest.keyClick(c, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    QTest.qWait(20)
    assert c.mscene.visuals[t.id].style.strike and ed.font().strikeOut()
    QTest.keyClick(c, Qt.Key.Key_Return)
    QTest.qWait(20)
    assert doc.map.find(t.id).text == "Novo texto"


# ------------------------------------------------- relações
def test_rotulo_de_relacao_nao_cobre_topicos(qapp):
    for layout in LAYOUTS:
        for seed in range(4):
            r = random.Random(seed)
            m = _mapa(layout, 4)
            tops = list(m.all_topics())
            for k in range(3):
                a, b = r.sample(tops[1:], 2)
                rel = ops.add_relation(m, a.id, b.id)
                rel.label = f"relação {k}"
            s = _cena(m)
            boxes = [it.mapRectToScene(it.box_rect()) for it in s.topic_items.values()]
            labels = []
            for ri in s.rel_items.values():
                lr = ri.label_scene_rect()
                hits = [bx for bx in boxes if lr.intersects(bx)]
                labels.append(lr)
                # só aceita sobreposição se não havia nenhum ponto livre na curva
                if hits:
                    free = False
                    for t in (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82):
                        c = ri.path().pointAtPercent(t)
                        test = lr.translated(c - lr.center())
                        if not any(test.adjusted(-3, -3, 3, 3).intersects(bx.adjusted(-4, -3, 4, 3)) for bx in boxes):
                            free = True
                    assert not free, (layout, seed)


def test_trocar_tema_em_mapa_grande_e_rapido(qapp):
    r = random.Random(3)
    m = MindMap(Topic("Raiz"), "mapa_mental")
    nodes = [m.root]
    for i in range(1000):
        nodes.append(ops.add_child(m, r.choice(nodes).id, f"T{i}"))
    doc = Document(m)
    s = MindScene(doc)
    s.sync()
    t0 = time.perf_counter()
    doc.apply("x", lambda mm: ops.apply_color_theme(mm, ct.CATALOG["classico/nordico"].as_setting(), 4))
    s.sync()
    assert time.perf_counter() - t0 < 3.0
