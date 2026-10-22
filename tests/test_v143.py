"""1.4.3 — colar sempre sem formatação, texto limpo de espaços/quebras/invisíveis."""
import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from mindforge.model import ops
from mindforge.textclean import clean_committed, clean_line, clean_paste, prepare_outline

SUJO = "  Olá  mundo​\r\n\r\n\t segunda linha­  \n"
HTML = ('<p style="margin:20px"><span style="font-size:40pt;color:#ff0000;font-family:Courier">'
        "  Olá&nbsp;&nbsp;mundo</span></p><p></p><p><b>segunda</b> linha</p>")


def _clip(text: str, html: str = "") -> None:
    md = QMimeData()
    md.setText(text)
    if html:
        md.setHtml(html)
    QGuiApplication.clipboard().setMimeData(md)


def _edit(w, tid=None):
    tid = tid or w.doc.map.root.children[0].id
    w.canvas.start_edit(tid)
    assert w.canvas.editor is not None
    return tid, w.canvas.editor


# ------------------------------------------------------------- limpeza pura
def test_limpeza_linha_unica_por_padrao():
    assert clean_paste(SUJO) == "Olá mundo segunda linha"


def test_limpeza_mantendo_linhas():
    assert clean_paste(SUJO, keep_lines=True) == "Olá mundo\nsegunda\nlinha"


@pytest.mark.parametrize("nl", ["\n", "\r\n", "\r", " ", " ", "\x0b"])
def test_todas_as_quebras(nl):
    assert clean_paste(f"a{nl}b", keep_lines=True) == "a\nb"
    assert clean_paste(f"a{nl}{nl}b") == "a b"


def test_simbolos_alt_ficam():
    s = "• item ◘ ♦ ☺ ♥ → ¶ § ° ½ ✓ – — “aspas”"
    assert clean_line(s) == s
    assert clean_paste(f"  {s}  ") == s
    assert clean_committed(s) == s


def test_invisiveis_e_espacos_especiais():
    assert clean_line("a​b‍c﻿d‎e") == "abcde"
    assert clean_line("a b c　d e") == "a b c d e"
    assert clean_paste("") == "" and clean_paste("  ​\n\t") == ""


def test_confirmar_limpa_de_leve():
    assert clean_committed("  texto​  \r\nsegunda   \n\n") == "texto\nsegunda"
    assert clean_committed("dois  espaços digitados") == "dois  espaços digitados"


def test_outline_mantem_indentacao():
    assert prepare_outline("Pai  X\n\tFilho​  Y") == "Pai X\n\tFilho Y"


def test_outline_simbolos_e_numeros_ficam():
    tops = ops.parse_outline("• Bullet\n♦ Losango\n- traço\n1. um\n1.5 kg\n-5 graus")
    assert [t.text for t in tops] == ["• Bullet", "♦ Losango", "traço", "um", "1.5 kg", "-5 graus"]


def test_outline_hierarquia_e_limpeza():
    tops = ops.parse_outline("Item A \tSub  B​\r\n\t\tNeto\n\nOutro")
    assert [t.text for t in tops] == ["Item A", "Outro"]
    assert tops[0].children[0].text == "Sub B"
    assert tops[0].children[0].children[0].text == "Neto"
    assert ops.count_topics(tops) == 4


# ---------------------------------------------------------- colar na edição
def test_colar_na_edicao_sem_formatacao(window):
    tid, ed = _edit(window)
    _clip("  Olá  mundo\n\nsegunda linha", HTML)
    QTest.keyClick(window.canvas, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert window.canvas.editor is ed                  # continua editando
    assert ed.toPlainText() == "Olá mundo segunda linha"
    html = ed.document().toHtml()
    assert "40pt" not in html and "Courier" not in html and "#ff0000" not in html
    window.canvas.commit_edit()
    assert window.doc.map.find(tid).text == "Olá mundo segunda linha"


def test_colar_mantendo_quebras(window):
    tid, ed = _edit(window)
    _clip("linha 1\r\n\r\n  linha 2  \n")
    QTest.keyClick(window.canvas, Qt.Key.Key_V,
                   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert ed.toPlainText() == "linha 1\nlinha 2"
    window.canvas.commit_edit()
    assert window.doc.map.find(tid).text == "linha 1\nlinha 2"


def test_colar_no_meio_do_texto(window):
    tid, ed = _edit(window)
    ed.setPlainText("começo fim")
    cur = ed.textCursor()
    cur.setPosition(len("começo "))
    ed.setTextCursor(cur)
    _clip(" meio​ ")
    window.canvas.paste()                              # menu Editar → Colar
    assert window.canvas.editor is ed
    assert ed.toPlainText() == "começo meiofim"
    n = len(window.doc.map.find(tid).children)
    window.canvas.cancel_edit()
    assert len(window.doc.map.find(tid).children) == n  # não criou tópico


def test_colar_vazio_nao_muda(window):
    _tid, ed = _edit(window)
    before = ed.toPlainText()
    _clip(" ​\n ")
    window.canvas.paste()
    assert ed.toPlainText() == before


def test_menu_de_contexto_do_editor(window, monkeypatch):
    _tid, ed = _edit(window)
    _clip("de fora", "<b style='font-size:30pt'>de fora</b>")
    seen = {}

    def fake_exec(menu, *a):
        seen["acts"] = [x.text() for x in menu.actions() if not x.isSeparator()]
        next(x for x in menu.actions() if x.text() == "Colar").trigger()

    monkeypatch.setattr(type(ed), "exec_menu", staticmethod(fake_exec))

    class Ev:
        def screenPos(self):
            from PySide6.QtCore import QPoint
            return QPoint(0, 0)

        def accept(self):
            pass

    ed.contextMenuEvent(Ev())
    assert seen["acts"] == ["Desfazer", "Refazer", "Recortar", "Copiar", "Colar",
                            "Colar mantendo as quebras de linha", "Selecionar tudo"]
    assert ed.toPlainText() == "de fora"
    assert "30pt" not in ed.document().toHtml()


def test_arrastar_texto_de_fora(window):
    _tid, ed = _edit(window)
    ed.setPlainText("")
    md = QMimeData()
    md.setText("  arrastado aqui \n\n")
    md.setHtml("<h1>arrastado aqui</h1>")

    class Ev:
        accepted = False

        def mimeData(self):
            return md

        def source(self):
            return None

        def pos(self):
            return QPointF(0, 0)

        def setDropAction(self, a):
            pass

        def accept(self):
            Ev.accepted = True

        def ignore(self):
            pass

    ed.dropEvent(Ev())
    assert Ev.accepted and ed.toPlainText() == "arrastado aqui"
    assert "<h1" not in ed.document().toHtml()


def test_confirmar_limpa_texto_digitado(window):
    tid, ed = _edit(window)
    ed.setPlainText("texto​  \nsegunda   ")
    window.canvas.commit_edit()
    assert window.doc.map.find(tid).text == "texto\nsegunda"


# ------------------------------------------------------- colar fora da edição
def test_colar_fora_da_edicao_limpa(window):
    root = window.doc.map.root
    window.canvas.select_id(root.id)
    n = len(root.children)
    _clip("Item A​\n\tSub  B\n♦ Losango")
    window.canvas.paste()
    assert len(root.children) == n + 2
    a, b = root.children[-2:]
    assert a.text == "Item A" and a.children[0].text == "Sub B" and b.text == "♦ Losango"


@pytest.mark.parametrize("answer,created", [(QMessageBox.StandardButton.Cancel, False),
                                            (QMessageBox.StandardButton.Yes, True)])
def test_muitas_linhas_pede_confirmacao(window, monkeypatch, answer, created):
    asked = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: asked.append(a) or answer))
    root = window.doc.map.root
    window.canvas.select_id(root.id)
    n = len(root.children)
    _clip("\n".join(f"linha {i}" for i in range(60)))
    window.canvas.paste()
    assert asked and "60" in asked[0][2]
    assert len(root.children) == n + (60 if created else 0)


def test_poucas_linhas_nao_pergunta(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: pytest.fail("perguntou")))
    window.canvas.select_id(window.doc.map.root.id)
    _clip("\n".join(f"l{i}" for i in range(50)))
    window.canvas.paste()


def test_copiar_e_colar_ramo_do_proprio_app_nao_pergunta(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: pytest.fail("perguntou")))
    root = window.doc.map.root
    parent = root.children[0]
    window.doc.apply("x", lambda m: [ops.add_child(m, parent.id) for _ in range(60)])
    window.canvas.select_id(parent.id)
    assert window.canvas.copy()
    window.canvas.select_id(root.id)
    n = len(root.children)
    window.canvas.paste()
    assert len(root.children) == n + 1
