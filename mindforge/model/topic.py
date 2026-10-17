"""Modelo de dados puro (sem Qt).

Toda a lógica aqui é testável sem interface gráfica. A interface nunca
altera estes objetos diretamente: ela usa as funções de ``ops`` através
do ``Document``, que registra cada alteração na pilha de desfazer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterator, Optional
from mindforge.i18n import tr

SCHEMA_VERSION = 1

DEFAULT_LAYOUT = "mapa_mental"
DEFAULT_THEME = "classico"

# Configurações do mapa (aba "Mapa" do painel). Ausente = padrão do tema.
MAP_SETTINGS_DEFAULTS = {
    "background": None,     # cor de fundo (hex) ou None = do tema
    "font": None,           # família da fonte global ou None = padrão do sistema
    "line_width": "padrao",  # fina | padrao | grossa
    "rainbow": True,        # ramos coloridos
    "compact": False,       # compactar mapa (menos espaço entre tópicos)
    "branch_style": None,   # estilo de ramo padrão do mapa (None = o do esqueleto)
    "fishbone_align": False,  # espinha de peixe: todas as espinhas com o mesmo comprimento
    # ---- temas de cores (1.3)
    "color_theme": None,    # {"id", "name", "colors": [6 hex]} ou None = tema antigo (m.theme)
    "color_variant": 0,     # 0..5: Contraste, Central colorido, Suave, Contorno, Noturno, Tom sobre tom
    "branch_palette": None,  # roda do Ramo colorido: chave de colorthemes.BRANCH_PALETTES ou None = do tema
    "static_color": None,   # cor única dos ramos com "Ramo colorido" desligado (None = do tema)
}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass(eq=False)
class Topic:
    text: str = ""
    id: str = field(default_factory=new_id)
    children: list["Topic"] = field(default_factory=list)
    collapsed: bool = False
    style: dict = field(default_factory=dict)       # sobrescritas de estilo
    note: str = ""
    markers: list[str] = field(default_factory=list)
    pos: Optional[tuple[float, float]] = None        # só para tópicos flutuantes
    parent: Optional["Topic"] = field(default=None, repr=False)

    # ------------------------------------------------------------ árvore
    def add_child(self, child: "Topic", index: Optional[int] = None) -> "Topic":
        child.parent = self
        child.pos = None
        if index is None or index > len(self.children):
            self.children.append(child)
        else:
            self.children.insert(max(0, index), child)
        return child

    def detach(self) -> None:
        if self.parent is not None:
            self.parent.children.remove(self)
            self.parent = None

    def walk(self) -> Iterator["Topic"]:
        """Percorre a subárvore em pré-ordem, sem recursão (suporta árvores profundas)."""
        stack = [self]
        while stack:
            t = stack.pop()
            yield t
            stack.extend(reversed(t.children))

    def walk_visible(self) -> Iterator["Topic"]:
        stack = [self]
        while stack:
            t = stack.pop()
            yield t
            if not t.collapsed:
                stack.extend(reversed(t.children))

    def ancestors(self) -> Iterator["Topic"]:
        p = self.parent
        while p is not None:
            yield p
            p = p.parent

    def is_ancestor_of(self, other: "Topic") -> bool:
        return any(a is self for a in other.ancestors())

    @property
    def depth(self) -> int:
        return sum(1 for _ in self.ancestors())

    def index_in_parent(self) -> int:
        return self.parent.children.index(self) if self.parent else 0

    def visible_children(self) -> list["Topic"]:
        return [] if self.collapsed else self.children

    def descendant_count(self) -> int:
        return sum(1 for _ in self.walk()) - 1

    # ------------------------------------------------------- serialização
    def _own_dict(self) -> dict:
        d: dict = {"id": self.id, "text": self.text}
        if self.collapsed:
            d["collapsed"] = True
        if self.style:
            d["style"] = dict(self.style)
        if self.note:
            d["note"] = self.note
        if self.markers:
            d["markers"] = list(self.markers)
        if self.pos is not None:
            d["pos"] = [float(self.pos[0]), float(self.pos[1])]
        return d

    def to_dict(self) -> dict:
        """Serializa a subárvore (iterativo: suporta árvores muito profundas)."""
        top = self._own_dict()
        stack = [(self, top)]
        while stack:
            t, d = stack.pop()
            if t.children:
                kids = [c._own_dict() for c in t.children]
                d["children"] = kids
                stack.extend(zip(t.children, kids))
        return top

    @classmethod
    def _from_own(cls, d: dict, parent: Optional["Topic"], seen: set) -> "Topic":
        tid = str(d.get("id") or new_id())
        if tid in seen:                       # defesa contra IDs duplicados
            tid = new_id()
        seen.add(tid)
        pos = d.get("pos")
        return cls(
            text=str(d.get("text", "")),
            id=tid,
            collapsed=bool(d.get("collapsed", False)),
            style=dict(d.get("style") or {}),
            note=str(d.get("note", "")),
            markers=[str(m) for m in (d.get("markers") or [])],
            pos=(float(pos[0]), float(pos[1])) if pos else None,
            parent=parent,
        )

    @classmethod
    def from_dict(cls, d: dict, parent: Optional["Topic"] = None,
                  seen: Optional[set] = None) -> "Topic":
        if seen is None:
            seen = set()
        top = cls._from_own(d, parent, seen)
        stack = [(top, d)]
        while stack:
            t, dd = stack.pop()
            for cd in dd.get("children") or []:
                c = cls._from_own(cd, t, seen)
                t.children.append(c)
                stack.append((c, cd))
        return top

    def clone(self) -> "Topic":
        """Cópia profunda com IDs novos (usada em colar/duplicar)."""
        c = Topic.from_dict(self.to_dict())
        for t in c.walk():
            t.id = new_id()
        c.parent = None
        return c


@dataclass(eq=False)
class Relation:
    source: str
    target: str
    label: str = ""
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        d = {"id": self.id, "source": self.source, "target": self.target}
        if self.label:
            d["label"] = self.label
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Relation":
        return cls(source=str(d["source"]), target=str(d["target"]),
                   label=str(d.get("label", "")), id=str(d.get("id") or new_id()))


class MindMap:
    def __init__(self, root: Optional[Topic] = None, layout: str = DEFAULT_LAYOUT,
                 theme: str = DEFAULT_THEME):
        self.root: Topic = root or Topic(tr("Tema central"))
        self.root.parent = None
        self.root.pos = None
        self.floating: list[Topic] = []
        self.relations: list[Relation] = []
        self.layout = layout
        self.theme = theme
        self.settings: dict = {}

    def setting(self, key: str):
        return self.settings.get(key, MAP_SETTINGS_DEFAULTS.get(key))

    # ---------------------------------------------------------- consultas
    def tops(self) -> list[Topic]:
        return [self.root, *self.floating]

    def all_topics(self) -> Iterator[Topic]:
        for top in self.tops():
            yield from top.walk()

    def find(self, tid: Optional[str]) -> Optional[Topic]:
        if tid is None:
            return None
        for t in self.all_topics():
            if t.id == tid:
                return t
        return None

    def index(self) -> dict[str, Topic]:
        return {t.id: t for t in self.all_topics()}

    def top_of(self, topic: Topic) -> Topic:
        t = topic
        while t.parent is not None:
            t = t.parent
        return t

    def is_floating_root(self, topic: Topic) -> bool:
        return topic.parent is None and topic is not self.root

    def count(self) -> int:
        return sum(1 for _ in self.all_topics())

    # ------------------------------------------------------- serialização
    def to_dict(self) -> dict:
        d = {
            "layout": self.layout,
            "theme": self.theme,
            "root": self.root.to_dict(),
        }
        if self.floating:
            d["floating"] = [f.to_dict() for f in self.floating]
        if self.relations:
            d["relations"] = [r.to_dict() for r in self.relations]
        if self.settings:
            d["settings"] = dict(self.settings)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MindMap":
        seen: set = set()
        root = Topic.from_dict(d.get("root") or {"text": tr("Tema central")}, None, seen)
        m = cls(root, str(d.get("layout") or DEFAULT_LAYOUT), str(d.get("theme") or DEFAULT_THEME))
        raw = d.get("settings") or {}
        if isinstance(raw, dict):
            m.settings = {k: v for k, v in raw.items() if k in MAP_SETTINGS_DEFAULTS}
            _sanitize_color_settings(m.settings)
        for fd in d.get("floating") or []:
            f = Topic.from_dict(fd, None, seen)
            if f.pos is None:
                f.pos = (0.0, 0.0)
            m.floating.append(f)
        ids = m.index()
        for rd in d.get("relations") or []:
            try:
                r = Relation.from_dict(rd)
            except (KeyError, TypeError):
                continue
            if r.source in ids and r.target in ids and r.source != r.target:
                m.relations.append(r)
        return m


def _sanitize_color_settings(st: dict) -> None:
    """Descarta valores de cor inválidos vindos do arquivo (o mapa abre com o padrão)."""
    from mindforge.colorthemes import BRANCH_PALETTES, is_hex, sanitize_setting
    if "color_theme" in st:
        v = sanitize_setting(st["color_theme"])
        if v is None:
            st.pop("color_theme")
        else:
            st["color_theme"] = v
    if "color_variant" in st:
        v = st["color_variant"]
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 5:
            st.pop("color_variant")
    if "branch_palette" in st and st["branch_palette"] not in BRANCH_PALETTES:
        st.pop("branch_palette")
    if "static_color" in st and not is_hex(st["static_color"]):
        st.pop("static_color")
