import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# testes rodam em português (idioma-fonte), qualquer que seja o idioma da máquina
os.environ.setdefault("MINDFORGE_IDIOMA", "pt_BR")
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
    w.canvas.cancel_edit()      # edição aberta viraria alteração ao fechar
    w.doc.mark_saved()          # evita a pergunta "salvar alterações?"
    w.close()
    QTest.qWait(10)


@pytest.fixture(autouse=True)
def _portugues():
    """Garante que um teste em inglês não vaze o idioma para os próximos."""
    yield
    from mindforge import i18n
    if i18n.language() != "pt_BR":
        app = QCoreApplication.instance()
        if hasattr(app, "_apply_language"):
            app._apply_language("pt_BR", persist=False)
        else:
            i18n.set_language("pt_BR")


# ------------------------------------------------------------ saída limpa
# No macOS, o PySide6 às vezes derruba o processo (segmentation fault) DEPOIS que todos os
# testes passaram, quando o Python destrói os objetos do Qt numa ordem que o Qt não espera.
# Para evitar isso, as janelas são fechadas e o processo sai direto, com o código do pytest.
_exit_status = 0


def pytest_sessionfinish(session, exitstatus):
    global _exit_status
    _exit_status = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    app = QCoreApplication.instance()
    if app is not None:
        for w in list(getattr(app, "windows", [])):
            try:
                w.doc.mark_saved()
                w.close()
            except Exception:
                pass
        app.processEvents()
    rep = config.pluginmanager.get_plugin("terminalreporter")
    if rep is not None:
        rep._tw.flush()
    for f in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
        try:
            f.flush()
        except Exception:
            pass
    os._exit(_exit_status)
