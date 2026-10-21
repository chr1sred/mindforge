"""Integração com o sistema: ícone e associação dos arquivos .mfmap (1.4.1).

- macOS : feito pelo Info.plist do .app (mindforge.spec); nada a fazer aqui.
- Windows: registra .mfmap no usuário atual (HKCU, sem pedir administrador): ícone, nome e
           "abrir com o MindForge" (duplo clique).
- Linux  : registra o tipo MIME (shared-mime-info), os ícones (tema hicolor) e um atalho .desktop
           em ~/.local/share, como os apps instalados pelo usuário.

Só roda no app empacotado (PyInstaller) e só quando algo mudou (versão ou local do executável),
então abrir o app várias vezes não refaz nada. Falhas nunca impedem o app de abrir.
Desligue com a variável de ambiente MINDFORGE_SEM_INTEGRACAO=1.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Callable, Optional

from mindforge import APP_NAME, __version__

PROG_ID = "MindForge.Map"
MIME = "application/x-mindforge-map"
MIME_ICON = "application-x-mindforge-map"
ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def resource_dir() -> str:
    """Pasta dos recursos: dentro do pacote do PyInstaller ou a raiz do projeto (código-fonte)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def doc_icon(name: str) -> str:
    return os.path.join(resource_dir(), "assets", "doc", name)


def executable_command() -> str:
    """Comando que abre o MindForge (empacotado: o executável; código-fonte: python -m mindforge)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m mindforge'


# ------------------------------------------------------------------ Windows
def windows_entries(command: str, ico: str) -> dict[str, str]:
    """Chaves (HKCU\\Software\\Classes\\...) → valor padrão. Separado para poder testar em qualquer sistema."""
    return {
        r"Software\Classes\.mfmap": PROG_ID,
        rf"Software\Classes\{PROG_ID}": "Mapa do MindForge",
        rf"Software\Classes\{PROG_ID}\DefaultIcon": f'"{ico}",0',
        rf"Software\Classes\{PROG_ID}\shell\open\command": f'{command} "%1"',
    }


def register_windows(command: str, ico: str) -> None:
    import ctypes
    import winreg  # type: ignore[import-not-found]
    for key, value in windows_entries(command, ico).items():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, value)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.mfmap") as k:
        winreg.SetValueEx(k, "Content Type", 0, winreg.REG_SZ, MIME)
    # avisa o Explorer para redesenhar os ícones (SHCNE_ASSOCCHANGED)
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


# ------------------------------------------------------------------ Linux
def linux_mime_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="{MIME}">
    <comment>MindForge map</comment>
    <comment xml:lang="pt_BR">Mapa do MindForge</comment>
    <icon name="{MIME_ICON}"/>
    <glob pattern="*.mfmap" weight="80"/>
    <magic priority="80">
      <match type="string" value="&quot;format&quot;: &quot;mindforge&quot;" offset="0:200"/>
    </magic>
  </mime-type>
</mime-info>
"""


def linux_desktop_entry(command: str, app_icon: str) -> str:
    return f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Comment=Mind map editor
Comment[pt_BR]=Editor de mapas mentais
Exec={command} %f
Icon={app_icon}
Terminal=false
Categories=Office;Graphics;
MimeType={MIME};
"""


def register_linux(command: str, data_home: Optional[str] = None,
                   run: Callable[[list], None] = None) -> list[str]:
    """Instala MIME, ícones e .desktop em ~/.local/share. Devolve os arquivos escritos."""
    data_home = data_home or os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    written = []

    def write(path: str, text: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        written.append(path)

    write(os.path.join(data_home, "mime", "packages", "mindforge.xml"), linux_mime_xml())
    for s in ICON_SIZES:
        src = doc_icon(f"mfmap-{s}.png")
        if os.path.exists(src):
            dst = os.path.join(data_home, "icons", "hicolor", f"{s}x{s}", "mimetypes", f"{MIME_ICON}.png")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            written.append(dst)
    app_png = os.path.join(resource_dir(), "assets", "icon.png")
    app_dst = os.path.join(data_home, "icons", "hicolor", "512x512", "apps", "mindforge.png")
    if os.path.exists(app_png):
        os.makedirs(os.path.dirname(app_dst), exist_ok=True)
        shutil.copyfile(app_png, app_dst)
        written.append(app_dst)
    write(os.path.join(data_home, "applications", "mindforge.desktop"), linux_desktop_entry(command, "mindforge"))
    run = run or _run_quiet
    run(["update-mime-database", os.path.join(data_home, "mime")])
    run(["update-desktop-database", os.path.join(data_home, "applications")])
    run(["gtk-update-icon-cache", "-f", "-t", os.path.join(data_home, "icons", "hicolor")])
    return written


def _run_quiet(cmd: list) -> None:
    if shutil.which(cmd[0]) is None:
        return
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


# ------------------------------------------------------------------ entrada
def ensure_file_association(settings=None) -> Optional[str]:
    """Registra .mfmap no Windows/Linux se ainda não foi feito para esta versão e este executável.
    Devolve o sistema registrado ("windows"/"linux") ou None."""
    if os.environ.get("MINDFORGE_SEM_INTEGRACAO") == "1" or not getattr(sys, "frozen", False):
        return None
    if sys.platform == "darwin":
        return None
    if settings is None:
        from PySide6.QtCore import QSettings
        settings = QSettings()
    stamp = f"{__version__}|{sys.executable}"
    if settings.value("integration/stamp", "") == stamp:
        return None
    command = executable_command()
    try:
        if sys.platform.startswith("win"):
            register_windows(command, doc_icon("mfmap.ico"))
            done = "windows"
        else:
            register_linux(command)
            done = "linux"
    except Exception:      # nunca impede o app de abrir
        return None
    settings.setValue("integration/stamp", stamp)
    return done
