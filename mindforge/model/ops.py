"""Operações sobre o mapa (funções puras que mutam o MindMap).

Cada função é chamada pelo ``Document.apply``, que tira um retrato do
estado antes e depois — assim TODA operação é desfazível por construção.
Funções levantam ``OpError`` quando a operação é inválida.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from mindforge.model.topic import MindMap, Relation, Topic

PRIORITY_MARKERS = ("prio1", "prio2", "prio3")
ALL_MARKERS = ("prio1", "prio2", "prio3", "feito", "estrela", "bandeira", "pergunta", "alerta")

DEFAULT_CHILD_TEXT = {0: "Tópico principal"}
DEFAULT_SUB_TEXT = "Subtópico"
DEFAULT_FLOATING_TEXT = "Tópico flutuante"


class OpError(Exception):
    pass


def _get(m: MindMap, tid: str) -> Topic:
    t = m.find(tid)
    if t is None:
        raise OpError(f"Tópico não encontrado: {tid}")
    return t


# ------------------------------------------------------------------ criar
def add_child(m: MindMap, parent_id: str, text: Optional[str] = None,
              index: Optional[int] = None) -> Topic:
    parent = _get(m, parent_id)
    parent.collapsed = False
    if text is None:
        text = DEFAULT_CHILD_TEXT[0] if parent is m.root else DEFAULT_SUB_TEXT
    return parent.add_child(Topic(text), index)


def add_sibling(m: MindMap, topic_id: str, before: bool = False,
                text: Optional[str] = None) -> Topic:
    t = _get(m, topic_id)
    if t.parent is None:                 # raiz ou flutuante: cria filho
        return add_child(m, topic_id, text)
    idx = t.index_in_parent() + (0 if before else 1)
    if text is None:
        text = DEFAULT_CHILD_TEXT[0] if t.parent is m.root else DEFAULT_SUB_TEXT
    return t.parent.add_child(Topic(text), idx)


def add_floating(m: MindMap, x: float, y: float, text: str = DEFAULT_FLOATING_TEXT) -> Topic:
    t = Topic(text, pos=(float(x), float(y)))
    m.floating.append(t)
    return t


# ---------------------------------------------------------------- excluir
def top_level_selection(m: MindMap, ids: Iterable[str]) -> list[Topic]:
    """Remove da seleção tópicos cujo ancestral também está selecionado."""
    topics = [t for t in (m.find(i) for i in ids) if t is not None]
    idset = {t.id for t in topics}
    out = []
    for t in topics:
        if not any(a.id in idset for a in t.ancestors()):
            out.append(t)
    return out


def delete_topics(m: MindMap, ids: Iterable[str]) -> Optional[str]:
    """Exclui tópicos (e seus ramos). Retorna o id sugerido para nova seleção."""
    topics = [t for t in top_level_selection(m, ids) if t is not m.root]
    if not topics:
        raise OpError("O tópico central não pode ser excluído.")
    next_sel: Optional[str] = None
    removed: set[str] = set()
    for t in topics:
        removed.update(x.id for x in t.walk())
        if t.parent is not None:
            sibs = t.parent.children
            i = sibs.index(t)
            if len(sibs) > 1:
                cand = sibs[i + 1] if i + 1 < len(sibs) else sibs[i - 1]
                next_sel = cand.id
            else:
                next_sel = t.parent.id
            t.detach()
        else:
            m.floating.remove(t)
            next_sel = m.root.id
    m.relations = [r for r in m.relations if r.source not in removed and r.target not in removed]
    if next_sel in removed:
        next_sel = m.root.id
    return next_sel


# ------------------------------------------------------------------ mover
def move_topic(m: MindMap, tid: str, new_parent_id: str, index: Optional[int] = None) -> None:
    t = _get(m, tid)
    new_parent = _get(m, new_parent_id)
    if t is m.root:
        raise OpError("O tópico central não pode ser movido.")
    if t is new_parent or t.is_ancestor_of(new_parent):
        raise OpError("Não é possível mover um tópico para dentro dele mesmo.")
    if t.parent is None:
        m.floating.remove(t)
    else:
        t.detach()
    new_parent.collapsed = False
    new_parent.add_child(t, index)


def reorder(m: MindMap, tid: str, delta: int) -> bool:
    t = _get(m, tid)
    if t.parent is None:
        return False
    sibs = t.parent.children
    i = sibs.index(t)
    j = max(0, min(len(sibs) - 1, i + delta))
    if i == j:
        return False
    sibs.insert(j, sibs.pop(i))
    return True


def set_floating_pos(m: MindMap, tid: str, x: float, y: float) -> None:
    t = _get(m, tid)
    if not m.is_floating_root(t):
        raise OpError("Somente tópicos flutuantes têm posição livre.")
    t.pos = (float(x), float(y))


def detach_to_floating(m: MindMap, tid: str, x: float, y: float) -> None:
    t = _get(m, tid)
    if t is m.root or t.parent is None:
        raise OpError("Tópico já é independente.")
    t.detach()
    t.pos = (float(x), float(y))
    m.floating.append(t)


# --------------------------------------------------------------- conteúdo
def set_text(m: MindMap, tid: str, text: str) -> None:
    _get(m, tid).text = text


def set_note(m: MindMap, tid: str, note: str) -> None:
    _get(m, tid).note = note


def toggle_collapse(m: MindMap, ids: Iterable[str], value: Optional[bool] = None) -> None:
    for tid in ids:
        t = _get(m, tid)
        if t is m.root or not t.children:
            continue
        t.collapsed = (not t.collapsed) if value is None else value


def set_collapsed_all(m: MindMap, collapsed: bool) -> None:
    for t in m.all_topics():
        if t is not m.root and t.children:
            # Recolher tudo: recolhe apenas os tópicos principais (como no XMind)
            if collapsed:
                t.collapsed = t.parent is m.root or m.is_floating_root(t)
            else:
                t.collapsed = False


def expand_ancestors(m: MindMap, tid: str) -> None:
    for a in _get(m, tid).ancestors():
        a.collapsed = False


def set_style(m: MindMap, ids: Iterable[str], key: str, value) -> None:
    for tid in ids:
        t = _get(m, tid)
        if value is None:
            t.style.pop(key, None)
        else:
            t.style[key] = value


def clear_style(m: MindMap, ids: Iterable[str]) -> None:
    for tid in ids:
        _get(m, tid).style.clear()


def toggle_marker(m: MindMap, ids: Iterable[str], marker: str) -> None:
    if marker not in ALL_MARKERS:
        raise OpError(f"Marcador desconhecido: {marker}")
    topics = [_get(m, i) for i in ids]
    turn_on = not all(marker in t.markers for t in topics)
    for t in topics:
        if turn_on:
            if marker in PRIORITY_MARKERS:
                t.markers = [x for x in t.markers if x not in PRIORITY_MARKERS]
            if marker not in t.markers:
                t.markers.append(marker)
        else:
            t.markers = [x for x in t.markers if x != marker]


def set_layout(m: MindMap, layout: str) -> None:
    m.layout = layout


def set_theme(m: MindMap, theme: str) -> None:
    m.theme = theme


def set_map_setting(m: MindMap, key: str, value) -> None:
    from mindforge.model.topic import MAP_SETTINGS_DEFAULTS
    if key not in MAP_SETTINGS_DEFAULTS:
        raise OpError(f"Configuração desconhecida: {key}")
    if value is None or value == MAP_SETTINGS_DEFAULTS[key]:
        m.settings.pop(key, None)
    else:
        m.settings[key] = value


def insert_parent(m: MindMap, tid: str, text: Optional[str] = None) -> Topic:
    """Insere um novo tópico entre o tópico e seu pai (Ctrl+Enter no XMind)."""
    t = _get(m, tid)
    if t.parent is None:
        raise OpError("O tópico central e os flutuantes não têm pai.")
    parent = t.parent
    idx = t.index_in_parent()
    t.detach()
    new = Topic(text or (DEFAULT_CHILD_TEXT[0] if parent is m.root else DEFAULT_SUB_TEXT))
    parent.add_child(new, idx)
    new.add_child(t)
    return new


# -------------------------------------------------------------- relações
def add_relation(m: MindMap, source: str, target: str, label: str = "") -> Relation:
    _get(m, source)
    _get(m, target)
    if source == target:
        raise OpError("Uma relação precisa ligar dois tópicos diferentes.")
    r = Relation(source, target, label)
    m.relations.append(r)
    return r


def delete_relations(m: MindMap, rel_ids: Iterable[str]) -> None:
    rs = set(rel_ids)
    m.relations = [r for r in m.relations if r.id not in rs]


def set_relation_label(m: MindMap, rel_id: str, label: str) -> None:
    for r in m.relations:
        if r.id == rel_id:
            r.label = label
            return
    raise OpError("Relação não encontrada.")


# ----------------------------------------------------- colar / duplicar
def paste_topics(m: MindMap, parent_id: Optional[str], topics: list[Topic],
                 at: Optional[tuple[float, float]] = None) -> list[str]:
    """Cola cópias (com IDs novos). Sem pai => vira(m) tópico(s) flutuante(s)."""
    out = []
    if parent_id is not None:
        parent = _get(m, parent_id)
        parent.collapsed = False
        for t in topics:
            c = t.clone()
            parent.add_child(c)
            out.append(c.id)
    else:
        x, y = at or (0.0, 0.0)
        for i, t in enumerate(topics):
            c = t.clone()
            c.pos = (x + 30 * i, y + 30 * i)
            m.floating.append(c)
            out.append(c.id)
    return out


def duplicate(m: MindMap, ids: Iterable[str]) -> list[str]:
    out = []
    for t in top_level_selection(m, ids):
        if t is m.root:
            continue
        c = t.clone()
        if t.parent is None:
            px, py = t.pos or (0, 0)
            c.pos = (px + 40, py + 40)
            m.floating.append(c)
        else:
            t.parent.add_child(c, t.index_in_parent() + 1)
        out.append(c.id)
    return out


# ------------------------------------------------------- texto em tópicos
_BULLET = re.compile(r"^(\s*)(?:[-*+•▪◦]|\d+[.)])?\s*(.*)$")


def parse_outline(text: str) -> list[Topic]:
    """Converte texto indentado (tabs, espaços ou marcadores) em tópicos.

    Útil para colar listas de notas, Markdown ou e-mails direto no mapa.
    """
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        return []
    roots: list[Topic] = []
    stack: list[tuple[int, Topic]] = []
    for ln in lines:
        expanded = ln.replace("\t", "    ")
        mt = _BULLET.match(expanded)
        indent = len(mt.group(1)) if mt else 0
        content = (mt.group(2) if mt else expanded).strip()
        heading = re.match(r"^(#+)\s*", expanded.strip())
        if heading:   # títulos Markdown: "#" é pai de tudo que vem abaixo
            indent = -1000 + len(heading.group(1))
            content = expanded.strip()[heading.end():].strip()
        if not content:
            continue
        node = Topic(content)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1].add_child(node)
        else:
            roots.append(node)
        stack.append((indent, node))
    return roots


def to_outline(topics: list[Topic]) -> str:
    out: list[str] = []
    stack = [(t, 0) for t in reversed(topics)]
    while stack:
        t, level = stack.pop()
        lines = t.text.split("\n") or [""]
        out.append(("\t" * level) + lines[0])
        out.extend(("\t" * level) + "  " + ln for ln in lines[1:])
        stack.extend((c, level + 1) for c in reversed(t.children))
    return "\n".join(out)
