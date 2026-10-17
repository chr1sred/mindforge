"""Temas de cores (1.3): paletas, variações, contraste, Ramo colorido, A Minha Cor e compatibilidade."""
import dataclasses
import json
import os

import pytest

from mindforge import colorthemes as ct
from mindforge.document import Document
from mindforge.model import ops
from mindforge.model.topic import MindMap, Topic
from mindforge.themes import MIN_LINE_CONTRAST, MIN_TEXT_CONTRAST, contrast_ratio

DATA = os.path.join(os.path.dirname(__file__), "data")


def _mapa(layout="mapa_mental", theme="classico", n=7):
    m = MindMap(Topic("Raiz"), layout, theme)
    for i in range(n):
        t = ops.add_child(m, m.root.id, f"P{i}")
        for j in range(2):
            ops.add_child(m, t.id, f"S{i}{j}")
    ops.add_floating(m, 900, 900, "F")
    return m


def _cena(m):
    from mindforge.view.scene import MindScene
    s = MindScene(Document(m))
    s.sync()
    return s


# ------------------------------------------------------------ compatibilidade
def test_mapas_antigos_continuam_identicos(qapp):
    """Estilos dos 5 temas antigos gravados antes da 1.3 (tests/data/legacy_styles.json)."""
    ref = json.load(open(os.path.join(DATA, "legacy_styles.json"), encoding="utf-8"))
    for key, exp in ref.items():
        theme, layout, rb = key.split("|")
        m = _mapa(layout, theme)
        m.settings["rainbow"] = rb == "True"
        s = _cena(m)
        assert s.background_color == exp["bg"], key
        got = [[t.text, dataclasses.asdict(s.visuals[t.id].style)] for t in m.all_topics()]
        assert json.loads(json.dumps(got)) == exp["rows"], key


# ------------------------------------------------------------ contraste
def _todas_combinacoes():
    for p in ct.CATALOG.values():
        for v in range(len(ct.VARIANTS)):
            yield p, v


def test_contraste_de_texto_e_linhas_em_todas_as_paletas(qapp):
    falhas = []
    for p, v in _todas_combinacoes():
        m = _mapa(n=6)
        ct.apply_default(m, p.as_setting(), v)
        s = _cena(m)
        bg = s.background_color
        for t in m.all_topics():
            vis = s.visuals[t.id]
            st = vis.style
            surface = st.fill or bg
            need = MIN_TEXT_CONTRAST[vis.level]
            if contrast_ratio(st.text_color, surface) < need - 0.01:
                falhas.append((p.id, v, vis.level, "texto", st.text_color, surface))
            if t is not m.root and contrast_ratio(st.line_color, bg) < MIN_LINE_CONTRAST - 0.01:
                falhas.append((p.id, v, vis.level, "linha", st.line_color, bg))
    assert not falhas, falhas[:10]


def test_central_e_principais_distinguiveis_e_sem_repetir_a_cor_do_central(qapp):
    for p, v in _todas_combinacoes():
        th = ct.build_theme(p.colors, v)
        assert len(th.palette) >= 3, (p.id, v)
        root_fill = th.root["fill"]
        assert root_fill not in th.palette, (p.id, v)


def test_noturno_tem_fundo_escuro_e_central_visivel():
    for p in ct.CATALOG.values():
        th = ct.build_theme(p.colors, 4)
        from mindforge.themes import is_dark
        assert is_dark(th.background), p.id
        assert contrast_ratio(th.root["fill"], th.background) >= 3.0, p.id


# ------------------------------------------------------------ ramo colorido
def test_roda_muda_os_ramos_e_nunca_o_central(qapp):
    m = _mapa()
    ct.apply_default(m, ct.CATALOG["colorido/aurora"].as_setting(), 0)
    s = _cena(m)
    root_before = dataclasses.asdict(s.visuals[m.root.id].style)
    mains_before = [s.visuals[t.id].branch for t in m.root.children]
    for key in ct.BRANCH_PALETTES:
        m.settings["branch_palette"] = key
        s = _cena(m)
        assert dataclasses.asdict(s.visuals[m.root.id].style) == root_before, key
        mains = [s.visuals[t.id].branch for t in m.root.children]
        assert mains != mains_before, key
        # subtópicos herdam a cor do seu ramo
        for t in m.root.children:
            for c in t.children:
                assert s.visuals[c.id].branch == s.visuals[t.id].branch


def test_cor_estatica_com_ramo_colorido_desligado(qapp):
    m = _mapa()
    ct.apply_default(m, ct.CATALOG["colorido/tropical"].as_setting(), 0)
    m.settings["rainbow"] = False
    s = _cena(m)
    cols = {s.visuals[t.id].branch for t in m.root.children}
    assert len(cols) == 1                                 # cor do tema
    m.settings["static_color"] = "#8250DF"
    s = _cena(m)
    assert {s.visuals[t.id].branch for t in m.root.children} == {"#8250DF"}
    assert s.visuals[m.root.id].style.fill == ct.build_theme(ct.CATALOG["colorido/tropical"].colors, 0).root["fill"]


# ------------------------------------------------------------ arquivo
def test_paleta_personalizada_vai_dentro_do_arquivo(qapp, tmp_path):
    from mindforge.storage import load_map, save_map
    m = _mapa()
    ops.set_color_theme(m, {"id": "custom/abc", "name": "Minha", "colors":
                            ["#112233", "#AA3355", "#33AA55", "#3355AA", "#EEAA33", "#9933CC"]}, 3)
    path = str(tmp_path / "x.mfmap")
    save_map(m, path)
    m2 = load_map(path)          # outro computador: a paleta "custom/abc" não existe lá
    assert m2.settings["color_theme"]["colors"][1] == "#AA3355"
    assert m2.settings["color_variant"] == 3
    s1, s2 = _cena(m), _cena(m2)
    for a, b in zip(m.all_topics(), m2.all_topics()):
        assert s1.visuals[a.id].style == s2.visuals[b.id].style


def test_configuracoes_de_cor_corrompidas_sao_descartadas():
    d = _mapa().to_dict()
    d["settings"] = {"color_theme": {"colors": ["#FFF", "azul"]}, "color_variant": 9,
                     "branch_palette": "inexistente", "static_color": "vermelho", "rainbow": True}
    m = MindMap.from_dict(d)
    assert m.settings == {"rainbow": True}


def test_trocar_tema_preserva_estilo_manual_e_e_um_desfazer_so(qapp):
    from mindforge.view.scene import MindScene
    m = _mapa()
    t = m.root.children[0]
    ops.set_styles(m, [t.id], {"fill": "#123456"})
    doc = Document(m)
    s = MindScene(doc)
    m.settings["background"] = "#FFEEDD"

    def fn(mm):
        ops.set_color_theme(mm, ct.CATALOG["classico/nordico"].as_setting(), 4)
        mm.settings.pop("background", None)
    doc.apply("Mudar tema de cores", fn)
    s.sync()
    assert s.visuals[t.id].style.fill == "#123456"
    assert "background" not in doc.map.settings
    doc.undo_stack.undo()
    assert "color_theme" not in doc.map.settings and doc.map.settings["background"] == "#FFEEDD"


# ------------------------------------------------------------ A Minha Cor
CORES = ["#112233", "#AA3355", "#33AA55", "#3355AA", "#EEAA33", "#9933CC"]


def test_paletas_do_usuario_persistem(tmp_path):
    from mindforge.storage.palettes import PaletteStore
    path = str(tmp_path / "temas.json")
    st = PaletteStore(path)
    a = st.add("Marca", CORES)
    b = st.add("Marca", CORES)                     # nome repetido ganha sufixo
    assert b.name == "Marca (2)"
    st.update(a.id, "Marca azul", list(reversed(CORES)))
    d = st.duplicate(a.id)
    st.set_default(d.as_setting(), 2)
    st2 = PaletteStore(path)                        # "reabrir o app"
    assert [p.name for p in st2.palettes] == ["Marca azul", "Marca (2)", "Marca azul (2)"]
    assert st2.palettes[0].colors[0] == CORES[-1]
    assert st2.default["color_variant"] == 2
    st2.delete(b.id)
    assert len(PaletteStore(path).palettes) == 2
    assert st2.suggested_name() == "Personalizado 1"


def test_paletas_do_usuario_validacoes(tmp_path):
    from mindforge.storage.palettes import PaletteStore
    path = str(tmp_path / "temas.json")
    st = PaletteStore(path)
    with pytest.raises(ValueError):
        st.add("x", CORES[:5])
    with pytest.raises(ValueError):
        st.add("x", CORES[:5] + ["azul"])
    for i in range(ct.MAX_CUSTOM):
        st.add(f"p{i}", CORES)
    assert not st.can_add()
    with pytest.raises(ValueError):
        st.add("demais", CORES)
    open(path, "w").write("{ isso não é json")
    assert PaletteStore(path).palettes == []        # arquivo corrompido não derruba o app


def test_completar_automaticamente():
    for seeds in (["#E76F51"], ["#2A9D8F", "#E9C46A"], ["#777777"], ["#FFFFFF"], []):
        out = ct.auto_complete(seeds)
        assert len(out) == 6 and all(ct.is_hex(c) for c in out)
        assert len(set(out)) == 6, (seeds, out)
        for s in seeds:
            assert s.upper() in out
        th = ct.build_theme(tuple(out), 0)            # sempre gera um tema utilizável
        assert len(th.palette) >= 3


def test_padrao_para_novos_mapas():
    from mindforge.templates import get_template
    try:
        ct.set_default_for_new_maps(ct.CATALOG["classico/vintage"].as_setting(), 5)
        m = get_template("mapa_mental").create()
        assert m.settings["color_theme"]["id"] == "classico/vintage" and m.settings["color_variant"] == 5
        m = get_template("mapa_mental").create(palette=ct.CATALOG["colorido/doces"].as_setting(), variant=0)
        assert m.settings["color_theme"]["id"] == "colorido/doces" and "color_variant" not in m.settings
    finally:
        ct.set_default_for_new_maps(None)


# ------------------------------------------------------------ interface
def test_painel_variacoes_e_popover(window):
    from PySide6.QtTest import QTest
    from mindforge.view.colorpanel import PalettePopup
    p = window.panel
    doc = window.doc
    p.variant_btns[4].click()
    assert doc.map.settings["color_variant"] == 4
    assert p.variant_btns[4].isChecked()
    from mindforge.themes import is_dark
    assert is_dark(window.canvas.mscene.background_color)
    pop = PalettePopup(window, ct.current_palette(doc.map).id, False)
    from mindforge.view.colorpanel import PaletteItem
    alvo = next(b for b in pop.findChildren(PaletteItem) if b.palette.id == "classico/terra")
    pop.picked.connect(lambda pal: p._apply_colors(pal.as_setting(), None))
    alvo.click()
    QTest.qWait(10)
    assert doc.map.settings["color_theme"]["id"] == "classico/terra"
    assert doc.map.settings["color_variant"] == 4      # trocar a paleta mantém a variação
    window.undo()
    assert doc.map.settings["color_theme"]["id"] != "classico/terra"


def test_painel_ramo_colorido_e_cor_estatica(window):
    p = window.panel
    doc = window.doc
    p.wheel_btn.picked.emit("neon")
    assert doc.map.settings["branch_palette"] == "neon"
    p.rainbow.click()
    from PySide6.QtTest import QTest
    QTest.qWait(30)
    assert not doc.map.setting("rainbow")
    assert not p.static_btn.isHidden() and p.wheel_btn.isHidden()
    p.static_btn.picked.emit("#E5534B")
    s = window.canvas.mscene
    assert {s.visuals[t.id].branch for t in doc.map.root.children} == {"#E5534B"}


def test_dialogo_criar_tema(window, tmp_path, monkeypatch):
    from mindforge.storage.palettes import PaletteStore
    from mindforge.view import colorpanel
    store = PaletteStore(str(tmp_path / "temas.json"))
    monkeypatch.setattr(window.app, "palettes", store, raising=False)
    dlg = colorpanel.PaletteDialog(window)
    assert not dlg.save_btn.isEnabled()
    dlg._set(0, "#2A9D8F")
    assert dlg.auto_btn.isEnabled()
    dlg._auto()
    assert len(dlg.filled()) == 6 and dlg.save_btn.isEnabled()
    dlg.name.setText("")
    assert not dlg.save_btn.isEnabled()
    dlg.name.setText("Minha marca")
    dlg._render_preview()
    assert dlg.preview.pixmap() is not None and not dlg.preview.pixmap().isNull()
    name, colors = dlg.result_palette()
    p = store.add(name, colors)
    window.panel._apply_colors(p.as_setting(), None)
    assert window.doc.map.settings["color_theme"]["name"] == "Minha marca"


def test_aviso_de_fundo_escuro_na_exportacao(qapp):
    from mindforge.view.dialogs import ExportDialog
    d = ExportDialog(None, False, "png", dark_background=True)
    d.show()
    d.png_transparent.setChecked(True)
    assert d.png_warn.isVisible()
    d.png_transparent.setChecked(False)
    assert not d.png_warn.isVisible()
    d.close()
    d2 = ExportDialog(None, False, "png", dark_background=False)
    d2.show()
    d2.png_transparent.setChecked(True)
    assert not d2.png_warn.isVisible()
    d2.close()


def test_menu_tema_de_cores(window):
    window._fill_theme_menu()
    acts = [a for a in window.theme_menu.actions() if a.isCheckable()]
    assert len(acts) >= len(ct.COLORIDO) + len(ct.CLASSICO)
    alvo = next(a for a in acts if a.text() == "Sálvia")
    alvo.trigger()
    assert window.doc.map.settings["color_theme"]["id"] == "classico/salvia"
    window._fill_theme_menu()
    assert next(a for a in window.theme_menu.actions() if a.text() == "Sálvia").isChecked()


def test_dialogo_de_modelos_usa_a_paleta_escolhida(qapp):
    from mindforge.view.dialogs import TemplateDialog
    d = TemplateDialog()
    i = next(k for k in range(d.theme.count()) if (d.theme.itemData(k) or {}).get("id") == "classico/marinho")
    d.theme.setCurrentIndex(i)
    t = d.selected_template()
    m = t.create(palette=d.selected_palette(), variant=0)
    assert m.settings["color_theme"]["id"] == "classico/marinho"
    d.deleteLater()
