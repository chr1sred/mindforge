"""Testes da versão 1.3: recolher/expandir, arrasto com botão direito e idiomas."""
import random

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtTest import QTest

from mindforge.document import Document
from mindforge.export import ExportOptions, export_file
from mindforge.layouts import LAYOUTS
from mindforge.model import ops
from mindforge.model.topic import MindMap, Topic
from mindforge.view.scene import MindScene


def big_map(layout, seed=1, n=60):
    r = random.Random(seed)
    m = MindMap(Topic("Raiz"), layout)
    nodes = [m.root]
    for i in range(n):
        nodes.append(ops.add_child(m, r.choice(nodes).id, f"Tópico {i}"))
    for t in nodes[1:]:
        if t.children and r.random() < 0.3:
            t.collapsed = True
    return m


# ------------------------------------------------------------------ recolher
def test_numero_conta_todos_os_descendentes(qapp):
    m = MindMap(Topic("Raiz"), "mapa_direita")
    a = ops.add_child(m, m.root.id, "A")
    b = ops.add_child(m, a.id, "B")
    ops.add_child(m, b.id, "C")
    ops.add_child(m, a.id, "D")
    a.collapsed = True
    s = MindScene(Document(m))
    s.sync()
    assert s.visuals[a.id].collapsed_count == 3


def test_numero_nunca_cobre_outro_topico(qapp):
    for layout in LAYOUTS:
        for seed in range(6):
            m = big_map(layout, seed)
            s = MindScene(Document(m))
            s.sync()
            rects = {tid: it.mapRectToScene(it.box_rect()) for tid, it in s.topic_items.items()}
            for tid, it in s.topic_items.items():
                if not it.vis.collapsed_count:
                    continue
                br = it.mapRectToScene(it.badge_rect(0))
                for other, r in rects.items():
                    if other != tid:
                        assert not br.adjusted(1, 1, -1, -1).intersects(r), f"{layout} seed={seed}"


def test_toggle_so_na_tela_numero_na_exportacao(qapp, tmp_path):
    m = MindMap(Topic("Raiz"), "mapa_direita")
    a = ops.add_child(m, m.root.id, "A")
    ops.add_child(m, a.id, "B")
    s = MindScene(Document(m))
    s.sync()
    it = s.topic_items[a.id]
    assert it.has_toggle() and not s.topic_items[m.root.id].has_toggle()
    it.setSelected(True)
    with s.exporting() as r1:
        pass
    a.collapsed = True
    s.sync()
    with s.exporting() as r2:
        pass
    assert r2.width() < r1.width()          # filho escondido...
    it = s.topic_items[a.id]
    assert it.visual_rect().width() > it.box_rect().width()   # ...mas o número entra na exportação
    export_file(s, str(tmp_path / "x.png"), ExportOptions("png", scale=1))


def test_clique_no_botao_recolhe_e_expande(window):
    w = window
    c = w.canvas
    a = w.doc.map.root.children[0]
    c.select_id(a.id)
    QTest.keyClick(c, Qt.Key.Key_Tab)
    QTest.keyClick(c, Qt.Key.Key_Return)
    QTest.qWait(20)
    it = c.mscene.topic_items[a.id]
    vp = c.viewport()
    QTest.mouseMove(vp, c.mapFromScene(it.mapToScene(it.box_rect().center())))   # hover no tópico
    QTest.qWait(20)
    assert it.handle.isVisible()
    center = it.mapToScene(it.badge_rect(0).center())
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, c.mapFromScene(center))
    QTest.qWait(20)
    assert w.doc.map.find(a.id).collapsed
    QTest.qWait(500)        # dois cliques rápidos no controle contam como duplo clique (alterna 1 vez)
    it = c.mscene.topic_items[a.id]
    center = it.mapToScene(it.badge_rect(0).center())
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, c.mapFromScene(center))
    QTest.qWait(20)
    assert not w.doc.map.find(a.id).collapsed
    assert c.current() == a.id


def test_recolher_move_selecao_escondida(window):
    w = window
    c = w.canvas
    a = w.doc.map.root.children[0]
    c.select_id(a.id)
    QTest.keyClick(c, Qt.Key.Key_Tab)
    QTest.keyClick(c, Qt.Key.Key_Return)
    child = w.doc.map.find(a.id).children[0]
    c.select_id(child.id)
    c.toggle_collapse([a.id])
    assert c.current() == a.id


def test_alt_clique_expande_todos_os_niveis(qapp):
    m = MindMap(Topic("Raiz"), "mapa_direita")
    a = ops.add_child(m, m.root.id, "A")
    b = ops.add_child(m, a.id, "B")
    ops.add_child(m, b.id, "C")
    a.collapsed = b.collapsed = True
    ops.expand_subtree(m, a.id)
    assert not a.collapsed and not b.collapsed


# ------------------------------------------------------------ botão direito
def _menus(w):
    got = []
    w.canvas.context_menu_requested.disconnect()
    w.canvas.context_menu_requested.connect(lambda tid, pos: got.append(tid))
    return got


def test_clique_direito_abre_menu(window):
    w = window
    got = _menus(w)
    c = w.canvas
    a = w.doc.map.root.children[0]
    it = c.mscene.topic_items[a.id]
    p = c.mapFromScene(it.mapToScene(it.box_rect().center()))
    QTest.mouseClick(c.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p)
    QTest.qWait(20)
    assert got == [a.id]
    assert c.current() == a.id


def test_arrastar_com_botao_direito_move_sem_menu(window):
    w = window
    got = _menus(w)
    c = w.canvas
    vp = c.viewport()
    start = vp.rect().center()
    h0, v0 = c.horizontalScrollBar().value(), c.verticalScrollBar().value()
    QTest.mousePress(vp, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, start)
    for i in range(1, 11):
        QTest.mouseMove(vp, start + QPoint(-12 * i, -6 * i))
        QTest.qWait(2)
    QTest.mouseRelease(vp, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, start + QPoint(-120, -60))
    QTest.qWait(20)
    assert got == []
    assert c.horizontalScrollBar().value() > h0 and c.verticalScrollBar().value() > v0
    assert not c._panning and c._rpress is None


def test_tremida_pequena_ainda_e_clique(window):
    w = window
    got = _menus(w)
    c = w.canvas
    vp = c.viewport()
    p = vp.rect().center()
    QTest.mousePress(vp, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p)
    QTest.mouseMove(vp, p + QPoint(2, 1))
    QTest.mouseRelease(vp, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p + QPoint(2, 1))
    QTest.qWait(20)
    assert len(got) == 1


def test_arrasto_alem_da_borda_aumenta_o_quadro(window):
    c = window.canvas
    r0 = c.mscene.sceneRect()
    for _ in range(80):
        c._pan_by(400, 0)
    assert c.mscene.sceneRect().left() < r0.left()


# ------------------------------------------- controle ⊖ independente (1.3.0)
def _map_com_filhos(layout):
    m = MindMap(Topic("Raiz"), layout)
    for i in range(3):
        t = ops.add_child(m, m.root.id, f"Tópico principal {i}")
        for j in range(2):
            ops.add_child(m, t.id, f"Sub {i}.{j}")
    return m


def _abrir(qapp, m, zoom=1.0):
    w = qapp.new_window(Document(m), fit=False)
    QTest.qWaitForWindowExposed(w)
    w.resize(1400, 900)
    w.activateWindow()
    QTest.qWait(30)
    c = w.canvas
    # o QTest.mouseDClick de um teste anterior pode deixar o botão "preso" no estado do Qt
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton:
        QTest.mouseRelease(c.viewport(), Qt.MouseButton.LeftButton)
    c.set_zoom(zoom)
    c.centerOn(c.mscene.topic_items[m.root.id])
    QTest.qWait(30)
    return w, c


def _fechar(w):
    w.doc.mark_saved()
    w.close()
    QTest.qWait(10)


def _vp(c, item, local):
    return c.mapFromScene(item.mapToScene(local))


def _mover(c, pos):
    """Move o mouse até pos (com um passo antes: o Qt ignora 'movimento' para o mesmo ponto)."""
    QTest.mouseMove(c.viewport(), pos + QPoint(3, 3))
    QTest.mouseMove(c.viewport(), pos)
    QTest.qWait(15)


def test_clique_em_toda_a_caixa_seleciona(qapp):
    """Regressão: a metade da caixa do lado do ramo era um 'buraco' sem clique."""
    for layout in LAYOUTS:
        for zoom in (1.0, 0.5):
            m = _map_com_filhos(layout)
            w, c = _abrir(qapp, m, zoom)
            try:
                vp = c.viewport()
                for t in m.root.children:
                    it = c.mscene.topic_items[t.id]
                    c.mscene.clearSelection()
                    QTest.mouseMove(vp, _vp(c, it, it.box_rect().center()))
                    QTest.qWait(5)
                    b = it.box_rect().adjusted(3 / zoom, 3 / zoom, -3 / zoom, -3 / zoom)
                    for fx in (0.0, 0.25, 0.5, 0.75, 1.0):
                        for fy in (0.0, 0.5, 1.0):
                            p = QPointF(b.left() + b.width() * fx, b.top() + b.height() * fy)
                            c.mscene.clearSelection()
                            QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                             _vp(c, it, p))
                            assert c.mscene.selected_topic_ids() == [t.id], (layout, zoom, fx, fy)
            finally:
                _fechar(w)


def test_duplo_clique_no_lado_do_ramo_edita_e_nao_cria_flutuante(qapp):
    for layout in LAYOUTS:
        m = _map_com_filhos(layout)
        w, c = _abrir(qapp, m)
        try:
            t = m.root.children[0]
            it = c.mscene.topic_items[t.id]
            b = it.box_rect()
            # ponto do lado de onde sai o ramo, na altura do texto (onde ficava o buraco)
            side = it.vis.side
            x = {"right": b.right() - 6, "left": b.left() + 6}.get(side, b.center().x())
            y = {"down": b.bottom() - 4, "up": b.top() + 4}.get(side, it.vis.ay)
            QTest.mouseDClick(c.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                              _vp(c, it, QPointF(x, y)))
            QTest.qWait(10)
            assert not m.floating, layout
            assert c.editor is not None and c.editor.tid == t.id, layout
            c.commit_edit()
        finally:
            _fechar(w)


def test_controle_tem_hover_proprio_e_espera_antes_de_sumir(qapp):
    m = _map_com_filhos("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        t = m.root.children[0]
        it = c.mscene.topic_items[t.id]
        h = it.handle
        c.mscene.clearSelection()
        assert not h.isVisible()
        _mover(c, _vp(c, it, it.box_rect().center()))
        QTest.qWait(10)
        assert h.isVisible() and not h.hovered
        _mover(c, _vp(c, it, it.badge_rect(0).center()))
        QTest.qWait(10)
        assert h.isVisible() and h.hovered          # hover do próprio controle
        assert h.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert "Recolher" in h.toolTip()
        far = it.mapToScene(it.box_rect().center()) + QPointF(0, -400)
        _mover(c, c.mapFromScene(far))
        QTest.qWait(10)
        assert h.isVisible()                        # ainda no tempo de espera
        QTest.qWait(400)
        assert not h.isVisible()
    finally:
        _fechar(w)


def test_controle_nao_e_selecionavel_e_nao_vai_para_exportacao(qapp):
    m = _map_com_filhos("mapa_direita")
    s = MindScene(Document(m))
    s.sync()
    it = s.topic_items[m.root.children[0].id]
    it.setSelected(True)
    assert it.handle.isVisible()
    assert not (it.handle.flags() & it.handle.GraphicsItemFlag.ItemIsSelectable)
    from PySide6.QtGui import QImage, QPainter
    with s.exporting() as r:
        img = QImage(int(r.width()), int(r.height()), QImage.Format.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        s.render(p, QRectF(img.rect()), r)
        p.end()
        c = it.mapToScene(it.badge_rect(0).center()) - r.topLeft()
        # no lugar do ⊖ só pode haver a linha do ramo (cor do ramo), nunca o círculo com fundo
        ring = it.mapToScene(it.badge_rect(0).center() + QPointF(0, -7)) - r.topLeft()
        assert img.pixelColor(int(ring.x()), int(ring.y())).alpha() == 0
        del c


def test_duplo_clique_no_controle_alterna_uma_vez_so(qapp):
    m = _map_com_filhos("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        vp = c.viewport()
        t = m.root.children[0]
        it = c.mscene.topic_items[t.id]
        _mover(c, _vp(c, it, it.box_rect().center()))
        QTest.qWait(10)
        pos = _vp(c, it, it.badge_rect(0).center())
        _mover(c, pos)
        # sequência real do sistema: clique + (2º clique como DblClick); o QTest.mouseDClick sozinho
        # manda só o evento de duplo clique
        QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        QTest.mouseDClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        QTest.qWait(20)
        assert m.find(t.id).collapsed                # alternou uma vez
        assert not m.floating                        # não criou tópico flutuante
        assert c.editor is None                      # não entrou em edição
    finally:
        _fechar(w)


def test_arrastar_a_partir_do_controle_nao_move_nem_alterna(qapp):
    m = _map_com_filhos("mapa_direita")
    w, c = _abrir(qapp, m)
    try:
        vp = c.viewport()
        t = m.root.children[0]
        it = c.mscene.topic_items[t.id]
        it.setSelected(True)
        before = QPointF(it.pos())
        start = _vp(c, it, it.badge_rect(0).center())
        _mover(c, start)
        QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        for k in range(1, 6):
            _mover(c, start + QPoint(0, 20 * k))
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(0, 100))
        QTest.qWait(20)
        it = c.mscene.topic_items[t.id]
        assert it.pos() == before
        assert not m.find(t.id).collapsed            # soltou fora: cancela, como um botão
        assert m.find(t.id).parent is m.root
    finally:
        _fechar(w)


def test_soltar_sobre_o_controle_conta_como_o_topico(qapp):
    m = _map_com_filhos("mapa_direita")
    s = MindScene(Document(m))
    s.sync()
    it = s.topic_items[m.root.children[0].id]
    it.setSelected(True)
    center = it.mapToScene(it.badge_rect(0).center())
    assert s.topic_at(center) is it


def test_area_minima_de_clique_no_zoom_baixo(qapp):
    m = _map_com_filhos("mapa_direita")
    s = MindScene(Document(m))
    s.sync()
    it = s.topic_items[m.root.children[0].id]
    h = it.handle
    s.set_view_scale(1.0)
    r1 = h.hit_radius()
    s.set_view_scale(0.4)
    r2 = h.hit_radius()
    assert r2 > r1 and r2 * 0.4 >= 7.9 or r2 == 20.0
    # a área ampliada nunca cobre a caixa do próprio tópico
    shape = h.shape()
    assert not shape.intersects(QRectF(it.box_rect()).adjusted(0.5, 0.5, -0.5, -0.5))
