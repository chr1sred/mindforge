"""Os esqueletos estruturais disponíveis."""
from __future__ import annotations

import math

from mindforge.layouts.base import (
    H_GAP, V_GAP_MAIN, Connector, Layout, LayoutResult, Metric, center_on_root,
    horizontal_subtree, indented_list, sp, vertical_subtree,
)
from mindforge.model.topic import Topic


def _bbox_y(res: LayoutResult, M: dict[str, Metric]) -> tuple[float, float]:
    _, y0, _, y1 = res.bbox(M)
    return y0, y1


# ---------------------------------------------------------------------------
class MindMapLayout(Layout):
    """Mapa mental balanceado: ramos dos dois lados, sentido horário."""
    key = "mapa_mental"
    label = "Mapa mental"
    MAIN_GAP = 64.0

    def compute(self, root: Topic, M: dict[str, Metric]) -> LayoutResult:
        rm = M[root.id]
        res = LayoutResult()
        res.pos[root.id] = (-rm.w / 2, -rm.h / 2)
        res.sides[root.id] = "right"
        kids = root.visible_children()
        if not kids:
            return res
        blocks = [horizontal_subtree(c, M, "right", "curve_h") for c in kids]
        heights = []
        for b in blocks:
            y0, y1 = _bbox_y(b, M)
            heights.append(y1 - y0)
        gap = sp(V_GAP_MAIN)
        total = sum(heights) + gap * (len(kids) - 1)
        right_n, acc = 0, 0.0
        for h in heights:
            if right_n > 0 and acc + h / 2 > total / 2:
                break
            acc += h + gap
            right_n += 1
        right = list(range(right_n))
        left = list(range(right_n, len(kids)))[::-1]   # sentido horário

        def place(indices: list[int], side: str) -> None:
            if not indices:
                return
            col: list[LayoutResult] = []
            for i in indices:
                b = blocks[i] if side == "right" else horizontal_subtree(kids[i], M, "left", "curve_h")
                col.append(b)
            hs = [(_bbox_y(b, M)) for b in col]
            col_h = sum(y1 - y0 for y0, y1 in hs) + gap * (len(col) - 1)
            y = -col_h / 2
            for i, b, (y0, y1) in zip(indices, col, hs):
                c = kids[i]
                cm = M[c.id]
                if side == "right":
                    dx = rm.w / 2 + sp(self.MAIN_GAP)
                else:
                    dx = -rm.w / 2 - sp(self.MAIN_GAP) - cm.w
                b.translate(dx, y - y0)
                cx, cy = b.pos[c.id]
                p1 = (cx, cy + cm.ay) if side == "right" else (cx + cm.w, cy + cm.ay)
                res.connectors.append(Connector(c.id, c.id, "curve_h", [(0.0, 0.0), p1]))
                res.merge(b)
                y += (y1 - y0) + gap

        place(right, "right")
        place(left, "left")
        return res


class LogicLayout(Layout):
    """Mapa lógico (diagrama de chaves) para a direita ou esquerda."""

    def __init__(self, key: str, label: str, direction: str):
        self.key, self.label, self.direction = key, label, direction
        self.floating_direction = direction if direction in ("right", "left") else "right"

    def compute(self, root: Topic, M: dict[str, Metric]) -> LayoutResult:
        res = horizontal_subtree(root, M, self.direction, "elbow_h", base_depth=0, hgap=sp(H_GAP + 6))
        return center_on_root(res, root, M)

    def compute_floating(self, top, M):
        res = horizontal_subtree(top, M, self.direction, "elbow_h", base_depth=2)
        px, py = top.pos or (0.0, 0.0)
        return res.translate(px, py)


class OrgChartLayout(Layout):
    key = "organograma"
    label = "Organograma"
    floating_direction = "down"

    def compute(self, root: Topic, M: dict[str, Metric]) -> LayoutResult:
        return center_on_root(vertical_subtree(root, M), root, M)


class TreeChartLayout(Layout):
    """Árvore: 1º nível lado a lado; demais níveis em lista indentada."""
    key = "arvore"
    label = "Árvore"
    COL_GAP = 34.0
    ROW_GAP = 46.0

    def compute(self, root: Topic, M: dict[str, Metric]) -> LayoutResult:
        rm = M[root.id]
        res = LayoutResult()
        res.pos[root.id] = (-rm.w / 2, 0.0)
        res.sides[root.id] = "down"
        kids = root.visible_children()
        if kids:
            cols = [indented_list(c, M, include_root=True) for c in kids]
            total = sum(w for _, w, _ in cols) + sp(self.COL_GAP) * (len(cols) - 1)
            x = -total / 2
            y = rm.h + sp(self.ROW_GAP)
            p0 = (0.0, rm.h)
            for c, (col, w, _) in zip(kids, cols):
                col.translate(x, y)
                cm = M[c.id]
                cx, cy = col.pos[c.id]
                res.connectors.append(Connector(c.id, c.id, "elbow_v", [p0, (cx + cm.w / 2, cy)]))
                res.merge(col)
                x += w + sp(self.COL_GAP)
        return center_on_root(res, root, M)


class TimelineLayout(Layout):
    """Linha do tempo horizontal: eventos na linha, detalhes acima/abaixo."""
    key = "linha_tempo"
    label = "Linha do tempo"
    SEG = 46.0
    LIST_OFFSET = 26.0
    INDENT = 22.0

    def compute(self, root: Topic, M: dict[str, Metric]) -> LayoutResult:
        rm = M[root.id]
        res = LayoutResult()
        res.pos[root.id] = (0.0, -rm.h / 2)
        res.sides[root.id] = "right"
        kids = root.visible_children()
        half = max([M[c.id].h for c in kids] + [rm.h]) / 2
        cursor = {"up": -math.inf, "down": -math.inf}
        prev_right = rm.w
        for i, c in enumerate(kids):
            side = "up" if i % 2 == 0 else "down"
            m = M[c.id]
            x = max(prev_right + sp(self.SEG), cursor[side])
            res.pos[c.id] = (x, -m.h / 2)
            res.sides[c.id] = side
            res.connectors.append(Connector(f"tl:{c.id}", c.id, "line", [(prev_right, 0.0), (x, 0.0)]))
            right_extent = x + m.w
            if c.visible_children():
                lst, lw, lh = indented_list(c, M, include_root=False, indent=self.INDENT)
                lx = x + self.INDENT
                off = sp(self.LIST_OFFSET)
                ly = (-half - off - lh) if side == "up" else (half + off)
                lst.translate(lx, ly)
                tx = x + self.INDENT / 2
                ty = -m.h / 2 if side == "up" else m.h / 2
                for cc in c.visible_children():
                    ccx, ccy = lst.pos[cc.id]
                    ay = ccy + M[cc.id].ay
                    lst.connectors.append(Connector(cc.id, cc.id, "poly", [(tx, ty), (tx, ay), (ccx, ay)]))
                res.merge(lst)
                right_extent = max(right_extent, lx + lw)
            cursor[side] = right_extent + sp(30.0)
            prev_right = x + m.w
        res.connectors.append(Connector("tl:end", root.id, "arrow_line",
                                        [(prev_right, 0.0), (prev_right + 56.0, 0.0)]))
        return center_on_root(res, root, M)


class FishboneLayout(Layout):
    """Espinha de peixe (Ishikawa) crescendo da esquerda para a direita.

    O tema central (efeito) fica à esquerda; a coluna segue para a direita e
    as causas ficam na ponta de espinhas inclinadas, alternando em cima e
    embaixo. Todas as espinhas têm o mesmo comprimento, então os tópicos
    principais ficam alinhados em duas fileiras (visual mais organizado).

    Implementação: calcula a versão "cabeça à direita" e espelha no fim.
    """
    key = "espinha_peixe"
    label = "Espinha de peixe"
    floating_direction = "right"
    TAN = math.tan(math.radians(62))
    RIB = 22.0          # comprimento da costela até o texto do subtópico
    NEAR = 26.0         # folga entre a coluna e a primeira costela
    END_GAP = 16.0      # folga entre a última costela e o tópico principal
    SUB_GAP = 8.0
    BONE_GAP = 40.0
    START = 56.0        # distância do tema central até a primeira espinha
    MIN_H = 70.0
    TAIL = 36.0

    def compute(self, root: Topic, M: dict[str, Metric]) -> LayoutResult:
        rm = M[root.id]
        res = LayoutResult()
        res.pos[root.id] = (0.0, -rm.h / 2)
        res.sides[root.id] = "left"
        kids = root.visible_children()
        prepared = []
        need = sp(self.MIN_H)
        for i, c in enumerate(kids):
            blocks = []
            for sc in c.visible_children():
                b = horizontal_subtree(sc, M, "left", "elbow_h", base_depth=3)
                _, by0, _, by1 = b.bbox(M)
                blocks.append((sc, b, by0, by1))
            if blocks:
                total = sum(by1 - by0 for _, _, by0, by1 in blocks) + sp(self.SUB_GAP) * (len(blocks) - 1)
                need = max(need, sp(self.NEAR) + total + sp(self.END_GAP))
            prepared.append((c, "up" if i % 2 == 0 else "down", blocks))
        H = need     # mesmo comprimento para todas as espinhas
        cursor = {"up": -sp(self.START), "down": -sp(self.START)}
        starts: list[float] = []
        for c, side, blocks in prepared:
            bone = self._bone(c, M, side, blocks, H)
            bx0, _, bx1, _ = bone.bbox(M)
            x0 = cursor[side] - max(0.0, bx1)
            bone.translate(x0, 0.0)
            res.merge(bone)
            cursor[side] = x0 + bx0 - sp(self.BONE_GAP)
            starts.append(x0)
        end = (min(starts) - sp(self.TAIL)) if starts else -sp(self.START)
        res.connectors.append(Connector("fb:spine", root.id, "line", [(0.0, 0.0), (end, 0.0)], 1.35))
        res.mirror_x(M)
        return center_on_root(res, root, M)

    def _bone(self, c: Topic, M: dict[str, Metric], side: str, blocks: list, H: float) -> LayoutResult:
        """Espinha em coordenadas locais: começa em (0, 0) na coluna vertebral."""
        cm = M[c.id]
        res = LayoutResult()
        res.sides[c.id] = side
        dxb = H / self.TAN
        bx = -dxb - cm.w / 2
        by = -H - cm.h if side == "up" else H
        res.pos[c.id] = (bx, by)
        end = (-dxb, -H if side == "up" else H)
        res.connectors.append(Connector(f"fb:{c.id}", c.id, "line", [(0.0, 0.0), end]))
        # costelas agrupadas junto ao tópico principal; leitura de cima para baixo
        total = sum(by1 - by0 for _, _, by0, by1 in blocks) + sp(self.SUB_GAP) * max(0, len(blocks) - 1)
        d = max(sp(self.NEAR), H - sp(self.END_GAP) - total)
        seq = list(reversed(blocks)) if side == "up" else blocks
        for sc, b, by0, by1 in seq:
            bh = by1 - by0
            sm = M[sc.id]
            band_top = -(d + bh) if side == "up" else d
            root_top = band_top - by0
            ya = root_top + sm.ay
            xb = -abs(ya) / self.TAN
            root_x = xb - sp(self.RIB) - sm.w
            b.translate(root_x, root_top)
            res.connectors.append(Connector(sc.id, sc.id, "line", [(xb, ya), (root_x + sm.w, ya)]))
            res.merge(b)
            d += bh + sp(self.SUB_GAP)
        return res


LAYOUTS: dict[str, Layout] = {}
for _l in (
    MindMapLayout(),
    LogicLayout("mapa_direita", "Mapa lógico (direita)", "right"),
    LogicLayout("mapa_esquerda", "Mapa lógico (esquerda)", "left"),
    OrgChartLayout(),
    TreeChartLayout(),
    TimelineLayout(),
    FishboneLayout(),
):
    LAYOUTS[_l.key] = _l


def get_layout(key: str) -> Layout:
    return LAYOUTS.get(key) or LAYOUTS["mapa_mental"]
