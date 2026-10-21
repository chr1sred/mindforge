"""Itens gráficos da cena: tópico, conector, relação e editor de texto."""
from __future__ import annotations

import math
import sys
import time

import shiboken6
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QKeyEvent, QPainter, QPainterPath,
    QPainterPathStroker, QPen, QTextOption,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem, QStyleOptionGraphicsItem

from mindforge.view.painting import (
    TopicVisual, badge_center, badge_radius, default_family, paint_badge, paint_control, paint_topic,
)
from mindforge.i18n import ntr, tr

if TYPE_CHECKING:
    from mindforge.view.scene import MindScene

Z_CONNECTOR = 0
Z_TOPIC = 10
Z_RELATION = 20
Z_EDITOR = 100


class TopicItem(QGraphicsItem):
    MARGIN = 26.0

    def __init__(self, tid: str):
        super().__init__()
        self.tid = tid
        self.vis: Optional[TopicVisual] = None
        self.hover = False
        self.drop_target = False
        self.editing = False
        self.is_root = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(Z_TOPIC)
        self.linger_until = 0.0              # ⊖ continua visível um instante depois que o mouse sai
        self.handle = CollapseHandle(self)
        self._resize: Optional[dict] = None  # arraste da borda (redimensionar largura, 1.4.1)

    def mind_scene(self) -> "MindScene":
        return self.scene()  # type: ignore[return-value]

    # --------------------------------------------------------------- geometria
    def set_visual(self, vis: TopicVisual) -> None:
        self.prepareGeometryChange()
        self.vis = vis
        self.handle.geometry_changed()
        self.update_handle()
        self.update()

    def boundingRect(self) -> QRectF:
        if self.vis is None:
            return QRectF()
        m = self.MARGIN
        return QRectF(-m, -m, self.vis.w + 2 * m, self.vis.h + 2 * m)

    def box_rect(self) -> QRectF:
        return QRectF(0, 0, self.vis.w, self.vis.h) if self.vis else QRectF()

    def visual_rect(self) -> QRectF:
        """Área realmente desenhada (para exportação), em coordenadas do item."""
        r = self.box_rect()
        if self.vis and self.vis.collapsed_count:
            r = r.united(self.badge_rect())
        return r

    def has_toggle(self) -> bool:
        return bool(self.vis and not self.is_root and (self.vis.collapsed_count or self.vis.has_children))

    def badge_rect(self, grow: float = 1.0) -> QRectF:
        c = badge_center(self.vis)
        r = badge_radius(self.vis) + grow
        return QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)

    def shape(self) -> QPainterPath:
        # Só a caixa. O controle de recolher é um item próprio (CollapseHandle), com área de clique
        # própria; misturar as duas áreas num mesmo caminho criava "buracos" sem clique no tópico.
        p = QPainterPath()
        p.addRect(self.box_rect())
        return p

    # ---------------------------------------------------- controle ⊖ / número
    def handle_wanted(self) -> bool:
        """O controle aparece com o ramo recolhido, ou com o tópico sob o mouse/selecionado."""
        if not self.has_toggle():
            return False
        if self.vis.collapsed_count:
            return True
        return (self.hover or self.isSelected() or self.handle.hovered or self.handle.pressed
                or time.monotonic() < self.linger_until)

    def update_handle(self) -> None:
        want = self.handle_wanted()
        if self.handle.isVisible() != want:
            self.handle.setVisible(want)
        self.handle.refresh_tooltip()
        self.handle.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update_handle()
        return super().itemChange(change, value)

    # ----------------------------------------------------------------- pintura
    def paint(self, p: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        if self.vis is None:
            return
        sc = self.mind_scene()
        export = sc.export_mode if sc else False
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        paint_topic(p, self.vis, text_as_paths=bool(sc and sc.text_as_paths), hide_text=self.editing)
        bg = sc.background_color if sc else "#FFFFFF"
        if self.vis.collapsed_count and not self.is_root:
            paint_badge(p, self.vis, bg)
        if export:
            return
        sel = QColor(sc.selection_color if sc else "#2F80ED")
        if self.drop_target:
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(sel, 2.5, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawRoundedRect(self.box_rect().adjusted(-6, -6, 6, 6), 8, 8)
        elif self.isSelected():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(sel, 2.4))
            p.drawRoundedRect(self.box_rect().adjusted(-4, -4, 4, 4), 7, 7)
        elif self.hover:
            c = QColor(sel)
            c.setAlphaF(0.45)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(c, 1.6))
            p.drawRoundedRect(self.box_rect().adjusted(-4, -4, 4, 4), 7, 7)

    # ------------------------------------------------------------------ eventos
    def hoverEnterEvent(self, e) -> None:
        self.hover = True
        self.update_handle()
        self.update()

    def hoverLeaveEvent(self, e) -> None:
        self.hover = False
        if self.has_toggle() and not self.vis.collapsed_count:
            self.linger_until = time.monotonic() + HANDLE_LINGER_S
            tid, sc = self.tid, self.scene()
            _schedule_refresh(sc, tid)
        self.update_handle()
        self.update()

    # ------------------------------------------------ redimensionar (1.4.1)
    def edge_at(self, pos: QPointF) -> Optional[str]:
        """"left"/"right" quando o ponteiro está na borda lateral da caixa (zona de redimensionar)."""
        sc = self.scene()
        if self.vis is None or self.editing or sc is None:
            return None
        for v in sc.views():
            if getattr(v, "brush_mode", None) or getattr(v, "relation_source", None):
                return None
        scale = getattr(sc, "view_scale", 1.0) or 1.0
        zone = min(max(RESIZE_ZONE_PX / scale, 4.0), self.vis.w / 4)
        if not (0 <= pos.y() <= self.vis.h):
            return None
        if 0 <= pos.x() <= zone:
            return "left"
        if self.vis.w - zone <= pos.x() <= self.vis.w:
            return "right"
        return None

    def min_width(self) -> float:
        """A palavra mais longa precisa caber (nenhuma palavra cortada)."""
        vis = self.vis
        fm = QFontMetricsF(vis.font)
        longest = max((fm.horizontalAdvance(w) for w in " ".join(vis.lines).split()), default=10.0)
        return max(40.0, (vis.w - vis.text_w) + longest + 2)

    def hoverMoveEvent(self, e) -> None:
        if self.edge_at(e.pos()):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(e)

    def mousePressEvent(self, e) -> None:
        side = self.edge_at(e.pos()) if e.button() == Qt.MouseButton.LeftButton else None
        if side:
            sc = self.mind_scene()
            if not self.isSelected():
                sc.clearSelection()
                self.setSelected(True)
            self._resize = {"side": side, "x0": e.scenePos().x(), "w0": self.vis.w,
                            "min": self.min_width(), "w": self.vis.w}
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        r = self._resize
        if r is not None:
            dx = e.scenePos().x() - r["x0"]
            w = r["w0"] + (dx if r["side"] == "right" else -dx)
            r["w"] = max(r["min"], min(RESIZE_MAX_W, w))
            self.mind_scene().width_preview.emit(self.tid, float(r["w"]))
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        r = self._resize
        if r is not None:
            self._resize = None
            if abs(r["w"] - r["w0"]) >= 1:
                self.mind_scene().width_commit.emit(self.tid, float(r["w"]))
            else:
                self.mind_scene().width_commit.emit(self.tid, -1.0)     # só clicou: nada muda
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.edge_at(e.pos()) and self.vis.style.fixed_width:
            # duplo clique na borda de um tópico com largura fixa: volta à automática
            # (sem largura fixa, o duplo clique continua editando o texto)
            self.mind_scene().width_commit.emit(self.tid, 0.0)
            e.accept()
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self.mind_scene().edit_requested.emit(self.tid)
            e.accept()
            return
        super().mouseDoubleClickEvent(e)


RESIZE_ZONE_PX = 6.0          # largura da zona de redimensionar, em pixels de tela
RESIZE_MAX_W = 2000.0

HANDLE_LINGER_S = 0.25        # tempo que o ⊖ espera antes de sumir (caminho do tópico até ele)
HANDLE_MIN_SCREEN_R = 8.0     # raio mínimo da área de clique, em pixels de tela (≈ 16 px de diâmetro)
HANDLE_MAX_HIT_R = 20.0       # teto da área de clique, em unidades do mapa (não invade os filhos)


def _refresh_handle(scene, tid: str) -> None:
    try:
        if scene is None or not shiboken6.isValid(scene):
            return
        it = scene.topic_items.get(tid)
        if it is not None and shiboken6.isValid(it):
            it.update_handle()
    except RuntimeError:        # cena/tópico destruídos no meio do caminho (janela fechada, idioma trocado)
        pass


def _schedule_refresh(scene, tid: str) -> None:
    """Reavalia o ⊖ depois do tempo de espera. O timer é ligado à cena: se a cena for destruída
    antes (janela fechada, troca de idioma), ele é cancelado pelo Qt."""
    if scene is None:
        return
    QTimer.singleShot(int(HANDLE_LINGER_S * 1000) + 20, scene, lambda: _refresh_handle(scene, tid))


class CollapseHandle(QGraphicsItem):
    """Controle de recolher/expandir de um tópico (⊖ ou número), no padrão do XMind.

    É um item filho do tópico, com área de clique, hover, cursor e dica próprios:
      - clique no ⊖ recolhe; clique no número expande um nível; Alt+clique expande tudo;
      - duplo clique não edita, não cria tópico flutuante e não alterna de volta;
      - não é selecionável e não inicia arraste do tópico.
    Usa as mesmas coordenadas do tópico (pos = 0,0 dentro dele).
    """

    def __init__(self, topic: "TopicItem"):
        super().__init__(topic)
        self.topic = topic
        self.hovered = False
        self.pressed = False
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setVisible(False)
        self._tip = ""
        self._last_toggle = 0.0

    # -------------------------------------------------------------- geometria
    def geometry_changed(self) -> None:
        self.prepareGeometryChange()
        self.hovered = False
        self.pressed = False

    def boundingRect(self) -> QRectF:
        vis = self.topic.vis
        if vis is None or not self.topic.has_toggle():
            return QRectF()
        c = badge_center(vis)
        r = HANDLE_MAX_HIT_R + 2
        return QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)

    def hit_radius(self) -> float:
        vis = self.topic.vis
        r = badge_radius(vis) + 3.0
        sc = self.scene()
        scale = getattr(sc, "view_scale", 1.0) if sc is not None else 1.0
        if scale > 0:
            r = max(r, HANDLE_MIN_SCREEN_R / scale)
        return min(r, HANDLE_MAX_HIT_R)

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        vis = self.topic.vis
        if vis is None or not self.topic.has_toggle():
            return p
        c = badge_center(vis)
        r = self.hit_radius()
        p.addEllipse(c, r, r)
        # nunca "rouba" cliques da caixa do próprio tópico (zoom baixo aumenta a área)
        box = QPainterPath()
        box.addRect(self.topic.box_rect())
        return p.subtracted(box)

    # ----------------------------------------------------------------- pintura
    def paint(self, p: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        vis = self.topic.vis
        sc = self.scene()
        if vis is None or (sc is not None and sc.export_mode):
            return
        state = "pressed" if self.pressed else ("hover" if self.hovered else "normal")
        if vis.collapsed_count and state == "normal":
            return          # o número em estado normal é desenhado pelo tópico (e sai na exportação)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        paint_control(p, vis, sc.background_color if sc else "#FFFFFF", state)

    def refresh_tooltip(self) -> None:
        vis = self.topic.vis
        if vis is None:
            return
        if vis.collapsed_count:
            tip = ntr("Expandir {n} tópico · Alt+clique: expandir tudo",
                      "Expandir {n} tópicos · Alt+clique: expandir tudo", vis.collapsed_count)
        else:
            tip = tr("Recolher (Ctrl+/)")
            if sys.platform == "darwin":
                tip = tip.replace("Ctrl+", "⌘")
        if tip != self._tip:
            self._tip = tip
            self.setToolTip(tip)

    # ------------------------------------------------------------------ eventos
    def hoverEnterEvent(self, e) -> None:
        self.hovered = True
        self.update()

    def hoverLeaveEvent(self, e) -> None:
        self.hovered = False
        self.topic.linger_until = time.monotonic() + HANDLE_LINGER_S
        sc, tid = self.scene(), self.topic.tid
        _schedule_refresh(sc, tid)
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            e.ignore()
            return
        sc = self.scene()
        if sc is not None:
            sc.last_handle_click = time.monotonic()
        from PySide6.QtWidgets import QApplication
        if time.monotonic() - self._last_toggle < QApplication.doubleClickInterval() / 1000.0:
            e.accept()      # 2º clique de um duplo clique: alterna uma vez só
            return
        self.pressed = True
        sc = self.scene()
        if sc is not None:
            sc.last_handle_click = time.monotonic()
        self.update()
        e.accept()          # não seleciona nem arrasta o tópico

    def mouseMoveEvent(self, e) -> None:
        inside = self.shape().contains(e.pos())
        if inside != self.hovered:
            self.hovered = inside
            self.update()
        e.accept()

    def mouseReleaseEvent(self, e) -> None:
        was = self.pressed
        self.pressed = False
        self.update()
        e.accept()
        if not was or e.button() != Qt.MouseButton.LeftButton or not self.shape().contains(e.pos()):
            return          # soltou fora do controle: cancela, como um botão comum
        sc = self.topic.mind_scene()
        if sc is None:
            return
        self._last_toggle = time.monotonic()
        if self.topic.vis.collapsed_count and e.modifiers() & Qt.KeyboardModifier.AltModifier:
            sc.expand_all_requested.emit(self.topic.tid)
        else:
            sc.collapse_requested.emit(self.topic.tid)

    def mouseDoubleClickEvent(self, e) -> None:
        e.accept()          # 2º clique rápido: ignorado (não edita, não alterna de volta)


class ConnectorItem(QGraphicsItem):
    """Linhas de um grupo de ramos (ou de uma linha estrutural): traços + pontas."""

    def __init__(self, key: str):
        super().__init__()
        self.key = key
        self.owner = ""                    # tópico "dono" (pai, no caso de grupos)
        self.kid_ids: set[str] = set()     # filhos ligados por este item
        self.is_group = False
        self.strokes: list[tuple[QPainterPath, QPen]] = []
        self.marks: list[tuple[QPainterPath, QColor, bool, QPen]] = []
        self._rect = QRectF()
        self.setZValue(Z_CONNECTOR)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def set_content(self, strokes, marks) -> None:
        self.prepareGeometryChange()
        self.strokes = strokes
        self.marks = marks
        r = QRectF()
        for path, pen in strokes:
            w = pen.widthF()
            r = r.united(path.boundingRect().adjusted(-w, -w, w, w))
        for path, _c, _f, pen in marks:
            w = pen.widthF()
            r = r.united(path.boundingRect().adjusted(-w, -w, w, w))
        self._rect = r
        self.update()

    def boundingRect(self) -> QRectF:
        return self._rect

    def visual_rect(self) -> QRectF:
        return self._rect

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addRect(self._rect)
        return p

    def paint(self, p: QPainter, option, widget=None) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for path, pen in self.strokes:
            p.setPen(pen)
            p.drawPath(path)
        for path, color, filled, pen in self.marks:
            if filled:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                p.drawPath(path)
                p.setBrush(Qt.BrushStyle.NoBrush)
            else:
                p.setPen(pen)
                p.drawPath(path)


def _clip_to_rect(center: QPointF, toward: QPointF, rect: QRectF) -> QPointF:
    """Ponto onde a reta centro→alvo cruza a borda do retângulo."""
    dx, dy = toward.x() - center.x(), toward.y() - center.y()
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return center
    hw, hh = rect.width() / 2 + 4, rect.height() / 2 + 4
    t = min(hw / abs(dx) if dx else math.inf, hh / abs(dy) if dy else math.inf)
    return QPointF(center.x() + dx * t, center.y() + dy * t)


def rect_point(rect: QRectF, t: float, pad: float = 4.0) -> QPointF:
    """Ponto na borda do retângulo (com folga `pad`), t de 0 a 1 em volta: topo → direita → base → esquerda."""
    r = rect.adjusted(-pad, -pad, pad, pad)
    w, h = r.width(), r.height()
    per = 2 * (w + h) or 1.0
    s = (t % 1.0) * per
    if s <= w:
        return QPointF(r.left() + s, r.top())
    s -= w
    if s <= h:
        return QPointF(r.right(), r.top() + s)
    s -= h
    if s <= w:
        return QPointF(r.right() - s, r.bottom())
    s -= w
    return QPointF(r.left(), r.bottom() - s)


def rect_param(rect: QRectF, pt: QPointF, pad: float = 4.0) -> float:
    """Inverso de rect_point: parâmetro (0..1) do ponto da borda mais próximo de `pt`."""
    r = rect.adjusted(-pad, -pad, pad, pad)
    w, h = r.width(), r.height()
    per = 2 * (w + h) or 1.0
    x = min(max(pt.x(), r.left()), r.right())
    y = min(max(pt.y(), r.top()), r.bottom())
    cands = [
        (abs(pt.y() - r.top()) + (0 if r.left() <= pt.x() <= r.right() else abs(pt.x() - x)), x - r.left()),
        (abs(pt.x() - r.right()) + (0 if r.top() <= pt.y() <= r.bottom() else abs(pt.y() - y)), w + (y - r.top())),
        (abs(pt.y() - r.bottom()) + (0 if r.left() <= pt.x() <= r.right() else abs(pt.x() - x)),
         w + h + (r.right() - x)),
        (abs(pt.x() - r.left()) + (0 if r.top() <= pt.y() <= r.bottom() else abs(pt.y() - y)),
         2 * w + h + (r.bottom() - y)),
    ]
    return (min(cands)[1] / per) % 1.0


REL_HANDLE_PX = 5.0       # tamanho dos controles da relação, em pixels de tela


class RelationItem(QGraphicsPathItem):
    """Relação (linha tracejada com seta) entre dois tópicos.

    Selecionada, mostra os controles (padrão XMind): dois quadrados que mudam a curvatura e dois
    círculos nas pontas que deslizam o ponto de encaixe pela borda do tópico (1.4.1)."""

    def __init__(self, rid: str):
        super().__init__()
        self.rid = rid
        self.label = ""
        self.color = QColor("#7C8594")
        self.arrows = "end"
        self._label_pos = QPointF()
        self._arrow = QPainterPath()
        self._a = QRectF()
        self._b = QRectF()
        self._shape: dict = {}
        self._pts: dict = {}              # p0, c1, c2, p1 (geometria atual)
        self._drag: Optional[dict] = None
        self.setZValue(Z_RELATION)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # -------------------------------------------------------------- geometria
    @staticmethod
    def _auto_controls(a: QRectF, b: QRectF, side: float) -> tuple[QPointF, QPointF]:
        ca, cb = a.center(), b.center()
        dist = math.hypot(cb.x() - ca.x(), cb.y() - ca.y()) or 1.0
        nx, ny = -(cb.y() - ca.y()) / dist * side, (cb.x() - ca.x()) / dist * side
        bend = min(120.0, dist * 0.3)
        c1 = QPointF(ca.x() + (cb.x() - ca.x()) * 0.25 + nx * bend, ca.y() + (cb.y() - ca.y()) * 0.25 + ny * bend)
        c2 = QPointF(ca.x() + (cb.x() - ca.x()) * 0.75 + nx * bend, ca.y() + (cb.y() - ca.y()) * 0.75 + ny * bend)
        return c1, c2

    def _build(self, a: QRectF, b: QRectF, shape: dict, side: float) -> dict:
        auto1, auto2 = self._auto_controls(a, b, side)
        ga, gb = shape.get("anchor_a"), shape.get("anchor_b")
        p0 = rect_point(a, ga) if ga is not None else None
        p1 = rect_point(b, gb) if gb is not None else None
        c1o, c2o = shape.get("c1"), shape.get("c2")
        # encaixe automático: onde a reta centro→controle cruza a borda
        if p0 is None:
            p0 = _clip_to_rect(a.center(), auto1 if c1o is None else a.center() + QPointF(*c1o), a)
        if p1 is None:
            p1 = _clip_to_rect(b.center(), auto2 if c2o is None else b.center() + QPointF(*c2o), b)
        c1 = p0 + QPointF(*c1o) if c1o is not None else auto1
        c2 = p1 + QPointF(*c2o) if c2o is not None else auto2
        path = QPainterPath(p0)
        path.cubicTo(c1, c2, p1)
        return {"p0": p0, "c1": c1, "c2": c2, "p1": p1, "path": path}

    @staticmethod
    def _crossings(path: QPainterPath, obstacles: list) -> int:
        n = 0
        for k in range(1, 40):
            pt = path.pointAtPercent(k / 40)
            if any(r.contains(pt) for r in obstacles):
                n += 1
        return n

    def set_geometry(self, a: QRectF, b: QRectF, label: str, color: str,
                     obstacles: Optional[list] = None, shape: Optional[dict] = None,
                     arrows: str = "end") -> None:
        """obstacles: caixas (cena) que a curva automática e o rótulo evitam. shape: forma personalizada."""
        self.prepareGeometryChange()
        self.label = label
        self.color = QColor(color)
        self.arrows = arrows
        self._a, self._b = QRectF(a), QRectF(b)
        self._shape = dict(shape or {})
        label_obstacles = list(obstacles or [])
        custom = any(self._shape.get(k) is not None for k in ("c1", "c2"))
        g = self._build(a, b, self._shape, 1.0)
        if not custom:
            free = [r for r in label_obstacles if not r.intersects(a) and not r.intersects(b)]
            if free and self._crossings(g["path"], free):
                alt = self._build(a, b, self._shape, -1.0)      # curva para o outro lado, se cruzar menos
                if self._crossings(alt["path"], free) < self._crossings(g["path"], free):
                    g = alt
        self._apply(g)
        self._label_pos = g["path"].pointAtPercent(0.5)
        if self.label and label_obstacles:
            best, best_hit = self._label_pos, None
            for t in (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82):
                self._label_pos = g["path"].pointAtPercent(t)
                r = self._label_rect().adjusted(-3, -3, 3, 3)
                hit = sum((r.intersected(o).width() * r.intersected(o).height()) for o in label_obstacles
                          if r.intersects(o))
                if best_hit is None or hit < best_hit:
                    best, best_hit = QPointF(self._label_pos), hit
                if hit == 0:
                    break
            self._label_pos = best

    def _apply(self, g: dict) -> None:
        self.prepareGeometryChange()
        self._pts = g
        self.setPath(g["path"])
        arrow = QPainterPath()
        if self.arrows in ("end", "both"):
            self._add_arrow(arrow, g["p1"], g["c2"])
        if self.arrows == "both":
            self._add_arrow(arrow, g["p0"], g["c1"])
        self._arrow = arrow

    @staticmethod
    def _add_arrow(path: QPainterPath, tip: QPointF, ctrl: QPointF) -> None:
        ang = math.atan2(tip.y() - ctrl.y(), tip.x() - ctrl.x())
        path.moveTo(tip)
        for sgn in (1, -1):
            a2 = ang + math.pi - sgn * math.radians(25)
            path.lineTo(QPointF(tip.x() + 11 * math.cos(a2), tip.y() + 11 * math.sin(a2)))
        path.closeSubpath()

    def label_scene_rect(self) -> QRectF:
        return self._label_rect()

    def _label_font(self) -> QFont:
        f = QFont(default_family())
        f.setPixelSize(12)
        f.setItalic(True)
        return f

    def _label_rect(self) -> QRectF:
        if not self.label:
            return QRectF()
        fm = QFontMetricsF(self._label_font())
        w = fm.horizontalAdvance(self.label) + 12
        h = fm.height() + 6
        return QRectF(self._label_pos.x() - w / 2, self._label_pos.y() - h / 2, w, h)

    # -------------------------------------------------------------- controles
    def _handle_r(self) -> float:
        sc = self.scene()
        scale = getattr(sc, "view_scale", 1.0) if sc is not None else 1.0
        return max(4.0, REL_HANDLE_PX / (scale or 1.0))

    def _editing(self) -> bool:
        sc = self.scene()
        return self.isSelected() and not getattr(sc, "export_mode", False) and bool(self._pts)

    def handle_at(self, pos: QPointF) -> Optional[str]:
        if not self._editing():
            return None
        r = self._handle_r() + 3
        best, best_d = None, None
        for key in ("c1", "c2", "p0", "p1"):     # o mais próximo vence (controles podem se sobrepor)
            pt = self._pts[key]
            if abs(pos.x() - pt.x()) <= r and abs(pos.y() - pt.y()) <= r:
                dist = math.hypot(pos.x() - pt.x(), pos.y() - pt.y())
                if best_d is None or dist < best_d:
                    best, best_d = key, dist
        return best

    def _handles_rect(self) -> QRectF:
        if not self._pts:
            return QRectF()
        r = self._handle_r() + 4
        xs = [self._pts[k].x() for k in ("p0", "c1", "c2", "p1")]
        ys = [self._pts[k].y() for k in ("p0", "c1", "c2", "p1")]
        return QRectF(min(xs) - r, min(ys) - r, max(xs) - min(xs) + 2 * r, max(ys) - min(ys) + 2 * r)

    def boundingRect(self) -> QRectF:
        br = self.path().boundingRect().adjusted(-14, -14, 14, 14).united(self._label_rect())
        return br.united(self._handles_rect())       # inclui os controles (aparecem ao selecionar)

    def shape(self) -> QPainterPath:
        s = QPainterPathStroker()
        s.setWidth(12)
        p = s.createStroke(self.path())
        r = self._label_rect()
        if not r.isNull():
            p.addRect(r)
        if self._editing():
            hr = self._handle_r() + 3
            for key in ("c1", "c2", "p0", "p1"):
                pt = self._pts[key]
                p.addRect(QRectF(pt.x() - hr, pt.y() - hr, 2 * hr, 2 * hr))
        return p

    def visual_rect(self) -> QRectF:
        return self.path().boundingRect().united(self._arrow.boundingRect()).united(self._label_rect())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.prepareGeometryChange()      # a área clicável muda (controles)
        return super().itemChange(change, value)

    # ----------------------------------------------------------------- pintura
    def paint(self, p: QPainter, option, widget=None) -> None:
        sc = self.scene()
        export = getattr(sc, "export_mode", False)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        sel = self.isSelected() and not export
        color = QColor(getattr(sc, "selection_color", "#2F80ED")) if sel else self.color
        pen = QPen(color, 2.0 if sel else 1.6, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(self.path())
        p.setPen(QPen(color, 1.2))
        p.setBrush(QBrush(color))
        p.drawPath(self._arrow)
        if self.label:
            r = self._label_rect()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(getattr(sc, "background_color", "#FFFFFF")))
            if not (export and getattr(sc, "transparent_export", False)):
                p.drawRoundedRect(r, 4, 4)
            f = self._label_font()
            if getattr(sc, "text_as_paths", False):
                tp = QPainterPath()
                fm = QFontMetricsF(f)
                tp.addText(QPointF(r.x() + 6, r.y() + 3 + fm.ascent()), f, self.label)
                p.fillPath(tp, color)
            else:
                p.setFont(f)
                p.setPen(color)
                p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), self.label)
        if sel and self._pts:
            self._paint_handles(p, color, QColor(getattr(sc, "background_color", "#FFFFFF")))

    def _paint_handles(self, p: QPainter, color: QColor, bg: QColor) -> None:
        g = self._pts
        hr = self._handle_r()
        thin = QPen(color, 1.0)
        thin.setCosmetic(True)
        p.setPen(thin)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(g["p0"], g["c1"])
        p.drawLine(g["p1"], g["c2"])
        edge = QPen(color, 1.6)
        edge.setCosmetic(True)
        p.setPen(edge)
        p.setBrush(bg)
        for key in ("c1", "c2"):                       # quadrados: curvatura
            c = g[key]
            p.drawRect(QRectF(c.x() - hr, c.y() - hr, 2 * hr, 2 * hr))
        for key in ("p0", "p1"):                       # círculos: ponto de encaixe
            p.drawEllipse(g[key], hr * 0.9, hr * 0.9)

    # ------------------------------------------------------------------ eventos
    def hoverMoveEvent(self, e) -> None:
        h = self.handle_at(e.pos())
        if h in ("c1", "c2"):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif h in ("p0", "p1"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverMoveEvent(e)

    def mousePressEvent(self, e) -> None:
        h = self.handle_at(e.pos()) if e.button() == Qt.MouseButton.LeftButton else None
        if h:
            self._drag = {"key": h, "shape": dict(self._shape), "moved": False}
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        d = self._drag
        if d is None:
            super().mouseMoveEvent(e)
            return
        pos = e.pos()
        sh = d["shape"]
        g = self._pts
        if d["key"] == "c1":
            sh["c1"] = (pos.x() - g["p0"].x(), pos.y() - g["p0"].y())
            sh.setdefault("c2", (g["c2"].x() - g["p1"].x(), g["c2"].y() - g["p1"].y()))
        elif d["key"] == "c2":
            sh["c2"] = (pos.x() - g["p1"].x(), pos.y() - g["p1"].y())
            sh.setdefault("c1", (g["c1"].x() - g["p0"].x(), g["c1"].y() - g["p0"].y()))
        elif d["key"] == "p0":
            sh["anchor_a"] = rect_param(self._a, pos)
        else:
            sh["anchor_b"] = rect_param(self._b, pos)
        # ao mexer num encaixe, mantém a curvatura atual (controles fixos em relação às pontas)
        if d["key"] in ("p0", "p1"):
            sh.setdefault("c1", (g["c1"].x() - g["p0"].x(), g["c1"].y() - g["p0"].y()))
            sh.setdefault("c2", (g["c2"].x() - g["p1"].x(), g["c2"].y() - g["p1"].y()))
        d["moved"] = True
        self._apply(self._build(self._a, self._b, sh, 1.0))
        self._label_pos = self.path().pointAtPercent(0.5)
        self.update()
        e.accept()

    def mouseReleaseEvent(self, e) -> None:
        d = self._drag
        if d is None:
            super().mouseReleaseEvent(e)
            return
        self._drag = None
        e.accept()
        if d["moved"]:
            keys = ("anchor_a", "anchor_b", "c1", "c2")
            self.scene().relation_shape_changed.emit(self.rid, {k: d["shape"].get(k) for k in keys})

    def mouseDoubleClickEvent(self, e) -> None:
        if self.handle_at(e.pos()):
            e.accept()
            return
        self.scene().relation_edit_requested.emit(self.rid)
        e.accept()


def text_format_for(e: QKeyEvent) -> Optional[str]:
    """Atalhos de formatação de texto: Ctrl/⌘+B, Ctrl/⌘+I, Ctrl/⌘+Shift+X."""
    mods = e.modifiers()
    if not mods & Qt.KeyboardModifier.ControlModifier or mods & Qt.KeyboardModifier.AltModifier:
        return None
    shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
    key = e.key()
    if key == Qt.Key.Key_B and not shift:
        return "bold"
    if key == Qt.Key.Key_I and not shift:
        return "italic"
    if key == Qt.Key.Key_X and shift:
        return "strike"
    return None


class EditorItem(QGraphicsTextItem):
    """Editor de texto embutido no tópico.

    Enter confirma · Shift+Enter quebra linha · Esc cancela · Tab confirma e cria subtópico.
    """

    def __init__(self, canvas, tid: str, original: str):
        super().__init__()
        self.canvas = canvas
        self.tid = tid
        self.original = original
        self.setZValue(Z_EDITOR)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.document().setDocumentMargin(1)

    def set_alignment(self, align: str) -> None:
        opt = QTextOption(self.document().defaultTextOption())
        flag = {"center": Qt.AlignmentFlag.AlignHCenter, "right": Qt.AlignmentFlag.AlignRight}.get(
            align, Qt.AlignmentFlag.AlignLeft)
        opt.setAlignment(flag)
        opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(opt)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        key = e.key()
        mods = e.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self.textCursor().insertText("\n")
            else:
                self.canvas.commit_edit()
            e.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.canvas.cancel_edit()
            e.accept()
            return
        if key == Qt.Key.Key_Tab:
            self.canvas.commit_edit()
            self.canvas.add_child()
            e.accept()
            return
        fmt = text_format_for(e)
        if fmt:         # ⌘B / ⌘I / ⌘⇧X durante a edição: formata o tópico sem sair da edição
            self.canvas.toggle_text_format(fmt)
            e.accept()
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e) -> None:
        super().focusOutEvent(e)
        # Trocar de janela/abrir menu não confirma a edição; clicar fora, sim.
        if e.reason() not in (Qt.FocusReason.ActiveWindowFocusReason, Qt.FocusReason.PopupFocusReason):
            self.canvas.schedule_commit_on_blur(self)

    def sceneEvent(self, e) -> bool:
        if e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key.Key_Tab:
            self.keyPressEvent(e)
            return True
        return super().sceneEvent(e)
