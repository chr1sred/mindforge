"""Leitura e gravação do formato .mfmap (JSON versionado, UTF-8).

* Gravação atômica: escreve num arquivo temporário na mesma pasta,
  força o flush em disco e só então substitui o original (os.replace).
  Uma queda de energia no meio nunca deixa o arquivo pela metade.
* Migração: cada versão do esquema tem uma função que converte para a próxima.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Callable

from mindforge import __version__
from mindforge.model.topic import SCHEMA_VERSION, MindMap

FORMAT_ID = "mindforge"


class MindForgeFileError(Exception):
    """Erro com mensagem amigável (em português) para exibir ao usuário."""


# Exemplo de como futuras migrações serão registradas:
#   MIGRATIONS[1] = lambda data: {...data convertida para o esquema 2...}
MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


def map_to_document(m: MindMap) -> dict:
    return {
        "format": FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "app_version": __version__,
        "map": m.to_dict(),
    }


def document_to_map(data: dict) -> MindMap:
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID:
        raise MindForgeFileError("Este arquivo não é um mapa do MindForge.")
    version = data.get("schema_version", 1)
    if not isinstance(version, int):
        raise MindForgeFileError("Versão do arquivo inválida.")
    if version > SCHEMA_VERSION:
        raise MindForgeFileError(
            "Este mapa foi criado por uma versão mais nova do MindForge. "
            "Atualize o aplicativo para abri-lo.")
    while version < SCHEMA_VERSION:
        migrate = MIGRATIONS.get(version)
        if migrate is None:
            raise MindForgeFileError(f"Não há migração para a versão {version} do arquivo.")
        data = migrate(data)
        version += 1
    try:
        return MindMap.from_dict(data["map"])
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise MindForgeFileError(f"O arquivo está corrompido ou incompleto ({exc}).") from exc


def atomic_write_text(path: str, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".mfmap-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_map(m: MindMap, path: str) -> None:
    text = json.dumps(map_to_document(m), ensure_ascii=False, indent=1)
    try:
        atomic_write_text(path, text)
    except OSError as exc:
        raise MindForgeFileError(f"Não foi possível salvar o arquivo:\n{exc.strerror or exc}") from exc


def load_map(path: str) -> MindMap:
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise MindForgeFileError("Arquivo não encontrado.") from exc
    except UnicodeDecodeError as exc:
        raise MindForgeFileError("O arquivo não está em UTF-8 — não parece um mapa do MindForge.") from exc
    except json.JSONDecodeError as exc:
        raise MindForgeFileError(f"O arquivo está corrompido (JSON inválido na linha {exc.lineno}).") from exc
    except OSError as exc:
        raise MindForgeFileError(f"Não foi possível abrir o arquivo:\n{exc.strerror or exc}") from exc
    return document_to_map(data)
