import xml.etree.ElementTree as ET

import pytest
from PySide6.QtGui import QImage

from mindforge.document import Document
from mindforge.export import ExportOptions, export_file
from mindforge.layouts import LAYOUTS
from mindforge.templates import get_template
from mindforge.view.scene import MindScene


@pytest.fixture
def scene(qapp):
    doc = Document(get_template("ex_campanha").create())
    s = MindScene(doc)
    s.sync()
    s.topic_items[doc.map.root.id].setSelected(True)   # seleção não pode aparecer
    return s


def test_png_transparente(scene, tmp_path):
    p = tmp_path / "m.png"
    r = export_file(scene, str(p), ExportOptions("png", scale=2, transparent=True))
    img = QImage(str(p))
    assert img.hasAlphaChannel()
    assert img.width() == r.width and img.width() > 400
    assert img.pixelColor(0, 0).alpha() == 0
    assert img.pixelColor(img.width() - 1, img.height() - 1).alpha() == 0
    opaque = sum(1 for x in range(0, img.width(), 7) for y in range(0, img.height(), 7)
                 if img.pixelColor(x, y).alpha() == 255)
    assert opaque > 100


def test_png_escala_e_fundo(scene, tmp_path):
    a = export_file(scene, str(tmp_path / "1.png"), ExportOptions("png", scale=1, transparent=False))
    b = export_file(scene, str(tmp_path / "2.png"), ExportOptions("png", scale=2, transparent=False))
    assert abs(b.width - 2 * a.width) <= 1
    img = QImage(str(tmp_path / "1.png"))
    assert img.pixelColor(0, 0).alpha() == 255


def test_selecao_nao_aparece_na_exportacao(scene, tmp_path):
    export_file(scene, str(tmp_path / "a.png"), ExportOptions("png", scale=1))
    scene.clearSelection()
    export_file(scene, str(tmp_path / "b.png"), ExportOptions("png", scale=1))
    assert QImage(str(tmp_path / "a.png")) == QImage(str(tmp_path / "b.png"))


def test_svg_valido_com_texto_editavel(scene, tmp_path):
    p = tmp_path / "m.svg"
    export_file(scene, str(p), ExportOptions("svg"))
    root = ET.parse(p).getroot()
    texts = "".join(t.text or "" for t in root.iter() if t.tag.endswith("text"))
    assert "Campanha" in texts


def test_svg_texto_em_curvas(scene, tmp_path):
    p = tmp_path / "c.svg"
    export_file(scene, str(p), ExportOptions("svg", text_as_paths=True))
    root = ET.parse(p).getroot()
    assert not any(t.tag.endswith("}text") or t.tag == "text" for t in root.iter())


@pytest.mark.parametrize("page", ["mapa", "a4_paisagem"])
def test_pdf(scene, tmp_path, page):
    p = tmp_path / f"m_{page}.pdf"
    export_file(scene, str(p), ExportOptions("pdf", pdf_page=page))
    data = p.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"/FontFile" in data            # fontes embutidas
    assert len(data) > 2000


def test_exportar_somente_ramo(scene, tmp_path):
    m = scene.doc.map
    ramo = m.root.children[0]
    ids = {t.id for t in ramo.walk()}
    full = export_file(scene, str(tmp_path / "f.png"), ExportOptions("png", scale=1))
    part = export_file(scene, str(tmp_path / "p.png"), ExportOptions("png", scale=1, only_ids=ids))
    assert part.width < full.width
    # a cena volta ao normal depois
    assert all(it.isVisible() for it in scene.topic_items.values())
    assert not scene.export_mode


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_todos_os_esqueletos_exportam(qapp, tmp_path, layout):
    doc = Document(get_template("ex_campanha").create())
    doc.map.layout = layout
    s = MindScene(doc)
    s.sync()
    for fmt in ("png", "svg", "pdf"):
        export_file(s, str(tmp_path / f"{layout}.{fmt}"), ExportOptions(fmt, scale=1))
