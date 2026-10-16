import math
import random

import pytest

from mindforge.layouts import LAYOUTS, Metric, find_overlaps
from mindforge.model.topic import Topic


def random_tree(seed: int, n: int):
    r = random.Random(seed)
    root = Topic("raiz")
    nodes = [root]
    for i in range(n):
        p = r.choice(nodes)
        nodes.append(p.add_child(Topic(f"t{i}")))
    for t in nodes[1:]:
        if t.children and r.random() < 0.1:
            t.collapsed = True
    metrics = {}
    for t in root.walk():
        h = r.uniform(18, 70)
        metrics[t.id] = Metric(r.uniform(30, 280), h, h if r.random() < 0.5 else h / 2)
    return root, metrics


@pytest.mark.parametrize("key", list(LAYOUTS))
def test_sem_sobreposicao_e_coordenadas_validas(key):
    layout = LAYOUTS[key]
    for seed in range(60):
        root, M = random_tree(seed, random.Random(seed).randint(0, 120))
        res = layout.compute(root, M)
        visiveis = {t.id for t in root.walk_visible()}
        assert set(res.pos) == visiveis, f"{key}: tópicos visíveis divergentes"
        assert not find_overlaps(res, M), f"{key} seed={seed}: caixas sobrepostas"
        for x, y in res.pos.values():
            assert math.isfinite(x) and math.isfinite(y)
        for c in res.connectors:
            assert all(math.isfinite(v) for p in c.points for v in p)


@pytest.mark.parametrize("key", list(LAYOUTS))
def test_raiz_centralizada_na_origem(key):
    root, M = random_tree(1, 20)
    res = LAYOUTS[key].compute(root, M)
    x, y = res.pos[root.id]
    m = M[root.id]
    assert abs(x + m.w / 2) < 1e-6 and abs(y + m.h / 2) < 1e-6


@pytest.mark.parametrize("key", list(LAYOUTS))
def test_mapa_grande_1000_topicos_rapido(key):
    import time
    root, M = random_tree(7, 1000)
    for t in root.walk():
        t.collapsed = False
    t0 = time.perf_counter()
    LAYOUTS[key].compute(root, M)
    assert time.perf_counter() - t0 < 0.5


def _seg_hits_rect(p0, p1, rect, shrink=1.5):
    """Segmento p0-p1 cruza o interior do retângulo (x, y, w, h)?"""
    x, y, w, h = rect
    x0, y0, x1, y1 = x + shrink, y + shrink, x + w - shrink, y + h - shrink
    if x1 <= x0 or y1 <= y0:
        return False
    (ax, ay), (bx, by) = p0, p1
    for i in range(101):                      # amostragem densa: robusto e simples
        t = i / 100
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        if x0 < px < x1 and y0 < py < y1:
            return True
    return False


def _fishbone(seed, n, align=False):
    from mindforge.layouts.base import layout_options
    root, M = random_tree(seed, n)
    for t in root.walk():
        t.collapsed = False
    with layout_options(fishbone_align=align):
        res = LAYOUTS["espinha_peixe"].compute(root, M)
    return root, M, res


def test_espinha_cresce_para_a_direita_sem_rabo():
    root, M, res = _fishbone(3, 40)
    rx, _ = res.pos[root.id]
    assert all(res.pos[c.id][0] > rx for c in root.children)
    keys = {c.key for c in res.connectors}
    assert "fb:tail" not in keys and "fb:spine" in keys


def test_espinha_pares_saem_do_mesmo_ponto():
    for seed in range(20):
        root, M, res = _fishbone(seed, 50)
        bones = {c.owner: c for c in res.connectors if c.key.startswith("fb:") and c.key != "fb:spine"}
        kids = root.children
        for k in range(0, len(kids) - 1, 2):
            a, b = bones[kids[k].id], bones[kids[k + 1].id]
            assert abs(a.points[0][0] - b.points[0][0]) < 1e-6


def test_espinha_nenhuma_linha_atravessa_texto():
    for seed in range(40):
        root, M, res = _fishbone(seed, random.Random(seed).randint(4, 70))
        rects = {k: res.rect(k, M) for k in res.pos}
        for c in res.connectors:
            if c.kind != "line":
                continue
            for tid, r in rects.items():
                if tid in (c.owner, root.id):
                    continue
                assert not _seg_hits_rect(c.points[0], c.points[-1], r), f"seed={seed}: {c.key} cruza {tid}"


def test_espinha_coluna_vai_ate_depois_de_tudo():
    root, M, res = _fishbone(7, 60)
    spine = next(c for c in res.connectors if c.key == "fb:spine")
    end_x = max(x for x, _ in spine.points)
    assert end_x >= max(res.pos[k][0] + M[k].w for k in res.pos) - 1e-6 or \
        end_x >= max(x for c in res.connectors if c.key.startswith("fb:") and c.key != "fb:spine"
                     for x, _ in c.points)


def test_espinha_comprimento_livre_e_opcao_alinhar():
    root, M, res = _fishbone(3, 40)
    tops = {round(res.pos[c.id][1] + M[c.id].h, 3) for i, c in enumerate(root.children) if i % 2 == 0}
    root, M, res2 = _fishbone(3, 40, align=True)
    tops2 = {round(res2.pos[c.id][1] + M[c.id].h, 3) for i, c in enumerate(root.children) if i % 2 == 0}
    assert len(tops2) == 1
    assert len(tops) >= 1


@pytest.mark.parametrize("key", list(LAYOUTS))
def test_cada_filho_em_um_unico_grupo(key):
    """Tronco único: cada tópico visível é ligado por exatamente um grupo ou linha."""
    root, M = random_tree(11, 80)
    res = LAYOUTS[key].compute(root, M)
    seen = {}
    for g in res.groups:
        assert len({k for k, _ in g.kids}) == len(g.kids)
        for k, _ in g.kids:
            seen[k] = seen.get(k, 0) + 1
    assert all(v == 1 for v in seen.values())
    parents = [g.parent for g in res.groups]
    # um grupo por pai e por lado (o mapa mental tem até 2 grupos na raiz)
    assert len(parents) - len(set(parents)) <= 1


def test_compactar_reduz_o_mapa():
    from mindforge.layouts.base import spacing
    root, M = random_tree(5, 40)
    for t in root.walk():
        t.collapsed = False
    normal = LAYOUTS["mapa_mental"].compute(root, M).bbox(M)
    with spacing(0.6):
        comp = LAYOUTS["mapa_mental"].compute(root, M).bbox(M)
    assert (comp[3] - comp[1]) < (normal[3] - normal[1])
