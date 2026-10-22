"""Testes da versão 1.4.1: copiar/colar estilo, pincel, redimensionar e relações editáveis."""
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtTest import QTest

from mindforge.document import Document
from mindforge.model import ops
from mindforge.model.topic import MindMap, Relation, Topic
from mindforge.view.items import rect_param, rect_point
from mindforge.view.scene import MindScene

CTRL_ALT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier


def _vp(c, item, local):
    return c.mapFromScene(item.mapToScene(local))


def _look(s, tid):
    st = s.visuals[tid].style
    return (st.shape, st.fill, st.text_color, round(st.font_size), st.weight, st.italic, st.strike,
            st.border if st.border_width else None, st.line_color, st.line_pattern)


# ------------------------------------------------- relação não some
def test_relacao_continua_visivel_depois_de_mover_topico(window):
    c = window.canvas
    doc = window.doc
    a = doc.map.root.children[0]
    doc.apply("f", lambda m: ops.add_floating(m, 600, -300, "Solto"), select=[])
    f = doc.map.floating[0]
    doc.apply("r", lambda m: ops.add_relation(m, f.id, a.id))
    rid = doc.map.relations[0].id
    QTest.qWait(20)
    s = c.mscene
    it = s.topic_items[f.id]
    s.clearSelection()
    start = _vp(c, it, it.box_rect().center())
    vp = c.viewport()
    QTest.mouseMove(vp, start)
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for k in range(1, 8):
        QTest.mouseMove(vp, start + QPoint(15 * k, 10 * k))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(105, 70))
    QTest.qWait(30)
    assert doc.map.floating[0].pos != (600, -300)            # o tópico flutuante foi movido
    assert s.rel_items[rid].isVisible()                       # e a relação continua lá
    # mover um tópico normal e soltar no vazio (volta ao lugar) também não pode esconder
    it2 = s.topic_items[doc.map.root.children[1].id]
    s.clearSelection()
    p2 = _vp(c, it2, it2.box_rect().center())
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p2)
    for k in range(1, 6):
        QTest.mouseMove(vp, p2 + QPoint(0, 40 * k))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p2 + QPoint(0, 200))
    QTest.qWait(30)
    assert s.rel_items[rid].isVisible()


# ------------------------------------------------- copiar / colar estilo
def test_copiar_e_colar_estilo_deixa_igual_e_um_desfazer(window):
    c = window.canvas
    doc = window.doc
    a, b = doc.map.root.children[0], doc.map.root.children[1]
    doc.apply("s", lambda m: ops.set_styles(m, [a.id], {"shape": "capsula", "fill": "#123456", "italic": True,
                                                        "font_size": 22, "border": "#FF0000",
                                                        "border_level": "grosso"}))
    c.select_id(a.id)
    QTest.keyClick(c, Qt.Key.Key_C, CTRL_ALT)
    assert c.has_copied_style()
    c.select_id(b.id)
    n = doc.undo_stack.index()
    QTest.keyClick(c, Qt.Key.Key_V, CTRL_ALT)
    QTest.qWait(10)
    s = c.mscene
    assert _look(s, a.id) == _look(s, b.id)
    assert doc.undo_stack.index() == n + 1
    assert doc.map.find(b.id).text != doc.map.find(a.id).text       # o texto não é copiado
    QTest.keyClick(c, Qt.Key.Key_R, CTRL_ALT)                         # repor estilo
    QTest.qWait(10)
    assert doc.map.find(b.id).style == {}


def test_estilo_como_aparece_entre_niveis(qapp):
    """Copiar de um principal (que só segue o tema) e colar num subtópico deixa-o igual ao principal."""
    from mindforge.themes import style_snapshot
    m = MindMap(Topic("Raiz"), "mapa_direita")
    a = ops.add_child(m, m.root.id, "A")
    sub = ops.add_child(m, a.id, "sub")
    s = MindScene(Document(m))
    s.sync()
    ops.paste_style(m, [sub.id], style_snapshot(s.visuals[a.id].style))
    s.sync()
    assert _look(s, a.id) == _look(s, sub.id)
    # central → principal
    ops.paste_style(m, [a.id], style_snapshot(s.visuals[m.root.id].style))
    s.sync()
    assert _look(s, m.root.id)[:5] == _look(s, a.id)[:5]


def test_pincel_uma_vez_e_travado(window):
    c = window.canvas
    doc = window.doc
    kids = doc.map.root.children
    doc.apply("s", lambda m: ops.set_styles(m, [kids[0].id], {"fill": "#2A9D8F", "italic": True}))
    c.select_id(kids[0].id)
    window._brush_clicked()                     # clique simples: 1 tópico
    assert c.brush_mode == "once" and window.brush_btn.isChecked()
    vp = c.viewport()
    it1 = c.mscene.topic_items[kids[1].id]
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     _vp(c, it1, it1.box_rect().center()))
    QTest.qWait(10)
    assert doc.map.find(kids[1].id).style.get("fill") == "#2A9D8F"
    assert c.brush_mode is None and not window.brush_btn.isChecked()
    # duplo clique no botão: travado, aplica em vários até Esc
    c.select_id(kids[0].id)
    window._brush_clicked()
    window._brush_clicked()
    assert c.brush_mode == "sticky"
    for k in (2, 3):
        it = c.mscene.topic_items[kids[k].id]
        QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         _vp(c, it, it.box_rect().center()))
        QTest.qWait(10)
        assert doc.map.find(kids[k].id).style.get("fill") == "#2A9D8F"
        assert c.brush_mode == "sticky"
    QTest.keyClick(c, Qt.Key.Key_Escape)
    assert c.brush_mode is None


def test_estilo_copiado_vale_em_outra_janela(qapp):
    from mindforge.templates import get_template
    w1 = qapp.new_window(Document(get_template("mapa_direita").create()))
    w2 = qapp.new_window(Document(get_template("mapa_direita").create()))
    try:
        t1 = w1.doc.map.root.children[0]
        w1.doc.apply("s", lambda m: ops.set_styles(m, [t1.id], {"fill": "#ABCDEF"}))
        w1.canvas.select_id(t1.id)
        w1.canvas.copy_style()
        t2 = w2.doc.map.root.children[2]
        w2.canvas.select_id(t2.id)
        w2.canvas.paste_style()
        assert w2.doc.map.find(t2.id).style["fill"] == "#ABCDEF"
    finally:
        for w in (w1, w2):
            w.doc.mark_saved()
            w.close()
        QTest.qWait(10)


# ------------------------------------------------- redimensionar
def test_arrastar_a_borda_muda_a_largura(window):
    c = window.canvas
    doc = window.doc
    t = doc.map.root.children[0]
    doc.apply("t", lambda m: ops.set_text(m, t.id, "Um texto bem comprido para quebrar em linhas"))
    QTest.qWait(10)
    s = c.mscene
    it = s.topic_items[t.id]
    vp = c.viewport()
    w0 = it.vis.w
    assert it.edge_at(QPointF(it.vis.w - 2, it.vis.h / 2)) is None      # 1.4.2: só com o tópico selecionado
    c.select_id(t.id)
    edge = _vp(c, it, QPointF(it.vis.w - 2, it.vis.h / 2))
    QTest.mouseMove(vp, edge + QPoint(-2, 0))
    QTest.mouseMove(vp, edge)
    QTest.qWait(10)
    assert it.edge_at(QPointF(it.vis.w - 2, it.vis.h / 2)) == "right"
    n = doc.undo_stack.index()
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, edge)
    for k in range(1, 6):
        QTest.mouseMove(vp, edge - QPoint(int(20 * k * c.zoom), 0))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                       edge - QPoint(int(100 * c.zoom), 0))
    QTest.qWait(20)
    width = doc.map.find(t.id).style.get("width")
    assert width is not None and width < w0
    assert doc.undo_stack.index() == n + 1                  # um desfazer só
    it = s.topic_items[t.id]
    assert len(it.vis.lines) > 1                            # o texto quebrou em linhas
    assert it.parentItem() is None and it.pos() is not None
    # a largura mínima nunca corta uma palavra
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     _vp(c, it, QPointF(it.vis.w - 2, it.vis.h / 2)))
    QTest.mouseMove(vp, _vp(c, it, QPointF(-900, it.vis.h / 2)))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                       _vp(c, it, QPointF(-900, it.vis.h / 2)))
    QTest.qWait(20)
    it = s.topic_items[t.id]
    words = set(doc.map.find(t.id).text.split())
    assert all(w in words for line in it.vis.lines for w in line.split())
    # duplo clique na borda: volta à largura automática
    QTest.mouseDClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                      _vp(c, it, QPointF(it.vis.w - 2, it.vis.h / 2)))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton)
    QTest.qWait(20)
    assert "width" not in doc.map.find(t.id).style
    assert c.editor is None


def test_meio_da_caixa_continua_selecionando_e_movendo(window):
    c = window.canvas
    t = window.doc.map.root.children[0]
    it = c.mscene.topic_items[t.id]
    assert it.edge_at(it.box_rect().center()) is None
    c.mscene.clearSelection()
    QTest.mouseClick(c.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     _vp(c, it, it.box_rect().center()))
    assert c.mscene.selected_topic_ids() == [t.id]


# ------------------------------------------------- relações editáveis
def test_parametro_da_borda_ida_e_volta():
    r = QRectF(10, 20, 120, 40)
    for t in (0.0, 0.1, 0.3, 0.5, 0.62, 0.8, 0.95):
        p = rect_point(r, t)
        assert abs(rect_param(r, p) - t) < 1e-6 or abs(abs(rect_param(r, p) - t) - 1) < 1e-6


def _rel_window(window):
    c = window.canvas
    doc = window.doc
    a, b = doc.map.root.children[0], doc.map.root.children[2]
    doc.apply("r", lambda m: ops.add_relation(m, a.id, b.id, "rel"))
    rid = doc.map.relations[0].id
    QTest.qWait(10)
    ri = c.mscene.rel_items[rid]
    c.mscene.clearSelection()
    ri.setSelected(True)
    return c, doc, rid, ri


def test_arrastar_controle_muda_a_curva_e_e_desfazivel(window):
    c, doc, rid, ri = _rel_window(window)
    vp = c.viewport()
    p = _vp(c, ri, ri._pts["c1"])
    assert ri.handle_at(ri._pts["c1"]) == "c1"
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
    for k in range(1, 6):
        QTest.mouseMove(vp, p + QPoint(0, -25 * k))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p + QPoint(0, -125))
    QTest.qWait(20)
    rel = doc.map.relations[0]
    assert rel.c1 is not None and rel.c1[1] < 0
    assert c.mscene.rel_items[rid].isSelected()          # continua selecionada para seguir ajustando
    window.undo()
    assert doc.map.relations[0].c1 is None


def test_arrastar_ponta_escolhe_o_encaixe(window):
    c, doc, rid, ri = _rel_window(window)
    vp = c.viewport()
    p = _vp(c, ri, ri._pts["p1"])
    target = c.mscene.topic_items[doc.map.relations[0].target]
    goal = _vp(c, target, QPointF(target.vis.w / 2, target.vis.h + 30))   # embaixo do destino
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
    QTest.mouseMove(vp, (p + goal) / 2)
    QTest.mouseMove(vp, goal)
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, goal)
    QTest.qWait(20)
    rel = doc.map.relations[0]
    assert rel.anchor_b is not None and 0.5 < rel.anchor_b < 0.75          # base da caixa
    ri = c.mscene.rel_items[rid]
    box = target.mapRectToScene(target.box_rect())
    assert ri._pts["p1"].y() > box.bottom()                                # a seta gruda embaixo


def test_forma_acompanha_os_topicos_e_vai_para_o_arquivo(qapp, tmp_path):
    from mindforge.storage import load_map, save_map
    m = MindMap(Topic("Raiz"), "mapa_mental")
    a = ops.add_child(m, m.root.id, "A")
    b = ops.add_child(m, m.root.id, "B")
    r = ops.add_relation(m, a.id, b.id)
    ops.set_relation_shape(m, r.id, anchor_a=0.25, anchor_b=0.75, c1=(40, -80), c2=(-30, -90))
    s = MindScene(Document(m))
    s.sync()
    g1 = dict(s.rel_items[r.id]._pts)
    off1 = (g1["c1"] - g1["p0"], g1["c2"] - g1["p1"])
    ops.set_text(m, a.id, "A com texto bem maior agora")          # o mapa se reorganiza
    s.sync()
    g2 = s.rel_items[r.id]._pts
    assert (g2["c1"] - g2["p0"], g2["c2"] - g2["p1"]) == off1        # a curvatura acompanha
    path = str(tmp_path / "r.mfmap")
    save_map(m, path)
    r2 = load_map(path).relations[0]
    assert (r2.anchor_a, r2.anchor_b, r2.c1, r2.c2) == (0.25, 0.75, (40.0, -80.0), (-30.0, -90.0))


def test_inverter_pontas_e_endireitar(qapp):
    m = MindMap(Topic("Raiz"), "mapa_mental")
    a = ops.add_child(m, m.root.id, "A")
    b = ops.add_child(m, m.root.id, "B")
    r = ops.add_relation(m, a.id, b.id)
    ops.set_relation_shape(m, r.id, anchor_a=0.1, c1=(5, 5))
    ops.reverse_relation(m, r.id)
    assert (r.source, r.target, r.anchor_b, r.c2) == (b.id, a.id, 0.1, (5, 5))
    for ends in ("both", "none", "end"):
        ops.set_relation_shape(m, r.id, arrows=ends)
        s = MindScene(Document(m))
        s.sync()
        ri = s.rel_items[r.id]
        n = ri._arrow.elementCount()
        assert (n == 0) == (ends == "none") and (ends != "both" or n >= 8)
    ops.reset_relation_shape(m, r.id)
    assert not r.is_custom_shape()


def test_relacao_antiga_e_campos_invalidos():
    old = Relation.from_dict({"id": "x", "source": "a", "target": "b"})
    assert not old.is_custom_shape() and old.arrows == "end"
    assert old.to_dict() == {"id": "x", "source": "a", "target": "b"}      # arquivo igual ao da 1.4.0
    bad = Relation.from_dict({"id": "y", "source": "a", "target": "b", "anchor_a": "x", "c1": [1, "z"],
                              "c2": [1, 2, 3], "arrows": "muitas", "anchor_b": float("nan")})
    assert not bad.is_custom_shape() and bad.arrows == "end"


def test_controles_nao_vao_para_a_exportacao(qapp):
    m = MindMap(Topic("Raiz"), "mapa_mental")
    a = ops.add_child(m, m.root.id, "A")
    b = ops.add_child(m, m.root.id, "B")
    r = ops.add_relation(m, a.id, b.id)
    ops.set_relation_shape(m, r.id, c1=(0, -300), c2=(0, -300))
    s = MindScene(Document(m))
    s.sync()
    ri = s.rel_items[r.id]
    with s.exporting() as r1:
        pass
    ri.setSelected(True)
    with s.exporting() as r2:
        pass
    assert r1 == r2
    assert ri.handle_at(ri._pts["c1"]) == "c1"
    with s.exporting():
        assert ri.handle_at(ri._pts["c1"]) is None
