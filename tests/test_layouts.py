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


def test_espinha_de_peixe_cresce_para_a_direita_e_alinhada():
    root, M = random_tree(3, 40)
    for t in root.walk():
        t.collapsed = False
    res = LAYOUTS["espinha_peixe"].compute(root, M)
    rx, _ = res.pos[root.id]
    principais = root.children
    assert all(res.pos[c.id][0] > rx for c in principais)        # causas à direita do efeito
    tops = {round(res.pos[c.id][1] + M[c.id].h, 3) for i, c in enumerate(principais) if i % 2 == 0}
    assert len(tops) == 1                                         # fileira de cima alinhada
    assert not any(c.key == "fb:tail" for c in res.connectors)   # sem "rabo"


def test_compactar_reduz_o_mapa():
    from mindforge.layouts.base import spacing
    root, M = random_tree(5, 40)
    for t in root.walk():
        t.collapsed = False
    normal = LAYOUTS["mapa_mental"].compute(root, M).bbox(M)
    with spacing(0.6):
        comp = LAYOUTS["mapa_mental"].compute(root, M).bbox(M)
    assert (comp[3] - comp[1]) < (normal[3] - normal[1])
