@echo off
REM Gera o instalável no Windows.  Uso:  build.bat
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
set QT_QPA_PLATFORM=offscreen
python -m pytest || exit /b 1
set QT_QPA_PLATFORM=
rmdir /s /q build dist 2>nul
pyinstaller mindforge.spec --noconfirm
echo Pronto: dist\MindForge\MindForge.exe
