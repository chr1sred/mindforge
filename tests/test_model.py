import pytest

from mindforge.model import ops
from mindforge.model.topic import MindMap, Topic


def make_map():
    m = MindMap(Topic("Raiz"))
    a = ops.add_child(m, m.root.id, "A")
    b = ops.add_child(m, m.root.id, "B")
    a1 = ops.add_child(m, a.id, "A1")
    ops.add_child(m, a1.id, "A1x")
    return m, a, b, a1


def test_roundtrip_preserva_tudo():
    m, a, b, a1 = make_map()
    a.style = {"fill": "#FF0000"}
    a.note = "nota com acentuação ção"
    a.markers = ["prio1", "feito"]
    a1.collapsed = True
    f = ops.add_floating(m, 10, 20, "Solto")
    ops.add_relation(m, a.id, f.id, "rótulo")
    m2 = MindMap.from_dict(m.to_dict())
    assert m2.to_dict() == m.to_dict()
    assert m2.find(a1.id).parent.id == a.id


def test_ids_duplicados_no_arquivo_sao_corrigidos():
    d = {"root": {"id": "x", "text": "r", "children": [{"id": "x", "text": "c"}]}}
    m = MindMap.from_dict(d)
    ids = [t.id for t in m.all_topics()]
    assert len(ids) == len(set(ids))


def test_raiz_nao_pode_ser_excluida():
    m, *_ = make_map()
    with pytest.raises(ops.OpError):
        ops.delete_topics(m, [m.root.id])


def test_excluir_remove_relacoes_e_sugere_selecao():
    m, a, b, a1 = make_map()
    ops.add_relation(m, a1.id, b.id)
    nxt = ops.delete_topics(m, [a.id])
    assert m.find(a1.id) is None
    assert m.relations == []
    assert nxt == b.id


def test_nao_move_para_dentro_de_si():
    m, a, b, a1 = make_map()
    with pytest.raises(ops.OpError):
        ops.move_topic(m, a.id, a1.id)
    ops.move_topic(m, b.id, a1.id)
    assert m.find(b.id).parent.id == a1.id


def test_reordenar_irmaos():
    m, a, b, _ = make_map()
    assert ops.reorder(m, b.id, -1)
    assert [c.text for c in m.root.children] == ["B", "A"]
    assert not ops.reorder(m, b.id, -1)       # já é o primeiro


def test_enter_na_raiz_cria_filho():
    m, *_ = make_map()
    t = ops.add_sibling(m, m.root.id)
    assert t.parent is m.root


def test_colar_gera_ids_novos():
    m, a, *_ = make_map()
    ids = ops.paste_topics(m, m.root.id, [a])
    novo = m.find(ids[0])
    assert novo.id != a.id
    assert {t.id for t in novo.walk()}.isdisjoint({t.id for t in a.walk()})
    assert [t.text for t in novo.walk()] == [t.text for t in a.walk()]


def test_marcadores_de_prioridade_sao_exclusivos():
    m, a, *_ = make_map()
    ops.toggle_marker(m, [a.id], "prio1")
    ops.toggle_marker(m, [a.id], "prio2")
    ops.toggle_marker(m, [a.id], "feito")
    assert a.markers == ["prio2", "feito"]
    ops.toggle_marker(m, [a.id], "feito")
    assert a.markers == ["prio2"]


def test_parse_outline_indentado_e_markdown():
    txt = "# Projeto\n- Fase 1\n    - Tarefa a\n    - Tarefa b\n- Fase 2\n\tdetalhe\n"
    roots = ops.parse_outline(txt)
    assert len(roots) == 1
    r = roots[0]
    assert r.text == "Projeto"
    assert [c.text for c in r.children] == ["Fase 1", "Fase 2"]
    assert [c.text for c in r.children[0].children] == ["Tarefa a", "Tarefa b"]
    assert r.children[1].children[0].text == "detalhe"


def test_outline_ida_e_volta():
    m, a, *_ = make_map()
    back = ops.parse_outline(ops.to_outline([a]))
    assert [t.text for t in back[0].walk()] == [t.text for t in a.walk()]


def test_arvore_profunda_nao_estoura_recursao():
    m = MindMap(Topic("r"))
    t = m.root
    for i in range(3000):
        t = t.add_child(Topic(str(i)))
    assert m.count() == 3001
    d = m.to_dict()
    assert d["root"]["text"] == "r"


def test_inserir_topico_pai():
    m, a, b, a1 = make_map()
    novo = ops.insert_parent(m, a1.id)
    assert novo.parent is a and a1.parent is novo
    assert a.children == [novo]
    with pytest.raises(ops.OpError):
        ops.insert_parent(m, m.root.id)


def test_configuracoes_do_mapa_persistem():
    m, *_ = make_map()
    ops.set_map_setting(m, "rainbow", False)
    ops.set_map_setting(m, "compact", True)
    ops.set_map_setting(m, "background", "#101010")
    ops.set_map_setting(m, "line_width", "padrao")      # padrão: não grava
    m2 = MindMap.from_dict(m.to_dict())
    assert m2.settings == {"rainbow": False, "compact": True, "background": "#101010"}
    assert m2.setting("line_width") == "padrao"
    ops.set_map_setting(m2, "background", None)
    assert "background" not in m2.settings
    with pytest.raises(ops.OpError):
        ops.set_map_setting(m2, "inexistente", 1)
