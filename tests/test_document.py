import pytest

from mindforge.document import UNDO_LIMIT, Document
from mindforge.model import ops


def test_cada_operacao_e_desfazivel(qapp):
    d = Document()
    m0 = d.map.to_dict()
    tid = d.apply("add", lambda m: ops.add_child(m, m.root.id, "A").id)
    d.apply("txt", lambda m: ops.set_text(m, tid, "B"))
    d.apply("style", lambda m: ops.set_style(m, [tid], "fill", "#123456"))
    d.apply("mk", lambda m: ops.toggle_marker(m, [tid], "estrela"))
    d.apply("layout", lambda m: ops.set_layout(m, "organograma"))
    states = []
    while d.undo_stack.canUndo():
        states.append(d.map.to_dict())
        d.undo_stack.undo()
    assert d.map.to_dict() == m0
    while d.undo_stack.canRedo():
        d.undo_stack.redo()
    assert d.map.find(tid).text == "B"
    assert d.map.layout == "organograma"


def test_operacao_sem_mudanca_nao_gera_comando(qapp):
    d = Document()
    d.apply("nada", lambda m: ops.set_text(m, m.root.id, m.root.text))
    assert d.undo_stack.count() == 0
    assert not d.is_modified()


def test_erro_restaura_estado(qapp):
    d = Document()
    before = d.map.to_dict()

    def falha(m):
        ops.add_child(m, m.root.id, "temporário")
        raise ops.OpError("x")

    with pytest.raises(ops.OpError):
        d.apply("falha", falha)
    assert d.map.to_dict() == before
    assert d.undo_stack.count() == 0


def test_criar_e_editar_mesclam_em_um_desfazer(qapp):
    d = Document()
    tid = d.apply("add", lambda m: ops.add_child(m, m.root.id).id, merge_key="k1")
    d.apply("txt", lambda m: ops.set_text(m, tid, "Final"), merge_key="k1")
    assert d.undo_stack.count() == 1
    d.undo_stack.undo()
    assert d.map.find(tid) is None


def test_limite_de_100_niveis(qapp):
    d = Document()
    for i in range(UNDO_LIMIT + 20):
        d.apply("t", lambda m, i=i: ops.set_text(m, m.root.id, f"v{i}"))
    assert d.undo_stack.count() == UNDO_LIMIT


def test_estado_modificado(qapp):
    d = Document()
    assert not d.is_modified()
    d.apply("t", lambda m: ops.set_text(m, m.root.id, "x"))
    assert d.is_modified()
    d.mark_saved("/tmp/x.mfmap")
    assert not d.is_modified()
    d.undo_stack.undo()
    assert d.is_modified()
