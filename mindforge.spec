# -*- mode: python ; coding: utf-8 -*-
# Especificação do PyInstaller para gerar o MindForge instalável.
#
#   macOS  : pyinstaller mindforge.spec --noconfirm   ->  dist/MindForge.app
#   Windows: pyinstaller mindforge.spec --noconfirm   ->  dist/MindForge/MindForge.exe
#   Linux  : pyinstaller mindforge.spec --noconfirm   ->  dist/MindForge/MindForge
import os
import sys

sys.path.insert(0, os.path.abspath(SPECPATH))  # noqa: F821 (definido pelo PyInstaller)
from mindforge import __version__  # noqa: E402

APP = "MindForge"
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
ICON = "assets/icon.icns" if IS_MAC else ("assets/icon.ico" if IS_WIN else None)

# Módulos Qt que o app NÃO usa (reduz bastante o tamanho do pacote)
EXCLUDES = [
    "tkinter", "unittest", "pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech", "PySide6.QtHttpServer",
]

a = Analysis(
    ["run_mindforge.py"],
    pathex=["."],
    binaries=[],
    datas=[("assets/icon.png", "assets"), ("assets/fonts", "assets/fonts")],
    hiddenimports=["PySide6.QtSvg"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON,
    argv_emulation=False,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP}.app",
        icon=ICON,
        bundle_identifier="br.com.ccastro.mindforge",
        version=__version__,
        info_plist={
            "CFBundleName": APP,
            "CFBundleDisplayName": APP,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "C. Castro Media & Performance",
            # Idiomas da interface (Ajustes → Idioma / Language); deixa os diálogos nativos no idioma certo
            "CFBundleDevelopmentRegion": "pt_BR",
            "CFBundleLocalizations": ["pt-BR", "en"],
            "CFBundleAllowMixedLocalizations": True,
            # Associa arquivos .mfmap ao app (duplo clique no Finder abre no MindForge)
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Mapa MindForge",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
                "LSItemContentTypes": ["br.com.ccastro.mindforge.mfmap"],
                "CFBundleTypeExtensions": ["mfmap"],
            }],
            "UTExportedTypeDeclarations": [{
                "UTTypeIdentifier": "br.com.ccastro.mindforge.mfmap",
                "UTTypeDescription": "Mapa MindForge",
                "UTTypeConformsTo": ["public.json", "public.data"],
                "UTTypeTagSpecification": {"public.filename-extension": ["mfmap"]},
            }],
        },
    )
