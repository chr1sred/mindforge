"""Documento aberto: mapa + pilha de desfazer + caminho do arquivo.

Estratégia de desfazer: cada alteração registra um *retrato* (snapshot)
do mapa antes e depois. Isso garante que 100% das operações sejam
desfazíveis sem código específico por comando — impossível "esquecer"
de implementar o undo de uma funcionalidade nova.
"""
from __future__ import annotations

import uuid
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from mindforge.model.topic import MindMap

UNDO_LIMIT = 100


class SnapshotCommand(QUndoCommand):
    MERGE_ID = 4242

    def __init__(self, doc: "Document", label: str, before: dict, after: dict,
                 sel_before: list, sel_after: list, merge_key: Optional[str]):
        super().__init__(label)
        self.doc = doc
        self.before, self.after = before, after
        self.sel_before, self.sel_after = sel_before, sel_after
        self.merge_key = merge_key
        self._skip_first_redo = True

    def id(self) -> int:  # noqa: A003 (API do Qt)
        return self.MERGE_ID if self.merge_key else -1

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, SnapshotCommand) and other.merge_key == self.merge_key:
            self.after = other.after
            self.sel_after = other.sel_after
            return True
        return False

    def redo(self) -> None:
        if self._skip_first_redo:          # a operação já foi aplicada ao vivo
            self._skip_first_redo = False
            return
        self.doc._restore(self.after, self.sel_after)

    def undo(self) -> None:
        self.doc._restore(self.before, self.sel_before)


class Document(QObject):
    changed = Signal()                  # o mapa mudou: a cena deve sincronizar
    selection_requested = Signal(list)  # ids a selecionar após desfazer/refazer
    modified_changed = Signal(bool)

    def __init__(self, mind_map: Optional[MindMap] = None, path: Optional[str] = None,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.map = mind_map or MindMap()
        self.path = path
        self.uid = uuid.uuid4().hex
        self.revision = 0
        self._force_dirty = False
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(UNDO_LIMIT)
        self.undo_stack.cleanChanged.connect(self._on_clean_changed)
        self.selection_provider: Callable[[], list] = lambda: []

    # ---------------------------------------------------------------- estado
    def _on_clean_changed(self, _clean: bool) -> None:
        try:
            self.modified_changed.emit(self.is_modified())
        except RuntimeError:     # objeto já destruído ao encerrar o app
            pass

    def is_modified(self) -> bool:
        return self._force_dirty or not self.undo_stack.isClean()

    def set_force_dirty(self, value: bool) -> None:
        self._force_dirty = value
        self.modified_changed.emit(self.is_modified())

    def mark_saved(self, path: Optional[str] = None) -> None:
        if path:
            self.path = path
        self._force_dirty = False
        self.undo_stack.setClean()
        self.modified_changed.emit(False)

    def is_pristine(self) -> bool:
        """Documento novo, sem arquivo e sem alterações (pode ser reaproveitado)."""
        return self.path is None and not self.is_modified() and self.undo_stack.count() == 0

    # ------------------------------------------------------------- alterações
    def apply(self, label: str, fn: Callable[[MindMap], object],
              select: Optional[Callable[[object], list] | list] = None,
              merge_key: Optional[str] = None):
        """Executa ``fn(map)`` como uma alteração desfazível.

        * Se ``fn`` levantar exceção, o mapa volta ao estado anterior.
        * Se nada mudou, nenhum comando é registrado.
        """
        before = self.map.to_dict()
        sel_before = list(self.selection_provider())
        try:
            result = fn(self.map)
        except Exception:
            self.map = MindMap.from_dict(before)
            self.changed.emit()
            raise
        after = self.map.to_dict()
        if callable(select):
            sel_after = list(select(result) or [])
        elif select is not None:
            sel_after = list(select)
        else:
            sel_after = sel_before
        if after == before:
            if sel_after != sel_before:
                self.selection_requested.emit(sel_after)
            return result
        self.revision += 1
        self.undo_stack.push(SnapshotCommand(self, label, before, after, sel_before, sel_after, merge_key))
        self.changed.emit()
        self.selection_requested.emit(sel_after)
        return result

    def _restore(self, state: dict, selection: list) -> None:
        self.map = MindMap.from_dict(state)
        self.revision += 1
        self.changed.emit()
        self.selection_requested.emit(list(selection))

    def replace_map(self, mind_map: MindMap) -> None:
        """Troca o mapa inteiro sem histórico (ao abrir/recuperar arquivo)."""
        self.map = mind_map
        self.undo_stack.clear()
        self.revision += 1
        self.changed.emit()
