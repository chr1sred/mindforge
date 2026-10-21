"""Ícone e associação dos arquivos .mfmap no macOS, Windows e Linux (1.4.1)."""
import os
import sys
import xml.etree.ElementTree as ET

from PIL import Image

from mindforge import integration

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_icones_em_todos_os_formatos():
    doc = os.path.join(ROOT, "assets", "doc")
    for s in integration.ICON_SIZES:
        im = Image.open(os.path.join(doc, f"mfmap-{s}.png"))
        assert im.size == (s, s) and im.mode == "RGBA"
        assert im.getpixel((0, 0))[3] == 0                    # fundo transparente
    ico = Image.open(os.path.join(doc, "mfmap.ico"))
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(ico.info["sizes"])
    icns = Image.open(os.path.join(doc, "mfmap.icns"))
    assert max(icns.info["sizes"])[0] >= 512


def test_info_plist_do_mac_declara_icone_e_tipo_proprio():
    spec = open(os.path.join(ROOT, "mindforge.spec"), encoding="utf-8").read()
    assert '"CFBundleTypeIconFile": "mfmap.icns"' in spec
    assert '"UTTypeIconFile": "mfmap.icns"' in spec
    assert '"public.json"' not in spec                  # o Finder não mostra mais o JSON cru
    assert '("assets/doc", "assets/doc")' in spec and '("assets/doc/mfmap.icns", ".")' in spec
    for lang, name in (("en.lproj", "MindForge Map"), ("pt-BR.lproj", "Mapa do MindForge")):
        txt = open(os.path.join(ROOT, "assets", "macos", lang, "InfoPlist.strings"), encoding="utf-8").read()
        assert f'"Mapa do MindForge" = "{name}";' in txt


def test_registro_do_windows():
    e = integration.windows_entries('"C:\\Apps\\MindForge\\MindForge.exe"', "C:\\x\\mfmap.ico")
    assert e[r"Software\Classes\.mfmap"] == "MindForge.Map"
    assert e[r"Software\Classes\MindForge.Map\DefaultIcon"] == '"C:\\x\\mfmap.ico",0'
    assert e[r"Software\Classes\MindForge.Map\shell\open\command"].endswith('MindForge.exe" "%1"')
    assert all(k.startswith("Software\\Classes") for k in e)     # só o usuário atual (sem administrador)


def test_registro_do_linux(tmp_path):
    calls = []
    files = integration.register_linux('"/opt/MindForge/MindForge"', str(tmp_path), run=calls.append)
    xml = tmp_path / "mime" / "packages" / "mindforge.xml"
    root = ET.parse(xml).getroot()
    mt = root[0]
    assert mt.get("type") == integration.MIME
    assert mt.find("{http://www.freedesktop.org/standards/shared-mime-info}glob").get("pattern") == "*.mfmap"
    for s in integration.ICON_SIZES:
        assert (tmp_path / "icons" / "hicolor" / f"{s}x{s}" / "mimetypes" / f"{integration.MIME_ICON}.png").exists()
    desk = (tmp_path / "applications" / "mindforge.desktop").read_text(encoding="utf-8")
    assert f"MimeType={integration.MIME};" in desk and 'Exec="/opt/MindForge/MindForge" %f' in desk
    assert [c[0] for c in calls] == ["update-mime-database", "update-desktop-database", "gtk-update-icon-cache"]
    assert len(files) >= len(integration.ICON_SIZES) + 2


class _Settings(dict):
    def value(self, k, default=None):
        return self.get(k, default)

    def setValue(self, k, v):
        self[k] = v


def test_registro_so_no_app_empacotado_e_uma_vez(tmp_path, monkeypatch):
    st = _Settings()
    assert integration.ensure_file_association(st) is None          # código-fonte: não mexe no sistema
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(integration, "_run_quiet", lambda cmd: None)
    assert integration.ensure_file_association(st) == "linux"
    assert (tmp_path / "mime" / "packages" / "mindforge.xml").exists()
    assert integration.ensure_file_association(st) is None          # já registrado nesta versão/local
    monkeypatch.setenv("MINDFORGE_SEM_INTEGRACAO", "1")
    st.clear()
    assert integration.ensure_file_association(st) is None
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("MINDFORGE_SEM_INTEGRACAO")
    assert integration.ensure_file_association(st) is None          # Mac: feito pelo Info.plist


def test_falha_no_registro_nao_derruba_o_app(monkeypatch):
    st = _Settings()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(integration, "register_linux", lambda *a, **k: (_ for _ in ()).throw(OSError("disco")))
    assert integration.ensure_file_association(st) is None
    assert "integration/stamp" not in st                            # tenta de novo na próxima abertura
