"""Atalhos de teclado e a máquina de estados de edição (risco nº 1 da especificação)."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

K = Qt.Key
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier


def key(w, k, mod=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(w.canvas, k, mod)
    QTest.qWait(5)


def type_text(w, text):
    """Digita texto com acentos (QTest.keyClicks só aceita ASCII)."""
    for ch in text:
        target = QApplication.focusWidget() or w.canvas
        for t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(target, QKeyEvent(t, 0, Qt.KeyboardModifier.NoModifier, ch))
    QTest.qWait(40)


def texts(w, parent=None):
    t = parent or w.doc.map.root
    return [c.text for c in t.children]


def cur(w):
    return w.doc.map.find(w.canvas.current())


def test_tab_cria_subtopico_e_edita(window):
    w = window
    n = len(texts(w))
    key(w, K.Key_Tab)
    assert w.canvas.is_editing()
    type_text(w, "Ação inicial")
    key(w, K.Key_Return)
    assert not w.canvas.is_editing()
    assert texts(w)[-1] == "Ação inicial"
    assert len(texts(w)) == n + 1


def test_tab_durante_edicao_confirma_e_cria_filho(window):
    w = window
    key(w, K.Key_Tab)
    type_text(w, "Pai")
    key(w, K.Key_Tab)          # confirma "Pai" e cria filho dele
    type_text(w, "Filho")
    key(w, K.Key_Return)
    pai = [c for c in w.doc.map.root.children if c.text == "Pai"][0]
    assert [c.text for c in pai.children] == ["Filho"]


def test_enter_e_shift_enter_criam_irmaos(window):
    w = window
    w.canvas.select_id(w.doc.map.root.children[1].id)
    key(w, K.Key_Return)
    type_text(w, "Depois")
    key(w, K.Key_Return)
    assert texts(w)[2] == "Depois"
    key(w, K.Key_Return, SHIFT)
    type_text(w, "Antes")
    key(w, K.Key_Return)
    assert texts(w)[2:4] == ["Antes", "Depois"]


def test_shift_enter_na_edicao_quebra_linha(window):
    w = window
    key(w, K.Key_F2)
    QTest.keyClick(w.canvas, K.Key_End)
    key(w, K.Key_Return, SHIFT)
    type_text(w, "segunda")
    key(w, K.Key_Return)
    assert w.doc.map.root.text.endswith("\nsegunda")


def test_delete_durante_edicao_apaga_letra_nao_topico(window):
    w = window
    first = w.doc.map.root.children[0]
    w.canvas.select_id(first.id)
    total = w.doc.map.count()
    key(w, K.Key_F2)
    QTest.keyClick(w.canvas, K.Key_End)
    key(w, K.Key_Backspace)
    key(w, K.Key_Return)
    assert w.doc.map.count() == total
    assert w.doc.map.find(first.id).text == "Tópico principal"  # espaço final é aparado


def test_esc_cancela_edicao(window):
    w = window
    original = w.doc.map.root.text
    key(w, K.Key_F2)
    type_text(w, "lixo")
    key(w, K.Key_Escape)
    assert w.doc.map.root.text == original
    assert not w.canvas.is_editing()


def test_digitar_inicia_edicao_substituindo(window):
    w = window
    w.canvas.select_id(w.doc.map.root.children[0].id)
    type_text(w, "Novo")
    key(w, K.Key_Return)
    assert texts(w)[0] == "Novo"


def test_espaco_edita_sem_apagar(window):
    w = window
    w.canvas.select_id(w.doc.map.root.children[0].id)
    key(w, K.Key_Space)
    assert w.canvas.is_editing()
    QTest.keyClick(w.canvas, K.Key_End)
    type_text(w, "!")
    key(w, K.Key_Return)
    assert texts(w)[0] == "Tópico principal 1!"


def test_delete_exclui_e_desfazer_refazer(window):
    w = window
    alvo = w.doc.map.root.children[0]
    w.canvas.select_id(alvo.id)
    key(w, K.Key_Delete)
    assert w.doc.map.find(alvo.id) is None
    key(w, K.Key_Z, CTRL)
    assert w.doc.map.find(alvo.id) is not None
    assert w.canvas.current() == alvo.id          # seleção restaurada
    key(w, K.Key_Z, CTRL | SHIFT)
    assert w.doc.map.find(alvo.id) is None
    key(w, K.Key_Z, CTRL)
    key(w, K.Key_Y, CTRL)
    assert w.doc.map.find(alvo.id) is None


def test_criar_mais_editar_desfaz_de_uma_vez(window):
    w = window
    n = len(texts(w))
    key(w, K.Key_Tab)
    type_text(w, "Temp")
    key(w, K.Key_Return)
    key(w, K.Key_Z, CTRL)
    assert len(texts(w)) == n


def test_raiz_nao_e_excluida(window):
    w = window
    w.canvas.select_id(w.doc.map.root.id)
    key(w, K.Key_Delete)
    assert w.doc.map.root is not None and w.doc.map.count() == 5


def test_navegacao_por_setas(window):
    w = window
    root = w.doc.map.root
    w.canvas.select_id(root.id)
    key(w, K.Key_Right)
    assert cur(w).parent is root
    key(w, K.Key_Down)
    assert cur(w) is root.children[1] or cur(w).parent is root
    key(w, K.Key_Left)
    assert cur(w) is root


def test_mover_entre_irmaos(window):
    w = window
    root = w.doc.map.root
    second = root.children[1]
    w.canvas.select_id(second.id)
    key(w, K.Key_Up, CTRL)
    assert root.children[0].id == second.id
    key(w, K.Key_Down, CTRL)
    assert w.doc.map.root.children[1].id == second.id


def test_recolher_expandir(window):
    w = window
    a = w.doc.map.root.children[0]
    w.canvas.select_id(a.id)
    key(w, K.Key_Tab)
    key(w, K.Key_Return)
    w.canvas.select_id(a.id)
    key(w, K.Key_Slash, CTRL)
    a = w.doc.map.find(a.id)
    assert a.collapsed
    assert a.children[0].id not in w.canvas.mscene.topic_items
    key(w, K.Key_Slash, CTRL)
    assert not w.doc.map.find(a.id).collapsed


def test_copiar_colar_duplicar(window):
    w = window
    a = w.doc.map.root.children[0]
    w.canvas.select_id(a.id)
    key(w, K.Key_C, CTRL)
    w.canvas.select_id(w.doc.map.root.children[1].id)
    key(w, K.Key_V, CTRL)
    assert [c.text for c in w.doc.map.root.children[1].children] == [a.text]
    total = w.doc.map.count()
    key(w, K.Key_D, CTRL)
    assert w.doc.map.count() == total + 1


def test_colar_texto_indentado(window):
    w = window
    QApplication.clipboard().setText("Lista\n\tItem 1\n\tItem 2")
    w.canvas.select_id(w.doc.map.root.id)
    key(w, K.Key_V, CTRL)
    lista = [c for c in w.doc.map.root.children if c.text == "Lista"][0]
    assert [c.text for c in lista.children] == ["Item 1", "Item 2"]


def test_ctrl_c_durante_edicao_nao_copia_ramo(window):
    w = window
    QApplication.clipboard().setText("antes")
    key(w, K.Key_F2)
    key(w, K.Key_C, CTRL)   # copia o TEXTO selecionado no editor
    assert QApplication.clipboard().text() == w.doc.map.root.text
    assert not QApplication.clipboard().mimeData().hasFormat("application/x-mindforge-topics")
    key(w, K.Key_Escape)


def test_ctrl_s_durante_edicao_confirma_texto(window, tmp_path, monkeypatch):
    w = window
    w.doc.path = str(tmp_path / "x.mfmap")
    key(w, K.Key_F2)
    type_text(w, "Salvo")
    key(w, K.Key_S, CTRL)
    assert not w.canvas.is_editing()
    assert w.doc.map.root.text == "Salvo"
    assert not w.doc.is_modified()


def test_delete_na_nota_nao_exclui_topico(window):
    w = window
    a = w.doc.map.root.children[0]
    w.canvas.select_id(a.id)
    w.panel.note.setFocus()
    QTest.qWait(10)
    QTest.keyClicks(w.panel.note, "abc")
    QTest.keyClick(w.panel.note, K.Key_Backspace)
    QTest.keyClick(w.panel.note, K.Key_Delete)
    assert w.doc.map.find(a.id) is not None
    w.panel._commit_note()
    assert w.doc.map.find(a.id).note == "ab"


def test_relacao_e_zoom(window):
    w = window
    c = w.canvas
    root = w.doc.map.root
    c.select_id(root.children[0].id)
    key(w, K.Key_R, CTRL)
    assert c.relation_source == root.children[0].id
    key(w, K.Key_Escape)
    assert c.relation_source is None
    z = c.zoom
    key(w, K.Key_Equal, CTRL)
    assert c.zoom > z
    key(w, K.Key_1, CTRL)
    assert abs(c.zoom - 1.0) < 1e-6


def test_ctrl_enter_insere_topico_pai(window):
    w = window
    a = w.doc.map.root.children[0]
    w.canvas.select_id(a.id)
    key(w, K.Key_Return, CTRL)
    assert w.canvas.is_editing()
    type_text(w, "Grupo")
    key(w, K.Key_Return)
    pai = w.doc.map.find(a.id).parent
    assert pai.text == "Grupo" and pai.parent is w.doc.map.root
    key(w, K.Key_Z, CTRL)                     # criar + nomear = um único desfazer
    assert w.doc.map.find(a.id).parent is w.doc.map.root


def test_painel_mapa_aplica_configuracoes(window):
    w = window
    p = w.panel
    p._set_setting("rainbow", False)
    sc = w.canvas.mscene
    cores = {sc.visuals[c.id].style.line_color for c in w.doc.map.root.children}
    assert len(cores) == 1
    p._set_setting("background", "#123456")
    assert sc.background_color == "#123456"
    p._set_theme("escuro")
    assert w.doc.map.theme == "escuro"
    p._set_layout("espinha_peixe")
    assert w.doc.map.layout == "espinha_peixe"
    key(w, K.Key_Z, CTRL)
    assert w.doc.map.layout == "mapa_direita"
