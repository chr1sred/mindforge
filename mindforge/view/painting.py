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

from mindforge.i18n import N_
from mindforge.themes import UNDERLINE_SHAPES, TopicStyle, underline_width

# ------------------------------------------------------------------- fontes
EMBEDDED_FAMILY = "Inter"
PREFERRED_FAMILIES = (EMBEDDED_FAMILY, "Helvetica Neue", "Segoe UI", "Noto Sans", "Ubuntu",
                      "DejaVu Sans", "Arial")
_FONTS_LOADED = [False]


def assets_dir() -> str:
    """Pasta assets/ (funciona no código-fonte e no app gerado pelo PyInstaller)."""
    import os
    import sys
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "assets")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "assets")


def ensure_fonts() -> None:
    """Registra a fonte Inter embutida (uma vez). Exige um QGuiApplication ativo."""
    if _FONTS_LOADED[0]:
        return
    import glob
    import os
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is None:
        return
    _FONTS_LOADED[0] = True
    for f in sorted(glob.glob(os.path.join(assets_dir(), "fonts", "*.otf"))):
        QFontDatabase.addApplicationFont(f)


@lru_cache(maxsize=1)
def default_family() -> str:
    """Fonte padrão: Inter (embutida); se faltar, uma fonte comum do sistema."""
    ensure_fonts()
    available = set(QFontDatabase.families())
    for fam in PREFERRED_FAMILIES:
        if fam in available:
            return fam
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


@lru_cache(maxsize=512)
def font_available(family: str) -> bool:
    ensure_fonts()
    return family in set(QFontDatabase.families())


def _weight_enum(w: int) -> QFont.Weight:
    w = int(round(max(100, min(900, w)) / 100.0) * 100)
    for e in QFont.Weight:
        if int(e.value) == w:
            return e
    return QFont.Weight.Normal


def make_font(style: TopicStyle, family: Optional[str] = None) -> QFont:
    fam = style.family or family or default_family()
    f = QFont(fam)
    if fam != default_family():
        f.setFamilies([fam, default_family()])        # substituta se a fonte não existir
    # Tamanho em PIXELS (não pontos): idêntico na tela, no PNG, no SVG e no PDF,
    # independentemente do DPI do sistema (72 no macOS, 96 no Windows).
    f.setPixelSize(max(6, round(style.font_size)))
    f.setWeight(_weight_enum(style.weight))
    f.setItalic(style.italic)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def apply_case(text: str, case: str) -> str:
    if case == "upper":
        return text.upper()
    if case == "lower":
        return text.lower()
    if case == "title":
        return "\n".join(" ".join(w[:1].upper() + w[1:] for w in ln.split(" ")) for ln in text.split("\n"))
    return text


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
    align: str = "center"
    side: str = "right"
    collapsed_count: int = 0
    branch: str = "#8A8F98"          # cor do ramo a que o tópico pertence
    has_children: bool = False       # mostra o botão de recolher (⊖) ao passar o mouse
    level: str = "sub"
    inner_x: float = 10.0            # recuo horizontal real (padding + extras da forma)

    @property
    def align_left(self) -> bool:
        return self.align == "left"


MARKER_GAP = 4.0
NOTE_W = 11.0


@lru_cache(maxsize=20000)
def _measure(text: str, family: str, px: float, weight: int, italic: bool,
             max_w: float) -> tuple[tuple[str, ...], tuple[float, ...], float, float, float, float]:
    st = TopicStyle(font_size=px, weight=weight, italic=italic, family=family)
    fm = QFontMetricsF(make_font(st, family))
    lines = wrap_text(fm, text, max_w)
    widths = tuple(fm.horizontalAdvance(ln) for ln in lines)
    tw = max(widths + (0.0,))
    lh = fm.lineSpacing()
    return tuple(lines), widths, tw, lh * len(lines), lh, fm.ascent()


def build_visual(text: str, style: TopicStyle, markers: list[str], has_note: bool,
                 family: Optional[str] = None) -> TopicVisual:
    fam = style.family or family or default_family()
    shown = apply_case(text, style.text_case)
    icon = max(16.0, round(style.font_size * 1.15))
    mk_w = len(markers) * (icon + MARKER_GAP) if markers else 0.0
    note_w = (NOTE_W + 7) if has_note else 0.0
    pad_x, pad_y = style.pad_x, style.pad_y
    shape = style.shape
    max_w = style.max_text_width
    if style.fixed_width:
        max_w = max(20.0, style.fixed_width - 2 * pad_x - mk_w - note_w)
    lines, _widths, tw, th, lh, asc = _measure(shown, fam, style.font_size, style.weight,
                                               style.italic, max_w)
    tw = max(tw, 10.0)
    if style.fixed_width:
        tw = max(tw, max_w)
    content_w = mk_w + tw + note_w
    content_h = max(th, icon if (markers or has_note) else 0.0)
    if shape == "capsula":
        pad_x += (content_h + 2 * pad_y) / 4
    elif shape == "hexagono":
        pad_x += (content_h + 2 * pad_y) / 2.6
    w = content_w + 2 * pad_x
    h = content_h + 2 * pad_y
    if shape == "elipse":
        w *= 1.22
        h *= 1.28
    elif shape == "losango":
        w = content_w * 1.7 + 2 * pad_x
        h = content_h * 2.2 + 2 * pad_y
    elif shape == "sublinhado_duplo":
        h += underline_width(style) * 2
    if style.fixed_width:
        w = max(w, style.fixed_width)
    # dimensões inteiras: linhas e caixas ficam alinhadas à grade de pixels
    w, h = float(math.ceil(max(w, 24.0))), float(math.ceil(max(h, 18.0)))
    if shape in UNDERLINE_SHAPES:
        # ponto de conexão no CENTRO do traço do sublinhado: a linha do ramo continua o traço
        ay = h - underline_width(style) / 2
    else:
        ay = h / 2
    return TopicVisual(style=style, font=make_font(style, fam), lines=list(lines), line_h=lh,
                       ascent=asc, text_w=tw, text_h=th, w=w, h=h, ay=ay, content_w=content_w,
                       content_h=content_h, icon=icon, markers=list(markers), has_note=has_note,
                       align=style.resolved_align, inner_x=pad_x)


# ------------------------------------------------------------------ formas
def shape_path(shape: str, rect: QRectF) -> Optional[QPainterPath]:
    p = QPainterPath()
    if shape == "retangulo":
        p.addRect(rect)
    elif shape == "arredondado":
        r = min(7.0, rect.height() / 3)
        p.addRoundedRect(rect, r, r)
    elif shape == "capsula":
        r = rect.height() / 2
        p.addRoundedRect(rect, r, r)
    elif shape == "elipse":
        p.addEllipse(rect)
    elif shape == "losango":
        c = rect.center()
        p.addPolygon(QPolygonF([QPointF(c.x(), rect.top()), QPointF(rect.right(), c.y()),
                                QPointF(c.x(), rect.bottom()), QPointF(rect.left(), c.y())]))
        p.closeSubpath()
    elif shape == "hexagono":
        k = min(rect.height() / 2, rect.width() / 4)
        c = rect.center()
        p.addPolygon(QPolygonF([QPointF(rect.left() + k, rect.top()), QPointF(rect.right() - k, rect.top()),
                                QPointF(rect.right(), c.y()), QPointF(rect.right() - k, rect.bottom()),
                                QPointF(rect.left() + k, rect.bottom()), QPointF(rect.left(), c.y())]))
        p.closeSubpath()
    else:
        return None
    return p


def pattern_pen(color: QColor, width: float, pattern: str, cap=Qt.PenCapStyle.RoundCap) -> QPen:
    pen = QPen(color, width, Qt.PenStyle.SolidLine, cap, Qt.PenJoinStyle.RoundJoin)
    if pattern == "tracejado":
        pen.setDashPattern([4.0, 2.6])
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    elif pattern == "pontilhado":
        pen.setDashPattern([0.01, 2.2])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def _content_origin(vis: TopicVisual) -> tuple[float, float]:
    """Canto superior esquerdo do bloco de conteúdo (marcadores + texto + nota)."""
    st = vis.style
    if st.shape in ("elipse", "losango") or vis.align == "center":
        cx = (vis.w - vis.content_w) / 2           # o bloco fica centralizado; as linhas se alinham dentro dele
    elif vis.align == "left":
        cx = vis.inner_x
    else:
        cx = vis.w - vis.inner_x - vis.content_w
    if st.shape in UNDERLINE_SHAPES or st.shape == "nenhuma":
        cy = st.pad_y
    else:
        cy = (vis.h - vis.content_h) / 2
    return cx, cy


def paint_topic(p: QPainter, vis: TopicVisual, text_as_paths: bool = False,
                hide_text: bool = False) -> None:
    st = vis.style
    rect = QRectF(0, 0, vis.w, vis.h)
    bw = st.border_width
    path = shape_path(st.shape, rect.adjusted(bw / 2, bw / 2, -bw / 2, -bw / 2))
    if path is not None:
        p.setBrush(QBrush(QColor(st.fill)) if st.fill else Qt.BrushStyle.NoBrush)
        if st.border and bw > 0 and st.border_style != "nenhum":
            p.setPen(pattern_pen(QColor(st.border), bw, st.border_style, Qt.PenCapStyle.SquareCap))
        else:
            p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
    elif st.shape in UNDERLINE_SHAPES and st.border_style != "nenhum":
        uw = underline_width(st)
        pen = pattern_pen(QColor(st.border or st.line_color), uw, st.border_style, Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        y = vis.h - uw / 2
        p.drawLine(QPointF(0, y), QPointF(vis.w, y))
        if st.shape == "sublinhado_duplo":
            y2 = y - uw * 2
            p.drawLine(QPointF(0, y2), QPointF(vis.w, y2))
    elif st.fill:
        p.fillRect(rect, QColor(st.fill))

    cx, cy = _content_origin(vis)
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
            if vis.align == "left":
                lx = tx
            elif vis.align == "right":
                lx = tx + vis.text_w - lw
            else:
                lx = tx + (vis.text_w - lw) / 2
            base = QPointF(lx, ty + i * vis.line_h + vis.ascent)
            if text_as_paths:
                tp = QPainterPath()
                tp.addText(base, vis.font, line)
                p.fillPath(tp, color)
            else:
                p.setFont(vis.font)
                p.setPen(color)
                p.drawText(base, line)
            if st.strike and line:
                # riscado desenhado como geometria (o SVG do Qt não exporta o riscado da fonte)
                t = max(1.0, fm.lineWidth())
                sy = base.y() - fm.strikeOutPos() - t / 2
                p.fillRect(QRectF(lx, sy, lw, t), color)
    if vis.has_note:
        nx = tx + vis.text_w + 7
        ny = cy + (vis.content_h - 13) / 2
        paint_note_icon(p, QRectF(nx, ny, NOTE_W, 13), QColor(st.text_color))


def text_rect(vis: TopicVisual) -> QRectF:
    """Área do texto dentro da caixa (usada para posicionar o editor)."""
    cx, cy = _content_origin(vis)
    mk_w = len(vis.markers) * (vis.icon + MARKER_GAP)
    return QRectF(cx + mk_w, cy + (vis.content_h - vis.text_h) / 2, vis.text_w, vis.text_h)


BADGE_R = 9.0          # círculo com o número (ramo recolhido)
TOGGLE_R = 7.0         # botão ⊖ (ramo aberto)
COUNT_OFFSET = 15.0    # distância do centro do número até a borda do tópico
TOGGLE_OFFSET = 11.0   # distância do centro do ⊖ até a borda (fica sobre a linha do ramo)


def _side_point(vis: TopicVisual, offset: float) -> tuple[QPointF, QPointF]:
    """(ponto na borda do tópico, centro do controle) para o lado em que os filhos crescem."""
    side = vis.side
    if side == "left":
        return QPointF(0, vis.ay), QPointF(-offset, vis.ay)
    if side == "down":
        return QPointF(vis.w / 2, vis.h), QPointF(vis.w / 2, vis.h + offset)
    if side == "up":
        return QPointF(vis.w / 2, 0), QPointF(vis.w / 2, -offset)
    return QPointF(vis.w, vis.ay), QPointF(vis.w + offset, vis.ay)


def badge_center(vis: TopicVisual) -> QPointF:
    """Centro do controle de recolher/expandir (número ou ⊖)."""
    return _side_point(vis, COUNT_OFFSET if vis.collapsed_count else TOGGLE_OFFSET)[1]


def badge_radius(vis: TopicVisual) -> float:
    return BADGE_R if vis.collapsed_count else TOGGLE_R


def _on_color(fill: QColor) -> QColor:
    """Branco sobre cores escuras; quase preto sobre cores claras (ramos em tema pastel)."""
    lum = 0.2126 * fill.redF() + 0.7152 * fill.greenF() + 0.0722 * fill.blueF()
    return QColor("#1F2328") if lum > 0.62 else QColor("#FFFFFF")


def paint_control(p: QPainter, vis: TopicVisual, background: str, state: str = "normal") -> None:
    """Círculo do controle de recolher/expandir: ⊖ (ramo aberto) ou número (ramo recolhido).

    state: "normal" (contorno), "hover" (preenchido e 10% maior) ou "pressed" (preenchido mais escuro).
    """
    collapsed = bool(vis.collapsed_count)
    c = badge_center(vis)
    r = badge_radius(vis)
    color = QColor(vis.style.line_color)
    filled = state in ("hover", "pressed")
    if filled:
        r *= 1.1
        fill = color.darker(118) if state == "pressed" else color
        ink = _on_color(fill)
        p.setPen(QPen(fill, 1.3))
        p.setBrush(fill)
    else:
        ink = color
        p.setPen(QPen(color, 1.3))
        p.setBrush(QColor(background))
    p.drawEllipse(c, r, r)
    if collapsed:
        n = vis.collapsed_count
        label = "99+" if n > 99 else str(n)
        f = QFont(default_family())
        f.setPixelSize(10 if len(label) < 3 else 8)
        if filled:
            f.setBold(True)
        p.setFont(f)
        p.setPen(ink)
        p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), int(Qt.AlignmentFlag.AlignCenter), label)
    else:
        half = 3.5 * (1.1 if filled else 1.0)
        p.setPen(QPen(ink, 1.5 if filled else 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(c.x() - half, c.y()), QPointF(c.x() + half, c.y()))


def paint_badge(p: QPainter, vis: TopicVisual, background: str) -> None:
    """Ramo recolhido: traço curto + círculo com a quantidade de tópicos escondidos (sai na exportação)."""
    edge, c = _side_point(vis, COUNT_OFFSET)
    color = QColor(vis.style.line_color)
    d = c - edge
    L = math.hypot(d.x(), d.y()) or 1.0
    p.setPen(QPen(color, max(1.2, vis.style.line_width), Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    p.drawLine(edge, c - d * (BADGE_R / L))
    paint_control(p, vis, background, "normal")


# --------------------------------------------------------------- marcadores
MARKER_LABELS = {
    "prio1": N_("Prioridade 1"), "prio2": N_("Prioridade 2"), "prio3": N_("Prioridade 3"),
    "feito": N_("Concluído"), "estrela": N_("Estrela"), "bandeira": N_("Bandeira"),
    "pergunta": N_("Dúvida"), "alerta": N_("Atenção"),
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
