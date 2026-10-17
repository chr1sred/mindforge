"""Área de edição: visualização da cena + controlador das ações do usuário.

Pontos de robustez tratados aqui:
* Máquina de estados de foco: durante a edição de texto, as teclas vão
  para o editor (Delete apaga letra, Ctrl+C copia texto, Ctrl+Z desfaz
  digitação) e não disparam os atalhos do mapa.
* Espaço: soltar sem arrastar = editar o tópico; segurar e arrastar = mover a tela.
* Tab nunca é "roubado" pela navegação de foco do Qt.
"""
from __future__ import annotations

import json
import math
import sys
import time
from typing import Optional

from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QFont, QGuiApplication, QKeyEvent, QPainter, QPen, QTransform
from PySide6.QtWidgets import (
    QGraphicsLineItem, QGraphicsView, QInputDialog, QMessageBox,
)

from mindforge.document import Document
from mindforge.i18n import N_, ntr, tr
from mindforge.model import ops
from mindforge.model.topic import Topic
from mindforge.view.items import EditorItem, RelationItem
from mindforge.view.painting import text_rect
from mindforge.view.scene import MindScene

MIME_TOPICS = "application/x-mindforge-topics"
ZOOM_MIN, ZOOM_MAX = 0.1, 4.0
RIGHT_DRAG_THRESHOLD = 4          # px que o mouse precisa andar para virar "arrasto"

# Atalhos de janela que continuam funcionando mesmo durante a edição de texto
_PASS_THROUGH = {Qt.Key.Key_S, Qt.Key.Key_N, Qt.Key.Key_O, Qt.Key.Key_E, Qt.Key.Key_W,
                 Qt.Key.Key_Q, Qt.Key.Key_F, Qt.Key.Key_P, Qt.Key.Key_Equal, Qt.Key.Key_Plus,
                 Qt.Key.Key_Minus, Qt.Key.Key_0, Qt.Key.Key_1}


class MindCanvas(QGraphicsView):
    status_message = Signal(str)
    zoom_changed = Signal(float)
    current_changed = Signal()
    context_menu_requested = Signal(object, object)   # (tid | None, posição global)
    editing_changed = Signal(bool)

    def __init__(self, doc: Document, parent=None):
        self.doc = doc
        self.mscene = MindScene(doc)
        super().__init__(self.mscene, parent)
        self.mscene.setParent(self)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        # tela "infinita": sem barras de rolagem (rolagem/trackpad continuam movendo a tela)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().grabGesture(Qt.GestureType.PinchGesture)

        self.editor: Optional[EditorItem] = None
        self.current_id: Optional[str] = None
        self.zoom = 1.0
        self._space_down = False
        self._space_used = False
        self._panning = False
        self._pan_last = QPointF()
        self._rpress: Optional[QPointF] = None      # botão direito pressionado (clique ou arrasto?)
        self._rdragging = False
        self._ctx_suppress_until = 0.0
        self._pending_merge: Optional[tuple[str, str]] = None
        self._merge_seq = 0
        self.relation_source: Optional[str] = None
        self._rel_line: Optional[QGraphicsLineItem] = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(25)
        self._preview_timer.timeout.connect(self._apply_preview)

        doc.changed.connect(self._on_doc_changed)
        doc.selection_requested.connect(self.select_ids)
        doc.selection_provider = self.selected_ids
        sc = self.mscene
        sc.selectionChanged.connect(self._on_selection_changed)
        sc.edit_requested.connect(lambda tid: self.start_edit(tid))
        sc.collapse_requested.connect(lambda tid: self.toggle_collapse([tid]))
        sc.expand_all_requested.connect(self.expand_all_from)
        sc.topics_dropped.connect(self._on_drop)
        sc.floating_moved.connect(self._on_floating_moved)
        sc.background_double_clicked.connect(self.add_floating)
        sc.relation_edit_requested.connect(self.edit_relation_label)
        self._on_doc_changed()
        self.select_ids([doc.map.root.id], center=False)
        QTimer.singleShot(0, self.center_on_root)

    # ============================================================== sincronismo
    def _on_doc_changed(self) -> None:
        if self.editor is not None and self.doc.map.find(self.editor.tid) is None:
            self._discard_editor()
        overrides = {self.editor.tid: self.editor.toPlainText() or " "} if self.editor else None
        self.mscene.sync(overrides)
        self.setBackgroundBrush(QColor(self.mscene.background_color))
        if self.editor:
            self._place_editor()

    def center_on_root(self) -> None:
        it = self.mscene.topic_items.get(self.doc.map.root.id)
        if it is not None:
            self.centerOn(it.sceneBoundingRect().center())

    # ================================================================== seleção
    def selected_ids(self) -> list[str]:
        ids = self.mscene.selected_topic_ids()
        if self.current_id in ids:      # o "atual" vai por último (é o foco)
            ids.remove(self.current_id)
            ids.append(self.current_id)
        return ids

    def current(self) -> Optional[str]:
        ids = self.mscene.selected_topic_ids()
        if self.current_id in ids:
            return self.current_id
        return ids[0] if ids else None

    def current_topic(self) -> Optional[Topic]:
        return self.doc.map.find(self.current())

    def select_ids(self, ids, center: bool = False) -> None:
        ids = [i for i in ids if i in self.mscene.topic_items]
        self.current_id = ids[-1] if ids else None
        self.mscene.select_ids(ids)
        if self.current_id:
            self.ensure_visible(self.current_id, center)

    def select_id(self, tid: str, center: bool = False) -> None:
        self.select_ids([tid], center)

    def _on_selection_changed(self) -> None:
        ids = self.mscene.selected_topic_ids()
        if self.current_id not in ids:
            self.current_id = ids[0] if ids else None
        self.current_changed.emit()

    def ensure_visible(self, tid: str, center: bool = False) -> None:
        it = self.mscene.topic_items.get(tid)
        if it is None:
            return
        if center:
            self.centerOn(it.sceneBoundingRect().center())
        else:
            self.ensureVisible(it.mapRectToScene(it.box_rect()), 60, 60)

    def select_all(self) -> None:
        self.select_ids(list(self.mscene.topic_items))

    # ============================================================ criar tópicos
    def _next_merge_key(self) -> str:
        self._merge_seq += 1
        return f"new:{id(self)}:{self._merge_seq}"

    def _create_and_edit(self, label: str, fn) -> None:
        key = self._next_merge_key()
        try:
            tid = self.doc.apply(label, lambda m: fn(m).id, select=lambda r: [r], merge_key=key)
        except ops.OpError as exc:
            self.status_message.emit(str(exc))
            return
        self._pending_merge = (tid, key)
        self.start_edit(tid)

    def add_child(self) -> None:
        self.commit_edit()
        parent = self.current() or self.doc.map.root.id
        self._create_and_edit(N_("Adicionar subtópico"), lambda m: ops.add_child(m, parent))

    def add_sibling(self, before: bool = False) -> None:
        self.commit_edit()
        cur = self.current() or self.doc.map.root.id
        label = tr("Adicionar tópico irmão")
        self._create_and_edit(label, lambda m: ops.add_sibling(m, cur, before=before))

    def add_parent(self) -> None:
        """Ctrl+Enter: insere um tópico entre o selecionado e o pai dele."""
        self.commit_edit()
        cur = self.current()
        t = self.doc.map.find(cur)
        if t is None or t.parent is None:
            self.status_message.emit(tr("Selecione um tópico que tenha pai para inserir um tópico pai."))
            return
        self._create_and_edit(N_("Inserir tópico pai"), lambda m: ops.insert_parent(m, cur))

    def add_floating(self, scene_pos: Optional[QPointF] = None) -> None:
        self.commit_edit()
        if scene_pos is None or not isinstance(scene_pos, QPointF):
            scene_pos = self.mapToScene(self.viewport().rect().center())
        x, y = scene_pos.x() - 50, scene_pos.y() - 16
        self._create_and_edit(N_("Adicionar tópico flutuante"), lambda m: ops.add_floating(m, x, y))

    # ================================================================== excluir
    def delete_selected(self) -> None:
        self.commit_edit()
        rels = self.mscene.selected_relation_ids()
        ids = self.mscene.selected_topic_ids()
        if rels and not ids:
            self.doc.apply(N_("Excluir relação"), lambda m: ops.delete_relations(m, rels), select=[])
            return
        if not ids:
            return
        if ids == [self.doc.map.root.id]:
            self.status_message.emit(tr("O tópico central não pode ser excluído."))
            return
        try:
            def fn(m):
                ops.delete_relations(m, rels)
                return ops.delete_topics(m, ids)
            self.doc.apply(N_("Excluir tópico"), fn, select=lambda r: [r] if r else [])
        except ops.OpError as exc:
            self.status_message.emit(str(exc))

    # ============================================================== edição texto
    def start_edit(self, tid: Optional[str] = None, replace_text: Optional[str] = None) -> None:
        if self.editor is not None:
            self.commit_edit()
        tid = tid or self.current()
        if tid is None or tid not in self.mscene.topic_items:
            return
        topic = self.doc.map.find(tid)
        item = self.mscene.topic_items[tid]
        if topic is None or item.vis is None:
            return
        if self.current() != tid:
            self.select_id(tid)
        ed = EditorItem(self, tid, topic.text)
        ed.setFont(item.vis.font)
        ed.setDefaultTextColor(QColor(item.vis.style.text_color))
        ed.set_alignment("left")     # durante a digitação o texto cresce a partir da esquerda
        f = QFont(item.vis.font)
        f.setStrikeOut(item.vis.style.strike)
        ed.setFont(f)
        ed.setPlainText(topic.text if replace_text is None else replace_text)
        self.mscene.addItem(ed)
        self.editor = ed
        cursor = ed.textCursor()
        if replace_text is None:
            cursor.select(cursor.SelectionType.Document)
        else:
            cursor.movePosition(cursor.MoveOperation.End)
        ed.setTextCursor(cursor)
        ed.document().contentsChanged.connect(self._on_editor_changed)
        self.mscene.sync({tid: ed.toPlainText() or " "})
        self._place_editor()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.mscene.setFocusItem(ed, Qt.FocusReason.OtherFocusReason)
        self.ensure_visible(tid)
        self.editing_changed.emit(True)

    def is_editing(self) -> bool:
        return self.editor is not None

    def _on_editor_changed(self) -> None:
        if self.editor is not None:
            ed = self.editor
            item = self.mscene.topic_items.get(ed.tid)
            if item and item.vis:
                ideal = ed.document().idealWidth()
                maxw = item.vis.style.max_text_width + 4
                ed.setTextWidth(maxw if ideal > maxw else -1)
            self._preview_timer.start()

    def _apply_preview(self) -> None:
        if self.editor is not None:
            self.mscene.sync({self.editor.tid: self.editor.toPlainText() or " "})
            self._place_editor()

    def _place_editor(self) -> None:
        ed = self.editor
        item = self.mscene.topic_items.get(ed.tid) if ed else None
        if ed is None or item is None or item.vis is None:
            return
        tr = item.mapRectToScene(text_rect(item.vis))
        ed.setPos(tr.topLeft() - QPointF(1, 1))

    def _discard_editor(self) -> Optional[EditorItem]:
        ed = self.editor
        if ed is None:
            return None
        self.editor = None
        self._preview_timer.stop()
        try:
            ed.document().contentsChanged.disconnect(self._on_editor_changed)
        except (RuntimeError, TypeError):
            pass
        if ed.scene() is not None:
            ed.scene().removeItem(ed)
        self.editing_changed.emit(False)
        return ed

    def commit_edit(self, refocus: bool = True) -> None:
        ed = self._discard_editor()
        if ed is None:
            return
        text = ed.toPlainText().strip()
        if not text:
            text = ed.original
        merge = self._pending_merge[1] if self._pending_merge and self._pending_merge[0] == ed.tid else None
        self._pending_merge = None
        if text != ed.original and self.doc.map.find(ed.tid) is not None:
            self.doc.apply(N_("Editar texto"), lambda m: ops.set_text(m, ed.tid, text),
                           select=[ed.tid], merge_key=merge)
        else:
            self.mscene.sync()
        if refocus:
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def cancel_edit(self) -> None:
        ed = self._discard_editor()
        self._pending_merge = None
        if ed is not None:
            self.mscene.sync()
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    def schedule_commit_on_blur(self, ed: EditorItem) -> None:
        QTimer.singleShot(0, lambda: self.commit_edit(refocus=False) if self.editor is ed else None)

    # ================================================================ navegação
    def navigate(self, direction: str) -> None:
        cur = self.current()
        items = self.mscene.topic_items
        if cur is None or cur not in items:
            self.select_id(self.doc.map.root.id)
            return
        dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[direction]
        c0 = items[cur].mapRectToScene(items[cur].box_rect()).center()
        best, best_score = None, math.inf
        for tid, it in items.items():
            if tid == cur:
                continue
            c = it.mapRectToScene(it.box_rect()).center()
            vx, vy = c.x() - c0.x(), c.y() - c0.y()
            along = vx * dx + vy * dy
            if along <= 2:
                continue
            perp = abs(vx * dy - vy * dx)
            if perp > along * 2.2 + 30:
                continue
            score = along + perp * 2.5
            if score < best_score:
                best, best_score = tid, score
        if best:
            self.select_id(best)

    def move_sibling(self, delta: int) -> None:
        self.commit_edit()
        cur = self.current()
        if cur:
            self.doc.apply(N_("Mover tópico"), lambda m: ops.reorder(m, cur, delta), select=[cur])

    # ================================================================ estrutura
    def toggle_collapse(self, ids: Optional[list] = None) -> None:
        self.commit_edit()
        ids = ids or self.mscene.selected_topic_ids()
        if not ids:
            return
        def fn(m):
            ops.toggle_collapse(m, ids)
            return self._visible_selection(m, ids)
        self.doc.apply(N_("Recolher/expandir"), fn, select=lambda sel: sel)

    def _visible_selection(self, m, toggled: list) -> list:
        """Seleção depois de recolher: quem ficou escondido passa a seleção para o tópico recolhido."""
        out: list = []
        for tid in list(self.mscene.selected_topic_ids()) + list(toggled):
            t = m.find(tid)
            if t is None:
                continue
            hidden_by = None
            for a in t.ancestors():
                if a.collapsed:
                    hidden_by = a
            target = hidden_by.id if hidden_by is not None else tid
            if target not in out:
                out.append(target)
        return [x for x in out if x in toggled] or out

    def expand_all_from(self, tid: str) -> None:
        self.commit_edit()
        self.doc.apply(N_("Expandir ramo"), lambda m: ops.expand_subtree(m, tid), select=[tid])

    def set_collapsed_all(self, collapsed: bool) -> None:
        self.commit_edit()
        label = tr("Recolher tudo") if collapsed else tr("Expandir tudo")
        keep = [i for i in self.selected_ids()]
        self.doc.apply(label, lambda m: ops.set_collapsed_all(m, collapsed), select=keep)

    def reveal(self, tid: str) -> None:
        """Expande ancestrais recolhidos e seleciona (usado pela busca)."""
        t = self.doc.map.find(tid)
        if t is None:
            return
        if any(a.collapsed for a in t.ancestors()):
            self.doc.apply(N_("Expandir ramo"), lambda m: ops.expand_ancestors(m, tid), select=[tid])
        self.select_id(tid, center=True)

    def _on_drop(self, ids: list, target: str) -> None:
        def fn(m):
            for tid in ids:
                ops.move_topic(m, tid, target)
        try:
            self.doc.apply(N_("Mover tópico"), fn, select=ids)
        except ops.OpError as exc:
            self.status_message.emit(str(exc))
            self.mscene.sync()

    def _on_floating_moved(self, moves: list) -> None:
        def fn(m):
            for tid, x, y in moves:
                ops.set_floating_pos(m, tid, x, y)
        self.doc.apply(N_("Mover tópico flutuante"), fn)

    # =========================================================== área de transf.
    def copy(self) -> bool:
        m = self.doc.map
        topics = ops.top_level_selection(m, self.mscene.selected_topic_ids())
        if not topics:
            return False
        data = QMimeData()
        data.setData(MIME_TOPICS, json.dumps([t.to_dict() for t in topics], ensure_ascii=False).encode("utf-8"))
        data.setText(ops.to_outline(topics))
        QGuiApplication.clipboard().setMimeData(data)
        self.status_message.emit(ntr("{n} tópico copiado.", "{n} tópicos copiados.", len(topics)))
        return True

    def cut(self) -> None:
        self.commit_edit()
        if self.mscene.selected_topic_ids() == [self.doc.map.root.id]:
            self.status_message.emit(tr("O tópico central não pode ser recortado."))
            return
        if self.copy():
            self.delete_selected()

    def paste(self) -> None:
        self.commit_edit()
        md = QGuiApplication.clipboard().mimeData()
        topics: list[Topic] = []
        if md is not None and md.hasFormat(MIME_TOPICS):
            try:
                raw = json.loads(bytes(md.data(MIME_TOPICS)).decode("utf-8"))
                topics = [Topic.from_dict(d) for d in raw]
            except (ValueError, TypeError, KeyError):
                topics = []
        if not topics and md is not None and md.hasText():
            topics = ops.parse_outline(md.text())
        if not topics:
            self.status_message.emit(tr("Nada para colar."))
            return
        parent = self.current()
        at = None
        if parent is None:
            c = self.mapToScene(self.viewport().rect().center())
            at = (c.x(), c.y())
        self.doc.apply(N_("Colar"), lambda m: ops.paste_topics(m, parent, topics, at), select=lambda r: r)

    def duplicate(self) -> None:
        self.commit_edit()
        ids = self.mscene.selected_topic_ids()
        if ids:
            self.doc.apply(N_("Duplicar"), lambda m: ops.duplicate(m, ids), select=lambda r: r or ids)

    # ================================================================= relações
    def start_relation(self) -> None:
        self.commit_edit()
        cur = self.current()
        if cur is None:
            self.status_message.emit(tr("Selecione o tópico de origem da relação."))
            return
        self.relation_source = cur
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.status_message.emit(tr("Clique no tópico de destino da relação (Esc cancela)."))

    def _end_relation_mode(self) -> None:
        self.relation_source = None
        if self._rel_line is not None:
            self.mscene.removeItem(self._rel_line)
            self._rel_line = None
        self.viewport().unsetCursor()
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def edit_relation_label(self, rid: str) -> None:
        rel = next((r for r in self.doc.map.relations if r.id == rid), None)
        if rel is None:
            return
        text, ok = QInputDialog.getText(self, tr("Rótulo da relação"), tr("Texto da relação:"), text=rel.label)
        if ok:
            self.doc.apply(N_("Rótulo da relação"), lambda m: ops.set_relation_label(m, rid, text.strip()))

    # ===================================================================== zoom
    def set_zoom(self, z: float, anchor_view_center: bool = False) -> None:
        z = max(ZOOM_MIN, min(ZOOM_MAX, z))
        if anchor_view_center:
            old = self.transformationAnchor()
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setTransform(QTransform.fromScale(z, z))
        if anchor_view_center:
            self.setTransformationAnchor(old)
        self.zoom = z
        self.mscene.set_view_scale(z)
        self.zoom_changed.emit(z)

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom * 1.2, True)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom / 1.2, True)

    def zoom_reset(self) -> None:
        self.set_zoom(1.0, True)
        if self.current():
            self.ensure_visible(self.current(), center=True)

    def zoom_fit(self) -> None:
        rect = self.mscene.content_rect()
        if rect.isNull():
            return
        vr = self.viewport().rect()
        rect = rect.adjusted(-40, -40, 40, 40)
        z = min(vr.width() / rect.width(), vr.height() / rect.height(), 1.25)
        self.set_zoom(z)
        self.centerOn(rect.center())

    # ================================================================== teclado
    def focusNextPrevChild(self, nxt: bool) -> bool:
        return False   # Tab é atalho de "novo subtópico", não troca de foco

    def event(self, e) -> bool:
        if e.type() == QEvent.Type.ShortcutOverride and self.editor is not None:
            mods = e.modifiers()
            cmd = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
            if not (cmd and e.key() in _PASS_THROUGH):
                e.accept()        # a tecla vai para o editor de texto
                return True
        return super().event(e)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if self.editor is not None:
            super().keyPressEvent(e)
            return
        key = e.key()
        mods = e.modifiers()
        if key == Qt.Key.Key_Space:
            if not e.isAutoRepeat():
                self._space_down = True
                self._space_used = False
                self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            e.accept()
            return
        if key == Qt.Key.Key_Escape:
            if self.relation_source:
                self._end_relation_mode()
                self.status_message.emit("")
            e.accept()
            return
        text = e.text()
        blocked = mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
                          | Qt.KeyboardModifier.AltModifier)
        if text and text.isprintable() and not blocked and self.current():
            self.start_edit(self.current(), replace_text=text)
            e.accept()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat() and self._space_down and self.editor is None:
            self._space_down = False
            if not self._panning:
                self.viewport().unsetCursor()
            if not self._space_used:
                self.start_edit()
            e.accept()
            return
        super().keyReleaseEvent(e)

    # ==================================================================== mouse
    # ------------------------------------------------------- mover o quadro
    def _pan_by(self, dx: float, dy: float) -> None:
        """Move a visualização; se chegar no limite do quadro, o quadro cresce (tela "infinita")."""
        hb, vb = self.horizontalScrollBar(), self.verticalScrollBar()
        nh, nv = hb.value() - dx, vb.value() - dy
        if nh < hb.minimum() or nh > hb.maximum() or nv < vb.minimum() or nv > vb.maximum():
            vis = self.mapToScene(self.viewport().rect()).boundingRect()
            k = 1.0 / max(self.zoom, 1e-6)
            self.mscene.grow_bounds(vis.translated(-dx * k, -dy * k).adjusted(-400, -400, 400, 400))
        hb.setValue(int(round(hb.value() - dx)))
        vb.setValue(int(round(vb.value() - dy)))

    def _start_pan(self, pos) -> None:
        self._panning = True
        self._pan_last = pos
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def _end_pan(self) -> None:
        self._panning = False
        if self._space_down:
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.viewport().unsetCursor()

    def _is_mac_ctrl_click(self, e) -> bool:
        # No Mac, Control+clique é o "clique secundário" de quem tem um botão só (Qt chama de Meta)
        return sys.platform == "darwin" and e.button() == Qt.MouseButton.LeftButton and \
            bool(e.modifiers() & Qt.KeyboardModifier.MetaModifier)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            # Botão direito: decide no SOLTAR se foi clique (menu) ou arrasto (mover o quadro).
            self.commit_edit()
            self._rpress = e.position()
            self._rdragging = False
            e.accept()
            return
        if self._is_mac_ctrl_click(e):
            self._open_context_menu(e.position().toPoint())
            e.accept()
            return
        if e.button() == Qt.MouseButton.MiddleButton or \
                (e.button() == Qt.MouseButton.LeftButton and self._space_down):
            self.commit_edit()
            self._space_used = True
            self._start_pan(e.position())
            e.accept()
            return
        if self.relation_source and e.button() == Qt.MouseButton.LeftButton:
            target = self.mscene.topic_at(self.mapToScene(e.position().toPoint()))
            src = self.relation_source
            self._end_relation_mode()
            if target is not None and target.tid != src:
                self.doc.apply(N_("Adicionar relação"), lambda m: ops.add_relation(m, src, target.tid))
                self.status_message.emit(tr("Relação criada. Dê duplo clique na linha para nomeá-la."))
            else:
                self.status_message.emit("")
            e.accept()
            return
        super().mousePressEvent(e)
        if e.button() == Qt.MouseButton.LeftButton:
            it = self.mscene.topic_at(self.mapToScene(e.position().toPoint()))
            if it is not None and it.isSelected():
                self.current_id = it.tid
                self.current_changed.emit()

    def mouseMoveEvent(self, e) -> None:
        if self._rpress is not None:
            if not self._rdragging:
                if (e.position() - self._rpress).manhattanLength() < RIGHT_DRAG_THRESHOLD:
                    e.accept()
                    return
                self._rdragging = True
                self._start_pan(self._rpress)
        if self._panning:
            d = e.position() - self._pan_last
            self._pan_last = e.position()
            self._pan_by(d.x(), d.y())
            e.accept()
            return
        if self.relation_source:
            src = self.mscene.topic_items.get(self.relation_source)
            if src is not None:
                p0 = src.mapRectToScene(src.box_rect()).center()
                p1 = self.mapToScene(e.position().toPoint())
                if self._rel_line is None:
                    self._rel_line = QGraphicsLineItem()
                    pen = QPen(QColor(self.mscene.selection_color), 1.6, Qt.PenStyle.DashLine)
                    self._rel_line.setPen(pen)
                    self._rel_line.setZValue(50)
                    self.mscene.addItem(self._rel_line)
                self._rel_line.setLine(p0.x(), p0.y(), p1.x(), p1.y())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.RightButton and self._rpress is not None:
            dragged = self._rdragging
            press = self._rpress
            self._rpress = None
            self._rdragging = False
            # o Windows manda o pedido de menu DEPOIS de soltar: ignoramos esse eco
            self._ctx_suppress_until = time.monotonic() + 0.4
            if dragged:
                self._end_pan()
            else:
                self._open_context_menu(press.toPoint())
            e.accept()
            return
        if self._panning and e.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._end_pan()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e) -> None:
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            dy = e.angleDelta().y() or e.pixelDelta().y()
            if dy:
                self.set_zoom(self.zoom * (1.0015 ** dy))
            e.accept()
            return
        super().wheelEvent(e)

    def viewportEvent(self, e) -> bool:
        # Pinça do trackpad do Mac
        if e.type() == QEvent.Type.NativeGesture and \
                e.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.set_zoom(self.zoom * (1.0 + e.value()))
            return True
        return super().viewportEvent(e)

    def contextMenuEvent(self, e) -> None:
        # O menu do mouse é aberto por nós ao soltar o botão direito (ver mouseReleaseEvent).
        # Aqui só tratamos: tecla de menu do teclado e cliques secundários que não passaram
        # pelo botão direito (ex.: toque com dois dedos em alguns trackpads).
        if e.reason() == QContextMenuEvent.Reason.Keyboard:
            cur = self.current()
            it = self.mscene.topic_items.get(cur) if cur else None
            pos = self.mapFromScene(it.mapRectToScene(it.box_rect()).center()) if it else self.viewport().rect().center()
            self._open_context_menu(pos)
        elif self._rpress is None and time.monotonic() > self._ctx_suppress_until:
            self._open_context_menu(e.pos())
        e.accept()

    def _open_context_menu(self, vpos) -> None:
        self.commit_edit()
        scene_pos = self.mapToScene(vpos)
        it = self.mscene.topic_at(scene_pos)
        if it is not None and not it.isSelected():
            self.select_id(it.tid)
        elif it is not None:
            self.current_id = it.tid
        if it is None:
            for x in self.mscene.items(scene_pos):
                if isinstance(x, RelationItem):
                    self.mscene.clearSelection()
                    x.setSelected(True)
                    break
        self.context_menu_requested.emit(it.tid if it else None, self.viewport().mapToGlobal(vpos))

    # ============================================================== utilitários
    def confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

