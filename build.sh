#!/usr/bin/env bash
# Gera o instalável no macOS ou Linux.  Uso:  ./build.sh
#   Usa o ambiente virtual que já estiver ativo; se nenhum estiver, cria .venv na pasta.
#   ./build.sh --sem-testes   pula os testes automatizados
set -euo pipefail
cd "$(dirname "$0")"

if [ -z "${VIRTUAL_ENV:-}" ]; then
  [ -d .venv ] || python3 -m venv .venv
  source .venv/bin/activate
fi
echo "==> Ambiente: ${VIRTUAL_ENV}"
python -m pip install --upgrade pip -q
pip install -r requirements-dev.txt -q

if [ "${1:-}" != "--sem-testes" ]; then
  echo "==> Rodando os testes"
  QT_QPA_PLATFORM=offscreen python -m pytest
fi

echo "==> Gerando o aplicativo"
rm -rf build dist
pyinstaller mindforge.spec --noconfirm

if [ "$(uname)" = "Darwin" ]; then
  echo "==> Gerando o instalador .dmg"
  hdiutil create -volname MindForge -srcfolder dist/MindForge.app -ov -format UDZO dist/MindForge.dmg
  echo "Pronto: dist/MindForge.app e dist/MindForge.dmg"
else
  echo "Pronto: dist/MindForge/MindForge"
fi
