"""Temas visuais, catálogos de opções e resolução de estilo (sem dependência de Qt).

O estilo final de um tópico =
    padrão do tema para o nível (central / principal / subtópico / flutuante)
  + dicas do esqueleto (ex.: a espinha de peixe usa subtópicos sem caixa)
  + cor do ramo
  + sobrescritas que o usuário aplicou no tópico.

Os temas usam "fichas" de cor resolvidas na hora:
    $branch  cor do ramo            $tint  cor do ramo bem clara (fundo de subtópico)
    $deep    cor do ramo escurecida (texto de subtópico)
    $bg      fundo do mapa          $ink   cor de texto padrão do tema
    $auto    texto claro/escuro conforme o preenchimento
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from mindforge.i18n import N_

# ------------------------------------------------------------------ catálogos
SHAPES = {
    "retangulo": N_("Retângulo"),
    "arredondado": N_("Arredondado"),
    "capsula": N_("Cápsula"),
    "elipse": N_("Elipse"),
    "losango": N_("Losango"),
    "hexagono": N_("Hexágono"),
    "sublinhado": N_("Sublinhado"),
    "sublinhado_duplo": N_("Sublinhado duplo"),
    "nenhuma": N_("Sem borda"),
}
BOXED_SHAPES = ("retangulo", "arredondado", "capsula", "elipse", "losango", "hexagono")
UNDERLINE_SHAPES = ("sublinhado", "sublinhado_duplo")

BRANCH_STYLES = {
    "colchete_curvo": N_("Colchete curvo"),
    "colchete_reto": N_("Colchete reto"),
    "leque_reto": N_("Leque reto"),
    "arco": N_("Arco"),
    "chave": N_("Chave"),
    "diagonal": N_("Diagonal"),
    "leque_curvo": N_("Leque curvo"),
}
LINE_PATTERNS = {"nenhum": N_("Nenhum"), "solido": N_("Sólido"), "tracejado": N_("Tracejado"), "pontilhado": N_("Pontilhado")}
BORDER_STYLES = LINE_PATTERNS
LINE_ENDS = {
    "nenhum": N_("Nenhum"), "circulo": N_("Círculo"), "seta": N_("Seta"), "seta_aberta": N_("Seta aberta"),
    "quadrado": N_("Quadrado"), "losango": N_("Losango"), "barra": N_("Barra"), "seta_invertida": N_("Seta invertida"),
}
LEVELS = {"xfino": N_("Extra fino"), "fino": N_("Fino"), "medio": N_("Médio"), "grosso": N_("Grosso"), "xgrosso": N_("Extra grosso")}
LINE_LEVEL_PX = {"xfino": 1.0, "fino": 1.5, "medio": 2.25, "grosso": 3.25, "xgrosso": 4.5}
BORDER_LEVEL_PX = {"xfino": 1.0, "fino": 1.5, "medio": 2.0, "grosso": 3.0, "xgrosso": 4.0}
TEXT_CASES = {"normal": N_("Normal"), "upper": N_("MAIÚSCULAS"), "lower": N_("minúsculas"), "title": N_("Primeira Maiúscula")}
ALIGNS = ("left", "center", "right")


def nearest_level(px: float, table: dict[str, float]) -> str:
    return min(table, key=lambda k: abs(table[k] - px))


@dataclass(frozen=True)
class TopicStyle:
    shape: str = "arredondado"
    fill: Optional[str] = None
    border: Optional[str] = None
    border_width: float = 0.0
    border_style: str = "solido"
    text_color: str = "#1F2328"
    font_size: float = 14.0
    weight: int = 400
    italic: bool = False
    strike: bool = False
    text_case: str = "normal"
    align: Optional[str] = None            # None = automático (centro p/ caixas, esquerda p/ sem caixa)
    family: Optional[str] = None
    line_color: str = "#8A8F98"
    line_width: float = 1.5
    line_pattern: str = "solido"
    line_end: str = "nenhum"
    branch_style: Optional[str] = None     # None = padrão do esqueleto/mapa
    pad_x: float = 10.0
    pad_y: float = 6.0
    max_text_width: float = 260.0
    fixed_width: Optional[float] = None

    @property
    def bold(self) -> bool:
        return self.weight >= 600

    @property
    def resolved_align(self) -> str:
        if self.align in ALIGNS:
            return self.align
        return "left" if self.shape in ("nenhuma", *UNDERLINE_SHAPES) else "center"


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
    selection_color: str = "#2F80ED"
    font_family: Optional[str] = None     # None = Inter (embutida) / fonte do sistema
    mono: str = "#3E5C85"                 # cor única quando "Ramo colorido" está desligado
    ink: str = "#1F2328"
    hidden: bool = False                  # temas internos (miniaturas) não aparecem na lista
    tint: float = 0.84                    # quanto do fundo entra no $tint
    extras: dict = field(default_factory=dict)
    strict: bool = False                  # temas de cores (1.3): garante contraste mínimo de texto/linhas


# ------------------------------------------------------------------- cores
def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (128, 128, 128)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def mix(a: str, b: str, t: float) -> str:
    """Mistura: t=0 → a, t=1 → b."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def _luminance(hex_color: str) -> float:
    r, g, b = (c / 255 for c in _rgb(hex_color))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(a: str, b: str) -> float:
    """Contraste WCAG entre duas cores (1 a 21)."""
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable(color: str, against: str, ratio: float, toward: Optional[str] = None) -> str:
    """Escurece/clareia `color` (mantendo o matiz) até atingir o contraste pedido com `against`."""
    if contrast_ratio(color, against) >= ratio:
        return color
    targets = [toward] if toward else []
    targets += ["#000000", "#FFFFFF"] if _luminance(against) > 0.18 else ["#FFFFFF", "#000000"]
    for target in targets:
        for i in range(1, 21):
            c = mix(color, target, i / 20)
            if contrast_ratio(c, against) >= ratio:
                return c
    return "#000000" if _luminance(against) > 0.18 else "#FFFFFF"


def is_dark(hex_color: str) -> bool:
    return _luminance(hex_color) < 0.18


def contrast_text(fill: str, dark: str = "#1F2328", light: str = "#FFFFFF") -> str:
    """Texto claro ou escuro conforme o fundo (contraste WCAG, com leve preferência por branco)."""
    lum = _luminance(fill)
    vs_black = (lum + 0.05) / 0.05
    vs_white = 1.05 / (lum + 0.05)
    return dark if vs_black > vs_white * 1.8 else light


# ------------------------------------------------------------------- temas
THEMES: dict[str, Theme] = {}


def _register(t: Theme) -> None:
    THEMES[t.key] = t


# Clássico — inspirado no XMind: central escuro, principais preenchidos com a
# cor do ramo e subtópicos em caixas suaves tingidas.
_register(Theme(
    key="classico", label=N_("Clássico"), background="#FFFFFF", relation_color="#7C8594",
    root=dict(shape="arredondado", fill="#0E1033", text_color="#FFFFFF", font_size=26, weight=600,
              pad_x=26, pad_y=15, line_width=2.5, line_color="#2A2E45", max_text_width=360),
    main=dict(shape="arredondado", fill="$branch", text_color="$auto", font_size=18, weight=600,
              pad_x=16, pad_y=9, line_width=2.0, max_text_width=300),
    sub=dict(shape="arredondado", fill="$tint", text_color="$deep", font_size=15, weight=400,
             pad_x=8, pad_y=4, line_width=1.5, max_text_width=280),
    floating=dict(shape="arredondado", fill="#EEF1F5", border="#9AA4B2", border_width=1.2,
                  font_size=15, pad_x=12, pad_y=8),
    palette=("#F24F4B", "#F59E57", "#F2C94C", "#27BE7E", "#3B82F6", "#8B5CF6", "#EC4899", "#14B8A6"),
    mono="#3E5C85",
))

_register(Theme(
    key="escuro", label=N_("Escuro"), background="#1C1E24", relation_color="#9AA4B2", ink="#F2F3F5",
    root=dict(shape="arredondado", fill="#F2F3F5", text_color="#1C1E24", font_size=26, weight=600,
              pad_x=26, pad_y=15, line_width=2.5, line_color="#8B949E", max_text_width=360),
    main=dict(shape="arredondado", fill="$branch", text_color="$auto", font_size=18, weight=600,
              pad_x=16, pad_y=9, line_width=2.0, max_text_width=300),
    sub=dict(shape="arredondado", fill="$tint", text_color="$deep", font_size=15,
             pad_x=8, pad_y=4, line_width=1.5, max_text_width=280),
    floating=dict(shape="arredondado", fill="#2A2D36", border="#5D6472", border_width=1.2,
                  text_color="#F2F3F5", font_size=15, pad_x=12, pad_y=8),
    palette=("#FF7B72", "#FFA657", "#E3B341", "#56D364", "#58A6FF", "#BC8CFF", "#FF7AB6", "#39C5CF"),
    selection_color="#58A6FF", mono="#8B949E", tint=0.72,
))

_register(Theme(
    key="oceano", label=N_("Oceano"), background="#F2F7FB", relation_color="#5E7A93", ink="#173B57",
    root=dict(shape="capsula", fill="#0B3C5D", text_color="#FFFFFF", font_size=26, weight=600,
              pad_x=28, pad_y=15, line_width=2.5, line_color="#0B3C5D", max_text_width=360),
    main=dict(shape="capsula", fill="$branch", text_color="$auto", font_size=18, weight=600,
              pad_x=16, pad_y=9, line_width=2.0, max_text_width=300),
    sub=dict(shape="arredondado", fill="#FFFFFF", border="$tint", border_width=1.2,
             text_color="#173B57", font_size=15, pad_x=9, pad_y=5, line_width=1.5),
    floating=dict(shape="arredondado", fill="#DCEBF5", border="#7FA6C2", border_width=1.2,
                  text_color="#0B3C5D", font_size=15, pad_x=12, pad_y=8),
    palette=("#1D70A2", "#169B9B", "#2A9D8F", "#3A86FF", "#4361EE", "#0077B6", "#00A6A6", "#5390D9"),
    mono="#1D70A2", tint=0.6,
))

_register(Theme(
    key="minimalista", label=N_("Minimalista"), background="#FFFFFF", relation_color="#9A9A9A", ink="#111111",
    root=dict(shape="retangulo", fill=None, border="#111111", border_width=2.4, text_color="#111111",
              font_size=24, weight=700, pad_x=20, pad_y=12, line_width=2.0, line_color="#444444",
              max_text_width=340),
    main=dict(shape="sublinhado", text_color="#111111", border="#111111", border_width=2.0,
              font_size=17, weight=600, pad_x=6, pad_y=6, line_width=1.8, line_color="#444444",
              max_text_width=280),
    sub=dict(shape="nenhuma", text_color="#333333", font_size=15, pad_x=6, pad_y=4,
             line_width=1.2, line_color="#9A9A9A"),
    floating=dict(shape="retangulo", border="#555555", border_width=1.0, text_color="#111111",
                  font_size=15, pad_x=10, pad_y=6),
    palette=("#444444",), selection_color="#E5534B", mono="#444444",
))

_register(Theme(
    key="pastel", label=N_("Pastel"), background="#FFFBF5", relation_color="#A08C7A", ink="#3E3A36",
    root=dict(shape="elipse", fill="#FFD6A5", text_color="#4A3426", font_size=24, weight=700,
              pad_x=30, pad_y=18, line_width=2.5, line_color="#C8A98C", max_text_width=320),
    main=dict(shape="arredondado", fill="$branch", text_color="#3E3A36", font_size=18, weight=600,
              pad_x=16, pad_y=9, line_width=2.0, max_text_width=300),
    sub=dict(shape="arredondado", fill="#FFFFFF", border="$branch", border_width=1.2,
             text_color="#4A4540", font_size=15, pad_x=9, pad_y=5, line_width=1.5),
    floating=dict(shape="arredondado", fill="#F1EAFF", border="#C9B6F2", border_width=1.2,
                  text_color="#3E3A36", font_size=15, pad_x=12, pad_y=8),
    palette=("#FFADAD", "#FFC89A", "#E9D985", "#B5E3A3", "#9BD5F0", "#BDB2FF", "#FFC6FF", "#A0E7D9"),
    mono="#8FB8DE",
))

# Tema interno usado nas miniaturas do seletor de esqueleto (visual "rascunho" do XMind)
_register(Theme(
    key="_esqueleto", label=N_("Esqueleto"), background="#FFFFFF", relation_color="#B8BDC6",
    root=dict(shape="arredondado", fill="#C9CED6", text_color="#C9CED6", font_size=22, weight=700,
              pad_x=22, pad_y=14, line_width=2.5, line_color="#9AA1AC", max_text_width=340),
    main=dict(shape="arredondado", fill="#DDE1E6", text_color="#DDE1E6", font_size=16, pad_x=14,
              pad_y=9, line_width=2.2, line_color="#9AA1AC", max_text_width=280),
    sub=dict(shape="arredondado", fill="#EEF0F3", text_color="#EEF0F3", font_size=14, pad_x=6,
             pad_y=4, line_width=1.8, line_color="#9AA1AC"),
    floating=dict(shape="arredondado", fill="#E3E6EB", text_color="#E3E6EB", font_size=15),
    palette=("#9AA1AC",), mono="#9AA1AC", hidden=True,
))


def visible_themes() -> list[Theme]:
    return [t for t in THEMES.values() if not t.hidden]


def get_theme(key: str) -> Theme:
    return THEMES.get(key) or THEMES["classico"]


def branch_color(theme: Theme, index: int) -> str:
    return theme.palette[index % len(theme.palette)]


# ------------------------------------------------------------- resolução
# Sobrescritas que o usuário pode aplicar em um tópico (Topic.style)
STYLE_KEYS = (
    "shape", "fill", "width",
    "border", "border_style", "border_level",
    "font_family", "font_weight", "font_size", "bold", "italic", "strike", "text_case", "align",
    "text_color",
    "branch_style", "line_pattern", "line_end", "line_level", "line_color",
)
COLOR_KEYS = ("fill", "border", "text_color", "line_color")


def _token(value, theme: Theme, branch: str, background: str, fill: Optional[str]):
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    dark_bg = is_dark(background)
    if value == "$branch":
        return branch
    if value == "$tint":
        return mix(branch, background, theme.tint)
    if value == "$deep":
        return mix(branch, "#FFFFFF", 0.55) if dark_bg else mix(branch, "#000000", 0.5)
    if value == "$bg":
        return background
    if value == "$ink":
        return theme.ink
    if value == "$auto":
        return contrast_text(fill) if fill else theme.ink
    return None


def _num(v, lo: float, hi: float) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, f))


def resolve_style(theme: Theme, level: str, branch: Optional[str],
                  overrides: Optional[dict] = None, hints: Optional[dict] = None,
                  background: Optional[str] = None) -> TopicStyle:
    """level: 'root' | 'main' | 'sub' | 'floating'."""
    bg = background or theme.background
    branch = branch or theme.mono
    base = dict(getattr(theme, level))
    if hints:
        base.update(hints)
    if "line_color" not in base:
        base["line_color"] = "$branch"
    if "text_color" not in base:
        base["text_color"] = "$auto" if base.get("fill") else "$ink"
    fill = _token(base.get("fill"), theme, branch, bg, None)
    base["fill"] = fill
    for k in ("border", "line_color", "text_color"):
        base[k] = _token(base.get(k), theme, branch, bg, fill)
    if theme.strict:
        _enforce_contrast(base, level, bg)
    if "bold" in base:                       # compatibilidade com temas antigos
        base.setdefault("weight", 700 if base.pop("bold") else 400)
    st = TopicStyle(**{k: v for k, v in base.items() if k in TopicStyle.__dataclass_fields__})
    return apply_overrides(st, overrides or {}, theme)


# contraste mínimo (WCAG): 4,5:1 para texto normal; 3:1 para texto grande (principal e central)
MIN_TEXT_CONTRAST = {"root": 3.0, "main": 3.0, "sub": 4.5, "floating": 4.5}
MIN_LINE_CONTRAST = 1.5


def _enforce_contrast(base: dict, level: str, bg: str) -> None:
    surface = base.get("fill") or bg
    tc = base.get("text_color")
    if isinstance(tc, str) and tc.startswith("#"):
        base["text_color"] = readable(tc, surface, MIN_TEXT_CONTRAST.get(level, 4.5))
    lc = base.get("line_color")
    if isinstance(lc, str) and lc.startswith("#"):
        base["line_color"] = readable(lc, bg, MIN_LINE_CONTRAST)
    bd = base.get("border")
    if isinstance(bd, str) and bd.startswith("#") and not base.get("fill"):
        base["border"] = readable(bd, bg, MIN_LINE_CONTRAST)


def apply_overrides(st: TopicStyle, o: dict, theme: Theme) -> TopicStyle:
    ch: dict = {}
    shape = o.get("shape")
    if shape in SHAPES:
        ch["shape"] = shape
    if "fill" in o and o["fill"] is not None:
        ch["fill"] = o["fill"] or None          # "" = sem preenchimento
    w = _num(o.get("width"), 40, 2000) if o.get("width") else None
    if w:
        ch["fixed_width"] = w
    # -------- limite (borda)
    if o.get("border"):
        ch["border"] = o["border"]
    elif o.get("border") == "":
        ch["border_width"] = 0.0
    if o.get("border_level") in BORDER_LEVEL_PX:
        ch["border_width"] = BORDER_LEVEL_PX[o["border_level"]]
    if o.get("border_style") in BORDER_STYLES:
        ch["border_style"] = o["border_style"]
    # -------- texto
    if isinstance(o.get("font_family"), str) and o["font_family"].strip():
        ch["family"] = o["font_family"].strip()
    fs = _num(o.get("font_size"), 6, 200)
    if fs:
        ch["font_size"] = fs
    fw = _num(o.get("font_weight"), 100, 900)
    if fw:
        ch["weight"] = int(round(fw / 100.0) * 100)
    elif o.get("bold") is not None:
        ch["weight"] = 700 if o["bold"] else 400
    for k in ("italic", "strike"):
        if o.get(k) is not None:
            ch[k] = bool(o[k])
    if o.get("text_case") in TEXT_CASES:
        ch["text_case"] = o["text_case"]
    if o.get("align") in ALIGNS:
        ch["align"] = o["align"]
    if o.get("text_color"):
        ch["text_color"] = o["text_color"]
    # -------- ramo
    if o.get("branch_style") in BRANCH_STYLES:
        ch["branch_style"] = o["branch_style"]
    if o.get("line_pattern") in LINE_PATTERNS:
        ch["line_pattern"] = o["line_pattern"]
    if o.get("line_end") in LINE_ENDS:
        ch["line_end"] = o["line_end"]
    if o.get("line_level") in LINE_LEVEL_PX:
        ch["line_width"] = LINE_LEVEL_PX[o["line_level"]]
    if o.get("line_color"):
        ch["line_color"] = o["line_color"]
    st = replace(st, **ch)
    # -------- coerências
    if "fill" in ch and "text_color" not in ch and ch["fill"]:
        st = replace(st, text_color=contrast_text(ch["fill"], dark=theme.ink if not is_dark(theme.ink) else "#1F2328"))
    wants_border = bool(o.get("border")) or o.get("border_level") in BORDER_LEVEL_PX or \
        o.get("border_style") in ("solido", "tracejado", "pontilhado")
    if wants_border and st.border_width <= 0:
        st = replace(st, border_width=1.5)
    if wants_border and not st.border:
        st = replace(st, border=st.line_color)
    if "shape" in ch and ch["shape"] in BOXED_SHAPES and not st.fill and not (st.border and st.border_width > 0):
        st = replace(st, border=st.line_color, border_width=max(st.border_width, 1.5))
    if st.shape in UNDERLINE_SHAPES and not st.border:
        st = replace(st, border=st.line_color)
    if st.shape in UNDERLINE_SHAPES and st.border_width <= 0 and st.border_style != "nenhum":
        st = replace(st, border_width=max(1.5, st.line_width))
    if st.border_style == "nenhum":
        st = replace(st, border_width=0.0)
    return st


def underline_width(st: TopicStyle) -> float:
    return max(1.0, st.border_width or st.line_width)
