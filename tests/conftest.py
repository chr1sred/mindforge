import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    from mindforge.app import MindForgeApp
    from PySide6.QtCore import QSettings, QStandardPaths
    QStandardPaths.setTestModeEnabled(True)
    app = QCoreApplication.instance() or MindForgeApp([])
    QSettings().clear()
    yield app


@pytest.fixture
def window(qapp):
    from PySide6.QtTest import QTest
    from mindforge.document import Document
    from mindforge.templates import get_template
    w = qapp.new_window(Document(get_template("mapa_direita").create()))
    QTest.qWaitForWindowExposed(w)
    w.activateWindow()
    w.canvas.setFocus()
    # espera o "ajustar à tela" automático da janela nova (agendado para 50 ms);
    # sem isso, em máquinas rápidas (ex.: Mac M1) ele roda no meio do teste
    QTest.qWait(150)
    yield w
    w.doc.mark_saved()          # evita a pergunta "salvar alterações?"
    w.close()
    QTest.qWait(10)
