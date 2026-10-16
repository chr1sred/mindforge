"""Salvamento automático para recuperação após falhas.

Cada documento aberto e modificado grava periodicamente um arquivo na
pasta de recuperação. Ao salvar ou fechar normalmente, o arquivo é
apagado. Se o app fechar de forma inesperada, os arquivos restantes são
oferecidos para recuperação na próxima abertura.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from mindforge.storage.fileio import atomic_write_text, document_to_map, map_to_document
from mindforge.model.topic import MindMap


@dataclass
class RecoveryEntry:
    uid: str
    file: str
    original_path: Optional[str]
    saved_at: float
    title: str

    def load(self) -> MindMap:
        with open(self.file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return document_to_map(data["document"])


class RecoveryManager:
    def __init__(self, directory: str):
        self.directory = directory

    def _file(self, uid: str) -> str:
        return os.path.join(self.directory, f"{uid}.recovery.json")

    def write(self, uid: str, m: MindMap, original_path: Optional[str]) -> None:
        os.makedirs(self.directory, exist_ok=True)
        payload = {
            "uid": uid,
            "original_path": original_path,
            "saved_at": time.time(),
            "title": m.root.text.split("\n")[0][:80],
            "document": map_to_document(m),
        }
        atomic_write_text(self._file(uid), json.dumps(payload, ensure_ascii=False))

    def remove(self, uid: str) -> None:
        try:
            os.unlink(self._file(uid))
        except OSError:
            pass

    def entries(self) -> list[RecoveryEntry]:
        if not os.path.isdir(self.directory):
            return []
        out = []
        for name in sorted(os.listdir(self.directory)):
            if not name.endswith(".recovery.json"):
                continue
            path = os.path.join(self.directory, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                out.append(RecoveryEntry(str(data["uid"]), path, data.get("original_path"),
                                         float(data.get("saved_at", 0)), str(data.get("title", ""))))
            except (OSError, ValueError, KeyError, TypeError):
                # arquivo de recuperação danificado: descarta
                try:
                    os.unlink(path)
                except OSError:
                    pass
        return out
