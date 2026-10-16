"""Itens gráficos da cena: tópico, conector, relação e editor de texto."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QKeyEvent, QPainter, QPainterPath,
    QPainterPathStroker, QPen, QTextOption,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem, QStyleOptionGraphicsItem

from mindforge.view.painting import (
    BADGE_R, TopicVisual, badge_center, default_family, paint_badge, paint_topic,
)

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

    def mind_scene(self) -> "MindScene":
        return self.scene()  # type: ignore[return-value]

    # --------------------------------------------------------------- geometria
    def set_visual(self, vis: TopicVisual) -> None:
        self.prepareGeometryChange()
        self.vis = vis
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
            c = badge_center(self.vis)
            r = r.united(QRectF(c.x() - BADGE_R - 1, c.y() - BADGE_R - 1, 2 * BADGE_R + 2, 2 * BADGE_R + 2))
        return r

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addRect(self.box_rect())
        if self.vis and self.vis.collapsed_count:
            p.addEllipse(badge_center(self.vis), BADGE_R + 2, BADGE_R + 2)
        return p

    def badge_hit(self, pos: QPointF) -> bool:
        if not self.vis or not self.vis.collapsed_count:
            return False
        c = badge_center(self.vis)
        return math.hypot(pos.x() - c.x(), pos.y() - c.y()) <= BADGE_R + 3

    # ----------------------------------------------------------------- pintura
    def paint(self, p: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        if self.vis is None:
            return
        sc = self.mind_scene()
        export = sc.export_mode if sc else False
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        paint_topic(p, self.vis, text_as_paths=bool(sc and sc.text_as_paths), hide_text=self.editing)
        if self.vis.collapsed_count:
            paint_badge(p, self.vis, sc.background_color if sc else "#FFFFFF")
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
        self.update()

    def hoverLeaveEvent(self, e) -> None:
        self.hover = False
        self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.badge_hit(e.pos()):
            self.mind_scene().collapse_requested.emit(self.tid)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.mind_scene().edit_requested.emit(self.tid)
            e.accept()
            return
        super().mouseDoubleClickEvent(e)


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


class RelationItem(QGraphicsPathItem):
    def __init__(self, rid: str):
        super().__init__()
        self.rid = rid
        self.label = ""
        self.color = QColor("#7C8594")
        self._label_pos = QPointF()
        self._arrow = QPainterPath()
        self.setZValue(Z_RELATION)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_geometry(self, a: QRectF, b: QRectF, label: str, color: str) -> None:
        self.prepareGeometryChange()
        self.label = label
        self.color = QColor(color)
        ca, cb = a.center(), b.center()
        dist = math.hypot(cb.x() - ca.x(), cb.y() - ca.y()) or 1.0
        nx, ny = -(cb.y() - ca.y()) / dist, (cb.x() - ca.x()) / dist
        bend = min(120.0, dist * 0.3)
        c1 = QPointF(ca.x() + (cb.x() - ca.x()) * 0.25 + nx * bend, ca.y() + (cb.y() - ca.y()) * 0.25 + ny * bend)
        c2 = QPointF(ca.x() + (cb.x() - ca.x()) * 0.75 + nx * bend, ca.y() + (cb.y() - ca.y()) * 0.75 + ny * bend)
        p0 = _clip_to_rect(ca, c1, a)
        p1 = _clip_to_rect(cb, c2, b)
        path = QPainterPath(p0)
        path.cubicTo(c1, c2, p1)
        self.setPath(path)
        ang = math.atan2(p1.y() - c2.y(), p1.x() - c2.x())
        arrow = QPainterPath()
        arrow.moveTo(p1)
        for sgn in (1, -1):
            a2 = ang + math.pi - sgn * math.radians(25)
            arrow.lineTo(QPointF(p1.x() + 11 * math.cos(a2), p1.y() + 11 * math.sin(a2)))
        arrow.closeSubpath()
        self._arrow = arrow
        self._label_pos = path.pointAtPercent(0.5)

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

    def boundingRect(self) -> QRectF:
        return self.path().boundingRect().adjusted(-14, -14, 14, 14).united(self._label_rect())

    def shape(self) -> QPainterPath:
        s = QPainterPathStroker()
        s.setWidth(12)
        p = s.createStroke(self.path())
        r = self._label_rect()
        if not r.isNull():
            p.addRect(r)
        return p

    def visual_rect(self) -> QRectF:
        return self.path().boundingRect().united(self._arrow.boundingRect()).united(self._label_rect())

    def paint(self, p: QPainter, option, widget=None) -> None:
        sc = self.scene()
        export = getattr(sc, "export_mode", False)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(getattr(sc, "selection_color", "#2F80ED")) if (self.isSelected() and not export) else self.color
        pen = QPen(color, 2.0 if self.isSelected() and not export else 1.6, Qt.PenStyle.DashLine,
                   Qt.PenCapStyle.RoundCap)
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

    def mouseDoubleClickEvent(self, e) -> None:
        self.scene().relation_edit_requested.emit(self.rid)
        e.accept()


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
