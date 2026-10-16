"""Cena gráfica: sincroniza o modelo com os itens desenhados.

``sync()`` é idempotente: calcula estilos, medidas e layout e então
reconcilia os itens existentes (reaproveita, cria ou remove), mantendo a
seleção. Tópicos são identificados pelo id, nunca pelo objeto Python.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from typing import Iterable, Iterator, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from mindforge.document import Document
from mindforge.layouts import LayoutResult, Metric, get_layout
from mindforge.layouts.base import layout_options, spacing
from mindforge.model.topic import Topic
from mindforge.themes import branch_color, get_theme, resolve_style
from mindforge.view.items import ConnectorItem, RelationItem, TopicItem
from mindforge.view.branches import draw_group
from mindforge.view.painting import TopicVisual, build_visual, connector_path, pattern_pen

SCENE_MARGIN = 2000.0
LINE_WIDTH_FACTOR = {"fina": 0.7, "padrao": 1.0, "grossa": 1.5}
COMPACT_SPACING = 0.6


class MindScene(QGraphicsScene):
    edit_requested = Signal(str)
    collapse_requested = Signal(str)
    topics_dropped = Signal(list, str)          # ids arrastados, id do novo pai
    floating_moved = Signal(list)               # [(id, x, y)]
    background_double_clicked = Signal(QPointF)
    relation_edit_requested = Signal(str)
    synced = Signal()

    def __init__(self, doc: Document, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.topic_items: dict[str, TopicItem] = {}
        self.conn_items: dict[str, ConnectorItem] = {}
        self.rel_items: dict[str, RelationItem] = {}
        self.visuals: dict[str, TopicVisual] = {}
        self.layout_result = LayoutResult()
        self.export_mode = False
        self.text_as_paths = False
        self.transparent_export = False
        self.background_color = "#FFFFFF"
        self.selection_color = "#2F80ED"
        self._drag: Optional[dict] = None
        self._bounds = QRectF()
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)

    # ================================================================ sincronizar
    def sync(self, text_overrides: Optional[dict[str, str]] = None) -> None:
        m = self.doc.map
        theme = get_theme(m.theme)
        layout = get_layout(m.layout)
        self.background_color = m.setting("background") or theme.background
        self.selection_color = theme.selection_color
        overrides = text_overrides or {}
        family = m.setting("font") or theme.font_family
        lw = LINE_WIDTH_FACTOR.get(m.setting("line_width"), 1.0)
        rainbow = bool(m.setting("rainbow"))

        def color_for(i: int) -> str:
            return branch_color(theme, i) if rainbow else theme.mono

        visuals: dict[str, TopicVisual] = {}
        metrics: dict[str, Metric] = {}
        bg = self.background_color
        hints = getattr(layout, "hints", {}) or {}

        def add_tree(top: Topic, top_level: str, color: Optional[str], main_palette: bool) -> None:
            stack: list[tuple[Topic, str, Optional[str]]] = [(top, top_level, color)]
            while stack:
                t, level, col = stack.pop()
                st = resolve_style(theme, level, col, t.style, hints.get(level), bg)
                if lw != 1.0 and "line_level" not in t.style:
                    st = replace(st, line_width=st.line_width * lw)
                vis = build_visual(overrides.get(t.id, t.text), st, t.markers, bool(t.note.strip()), family)
                vis.branch = col or theme.mono
                vis.level = level
                if t.collapsed and t.children:
                    vis.collapsed_count = t.descendant_count()
                visuals[t.id] = vis
                metrics[t.id] = Metric(vis.w, vis.h, vis.ay)
                for i, c in enumerate(t.visible_children()):
                    if level == "root" and main_palette:
                        stack.append((c, "main", color_for(i)))
                    else:
                        stack.append((c, "sub", col))

        add_tree(m.root, "root", None, True)
        for k, f in enumerate(m.floating):
            add_tree(f, "floating", color_for(k + 3), False)

        with spacing(COMPACT_SPACING if m.setting("compact") else 1.0), \
                layout_options(fishbone_align=bool(m.setting("fishbone_align"))):
            res = layout.compute(m.root, metrics)
            for f in m.floating:
                res.merge(layout.compute_floating(f, metrics))
        self.visuals = visuals
        self.layout_result = res

        # ---- tópicos
        for tid in list(self.topic_items):
            if tid not in res.pos:
                self.removeItem(self.topic_items.pop(tid))
        for tid, (x, y) in res.pos.items():
            item = self.topic_items.get(tid)
            if item is None:
                item = TopicItem(tid)
                self.addItem(item)
                self.topic_items[tid] = item
            vis = visuals[tid]
            vis.side = res.sides.get(tid, "right")
            item.is_root = tid == m.root.id
            item.editing = tid in overrides
            item.set_visual(vis)
            item.setPos(x, y)
            item.setFlag(item.GraphicsItemFlag.ItemIsMovable, not item.is_root)
            item.setVisible(True)
            item.drop_target = False

        # ---- linhas
        keys = set()
        index = {t.id: t for t in m.all_topics()}
        default_branch = m.setting("branch_style")

        def item_for(key: str) -> ConnectorItem:
            keys.add(key)
            ci = self.conn_items.get(key)
            if ci is None:
                ci = ConnectorItem(key)
                self.addItem(ci)
                self.conn_items[key] = ci
            ci.setVisible(True)
            return ci

        def line_color(parent_id: str, child_id: str) -> str:
            """Cor da linha pai → filho: escolha no filho > escolha no pai > cor do ramo."""
            ct, pt = index.get(child_id), index.get(parent_id)
            if ct is not None and ct.style.get("line_color"):
                return ct.style["line_color"]
            if pt is not None and pt.style.get("line_color"):
                return pt.style["line_color"]
            cv = visuals.get(child_id)
            return cv.style.line_color if cv else "#8A8F98"

        for g in res.groups:
            pv = visuals.get(g.parent)
            if pv is None:
                continue
            pst = pv.style
            if g.style == "indent":
                style = "indent"
            else:
                style = pst.branch_style or default_branch or g.style
            ci = item_for(g.key)
            ci.owner, ci.kid_ids, ci.is_group = g.parent, {k for k, _ in g.kids}, True
            if pst.line_pattern == "nenhum":
                ci.set_content([], [])
                continue
            colors = {cid: line_color(g.parent, cid) for cid, _ in g.kids}
            pt = index.get(g.parent)
            stub = pt.style.get("line_color") if pt is not None and pt.style.get("line_color") else None
            if stub is None and g.parent != m.root.id:
                stub = pst.line_color
            width = pst.line_width
            drawing = draw_group(style, g.direction, g.origin, g.kids, colors, stub, pst.line_end, width)
            strokes = [(st.path, pattern_pen(QColor(st.color), width, pst.line_pattern)) for st in drawing.strokes]
            marks = [(mk.path, QColor(mk.color), mk.filled,
                      QPen(QColor(mk.color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                           Qt.PenJoinStyle.RoundJoin)) for mk in drawing.marks]
            ci.set_content(strokes, marks)

        for c in res.connectors:
            ci = item_for(c.key)
            owner_vis = visuals.get(c.owner)
            color = owner_vis.style.line_color if owner_vis else "#8A8F98"
            width = (owner_vis.style.line_width if owner_vis else 1.6) * c.width
            pattern = owner_vis.style.line_pattern if owner_vis and c.key.startswith("rib:") else "solido"
            ci.owner, ci.kid_ids, ci.is_group = c.owner, set(), False
            ci.set_content([(connector_path(c.kind, c.points), pattern_pen(QColor(color), width, pattern))], [])
        for k in list(self.conn_items):
            if k not in keys:
                self.removeItem(self.conn_items.pop(k))

        self._sync_relations(theme.relation_color)
        self._update_scene_rect()
        self.update()
        self.synced.emit()

    def _sync_relations(self, color: str) -> None:
        m = self.doc.map
        keep = set()
        for r in m.relations:
            a = self.topic_items.get(r.source)
            b = self.topic_items.get(r.target)
            if a is None or b is None:
                continue
            keep.add(r.id)
            ri = self.rel_items.get(r.id)
            if ri is None:
                ri = RelationItem(r.id)
                self.addItem(ri)
                self.rel_items[r.id] = ri
            ra = a.mapRectToScene(a.box_rect())
            rb = b.mapRectToScene(b.box_rect())
            ri.set_geometry(ra, rb, r.label, color)
        for rid in list(self.rel_items):
            if rid not in keep:
                self.removeItem(self.rel_items.pop(rid))

    def content_rect(self, ids: Optional[set] = None) -> QRectF:
        rect = QRectF()
        for tid, it in self.topic_items.items():
            if it.isVisible() and (ids is None or tid in ids):
                rect = rect.united(it.mapRectToScene(it.visual_rect()))
        for ci in self.conn_items.values():
            if ci.isVisible() and (ids is None or ci.owner in ids) and not ci.visual_rect().isNull():
                rect = rect.united(ci.visual_rect())
        for ri in self.rel_items.values():
            if ri.isVisible():
                rect = rect.united(ri.visual_rect())
        return rect

    def _update_scene_rect(self) -> None:
        content = self.content_rect()
        if content.isNull():
            content = QRectF(-100, -100, 200, 200)
        wanted = content.adjusted(-SCENE_MARGIN, -SCENE_MARGIN, SCENE_MARGIN, SCENE_MARGIN)
        # só cresce durante a sessão: evita "pulos" da visualização ao editar
        self._bounds = wanted if self._bounds.isNull() else self._bounds.united(wanted)
        self.setSceneRect(self._bounds)

    # ================================================================== consulta
    def selected_topic_ids(self) -> list[str]:
        return [it.tid for it in self.selectedItems() if isinstance(it, TopicItem)]

    def selected_relation_ids(self) -> list[str]:
        return [it.rid for it in self.selectedItems() if isinstance(it, RelationItem)]

    def select_ids(self, ids: Iterable[str]) -> None:
        ids = set(ids)
        self.blockSignals(True)
        try:
            self.clearSelection()
            for tid in ids:
                it = self.topic_items.get(tid)
                if it is not None:
                    it.setSelected(True)
        finally:
            self.blockSignals(False)
        self.selectionChanged.emit()

    def topic_at(self, pos: QPointF, exclude: set = frozenset()) -> Optional[TopicItem]:
        for it in self.items(pos):
            if isinstance(it, TopicItem) and it.tid not in exclude and it.isVisible():
                if it.shape().contains(it.mapFromScene(pos)):
                    return it
        return None

    # ================================================================ exportação
    @contextmanager
    def exporting(self, only_ids: Optional[set] = None, text_as_paths: bool = False,
                  transparent: bool = False) -> Iterator[QRectF]:
        """Prepara a cena para exportar: sem seleção, sem editor e (opcional) só um ramo."""
        hidden = []
        self.export_mode = True
        self.text_as_paths = text_as_paths
        self.transparent_export = transparent
        try:
            if only_ids is not None:
                for tid, it in self.topic_items.items():
                    if tid not in only_ids and it.isVisible():
                        it.setVisible(False)
                        hidden.append(it)
                root_id = self.doc.map.root.id
                for ci in self.conn_items.values():
                    # dentro do ramo, mantém só as linhas cujo dono está no ramo
                    # (a linha que liga o ramo ao pai fica de fora)
                    if ci.is_group:
                        keep = ci.owner in only_ids
                    else:
                        keep = ci.owner in only_ids and not self._connects_outside(ci.owner, only_ids)
                    if ci.owner == root_id and root_id not in only_ids:
                        keep = False
                    if not keep and ci.isVisible():
                        ci.setVisible(False)
                        hidden.append(ci)
                rels = {r.id: r for r in self.doc.map.relations}
                for rid, ri in self.rel_items.items():
                    r = rels.get(rid)
                    if r is None or r.source not in only_ids or r.target not in only_ids:
                        if ri.isVisible():
                            ri.setVisible(False)
                            hidden.append(ri)
            self.update()
            yield self.content_rect()
        finally:
            for it in hidden:
                it.setVisible(True)
            self.export_mode = False
            self.text_as_paths = False
            self.transparent_export = False
            self.update()

    def _connects_outside(self, owner: str, ids: set) -> bool:
        t = self.doc.map.find(owner)
        return t is not None and t.parent is not None and t.parent.id not in ids

    # ========================================================== arrastar e soltar
    def mousePressEvent(self, e: QGraphicsSceneMouseEvent) -> None:
        super().mousePressEvent(e)
        self._drag = None
        if e.button() != Qt.MouseButton.LeftButton:
            return
        grabbed = self.mouseGrabberItem()
        if isinstance(grabbed, TopicItem) and not grabbed.is_root and grabbed.isSelected():
            m = self.doc.map
            from mindforge.model import ops
            tops = [t for t in ops.top_level_selection(m, self.selected_topic_ids()) if t is not m.root]
            moved = set()
            for t in tops:
                moved.update(x.id for x in t.walk_visible())
            orig = {tid: QPointF(self.topic_items[tid].pos()) for tid in moved if tid in self.topic_items}
            self._drag = {"item": grabbed, "tops": [t.id for t in tops], "moved": moved,
                          "orig": orig, "start": QPointF(e.scenePos()), "active": False}

    def mouseMoveEvent(self, e: QGraphicsSceneMouseEvent) -> None:
        super().mouseMoveEvent(e)
        d = self._drag
        if not d:
            return
        if not d["active"]:
            if (e.scenePos() - d["start"]).manhattanLength() < 4:
                return
            d["active"] = True
            for ci in self.conn_items.values():
                if ci.owner in d["moved"] or (ci.kid_ids & d["moved"]):
                    ci.setVisible(False)
            for ri in self.rel_items.values():
                ri.setVisible(False)
        item: TopicItem = d["item"]
        delta = item.pos() - d["orig"][item.tid]
        selected = set(self.selected_topic_ids())
        for tid, p0 in d["orig"].items():
            if tid not in selected:
                self.topic_items[tid].setPos(p0 + delta)
        target = self.topic_at(e.scenePos(), exclude=d["moved"])
        for it in self.topic_items.values():
            flag = it is target
            if it.drop_target != flag:
                it.drop_target = flag
                it.update()

    def mouseReleaseEvent(self, e: QGraphicsSceneMouseEvent) -> None:
        d = self._drag
        super().mouseReleaseEvent(e)
        self._drag = None
        if not d or not d["active"]:
            return
        target = self.topic_at(e.scenePos(), exclude=d["moved"])
        for it in self.topic_items.values():
            it.drop_target = False
        if target is not None:
            self.topics_dropped.emit(list(d["tops"]), target.tid)
            return
        m = self.doc.map
        moves = []
        for tid in d["tops"]:
            t = m.find(tid)
            if t is not None and m.is_floating_root(t):
                p = self.topic_items[tid].pos()
                moves.append((tid, p.x(), p.y()))
        if moves:
            self.floating_moved.emit(moves)
        else:
            self.sync()     # solto no vazio: volta ao lugar

    def mouseDoubleClickEvent(self, e: QGraphicsSceneMouseEvent) -> None:
        hit = any(isinstance(i, (TopicItem, RelationItem)) for i in self.items(e.scenePos()))
        if not hit and e.button() == Qt.MouseButton.LeftButton:
            self.background_double_clicked.emit(e.scenePos())
            e.accept()
            return
        super().mouseDoubleClickEvent(e)
