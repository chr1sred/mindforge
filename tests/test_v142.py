"""Testes da versão 1.4.2: reordenar arrastando, redimensionar sem roubar o arraste e setas pela estrutura."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from mindforge import colorthemes as ct
from mindforge.document import Document
from mindforge.layouts import LAYOUTS
from mindforge.model import ops
from mindforge.model.topic import MindMap, Topic


def _mapa(layout):
    m = MindMap(Topic("Raiz"), layout)
    ct.apply_default(m)
    for i in range(3):
        p = ops.add_child(m, m.root.id, f"Principal {i}")
        for j in range(3):
            ops.add_child(m, p.id, f"Sub {i}.{j}")
    return m


def _abrir(qapp, m):
    w = qapp.new_window(Document(m), fit=False)
    QTest.qWaitForWindowExposed(w)
    w.resize(1500, 1000)
    w.activateWindow()
    QTest.qWait(30)
    c = w.canvas
    c.set_zoom(1.0)
    c.centerOn(c.mscene.topic_items[m.root.id])
    QTest.qWait(20)
    return w, c


def _fechar(w):
    w.canvas.cancel_edit()
    w.doc.mark_saved()
    w.close()
    QTest.qWait(10)


def _pt(c, tid, fx, fy):
    it = c.mscene.topic_items[tid]
    b = it.box_rect()
    return c.mapFromScene(it.mapToScene(QPointF(b.left() + b.width() * fx, b.top() + b.height() * fy)))


def _drag(c, src, dst, ensure_center=True):
    vp = c.viewport()
    start = _pt(c, src, 0.5, 0.5) if ensure_center else src
    QTest.mouseMove(vp, start)
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for k in range(1, 9):
        QTest.mouseMove(vp, start + (dst - start) * (k / 8))
    QTest.qWait(5)
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, dst)
    QTest.qWait(20)


def _zone(c, tid, kind):
    s = c.mscene
    t = c.doc.map.find(tid)
    axis = s._sibling_axis(t)
    f = {"before": 0.12, "after": 0.88, "child": 0.5}[kind]
    return _pt(c, tid, f, 0.5) if axis == "h" else _pt(c, tid, 0.5, f)


# ------------------------------------------------- reordenar arrastando
def test_reordenar_subtopicos_arrastando_em_todos_os_esqueletos(qapp):
    for layout in LAYOUTS:
        m = _mapa(layout)
        w, c = _abrir(qapp, m)
        try:
            doc = w.doc
            p = doc.map.root.children[1]
            a, b, z = [x.id for x in p.children]
            n = doc.undo_stack.index()
            _drag(c, z, _zone(c, a, "before"))           # o último vai para o começo
            assert [x.id for x in doc.map.find(p.id).children] == [z, a, b], layout
            assert doc.undo_stack.index() == n + 1, layout
            assert c.mscene.selected_topic_ids() == [z], layout
            _drag(c, z, _zone(c, b, "after"))            # e volta para o fim
            assert [x.id for x in doc.map.find(p.id).children] == [a, b, z], layout
            assert doc.map.find(z).parent.id == p.id, layout
            assert not any(it.drop_target for it in c.mscene.topic_items.values())
            assert c.mscene._marker is None or not c.mscene._marker.isVisible()
        finally:
            _fechar(w)


def test_meio_do_topico_ainda_torna_filho_e_pai_proprio_nao_muda_nada(qapp):
    m = _mapa("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        doc = w.doc
        p0, p1 = doc.map.root.children[0], doc.map.root.children[1]
        sub = p1.children[0].id
        _drag(c, sub, _zone(c, p0.children[1].id, "child"))
        assert doc.map.find(sub).parent.id == p0.children[1].id
        window_order = [x.id for x in doc.map.find(p0.id).children]
        last = window_order[0]
        _drag(c, last, _zone(c, p0.id, "child"))         # sobre o próprio pai: nada muda
        assert [x.id for x in doc.map.find(p0.id).children] == window_order
    finally:
        _fechar(w)


def test_reordenar_topicos_principais(qapp):
    for layout in ("mapa_direita", "organograma", "linha_tempo"):
        m = _mapa(layout)
        w, c = _abrir(qapp, m)
        try:
            doc = w.doc
            ids = [x.id for x in doc.map.root.children]
            _drag(c, ids[2], _zone(c, ids[0], "before"))
            assert [x.id for x in doc.map.root.children] == [ids[2], ids[0], ids[1]], layout
        finally:
            _fechar(w)


def test_varios_selecionados_entram_juntos_na_ordem(qapp):
    m = _mapa("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        doc = w.doc
        p0, p1 = doc.map.root.children[0], doc.map.root.children[1]
        x, y = p1.children[0].id, p1.children[2].id
        c.select_ids([y, x])
        it = c.mscene.topic_items[x]
        start = _pt(c, x, 0.5, 0.5)
        vp = c.viewport()
        dst = _zone(c, p0.children[0].id, "after")
        QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, start)
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, start)
        c.select_ids([y, x])
        QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        for k in range(1, 9):
            QTest.mouseMove(vp, start + (dst - start) * (k / 8))
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, dst)
        QTest.qWait(20)
        kids = [k.id for k in doc.map.find(p0.id).children]
        assert kids[1:3] == [x, y]                 # ordem relativa mantida
        del it
    finally:
        _fechar(w)


def test_flutuante_solto_entre_irmaos_vira_irmao(qapp):
    m = _mapa("mapa_direita")
    f = ops.add_floating(m, 700, -400, "Solto")
    w, c = _abrir(qapp, m)
    try:
        doc = w.doc
        p0 = doc.map.root.children[0]
        _drag(c, f.id, _zone(c, p0.children[0].id, "after"))
        assert not doc.map.floating
        assert [k.text for k in doc.map.find(p0.id).children][1] == "Solto"
        assert doc.map.find(f.id).pos is None
    finally:
        _fechar(w)


def test_nao_solta_dentro_do_proprio_ramo(qapp):
    m = _mapa("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        p0 = w.doc.map.root.children[0]
        s = c.mscene
        tgt = s.topic_items[p0.children[0].id]
        pos = tgt.mapToScene(tgt.box_rect().center())
        moved = {p0.id, *[k.id for k in p0.children]}
        assert s.drop_intent(pos, moved - {p0.children[0].id}, [p0.id]) is None
    finally:
        _fechar(w)


def test_linha_de_insercao_aparece_durante_o_arraste(qapp):
    m = _mapa("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        p = w.doc.map.root.children[1]
        a, z = p.children[0].id, p.children[2].id
        vp = c.viewport()
        start = _pt(c, z, 0.5, 0.5)
        dst = _zone(c, a, "before")
        QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        for k in range(1, 9):
            QTest.mouseMove(vp, start + (dst - start) * (k / 8))
        mk = c.mscene._marker
        assert mk is not None and mk.isVisible()
        box = c.mscene.topic_items[a].mapRectToScene(c.mscene.topic_items[a].box_rect())
        assert mk.path().boundingRect().bottom() <= box.top() + 4      # linha acima do alvo
        QTest.mouseMove(vp, _zone(c, a, "child"))
        assert not mk.isVisible() and c.mscene.topic_items[a].drop_target
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _zone(c, a, "child"))
    finally:
        _fechar(w)


# ------------------------------------------------- redimensionar não rouba o arraste
def test_borda_so_redimensiona_tópico_selecionado_e_sem_caixa_so_a_direita(qapp):
    m = _mapa("espinha_peixe")
    w, c = _abrir(qapp, m)
    try:
        doc = w.doc
        p = doc.map.root.children[1]
        sub = p.children[2]
        it = c.mscene.topic_items[sub.id]
        assert it.vis.style.shape == "nenhuma"
        c.mscene.clearSelection()
        assert it.edge_at(QPointF(2, it.vis.h / 2)) is None and it.edge_at(QPointF(it.vis.w - 2, 5)) is None
        c.select_id(sub.id)
        assert it.edge_at(QPointF(2, it.vis.h / 2)) is None          # 1ª letra nunca redimensiona
        assert it.edge_at(QPointF(it.vis.w - 2, it.vis.h / 2)) == "right"
        # arrastar pelo começo do texto (sem estar selecionado) reordena, não redimensiona
        c.mscene.clearSelection()
        a = p.children[0].id
        _drag(c, _pt(c, sub.id, 0.02, 0.5), _zone(c, a, "before"), ensure_center=False)
        assert [k.id for k in doc.map.find(p.id).children][0] == sub.id
        assert "width" not in doc.map.find(sub.id).style
    finally:
        _fechar(w)


# ------------------------------------------------- setas pela estrutura
def _key(c, k):
    QTest.keyClick(c, k)
    QTest.qWait(3)
    return c.current()


def test_setas_seguem_irmaos_pai_e_filho_em_todos_os_esqueletos(qapp):
    K = Qt.Key
    keys = {("v", 1): K.Key_Down, ("v", -1): K.Key_Up, ("h", 1): K.Key_Right, ("h", -1): K.Key_Left}
    for layout in LAYOUTS:
        m = _mapa(layout)
        w, c = _abrir(qapp, m)
        try:
            s = c.mscene
            p = w.doc.map.root.children[1]
            kids = [k.id for k in p.children]
            axis = s._sibling_axis(p.children[0])
            c.select_id(kids[0])
            c.setFocus()
            # irmão seguinte e anterior, na ordem do mapa (a direção da fila vem da tela)
            c0 = s.topic_items[kids[0]].sceneBoundingRect().center()
            c1 = s.topic_items[kids[1]].sceneBoundingRect().center()
            sign = 1 if ((c1.y() - c0.y()) if axis == "v" else (c1.x() - c0.x())) > 0 else -1
            assert _key(c, keys[(axis, sign)]) == kids[1], layout
            assert _key(c, keys[(axis, -sign)]) == kids[0], layout
        finally:
            _fechar(w)


def test_setas_pai_e_filho_no_mapa_logico(qapp):
    m = _mapa("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        root = w.doc.map.root
        c.select_id(root.id)
        c.setFocus()
        assert _key(c, Qt.Key.Key_Right) == root.children[0].id           # primeiro filho
        assert _key(c, Qt.Key.Key_Right) == root.children[0].children[0].id
        assert _key(c, Qt.Key.Key_Left) == root.children[0].id            # pai
    finally:
        _fechar(w)


def test_seta_no_ultimo_irmao_vai_para_o_proximo_do_ramo_de_cima(qapp):
    """O caso relatado: ↓ no último subtópico da espinha de peixe ia para um tópico distante."""
    m = MindMap(Topic("AIDGlobal V3"), "espinha_peixe")
    ct.apply_default(m)
    ops.add_child(m, m.root.id, "Estratégia Base")
    nov = ops.add_child(m, m.root.id, "Novembro/26")
    g = ops.add_child(m, nov.id, "Google Ads Pago")
    ops.add_child(m, g.id, "Displays Demand Gen")
    y = ops.add_child(m, g.id, "Youtube")
    grants = ops.add_child(m, nov.id, "Google Ads Grants")
    for t in ("Meta Ads", "Tiktok Ads"):
        ops.add_child(m, nov.id, t)
    w, c = _abrir(qapp, m)
    try:
        c.select_id(y.id)
        c.setFocus()
        assert _key(c, Qt.Key.Key_Down) == grants.id
    finally:
        _fechar(w)


# ------------------------------------------------- travamentos encontrados no teste de fluidez
def test_zoom_e_apagar_topico_com_relacao_nao_trava(qapp):
    """A área dos controles da relação mudava com o zoom sem avisar a cena → o Qt travava ao apagar."""
    m = _mapa("mapa_mental")
    p0, p1 = m.root.children[0], m.root.children[1]
    ops.add_relation(m, p0.children[0].id, p1.children[0].id, "rel")
    w, c = _abrir(qapp, m)
    try:
        ri = next(iter(c.mscene.rel_items.values()))
        r1 = ri.boundingRect()
        for z in (0.3, 2.0, 0.25):
            c.set_zoom(z)
            QTest.qWait(5)
            assert ri.boundingRect() == r1           # não depende do zoom
        c.select_all()
        c.cut()
        QTest.qWait(50)
        w.grab()                                     # força a pintura (onde o Qt travava)
        assert len(w.doc.map.root.children) == 0
    finally:
        _fechar(w)


def test_modo_relacao_com_origem_apagada(qapp):
    m = _mapa("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        src = w.doc.map.root.children[0].id
        c.select_id(src)
        c.start_relation()
        w.doc.apply("x", lambda mm: ops.delete_topics(mm, [src]) if hasattr(ops, "delete_topics")
                    else mm.find(src).detach())
        QTest.qWait(10)
        assert c.relation_source is None
        tgt = w.doc.map.root.children[0].id
        QTest.mouseClick(c.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _pt(c, tgt, 0.5, 0.5))
        assert not w.doc.map.relations
    finally:
        _fechar(w)


def test_selecionar_tudo_e_excluir_apaga_tudo_menos_o_central(qapp):
    m = _mapa("mapa_direita")
    ops.add_floating(m, 500, 500, "Solto")
    w, c = _abrir(qapp, m)
    try:
        c.select_all()
        c.delete_selected()
        assert w.doc.map.root.children == [] and w.doc.map.floating == []
        w.undo()
        assert len(w.doc.map.root.children) == 3
    finally:
        _fechar(w)
