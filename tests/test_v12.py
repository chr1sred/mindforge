"""Testes da versão 1.2: ramos, texto, limite, painel e compatibilidade."""
import xml.etree.ElementTree as ET

import pytest

from mindforge.document import Document
from mindforge.export import ExportOptions, export_file
from mindforge.model import ops
from mindforge.model.topic import MindMap, Topic
from mindforge.themes import BRANCH_STYLES, LINE_ENDS, SHAPES, get_theme, resolve_style
from mindforge.view.painting import apply_case, build_visual, default_family
from mindforge.view.scene import MindScene


def sample(layout="mapa_direita"):
    m = MindMap(Topic("Raiz"), layout)
    for i in range(3):
        c = ops.add_child(m, m.root.id, f"Principal {i}")
        for j in range(3):
            ops.add_child(m, c.id, f"Sub {j}")
    return m


def scene_for(m):
    s = MindScene(Document(m))
    s.sync()
    return s


def test_fonte_inter_embutida(qapp):
    assert default_family() == "Inter"


def test_compatibilidade_estilos_da_versao_anterior(qapp):
    th = get_theme("classico")
    st = resolve_style(th, "sub", "#F24F4B", {"bold": True, "shape": "sublinhado", "font_size": 20})
    assert st.weight == 700 and st.shape == "sublinhado" and st.font_size == 20
    assert st.border and st.border_width > 0          # sublinhado sempre tem traço


def test_valores_invalidos_sao_ignorados(qapp):
    th = get_theme("classico")
    st = resolve_style(th, "main", "#F24F4B", {"shape": "xyz", "font_size": "abc", "font_weight": "x",
                                               "line_end": "??", "branch_style": 3, "align": "meio"})
    base = resolve_style(th, "main", "#F24F4B")
    assert st == base


def test_peso_numerico_e_negrito(qapp):
    th = get_theme("classico")
    assert resolve_style(th, "sub", None, {"font_weight": 560}).weight == 600
    assert resolve_style(th, "sub", None, {"font_weight": 300, "bold": True}).weight == 300


def test_maiusculas_so_na_exibicao(qapp):
    th = get_theme("classico")
    st = resolve_style(th, "sub", None, {"text_case": "upper"})
    vis = build_visual("olá mundo", st, [], False)
    assert vis.lines == ["OLÁ MUNDO"]
    assert apply_case("ação rápida", "title") == "Ação Rápida"


def test_largura_fixa_quebra_texto(qapp):
    th = get_theme("classico")
    st = resolve_style(th, "sub", None, {"width": 140})
    vis = build_visual("um texto razoavelmente comprido para quebrar", st, [], False)
    assert vis.w == 140 and len(vis.lines) > 1


@pytest.mark.parametrize("shape", list(SHAPES))
def test_todas_as_formas_desenham_e_exportam(qapp, tmp_path, shape):
    m = sample()
    m.root.children[0].style.update(shape=shape, border_style="tracejado", border_level="grosso",
                                    strike=True, align="right")
    s = scene_for(m)
    for fmt in ("png", "svg"):
        export_file(s, str(tmp_path / f"{shape}.{fmt}"), ExportOptions(fmt, scale=1))


def test_riscado_aparece_no_svg(qapp, tmp_path):
    m = sample()
    m.root.children[0].style["strike"] = True
    s = scene_for(m)
    p = tmp_path / "r.svg"
    export_file(s, str(p), ExportOptions("svg"))
    ET.parse(p)                                     # SVG válido
    m.root.children[0].style["strike"] = False
    s.sync()
    p2 = tmp_path / "s.svg"
    export_file(s, str(p2), ExportOptions("svg"))
    assert p.read_text() != p2.read_text()          # o riscado gera geometria própria


@pytest.mark.parametrize("style", list(BRANCH_STYLES))
@pytest.mark.parametrize("layout", ["mapa_direita", "mapa_esquerda", "organograma", "mapa_mental"])
def test_estilos_de_ramo_em_todas_as_direcoes(qapp, style, layout):
    m = sample(layout)
    for t in m.all_topics():
        t.style["branch_style"] = style
    s = scene_for(m)
    groups = [ci for ci in s.conn_items.values() if ci.is_group]
    assert groups and all(ci.strokes for ci in groups)
    assert all(not ci.visual_rect().isNull() for ci in groups)


@pytest.mark.parametrize("end", list(LINE_ENDS))
def test_pontas_de_linha(qapp, end):
    m = sample()
    m.root.style["line_end"] = end
    s = scene_for(m)
    g = next(ci for ci in s.conn_items.values() if ci.is_group and ci.owner == m.root.id)
    assert (len(g.marks) == 3) == (end != "nenhum")


def test_linha_nenhum_nao_desenha(qapp):
    m = sample()
    m.root.style["line_pattern"] = "nenhum"
    s = scene_for(m)
    g = next(ci for ci in s.conn_items.values() if ci.is_group and ci.owner == m.root.id)
    assert g.strokes == []


def test_mesma_cor_vira_um_unico_traco(qapp):
    """Tronco único: filhos com a mesma cor = um traço só (sem sobreposição)."""
    m = sample()
    s = scene_for(m)
    c0 = m.root.children[0]
    g = next(ci for ci in s.conn_items.values() if ci.is_group and ci.owner == c0.id)
    assert len(g.strokes) == 1
    root_g = next(ci for ci in s.conn_items.values() if ci.is_group and ci.owner == m.root.id)
    assert len(root_g.strokes) == 3                  # ramo colorido: um traço por cor


def test_cor_do_ramo_no_topico(qapp):
    m = sample()
    c0 = m.root.children[0]
    c0.style["line_color"] = "#123456"
    s = scene_for(m)
    g = next(ci for ci in s.conn_items.values() if ci.is_group and ci.owner == c0.id)
    assert g.strokes[0][1].color().name().upper() == "#123456"


def test_aplicar_ao_nivel_e_descendentes(qapp):
    m = sample()
    c0 = m.root.children[0]
    c0.style = {"fill": "#000000", "font_weight": 300}
    changed = ops.apply_style_to_level(m, c0.id)
    assert len(changed) == 2
    assert all(c.style == c0.style for c in m.root.children)
    assert len(ops.with_descendants(m, [c0.id])) == 4


def test_painel_texto_ramo_e_desfazer(window):
    w = window
    p = w.panel
    a = w.doc.map.root.children[0]
    w.canvas.select_id(a.id)
    p.set_styles({"font_weight": 300, "bold": None})
    p.set_style("align", "right")
    p.set_style("text_case", "upper")
    a = w.doc.map.find(a.id)
    assert a.style["font_weight"] == 300 and a.style["align"] == "right"
    vis = w.canvas.mscene.visuals[a.id]
    assert vis.align == "right" and vis.lines[0] == vis.lines[0].upper()
    w.canvas.select_id(w.doc.map.root.id)
    p.set_style("branch_style", "chave", branch=True)
    assert w.doc.map.root.style["branch_style"] == "chave"
    for _ in range(4):
        w.doc.undo_stack.undo()
    assert w.doc.map.find(a.id).style == {}


def test_painel_selecao_multipla(window):
    w = window
    kids = w.doc.map.root.children
    kids[0].style["fill"] = "#FF0000"
    w.doc.changed.emit()
    w.canvas.select_ids([k.id for k in kids])
    w.panel.refresh()
    assert w.panel.border_style.currentIndex() == 0
    w.panel.set_style("strike", True)
    assert all(w.doc.map.find(k.id).style.get("strike") for k in kids)
