"""Desenho dos ramos (linhas de um pai para os filhos).

Cada grupo (pai → filhos) vira UM conjunto de traços:
* com todos os filhos na mesma cor, um único caminho — nada é desenhado duas
  vezes, então não há bordas "engrossadas" nem serrilhado por sobreposição;
* com cores diferentes (ramo colorido), o tronco é dividido em trechos que não
  se sobrepõem, cada um com a cor do filho a que leva.

A geometria é feita num referencial local (u = para fora do pai, v = ao longo
do tronco) e depois girada/espelhada para o sentido real do grupo, então os
mesmos 7 estilos servem para mapas horizontais e verticais.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath, QPolygonF, QTransform

Point = tuple[float, float]


@dataclass
class Stroke:
    path: QPainterPath
    color: str


@dataclass
class Mark:
    path: QPainterPath
    color: str
    filled: bool


@dataclass
class BranchDrawing:
    strokes: list[Stroke] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)


def _transform(direction: str, origin: Point) -> QTransform:
    ox, oy = origin
    if direction == "left":
        return QTransform(-1, 0, 0, 1, ox, oy)
    if direction == "down":
        return QTransform(0, 1, 1, 0, ox, oy)
    if direction == "up":
        return QTransform(0, -1, 1, 0, ox, oy)
    return QTransform(1, 0, 0, 1, ox, oy)


def _to_local(direction: str, origin: Point, p: Point) -> Point:
    dx, dy = p[0] - origin[0], p[1] - origin[1]
    if direction == "left":
        return (-dx, dy)
    if direction == "down":
        return (dy, dx)
    if direction == "up":
        return (-dy, dx)
    return (dx, dy)


# ------------------------------------------------------------------- estilos
def _segments(style: str, kids: list[tuple[str, float, float]], radius: float):
    """Gera os trechos em coordenadas locais.

    Retorna (trechos, tangentes) onde trechos = [(id_do_filho | None, QPainterPath)]
    e tangentes = {id: (du, dv)} no fim de cada filho (para as pontas).
    """
    out: list[tuple[Optional[str], QPainterPath]] = []
    tangent: dict[str, Point] = {}
    G = min(u for _, u, _ in kids)
    uk = max(6.0, min(G * 0.42, 26.0))         # posição do tronco
    p = max(3.0, min(G * 0.16, 12.0))          # comprimento do "toco" nos estilos de leque
    ups = sorted([k for k in kids if k[2] < -0.5], key=lambda k: -k[2])      # do mais próximo ao mais distante
    downs = sorted([k for k in kids if k[2] > 0.5], key=lambda k: k[2])
    mids = [k for k in kids if -0.5 <= k[2] <= 0.5]

    def line(a: Point, b: Point) -> QPainterPath:
        pa = QPainterPath(QPointF(*a))
        pa.lineTo(QPointF(*b))
        return pa

    for cid, _, _ in kids:
        tangent[cid] = (1.0, 0.0)

    if style in ("colchete_curvo", "colchete_reto", "arco"):
        has_trunk = bool(ups or downs)
        stub_end = uk if has_trunk else 0.0
        if has_trunk:
            out.append((None, line((0, 0), (uk, 0))))
        for cid, u, _ in mids:
            out.append((cid, line((stub_end, 0), (u, 0))))
        vs = [v for _, _, v in kids] + [0.0]
        vtop, vbot = min(vs), max(vs)
        half = (vbot - vtop) / 2 or 1.0
        vmid = (vtop + vbot) / 2
        bulge = min(G * 0.28, 14.0, half * 0.7)

        def arc_u(v: float) -> float:
            t = (v - vmid) / half
            return uk + bulge * t * t

        for seq in (ups, downs):
            prev = 0.0
            for idx, (cid, u, v) in enumerate(seq):
                outer = idx == len(seq) - 1
                path = QPainterPath()
                if style == "arco":
                    n = max(6, int(abs(v - prev) / 6))
                    path.moveTo(QPointF(arc_u(prev), prev))
                    for i in range(1, n + 1):
                        vv = prev + (v - prev) * i / n
                        path.lineTo(QPointF(arc_u(vv), vv))
                    lead = QPainterPath(QPointF(arc_u(v), v))
                    lead.lineTo(QPointF(u, v))
                    out.append((cid, path))
                    out.append((cid, lead))
                else:
                    sgn = 1.0 if v > prev else -1.0
                    r = radius if (style == "colchete_curvo" and outer) else 0.0
                    r = min(r, abs(v - prev), max(0.0, u - uk))
                    path.moveTo(QPointF(uk, prev))
                    if r > 0.5:
                        path.lineTo(QPointF(uk, v - sgn * r))
                        path.quadTo(QPointF(uk, v), QPointF(uk + r, v))
                        path.lineTo(QPointF(u, v))
                        out.append((cid, path))
                    else:
                        path.lineTo(QPointF(uk, v))
                        out.append((cid, path))
                        out.append((cid, line((uk, v), (u, v))))
                prev = v
        return out, tangent

    # estilos que partem de um ponto (leques e chave)
    if kids:
        out.append((None, line((0, 0), (p, 0))))
    for cid, u, v in kids:
        if abs(v) <= 0.5:
            out.append((cid, line((p, 0), (u, 0))))
            continue
        path = QPainterPath(QPointF(p, 0))
        if style == "chave":
            mx = p + (u - p) * 0.5
            path.cubicTo(QPointF(mx, 0), QPointF(mx, v), QPointF(u, v))
        elif style == "leque_reto":
            path.lineTo(QPointF(u, v))
            L = math.hypot(u - p, v) or 1.0
            tangent[cid] = ((u - p) / L, v / L)
        elif style == "diagonal":
            L = min((u - p) * 0.4, 18.0)
            path.lineTo(QPointF(u - L, v))
            path.lineTo(QPointF(u, v))
        else:  # leque_curvo
            m = p + (u - p) * 0.55
            path.cubicTo(QPointF(p + (m - p) * 0.12, v * 0.72), QPointF(m - (m - p) * 0.35, v), QPointF(m, v))
            path.lineTo(QPointF(u, v))
        out.append((cid, path))
    return out, tangent


def _indent_segments(origin: Point, kids: list[tuple[str, Point]], radius: float):
    """Lista indentada: tronco vertical a partir do pai e ramos horizontais."""
    ox, oy = origin
    out: list[tuple[Optional[str], QPainterPath]] = []
    tangent: dict[str, Point] = {}
    for sgn in (1.0, -1.0):
        seq = sorted([k for k in kids if (k[1][1] - oy) * sgn > 0], key=lambda k: abs(k[1][1] - oy))
        prev = oy
        for idx, (cid, (x, y)) in enumerate(seq):
            outer = idx == len(seq) - 1
            path = QPainterPath(QPointF(ox, prev))
            r = min(radius, abs(y - prev), abs(x - ox)) if outer else 0.0
            if r > 0.5:
                path.lineTo(QPointF(ox, y - sgn * r))
                path.quadTo(QPointF(ox, y), QPointF(ox + math.copysign(r, x - ox), y))
                path.lineTo(QPointF(x, y))
                out.append((cid, path))
            else:
                path.lineTo(QPointF(ox, y))
                out.append((cid, path))
                lead = QPainterPath(QPointF(ox, y))
                lead.lineTo(QPointF(x, y))
                out.append((cid, lead))
            tangent[cid] = (1.0 if x >= ox else -1.0, 0.0)
            prev = y
    return out, tangent


# ------------------------------------------------------------------- pontas
def end_mark(kind: str, tip: QPointF, d: Point, width: float) -> Optional[tuple[QPainterPath, bool]]:
    """Ponta do ramo junto ao filho. ``d`` = direção (unitária) da linha chegando."""
    if kind in (None, "", "nenhum"):
        return None
    dx, dy = d
    nx, ny = -dy, dx
    s = 3.5 + 2.2 * width

    def pt(a: float, b: float) -> QPointF:      # a ao longo da linha (para trás), b na perpendicular
        return QPointF(tip.x() - dx * a + nx * b, tip.y() - dy * a + ny * b)

    path = QPainterPath()
    if kind == "circulo":
        path.addEllipse(pt(s * 0.55, 0), s * 0.55, s * 0.55)
        return path, True
    if kind == "seta":
        path.addPolygon(QPolygonF([tip, pt(s * 1.5, s * 0.62), pt(s * 1.5, -s * 0.62)]))
        path.closeSubpath()
        return path, True
    if kind == "seta_invertida":
        path.addPolygon(QPolygonF([pt(s * 1.5, 0), pt(0, s * 0.62), pt(0, -s * 0.62)]))
        path.closeSubpath()
        return path, True
    if kind == "quadrado":
        a = s * 0.5
        path.addPolygon(QPolygonF([pt(0, a), pt(0, -a), pt(2 * a, -a), pt(2 * a, a)]))
        path.closeSubpath()
        return path, True
    if kind == "losango":
        a = s * 0.75
        path.addPolygon(QPolygonF([tip, pt(a, a * 0.75), pt(2 * a, 0), pt(a, -a * 0.75)]))
        path.closeSubpath()
        return path, True
    if kind == "seta_aberta":
        path.moveTo(pt(s * 1.5, s * 0.8))
        path.lineTo(tip)
        path.lineTo(pt(s * 1.5, -s * 0.8))
        return path, False
    if kind == "barra":
        path.moveTo(pt(0, s * 0.85))
        path.lineTo(pt(0, -s * 0.85))
        return path, False
    return None


# ------------------------------------------------------------------- API
def draw_group(style: str, direction: str, origin: Point, kids: list[tuple[str, Point]],
               colors: dict[str, str], stub_color: Optional[str], line_end: str, width: float,
               radius: float = 10.0) -> BranchDrawing:
    """Monta o desenho de um grupo. ``colors`` = cor da linha até cada filho."""
    drawing = BranchDrawing()
    if not kids:
        return drawing
    if style == "indent":
        segs, tangents = _indent_segments(origin, kids, 6.0)
        tf = QTransform()
        tangents_g = tangents
        ends = {cid: QPointF(*p) for cid, p in kids}
    else:
        local = []
        for cid, p in kids:
            u, v = _to_local(direction, origin, p)
            local.append((cid, max(u, 1.0), v))
        segs, tangents = _segments(style, local, radius)
        tf = _transform(direction, origin)
        ends = {cid: QPointF(*p) for cid, p in kids}
        o = tf.map(QPointF(0, 0))
        tangents_g = {}
        for cid, (du, dv) in tangents.items():
            q = tf.map(QPointF(du, dv)) - o
            L = math.hypot(q.x(), q.y()) or 1.0
            tangents_g[cid] = (q.x() / L, q.y() / L)

    # cor do "toco" (trecho antes de abrir para os filhos): a do filho mais próximo do eixo
    if stub_color is None:
        nearest = min(kids, key=lambda k: abs(_to_local(direction, origin, k[1])[1]) if style != "indent" else 0)
        stub_color = colors.get(nearest[0], "#8A8F98")
    unique = set(colors.get(cid, stub_color) for cid, _ in kids) | {stub_color}
    if len(unique) == 1:
        merged = QPainterPath()
        for _, path in segs:
            merged.addPath(tf.map(path))
        drawing.strokes.append(Stroke(merged, stub_color))
    else:
        by_color: dict[str, QPainterPath] = {}
        for cid, path in segs:
            col = stub_color if cid is None else colors.get(cid, stub_color)
            by_color.setdefault(col, QPainterPath()).addPath(tf.map(path))
        for col, path in by_color.items():
            drawing.strokes.append(Stroke(path, col))
    for cid, _ in kids:
        m = end_mark(line_end, ends[cid], tangents_g.get(cid, (1.0, 0.0)), width)
        if m is not None:
            drawing.marks.append(Mark(m[0], colors.get(cid, stub_color), m[1]))
    return drawing


def sample_group(style: str, w: float = 36, h: float = 22) -> tuple[str, Point, list[tuple[str, Point]]]:
    """Grupo de exemplo (ícones do painel)."""
    return ("right", (2.0, h / 2), [("a", (w - 2, 3.0)), ("b", (w - 2, h / 2)), ("c", (w - 2, h - 3.0))])
