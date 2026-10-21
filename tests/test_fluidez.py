"""Teste de "fluidez": sequências aleatórias de ações reais do usuário não podem gerar erro (1.4).

Teclado, mouse, troca de esqueleto/tema/tema rápido/roda, formatação, recolher, relação, zoom e idioma.
Qualquer exceção (inclusive dentro de sinais/timers do Qt) ou item da cena fora de sincronia falha o teste.
"""
import random
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from mindforge import colorthemes as ct
from mindforge.document import Document
from mindforge.layouts import LAYOUTS
from mindforge.templates import TEMPLATES


def _edge_drag(c, r):
    from PySide6.QtCore import QPoint, QPointF
    items = list(c.mscene.topic_items.values())
    if not items:
        return
    it = r.choice(items)
    vp = c.viewport()
    p = c.mapFromScene(it.mapToScene(QPointF(it.vis.w - 1, it.vis.h / 2)))
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
    QTest.mouseMove(vp, p + QPoint(r.randint(-150, 150), 0))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p + QPoint(r.randint(-150, 150), 0))


def _rel_drag(c, r):
    from PySide6.QtCore import QPoint
    rels = list(c.mscene.rel_items.values())
    if not rels:
        return
    ri = r.choice(rels)
    c.mscene.clearSelection()
    ri.setSelected(True)
    if not ri._pts:
        return
    key = r.choice(["c1", "c2", "p0", "p1"])
    vp = c.viewport()
    p = c.mapFromScene(ri.mapToScene(ri._pts[key]))
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
    QTest.mouseMove(vp, p + QPoint(r.randint(-80, 80), r.randint(-80, 80)))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p + QPoint(r.randint(-80, 80), 0))


def _rel_action(c, r):
    rels = c.doc.map.relations
    if rels:
        rel = r.choice(rels)
        c.relation_action(rel.id, r.choice(["reverse", "straighten", "arrows"]), r.choice(["end", "both", "none"]))


def test_acoes_aleatorias_nao_quebram(qapp):
    app = qapp
    errors = []
    old_hook = sys.excepthook
    sys.excepthook = lambda *a: errors.append("".join(traceback.format_exception(*a)))
    try:
        K=Qt.Key; M=Qt.KeyboardModifier
        for seed in range(3):
            r=random.Random(seed)
            w=app.new_window(Document(r.choice(TEMPLATES).create())); w.resize(1200,800); QTest.qWaitForWindowExposed(w); QTest.qWait(60)
            c=w.canvas; p=w.panel
            acts=[
             lambda: QTest.keyClick(c,K.Key_Tab), lambda: QTest.keyClick(c,K.Key_Return), lambda: QTest.keyClick(c,K.Key_Escape),
             lambda: QTest.keyClick(c,K.Key_Return,M.ShiftModifier), lambda: QTest.keyClick(c,K.Key_Delete),
             lambda: QTest.keyClick(c,r.choice([K.Key_Left,K.Key_Right,K.Key_Up,K.Key_Down])),
             lambda: QTest.keyClick(c,K.Key_Slash,M.ControlModifier), lambda: QTest.keyClick(c,K.Key_B,M.ControlModifier),
             lambda: QTest.keyClick(c,K.Key_I,M.ControlModifier), lambda: QTest.keyClick(c,K.Key_X,M.ControlModifier|M.ShiftModifier),
             lambda: QTest.keyClick(c,K.Key_Z,M.ControlModifier), lambda: QTest.keyClick(c,K.Key_Z,M.ControlModifier|M.ShiftModifier),
             lambda: QTest.keyClick(c,K.Key_D,M.ControlModifier), lambda: QTest.keyClick(c,K.Key_C,M.ControlModifier),
             lambda: QTest.keyClick(c,K.Key_V,M.ControlModifier), lambda: QTest.keyClick(c,K.Key_X,M.ControlModifier),
             lambda: QTest.keyClick(c,K.Key_Return,M.ControlModifier), lambda: QTest.keyClicks(c,"abc"),
             lambda: QTest.keyClick(c,K.Key_Up,M.ControlModifier),
             lambda: w._set_layout(r.choice(list(LAYOUTS))), lambda: p._apply_quick_theme(r.choice(list(ct.QUICK_THEMES))),
             lambda: p._set_variant(r.randrange(6)), lambda: p._apply_colors(r.choice(list(ct.CATALOG.values())).as_setting(), None),
             lambda: p.wheel_btn.picked.emit(r.choice([None,*ct.BRANCH_PALETTES])), lambda: p.rainbow.click(),
             lambda: p.static_btn.picked.emit("#336699"), lambda: c.set_collapsed_all(r.random()<0.5),
             lambda: c.select_all(), lambda: c.add_floating(),
             lambda: (c.start_relation(), QTest.mouseClick(c.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, c.mapFromScene(r.choice(list(c.mscene.topic_items.values())).sceneBoundingRect().center()))),
             lambda: c.set_zoom(r.choice([0.3,0.7,1,2])),
             lambda: QTest.mouseClick(c.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, c.mapFromScene(r.choice(list(c.mscene.topic_items.values())).sceneBoundingRect().center())),
             lambda: app._apply_language(r.choice(["pt_BR","en_US"]), persist=False),
             # 1.4.1: estilo, pincel, redimensionar, relações
             lambda: QTest.keyClick(c,K.Key_C,M.ControlModifier|M.AltModifier),
             lambda: QTest.keyClick(c,K.Key_V,M.ControlModifier|M.AltModifier),
             lambda: QTest.keyClick(c,K.Key_R,M.ControlModifier|M.AltModifier),
             lambda: w._brush_clicked(),
             lambda: _edge_drag(c, r),
             lambda: _rel_drag(c, r),
             lambda: _rel_action(c, r),
            ]
            for step in range(150):
                try:
                    r.choice(acts)()
                except Exception:
                    errors.append(f"seed {seed} step {step}\n"+traceback.format_exc())
                QTest.qWait(1)
                # consistência: todo tópico visível tem item; seleção válida
                m=w.doc.map
                vis_ids={t.id for top in m.tops() for t in top.walk_visible()}
                if set(c.mscene.topic_items)!=vis_ids and c.editor is None:
                    errors.append(f"seed {seed} step {step}: itens != tópicos visíveis")
                    break
            c.end_brush(); c.cancel_edit(); w.doc.mark_saved(); w.close(); QTest.qWait(5)
            app._apply_language("pt_BR", persist=False)
    finally:
        sys.excepthook = old_hook
        app._apply_language("pt_BR", persist=False)
    assert not errors, errors[0][-2000:]
