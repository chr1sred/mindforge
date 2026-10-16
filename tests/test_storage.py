import json
import os

import pytest

from mindforge.model import ops
from mindforge.model.topic import MindMap, Topic
from mindforge.storage import MindForgeFileError, RecoveryManager, load_map, save_map


def sample():
    m = MindMap(Topic("Tema com acentuação: ção, ã, é 😀"))
    a = ops.add_child(m, m.root.id, "Linha 1\nLinha 2")
    a.note = "Nota"
    ops.add_floating(m, 5, 5)
    return m


def test_salvar_e_abrir(tmp_path):
    p = tmp_path / "mapa.mfmap"
    m = sample()
    save_map(m, str(p))
    assert load_map(str(p)).to_dict() == m.to_dict()
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["format"] == "mindforge" and raw["schema_version"] == 1


def test_salvamento_atomico_nao_deixa_temporarios(tmp_path):
    p = tmp_path / "m.mfmap"
    for _ in range(3):
        save_map(sample(), str(p))
    assert sorted(os.listdir(tmp_path)) == ["m.mfmap"]


def test_falha_na_gravacao_preserva_original(tmp_path, monkeypatch):
    p = tmp_path / "m.mfmap"
    save_map(sample(), str(p))
    original = p.read_bytes()

    def boom(*a, **k):
        raise OSError(28, "Sem espaço em disco")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(MindForgeFileError):
        save_map(MindMap(Topic("outro")), str(p))
    assert p.read_bytes() == original
    assert sorted(os.listdir(tmp_path)) == ["m.mfmap"]


@pytest.mark.parametrize("content,msg", [
    ("{quebrado", "corrompido"),
    ('{"format": "outro"}', "não é um mapa"),
    ('{"format": "mindforge", "schema_version": 99, "map": {}}', "versão mais nova"),
])
def test_arquivos_invalidos_dao_mensagem_clara(tmp_path, content, msg):
    p = tmp_path / "x.mfmap"
    p.write_text(content, encoding="utf-8")
    with pytest.raises(MindForgeFileError, match=msg):
        load_map(str(p))


def test_recuperacao(tmp_path):
    rm = RecoveryManager(str(tmp_path / "rec"))
    m = sample()
    rm.write("abc", m, "/x/y.mfmap")
    (tmp_path / "rec" / "lixo.recovery.json").write_text("{", encoding="utf-8")
    entries = rm.entries()
    assert [e.uid for e in entries] == ["abc"]
    assert entries[0].load().to_dict() == m.to_dict()
    assert entries[0].original_path == "/x/y.mfmap"
    rm.remove("abc")
    assert rm.entries() == []
