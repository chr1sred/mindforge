"""Primitivas de desenho compartilhadas (tela, miniaturas e exportação).

Tudo é desenhado com QPainter (sem imagens externas), então marcadores,
ícones e linhas saem vetoriais em SVG e PDF.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF,
)

from mindforge.themes import TopicStyle

# ------------------------------------------------------------------- fontes
PREFERRED_FAMILIES = ("Helvetica Neue", "Segoe UI", "Inter", "Noto Sans", "Ubuntu",
                      "DejaVu Sans", "Arial")


@lru_cache(maxsize=1)
def default_family() -> str:
    """Fonte com nome portável (importante para SVG abrir igual em outro computador)."""
    available = set(QFontDatabase.families())
    for fam in PREFERRED_FAMILIES:
        if fam in available:
            return fam
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


def make_font(style: TopicStyle, family: Optional[str] = None) -> QFont:
    f = QFont(family or default_family())
    # Tamanho em PIXELS (não pontos): idêntico na tela, no PNG, no SVG e no PDF,
    # independentemente do DPI do sistema (72 no macOS, 96 no Windows).
    f.setPixelSize(max(6, round(style.font_size)))
    f.setBold(style.bold)
    f.setItalic(style.italic)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


# ----------------------------------------------------------------- medidas
def wrap_text(fm: QFontMetricsF, text: str, max_width: float) -> list[str]:
    """Quebra de linha própria (mesma na tela e na exportação)."""
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if fm.horizontalAdvance(candidate) <= max_width:
                line = candidate
                continue
            if line:
                out.append(line)
                line = ""
            # palavra maior que a largura: quebra por caracteres
            while fm.horizontalAdvance(word) > max_width and len(word) > 1:
                cut = len(word)
                while cut > 1 and fm.horizontalAdvance(word[:cut]) > max_width:
                    cut -= 1
                out.append(word[:cut])
                word = word[cut:]
            line = word
        out.append(line)
    return out or [""]


@dataclass
class TopicVisual:
    style: TopicStyle
    font: QFont
    lines: list[str]
    line_h: float
    ascent: float
    text_w: float
    text_h: float
    w: float
    h: float
    ay: float
    content_w: float
    content_h: float
    icon: float
    markers: list[str] = field(default_factory=list)
    has_note: bool = False
    align_left: bool = False
    side: str = "right"
    collapsed_count: int = 0


MARKER_GAP = 4.0
NOTE_W = 11.0


@lru_cache(maxsize=20000)
def _measure(text: str, family: str, px: float, bold: bool, italic: bool,
             max_w: float) -> tuple[tuple[str, ...], float, float, float, float]:
    st = TopicStyle(font_size=px, bold=bold, italic=italic)
    fm = QFontMetricsF(make_font(st, family))
    lines = wrap_text(fm, text, max_w)
    tw = max([fm.horizontalAdvance(ln) for ln in lines] + [0.0])
    lh = fm.lineSpacing()
    return tuple(lines), tw, lh * len(lines), lh, fm.ascent()


def build_visual(text: str, style: TopicStyle, markers: list[str], has_note: bool,
                 family: Optional[str] = None) -> TopicVisual:
    fam = family or default_family()
    lines, tw, th, lh, asc = _measure(text, fam, style.font_size, style.bold, style.italic,
                                      style.max_text_width)
    tw = max(tw, 10.0)
    icon = max(16.0, round(style.font_size * 1.15))
    mk_w = len(markers) * (icon + MARKER_GAP) if markers else 0.0
    note_w = (NOTE_W + 7) if has_note else 0.0
    content_w = mk_w + tw + note_w
    content_h = max(th, icon if (markers or has_note) else 0.0)
    pad_x, pad_y = style.pad_x, style.pad_y
    shape = style.shape
    if shape == "capsula":
        pad_x += (content_h + 2 * pad_y) / 4
    w = content_w + 2 * pad_x
    h = content_h + 2 * pad_y
    if shape == "elipse":
        w *= 1.22
        h *= 1.28
    w, h = max(w, 24.0), max(h, 18.0)
    # ponto de conexão no CENTRO do traço do sublinhado: a linha do ramo
    # emenda sem "degrau" (era a causa do aspecto serrilhado nas junções)
    ay = h - max(1.0, style.border_width or style.line_width) / 2 if shape == "sublinhado" else h / 2
    return TopicVisual(style=style, font=make_font(style, fam), lines=list(lines), line_h=lh,
                       ascent=asc, text_w=tw, text_h=th, w=w, h=h, ay=ay, content_w=content_w,
                       content_h=content_h, icon=icon, markers=list(markers), has_note=has_note,
                       align_left=shape in ("sublinhado", "nenhuma"))


# ------------------------------------------------------------------ formas
def shape_path(shape: str, rect: QRectF) -> Optional[QPainterPath]:
    p = QPainterPath()
    if shape == "retangulo":
        p.addRect(rect)
    elif shape == "arredondado":
        r = min(8.0, rect.height() / 3)
        p.addRoundedRect(rect, r, r)
    elif shape == "capsula":
        r = rect.height() / 2
        p.addRoundedRect(rect, r, r)
    elif shape == "elipse":
        p.addEllipse(rect)
    else:
        return None
    return p


def paint_topic(p: QPainter, vis: TopicVisual, text_as_paths: bool = False,
                hide_text: bool = False) -> None:
    st = vis.style
    rect = QRectF(0, 0, vis.w, vis.h)
    path = shape_path(st.shape, rect.adjusted(st.border_width / 2, st.border_width / 2,
                                              -st.border_width / 2, -st.border_width / 2))
    if path is not None:
        p.setBrush(QBrush(QColor(st.fill)) if st.fill else Qt.BrushStyle.NoBrush)
        if st.border and st.border_width > 0:
            p.setPen(QPen(QColor(st.border), st.border_width))
        else:
            p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
    elif st.shape == "sublinhado":
        bw = max(1.0, st.border_width or st.line_width)
        color = QColor(st.border or st.line_color)
        p.setPen(QPen(color, bw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        y = vis.h - bw / 2
        p.drawLine(QPointF(0, y), QPointF(vis.w, y))

    # conteúdo centralizado
    cx = (vis.w - vis.content_w) / 2
    cy = (vis.h - vis.content_h) / 2
    if vis.align_left:
        cx = st.pad_x
        cy = st.pad_y
    x = cx
    for mk in vis.markers:
        paint_marker(p, mk, QRectF(x, cy + (vis.content_h - vis.icon) / 2, vis.icon, vis.icon))
        x += vis.icon + MARKER_GAP
    tx = x
    ty = cy + (vis.content_h - vis.text_h) / 2
    if not hide_text:
        color = QColor(st.text_color)
        fm = QFontMetricsF(vis.font)
        for i, line in enumerate(vis.lines):
            lw = fm.horizontalAdvance(line)
            lx = tx if vis.align_left else tx + (vis.text_w - lw) / 2
            base = QPointF(lx, ty + i * vis.line_h + vis.ascent)
            if text_as_paths:
                tp = QPainterPath()
                tp.addText(base, vis.font, line)
                p.fillPath(tp, color)
            else:
                p.setFont(vis.font)
                p.setPen(color)
                p.drawText(base, line)
    if vis.has_note:
        nx = tx + vis.text_w + 7
        ny = cy + (vis.content_h - 13) / 2
        paint_note_icon(p, QRectF(nx, ny, NOTE_W, 13), QColor(st.text_color))


def text_rect(vis: TopicVisual) -> QRectF:
    """Área do texto dentro da caixa (usada para posicionar o editor)."""
    cx = (vis.w - vis.content_w) / 2
    cy = (vis.h - vis.content_h) / 2
    if vis.align_left:
        cx, cy = vis.style.pad_x, vis.style.pad_y
    mk_w = len(vis.markers) * (vis.icon + MARKER_GAP)
    return QRectF(cx + mk_w, cy + (vis.content_h - vis.text_h) / 2, vis.text_w, vis.text_h)


def badge_center(vis: TopicVisual) -> QPointF:
    side = vis.side
    if side == "left":
        return QPointF(-11, vis.ay)
    if side == "down":
        return QPointF(vis.w / 2, vis.h + 11)
    if side == "up":
        return QPointF(vis.w / 2, -11)
    return QPointF(vis.w + 11, vis.ay)


BADGE_R = 9.0


def paint_badge(p: QPainter, vis: TopicVisual, background: str) -> None:
    c = badge_center(vis)
    p.setPen(QPen(QColor(vis.style.line_color), 1.4))
    p.setBrush(QColor(background))
    p.drawEllipse(c, BADGE_R, BADGE_R)
    n = vis.collapsed_count
    label = "99+" if n > 99 else str(n)
    f = QFont(default_family())
    f.setPixelSize(9 if len(label) < 3 else 7)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(vis.style.line_color))
    p.drawText(QRectF(c.x() - BADGE_R, c.y() - BADGE_R, 2 * BADGE_R, 2 * BADGE_R),
               int(Qt.AlignmentFlag.AlignCenter), label)


# --------------------------------------------------------------- marcadores
MARKER_LABELS = {
    "prio1": "Prioridade 1", "prio2": "Prioridade 2", "prio3": "Prioridade 3",
    "feito": "Concluído", "estrela": "Estrela", "bandeira": "Bandeira",
    "pergunta": "Dúvida", "alerta": "Atenção",
}


def _circle_text(p: QPainter, r: QRectF, fill: str, text: str) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(fill))
    p.drawEllipse(r)
    f = QFont(default_family())
    f.setPixelSize(max(7, round(r.height() * 0.62)))
    f.setBold(True)
    path = QPainterPath()
    fm = QFontMetricsF(f)
    tw = fm.horizontalAdvance(text)
    path.addText(QPointF(r.center().x() - tw / 2, r.center().y() + fm.ascent() * 0.36), f, text)
    p.fillPath(path, QColor("#FFFFFF"))


def paint_marker(p: QPainter, key: str, r: QRectF) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if key == "prio1":
        _circle_text(p, r, "#E5534B", "1")
    elif key == "prio2":
        _circle_text(p, r, "#F0883E", "2")
    elif key == "prio3":
        _circle_text(p, r, "#2F80ED", "3")
    elif key == "pergunta":
        _circle_text(p, r, "#8250DF", "?")
    elif key == "feito":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2DA44E"))
        p.drawEllipse(r)
        pen = QPen(QColor("#FFFFFF"), max(1.6, r.width() * 0.13), Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        w, h = r.width(), r.height()
        path = QPainterPath(QPointF(r.x() + w * 0.27, r.y() + h * 0.53))
        path.lineTo(QPointF(r.x() + w * 0.44, r.y() + h * 0.69))
        path.lineTo(QPointF(r.x() + w * 0.74, r.y() + h * 0.34))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    elif key == "estrela":
        c = r.center()
        R, ri = r.width() / 2, r.width() / 2 * 0.45
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rad = R if i % 2 == 0 else ri
            pts.append(QPointF(c.x() + rad * math.cos(ang), c.y() + rad * math.sin(ang) + R * 0.06))
        p.setPen(QPen(QColor("#B7791F"), 0.8))
        p.setBrush(QColor("#F6C343"))
        p.drawPolygon(QPolygonF(pts))
    elif key == "bandeira":
        w, h = r.width(), r.height()
        p.setPen(QPen(QColor("#57606A"), max(1.2, w * 0.09), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(r.x() + w * 0.24, r.y() + h * 0.1), QPointF(r.x() + w * 0.24, r.y() + h * 0.92))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E5534B"))
        p.drawPolygon(QPolygonF([QPointF(r.x() + w * 0.28, r.y() + h * 0.12),
                                 QPointF(r.x() + w * 0.86, r.y() + h * 0.3),
                                 QPointF(r.x() + w * 0.28, r.y() + h * 0.5)]))
    elif key == "alerta":
        w, h = r.width(), r.height()
        tri = QPolygonF([QPointF(r.x() + w / 2, r.y() + h * 0.06), QPointF(r.right(), r.bottom() - h * 0.08),
                         QPointF(r.x(), r.bottom() - h * 0.08)])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F0A020"))
        p.drawPolygon(tri)
        f = QFont(default_family())
        f.setPixelSize(max(7, round(h * 0.62)))
        f.setBold(True)
        path = QPainterPath()
        fm = QFontMetricsF(f)
        path.addText(QPointF(r.center().x() - fm.horizontalAdvance("!") / 2, r.bottom() - h * 0.17), f, "!")
        p.fillPath(path, QColor("#FFFFFF"))
    p.restore()


def paint_note_icon(p: QPainter, r: QRectF, color: QColor) -> None:
    p.save()
    c = QColor(color)
    c.setAlphaF(0.75)
    p.setPen(QPen(c, 1.1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(r, 1.8, 1.8)
    for i in range(3):
        y = r.y() + 3.5 + i * 3
        p.drawLine(QPointF(r.x() + 2.5, y), QPointF(r.right() - 2.5, y))
    p.restore()


# --------------------------------------------------------------- conectores
def _rounded_polyline(points: list[tuple[float, float]], radius: float) -> QPainterPath:
    pts = [QPointF(x, y) for x, y in points]
    # remove pontos repetidos
    clean = [pts[0]]
    for q in pts[1:]:
        if (q - clean[-1]).manhattanLength() > 0.01:
            clean.append(q)
    path = QPainterPath(clean[0])
    if len(clean) == 1:
        return path
    for i in range(1, len(clean) - 1):
        a, b, c = clean[i - 1], clean[i], clean[i + 1]
        v1, v2 = b - a, c - b
        l1 = math.hypot(v1.x(), v1.y())
        l2 = math.hypot(v2.x(), v2.y())
        r = min(radius, l1 / 2, l2 / 2)
        if r < 0.5:
            path.lineTo(b)
            continue
        p1 = b - v1 * (r / l1)
        p2 = b + v2 * (r / l2)
        path.lineTo(p1)
        path.quadTo(b, p2)
    path.lineTo(clean[-1])
    return path


def connector_path(kind: str, points: list[tuple[float, float]]) -> QPainterPath:
    if kind == "curve_h":
        (x0, y0), (x1, y1) = points[0], points[-1]
        dx = (x1 - x0) * 0.5
        path = QPainterPath(QPointF(x0, y0))
        path.cubicTo(QPointF(x0 + dx, y0), QPointF(x1 - dx, y1), QPointF(x1, y1))
        return path
    if kind == "curve_v":
        (x0, y0), (x1, y1) = points[0], points[-1]
        dy = (y1 - y0) * 0.5
        path = QPainterPath(QPointF(x0, y0))
        path.cubicTo(QPointF(x0, y0 + dy), QPointF(x1, y1 - dy), QPointF(x1, y1))
        return path
    if kind == "elbow_h":
        (x0, y0), (x1, y1) = points[0], points[-1]
        dx = x1 - x0
        mx = x0 + math.copysign(min(20.0, abs(dx) / 2), dx)
        return _rounded_polyline([(x0, y0), (mx, y0), (mx, y1), (x1, y1)], 8)
    if kind == "elbow_v":
        (x0, y0), (x1, y1) = points[0], points[-1]
        my = y0 + (y1 - y0) / 2
        return _rounded_polyline([(x0, y0), (x0, my), (x1, my), (x1, y1)], 8)
    if kind == "poly":
        return _rounded_polyline(points, 6)
    if kind == "arrow_line":
        (x0, y0), (x1, y1) = points[0], points[-1]
        path = QPainterPath(QPointF(x0, y0))
        path.lineTo(QPointF(x1, y1))
        ang = math.atan2(y1 - y0, x1 - x0)
        for sgn in (1, -1):
            a = ang + math.pi - sgn * math.radians(28)
            path.moveTo(QPointF(x1, y1))
            path.lineTo(QPointF(x1 + 12 * math.cos(a), y1 + 12 * math.sin(a)))
        return path
    path = QPainterPath(QPointF(*points[0]))
    for x, y in points[1:]:
        path.lineTo(QPointF(x, y))
    return path
