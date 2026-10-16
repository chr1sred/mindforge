"""Temas visuais e resolução de estilo (sem dependência de Qt).

O estilo final de um tópico = padrão do tema para o nível
(central / principal / subtópico / flutuante) + cor do ramo +
sobrescritas que o usuário aplicou no tópico.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

SHAPES = {
    "retangulo": "Retângulo",
    "arredondado": "Arredondado",
    "capsula": "Cápsula",
    "elipse": "Elipse",
    "sublinhado": "Sublinhado",
    "nenhuma": "Sem borda",
}


@dataclass(frozen=True)
class TopicStyle:
    shape: str = "arredondado"
    fill: Optional[str] = None
    border: Optional[str] = None
    border_width: float = 0.0
    text_color: str = "#1F2328"
    font_size: float = 14.0
    bold: bool = False
    italic: bool = False
    line_color: str = "#8A8F98"
    line_width: float = 1.6
    pad_x: float = 10.0
    pad_y: float = 6.0
    max_text_width: float = 260.0


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    background: str
    relation_color: str
    root: dict
    main: dict
    sub: dict
    floating: dict
    palette: tuple[str, ...]
    main_fill_from_branch: bool = False
    main_border_from_branch: bool = False
    sub_border_from_branch: bool = False
    selection_color: str = "#2F80ED"
    font_family: Optional[str] = None     # None = fonte do sistema
    mono: str = "#3E5C85"                 # cor única quando "Ramo colorido" está desligado
    hidden: bool = False                  # temas internos (ex.: miniaturas) não aparecem na lista


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return 1.0
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_text(fill: str, dark: str = "#1F2328", light: str = "#FFFFFF") -> str:
    """Escolhe texto claro ou escuro conforme a cor de fundo (contraste WCAG)."""
    lum = _luminance(fill)
    vs_black = (lum + 0.05) / 0.05
    vs_white = 1.05 / (lum + 0.05)
    # leve preferência por texto branco em cores médias (mais legível em botões coloridos)
    return dark if vs_black > vs_white * 1.4 else light


THEMES: dict[str, Theme] = {}


def _register(t: Theme) -> None:
    THEMES[t.key] = t


_register(Theme(
    key="classico", label="Clássico", background="#FFFFFF", relation_color="#7C8594",
    root=dict(shape="arredondado", fill="#24364F", text_color="#FFFFFF", font_size=22, bold=True,
              pad_x=22, pad_y=14, line_width=3.0, max_text_width=340),
    main=dict(shape="arredondado", font_size=16, bold=True, pad_x=14, pad_y=9, line_width=2.6,
              max_text_width=280),
    sub=dict(shape="sublinhado", font_size=14, pad_x=6, pad_y=5, line_width=1.7, border_width=1.7),
    floating=dict(shape="arredondado", fill="#EEF1F5", border="#9AA4B2", border_width=1.2,
                  font_size=15, pad_x=12, pad_y=8),
    palette=("#E5534B", "#F0883E", "#D4A72C", "#3FA66B", "#2F80ED", "#8250DF", "#D63F8C", "#1B9AAA"),
    main_fill_from_branch=True, sub_border_from_branch=True,
))

_register(Theme(
    key="escuro", label="Escuro", background="#1C1E24", relation_color="#9AA4B2",
    root=dict(shape="arredondado", fill="#F2F3F5", text_color="#1C1E24", font_size=22, bold=True,
              pad_x=22, pad_y=14, line_width=3.0, max_text_width=340),
    main=dict(shape="arredondado", fill="#2A2D36", text_color="#F2F3F5", border_width=2.2,
              font_size=16, bold=True, pad_x=14, pad_y=9, line_width=2.6, max_text_width=280),
    sub=dict(shape="sublinhado", text_color="#D9DCE1", font_size=14, pad_x=6, pad_y=5,
             line_width=1.7, border_width=1.7),
    floating=dict(shape="arredondado", fill="#2A2D36", border="#5D6472", border_width=1.2,
                  text_color="#F2F3F5", font_size=15, pad_x=12, pad_y=8),
    palette=("#FF7B72", "#FFA657", "#E3B341", "#56D364", "#58A6FF", "#BC8CFF", "#FF7AB6", "#39C5CF"),
    main_border_from_branch=True, sub_border_from_branch=True, selection_color="#58A6FF",
    mono="#8B949E",
))

_register(Theme(
    key="oceano", label="Oceano", background="#F2F7FB", relation_color="#5E7A93",
    root=dict(shape="capsula", fill="#0B3C5D", text_color="#FFFFFF", font_size=22, bold=True,
              pad_x=26, pad_y=14, line_width=3.0, max_text_width=340),
    main=dict(shape="capsula", font_size=16, bold=True, pad_x=16, pad_y=9, line_width=2.4,
              max_text_width=280),
    sub=dict(shape="arredondado", fill="#FFFFFF", border="#BFD3E3", border_width=1.0,
             text_color="#173B57", font_size=14, pad_x=10, pad_y=6, line_width=1.6),
    floating=dict(shape="arredondado", fill="#DCEBF5", border="#7FA6C2", border_width=1.2,
                  text_color="#0B3C5D", font_size=15, pad_x=12, pad_y=8),
    palette=("#1D70A2", "#169B9B", "#2A9D8F", "#3A86FF", "#4361EE", "#0077B6", "#00A6A6", "#5390D9"),
    main_fill_from_branch=True,
    mono="#1D70A2",
))

_register(Theme(
    key="minimalista", label="Minimalista", background="#FFFFFF", relation_color="#9A9A9A",
    root=dict(shape="retangulo", fill=None, border="#111111", border_width=2.4, text_color="#111111",
              font_size=22, bold=True, pad_x=20, pad_y=12, line_width=2.0, line_color="#444444",
              max_text_width=340),
    main=dict(shape="sublinhado", text_color="#111111", border="#111111", border_width=2.0,
              font_size=16, bold=True, pad_x=6, pad_y=6, line_width=1.8, line_color="#444444",
              max_text_width=280),
    sub=dict(shape="nenhuma", text_color="#333333", font_size=14, pad_x=6, pad_y=4,
             line_width=1.2, line_color="#9A9A9A"),
    floating=dict(shape="retangulo", border="#555555", border_width=1.0, text_color="#111111",
                  font_size=15, pad_x=10, pad_y=6),
    palette=("#444444",), selection_color="#E5534B",
    mono="#444444",
))

_register(Theme(
    key="pastel", label="Pastel", background="#FFFBF5", relation_color="#A08C7A",
    root=dict(shape="elipse", fill="#FFD6A5", text_color="#4A3426", font_size=22, bold=True,
              pad_x=30, pad_y=18, line_width=3.0, line_color="#C8A98C", max_text_width=320),
    main=dict(shape="arredondado", text_color="#3E3A36", font_size=16, bold=True, pad_x=14,
              pad_y=9, line_width=2.4, max_text_width=280),
    sub=dict(shape="arredondado", fill="#FFFFFF", border="#E8DCCD", border_width=1.0,
             text_color="#4A4540", font_size=14, pad_x=10, pad_y=6, line_width=1.6),
    floating=dict(shape="arredondado", fill="#F1EAFF", border="#C9B6F2", border_width=1.2,
                  text_color="#3E3A36", font_size=15, pad_x=12, pad_y=8),
    palette=("#FFADAD", "#FFC89A", "#E9D985", "#B5E3A3", "#9BD5F0", "#BDB2FF", "#FFC6FF", "#A0E7D9"),
    main_fill_from_branch=True,
    mono="#8FB8DE",
))


# Tema interno usado nas miniaturas do seletor de esqueleto (visual "rascunho" do XMind)
_register(Theme(
    key="_esqueleto", label="Esqueleto", background="#FFFFFF", relation_color="#B8BDC6",
    root=dict(shape="arredondado", fill="#C9CED6", text_color="#C9CED6", font_size=22, bold=True,
              pad_x=22, pad_y=14, line_width=3.0, line_color="#9AA1AC", max_text_width=340),
    main=dict(shape="arredondado", fill="#E3E6EB", text_color="#E3E6EB", font_size=16, pad_x=14,
              pad_y=9, line_width=2.6, line_color="#9AA1AC", max_text_width=280),
    sub=dict(shape="sublinhado", text_color="#FFFFFF", border="#9AA1AC", font_size=14, pad_x=6,
             pad_y=5, line_width=1.8, border_width=1.8, line_color="#9AA1AC"),
    floating=dict(shape="arredondado", fill="#E3E6EB", text_color="#E3E6EB", font_size=15),
    palette=("#9AA1AC",), mono="#9AA1AC", hidden=True,
))


def visible_themes() -> list[Theme]:
    return [t for t in THEMES.values() if not t.hidden]


def get_theme(key: str) -> Theme:
    return THEMES.get(key) or THEMES["classico"]


# Sobrescritas que o usuário pode aplicar em um tópico
STYLE_KEYS = ("shape", "fill", "border", "text_color", "font_size", "bold", "italic", "line_color")


def resolve_style(theme: Theme, level: str, branch_color: Optional[str],
                  overrides: Optional[dict] = None) -> TopicStyle:
    """level: 'root' | 'main' | 'sub' | 'floating'."""
    base = dict(getattr(theme, level))
    st = TopicStyle(**base)
    if branch_color:
        if level in ("main", "sub") and "line_color" not in base:
            st = replace(st, line_color=branch_color)
        if level == "main":
            if theme.main_fill_from_branch:
                st = replace(st, fill=branch_color)
                if "text_color" not in base:
                    st = replace(st, text_color=contrast_text(branch_color))
            if theme.main_border_from_branch:
                st = replace(st, border=branch_color)
        if level == "sub" and theme.sub_border_from_branch and "border" not in base:
            st = replace(st, border=branch_color)
        if level == "main" and st.shape == "sublinhado" and "border" not in base:
            st = replace(st, border=branch_color)
    if level == "root" and "line_color" not in base and branch_color:
        st = replace(st, line_color=branch_color)
    if overrides:
        clean = {k: v for k, v in overrides.items() if k in STYLE_KEYS and v is not None}
        if "font_size" in clean:
            try:
                clean["font_size"] = float(clean["font_size"])
            except (TypeError, ValueError):
                clean.pop("font_size")
        if "shape" in clean and clean["shape"] not in SHAPES:
            clean.pop("shape")
        st = replace(st, **clean)
        if "fill" in clean and "text_color" not in clean and clean["fill"]:
            st = replace(st, text_color=contrast_text(clean["fill"]))
        if clean.get("shape") in ("retangulo", "arredondado", "capsula", "elipse") \
                and not st.fill and not st.border:
            st = replace(st, border=st.line_color, border_width=max(st.border_width, 1.4))
        if clean.get("shape") == "sublinhado" and not st.border:
            st = replace(st, border=st.line_color, border_width=max(st.border_width, 1.6))
    return st


def branch_color(theme: Theme, index: int) -> str:
    return theme.palette[index % len(theme.palette)]
