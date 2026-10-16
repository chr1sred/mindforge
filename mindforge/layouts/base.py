"""Infraestrutura comum dos algoritmos de layout (sem Qt).

Um layout recebe a árvore de tópicos e o tamanho de cada caixa
(``Metric``) e devolve a posição (canto superior esquerdo) de cada
tópico visível, os conectores a desenhar e o lado para onde os filhos
crescem (usado para posicionar o indicador de ramo recolhido).

Os blocos de subárvore são calculados em coordenadas locais e depois
transladados — isso permite reaproveitar o mesmo algoritmo dentro de
layouts compostos (ex.: costelas da espinha de peixe).
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Optional

from mindforge.model.topic import Topic

Point = tuple[float, float]


@dataclass
class Metric:
    w: float
    h: float
    ay: float          # deslocamento vertical do ponto de conexão (h/2 ou h p/ sublinhado)


@dataclass
class Connector:
    key: str
    owner: str          # id do tópico cujo estilo (cor/espessura) a linha usa
    kind: str           # curve_h | curve_v | elbow_h | elbow_v | poly | line | arrow_line
    points: list[Point]
    width: float = 1.0  # multiplicador da espessura do traço


@dataclass
class BranchGroup:
    """Todas as linhas de um pai para os seus filhos (desenhadas juntas, tronco único).

    ``direction`` é o sentido em que os filhos estão (right | left | down | up);
    ``style`` é o estilo padrão do esqueleto ("indent" = lista indentada, fixo).
    """
    key: str
    parent: str
    direction: str
    origin: Point
    kids: list[tuple[str, Point]]
    style: str = "colchete_curvo"

    def translate(self, dx: float, dy: float) -> None:
        self.origin = (self.origin[0] + dx, self.origin[1] + dy)
        self.kids = [(k, (x + dx, y + dy)) for k, (x, y) in self.kids]


@dataclass
class LayoutResult:
    pos: dict[str, Point] = field(default_factory=dict)
    connectors: list[Connector] = field(default_factory=list)
    sides: dict[str, str] = field(default_factory=dict)   # right | left | down | up
    groups: list[BranchGroup] = field(default_factory=list)

    def translate(self, dx: float, dy: float) -> "LayoutResult":
        self.pos = {k: (x + dx, y + dy) for k, (x, y) in self.pos.items()}
        for c in self.connectors:
            c.points = [(x + dx, y + dy) for x, y in c.points]
        for g in self.groups:
            g.translate(dx, dy)
        return self

    def mirror_x(self, metrics: dict[str, "Metric"]) -> "LayoutResult":
        """Espelha horizontalmente (usado para inverter o sentido de um layout)."""
        flip = {"left": "right", "right": "left"}
        self.pos = {k: (-x - metrics[k].w, y) for k, (x, y) in self.pos.items()}
        for c in self.connectors:
            c.points = [(-x, y) for x, y in c.points]
        for g in self.groups:
            g.origin = (-g.origin[0], g.origin[1])
            g.kids = [(k, (-x, y)) for k, (x, y) in g.kids]
            g.direction = flip.get(g.direction, g.direction)
        self.sides = {k: flip.get(v, v) for k, v in self.sides.items()}
        return self

    def merge(self, other: "LayoutResult") -> None:
        self.pos.update(other.pos)
        self.connectors.extend(other.connectors)
        self.sides.update(other.sides)
        self.groups.extend(other.groups)

    def bbox(self, metrics: dict[str, Metric]) -> tuple[float, float, float, float]:
        xs0, ys0, xs1, ys1 = [], [], [], []
        for k, (x, y) in self.pos.items():
            m = metrics[k]
            xs0.append(x)
            ys0.append(y)
            xs1.append(x + m.w)
            ys1.append(y + m.h)
        pts = [p for c in self.connectors for p in c.points]
        for g in self.groups:
            pts.append(g.origin)
            pts.extend(p for _, p in g.kids)
        for x, y in pts:
            xs0.append(x)
            xs1.append(x)
            ys0.append(y)
            ys1.append(y)
        if not xs0:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs0), min(ys0), max(xs1), max(ys1))

    def rect(self, tid: str, metrics: dict[str, Metric]) -> tuple[float, float, float, float]:
        x, y = self.pos[tid]
        m = metrics[tid]
        return (x, y, m.w, m.h)


H_GAP = 44.0
V_GAP_MAIN = 18.0
V_GAP_SUB = 8.0

# Fator de espaçamento global ("Compactar mapa" usa < 1)
_SPACING = [1.0]


def sp(v: float) -> float:
    return v * _SPACING[0]


# Opções do mapa que alguns esqueletos usam (definidas pela cena antes de calcular)
OPTIONS: dict = {"fishbone_align": False}


@contextmanager
def layout_options(**kw) -> Iterator[None]:
    old = dict(OPTIONS)
    OPTIONS.update(kw)
    try:
        yield
    finally:
        OPTIONS.clear()
        OPTIONS.update(old)


@contextmanager
def spacing(factor: float) -> Iterator[None]:
    old = _SPACING[0]
    _SPACING[0] = factor
    try:
        yield
    finally:
        _SPACING[0] = old


def vgap_for(depth: int) -> float:
    return sp(V_GAP_MAIN if depth <= 1 else V_GAP_SUB)


# ---------------------------------------------------------------------------
# Subárvore horizontal (mapa lógico para a direita/esquerda)
# ---------------------------------------------------------------------------
def horizontal_subtree(t: Topic, M: dict[str, Metric], direction: str = "right",
                       style: str = "colchete_curvo", base_depth: int = 1,
                       hgap: Optional[float] = None) -> LayoutResult:
    """Layout de uma subárvore crescendo para a direita ou esquerda.

    Retorna coordenadas locais com o canto superior esquerdo de ``t`` em (0, 0).
    Implementação iterativa no cálculo das alturas (árvores profundas).
    """
    hgap = sp(H_GAP) if hgap is None else hgap
    heights: dict[str, float] = {}
    # pós-ordem iterativa para calcular a altura de cada bloco
    order: list[tuple[Topic, int]] = []
    stack = [(t, base_depth)]
    while stack:
        node, d = stack.pop()
        order.append((node, d))
        for c in node.visible_children():
            stack.append((c, d + 1))
    for node, d in reversed(order):
        kids = node.visible_children()
        m = M[node.id]
        if kids:
            gap = vgap_for(d + 1)
            kh = sum(heights[c.id] for c in kids) + gap * (len(kids) - 1)
            heights[node.id] = max(m.h, kh)
        else:
            heights[node.id] = m.h

    res = LayoutResult()
    sign = 1 if direction == "right" else -1
    # (nó, x de ancoragem, topo do bloco, profundidade)
    # para direita x = borda esquerda; para esquerda x = borda direita
    work = [(t, 0.0, 0.0, base_depth)]
    while work:
        node, ax, ytop, d = work.pop()
        m = M[node.id]
        bh = heights[node.id]
        ny = ytop + bh / 2 - m.h / 2
        nx = ax if sign > 0 else ax - m.w
        res.pos[node.id] = (nx, ny)
        kids = node.visible_children()
        res.sides[node.id] = direction
        if not kids:
            continue
        gap = vgap_for(d + 1)
        kh = sum(heights[c.id] for c in kids) + gap * (len(kids) - 1)
        cy = ytop + (bh - kh) / 2
        child_ax = (nx + m.w + hgap) if sign > 0 else (nx - hgap)
        p0 = ((nx + m.w) if sign > 0 else nx, ny + m.ay)
        group = BranchGroup(f"g:{node.id}", node.id, direction, p0, [], style)
        for c in kids:
            cm = M[c.id]
            ch = heights[c.id]
            cny = cy + ch / 2 - cm.h / 2
            group.kids.append((c.id, (child_ax, cny + cm.ay)))
            work.append((c, child_ax, cy, d + 1))
            cy += ch + gap
        res.groups.append(group)
    x0, y0 = res.pos[t.id]
    return res.translate(-x0, -y0)


# ---------------------------------------------------------------------------
# Subárvore vertical (organograma)
# ---------------------------------------------------------------------------
def vertical_subtree(t: Topic, M: dict[str, Metric], direction: str = "down",
                     style: str = "colchete_reto", hgap: Optional[float] = None, vgap: Optional[float] = None) -> LayoutResult:
    hgap = sp(22.0) if hgap is None else hgap
    vgap = sp(46.0) if vgap is None else vgap
    widths: dict[str, float] = {}
    order: list[Topic] = []
    stack = [t]
    while stack:
        n = stack.pop()
        order.append(n)
        stack.extend(n.visible_children())
    for n in reversed(order):
        kids = n.visible_children()
        w = M[n.id].w
        if kids:
            kw = sum(widths[c.id] for c in kids) + hgap * (len(kids) - 1)
            w = max(w, kw)
        widths[n.id] = w

    res = LayoutResult()
    sign = 1 if direction == "down" else -1
    work = [(t, 0.0, 0.0)]   # (nó, esquerda do bloco, y de ancoragem)
    while work:
        n, left, ay = work.pop()
        m = M[n.id]
        bw = widths[n.id]
        nx = left + bw / 2 - m.w / 2
        ny = ay if sign > 0 else ay - m.h
        res.pos[n.id] = (nx, ny)
        res.sides[n.id] = direction
        kids = n.visible_children()
        if not kids:
            continue
        kw = sum(widths[c.id] for c in kids) + hgap * (len(kids) - 1)
        cx = left + (bw - kw) / 2
        child_ay = (ny + m.h + vgap) if sign > 0 else (ny - vgap)
        p0 = (nx + m.w / 2, (ny + m.h) if sign > 0 else ny)
        group = BranchGroup(f"g:{n.id}", n.id, direction, p0, [], style)
        for c in kids:
            cm = M[c.id]
            cw = widths[c.id]
            cnx = cx + cw / 2 - cm.w / 2
            group.kids.append((c.id, (cnx + cm.w / 2, child_ay)))
            work.append((c, cx, child_ay))
            cx += cw + hgap
        res.groups.append(group)
    x0, y0 = res.pos[t.id]
    return res.translate(-x0, -y0)


# ---------------------------------------------------------------------------
# Lista indentada (árvore / linha do tempo)
# ---------------------------------------------------------------------------
INDENT = 26.0
LIST_GAP = 10.0


def indented_list(t: Topic, M: dict[str, Metric], include_root: bool = True,
                  indent: float = INDENT, gap: Optional[float] = None) -> tuple[LayoutResult, float, float]:
    """Lista indentada de cima para baixo. Retorna (resultado, largura, altura).

    Se ``include_root`` for False, apenas os descendentes de ``t`` são
    posicionados, começando em (0, 0); os conectores do primeiro nível
    ficam a cargo de quem chamou.
    """
    gap = sp(LIST_GAP) if gap is None else gap
    res = LayoutResult()
    y = 0.0
    maxx = 0.0
    seq = [(t, 0.0)] if include_root else [(c, 0.0) for c in t.visible_children()]
    # pré-ordem iterativa
    stack = list(reversed(seq))
    while stack:
        n, x = stack.pop()
        m = M[n.id]
        res.pos[n.id] = (x, y)
        res.sides[n.id] = "down"
        maxx = max(maxx, x + m.w)
        y += m.h + gap
        for c in reversed(n.visible_children()):
            stack.append((c, x + indent))
    # conectores pai → filhos (tronco vertical + ramo horizontal)
    _connect_indented(t, M, res, include_root, indent)
    height = max(0.0, y - gap)
    return res, maxx, height


def _connect_indented(t: Topic, M: dict[str, Metric], res: LayoutResult,
                      include_root: bool, indent: float) -> None:
    stack = [t] if include_root else list(t.visible_children())
    while stack:
        n = stack.pop()
        kids = n.visible_children()
        if not kids or n.id not in res.pos:
            stack.extend(kids)
            continue
        px, py = res.pos[n.id]
        pm = M[n.id]
        tx = px + min(indent / 2, pm.w / 2)
        group = BranchGroup(f"g:{n.id}", n.id, "down", (tx, py + pm.h), [], "indent")
        for c in kids:
            cx, cy = res.pos[c.id]
            group.kids.append((c.id, (cx, cy + M[c.id].ay)))
        res.groups.append(group)
        stack.extend(kids)


class Layout:
    key = ""
    label = ""
    floating_direction = "right"
    default_branch = "colchete_curvo"
    # Ajustes de estilo por nível que o esqueleto sugere (aplicados antes das escolhas do usuário)
    hints: dict = {}

    def compute(self, root: Topic, M: dict[str, Metric]) -> LayoutResult:
        raise NotImplementedError

    def compute_floating(self, top: Topic, M: dict[str, Metric]) -> LayoutResult:
        """Tópicos flutuantes usam um layout simples ancorado em ``top.pos``."""
        if self.floating_direction == "down":
            res = vertical_subtree(top, M)
        else:
            res = horizontal_subtree(top, M, "right", self.default_branch, base_depth=2)
        px, py = top.pos or (0.0, 0.0)
        return res.translate(px, py)


def center_on_root(res: LayoutResult, root: Topic, M: dict[str, Metric]) -> LayoutResult:
    x, y = res.pos[root.id]
    m = M[root.id]
    return res.translate(-(x + m.w / 2), -(y + m.h / 2))


def rects_overlap(a: tuple, b: tuple, tol: float = 0.5) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax + aw - tol > bx and bx + bw - tol > ax and
            ay + ah - tol > by and by + bh - tol > ay)


def find_overlaps(res: LayoutResult, M: dict[str, Metric]) -> list[tuple[str, str]]:
    """Retorna pares de tópicos que se sobrepõem (usado nos testes)."""
    items = sorted(((res.rect(k, M), k) for k in res.pos), key=lambda r: r[0][0])
    out = []
    for i, (ra, ka) in enumerate(items):
        for rb, kb in items[i + 1:]:
            if rb[0] >= ra[0] + ra[2]:
                break
            if rects_overlap(ra, rb):
                out.append((ka, kb))
    return out
