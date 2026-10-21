"""Temas de cores (padrão XMind): paleta de 6 cores × 6 variações de aplicação.

Camadas, da mais fraca para a mais forte:
  1. Tema de cores  (6 cores + variação)        -> mapa.settings["color_theme"/"color_variant"]
  2. Ramo colorido  (roda) ou cor estática       -> mapa.settings["rainbow"/"branch_palette"/"static_color"]
  3. Cor de fundo do mapa                         -> mapa.settings["background"]
  4. Estilo aplicado à mão em cada tópico         -> Topic.style  (sempre vence)

Mapas sem "color_theme" continuam usando os temas antigos (themes.THEMES) exatamente como antes.
O mapa guarda as 6 cores dentro do arquivo: abre igual em outro computador mesmo que a
paleta personalizada não exista lá (ou tenha sido excluída).

Python puro (sem Qt).
"""
from __future__ import annotations

import colorsys
import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from mindforge.i18n import N_
from mindforge.themes import THEMES, Theme, contrast_ratio, get_theme, mix, readable

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
N_COLORS = 6
MAX_CUSTOM = 50


@dataclass(frozen=True)
class Palette:
    id: str
    name: str            # chave de tradução (N_) nos catálogos; nome livre nas personalizadas
    colors: tuple[str, ...]
    group: str           # "colorido" | "classico" | "custom"

    def as_setting(self) -> dict:
        return {"id": self.id, "name": self.name, "colors": list(self.colors)}


def _p(group: str, slug: str, name: str, colors: list[str]) -> Palette:
    return Palette(f"{group}/{slug}", name, tuple(c.upper() for c in colors), group)


# ------------------------------------------------------------------ catálogos
COLORIDO: list[Palette] = [
    _p("colorido", "arco_iris", N_("Arco-íris"), ["#F24F4B", "#F59E57", "#F2C94C", "#27BE7E", "#3B82F6", "#8B5CF6"]),
    _p("colorido", "aurora", N_("Aurora"), ["#FF5F6D", "#FFC371", "#47CF73", "#2EC4B6", "#3A86FF", "#8338EC"]),
    _p("colorido", "tropical", N_("Tropical"), ["#F94144", "#F3722C", "#F9C74F", "#90BE6D", "#43AA8B", "#277DA1"]),
    _p("colorido", "neon_suave", N_("Neon suave"), ["#FF6B9A", "#FFB86B", "#FFE066", "#6BE4A8", "#5EC8F2", "#8C7CF0"]),
    _p("colorido", "por_do_sol", N_("Pôr do sol"), ["#2B1B3D", "#6C2D5F", "#C0395A", "#F06449", "#F9A03F", "#FCD581"]),
    _p("colorido", "oceano", N_("Oceano"), ["#03256C", "#2541B2", "#1768AC", "#06BEE1", "#4FD1C5", "#B2F0E8"]),
    _p("colorido", "primavera", N_("Primavera"), ["#809BCE", "#95B8D1", "#B8E0D2", "#F8EDEB", "#FCD5CE", "#FFB5A7"]),
    _p("colorido", "doces", N_("Doces"), ["#9B5DE5", "#E4C1F9", "#A9DEF9", "#D0F4DE", "#FCF6BD", "#FF99C8"]),
    _p("colorido", "vibrante", N_("Vibrante"), ["#073B4C", "#118AB2", "#06D6A0", "#FFD166", "#EF476F", "#8F2D56"]),
    _p("colorido", "floresta", N_("Floresta"), ["#1B4332", "#2D6A4F", "#40916C", "#74C69D", "#B7E4C7", "#E9C46A"]),
    _p("colorido", "citrico", N_("Cítrico"), ["#386641", "#6A994E", "#A7C957", "#FFD000", "#FFAA00", "#FF7B00"]),
    _p("colorido", "pastel", N_("Pastel"), ["#FFADAD", "#FFC89A", "#E9D985", "#B5E3A3", "#9BD5F0", "#BDB2FF"]),
]
CLASSICO: list[Palette] = [
    _p("classico", "executivo", N_("Executivo"), ["#1F2A44", "#3E5C85", "#6C8EBF", "#A3B8D8", "#C9A227", "#8C2F39"]),
    _p("classico", "grafite", N_("Grafite"), ["#111111", "#333333", "#555555", "#808080", "#AAAAAA", "#D4D4D4"]),
    _p("classico", "terra", N_("Terra"), ["#5C4033", "#8B5E3C", "#B07D4F", "#D4A373", "#E9C9A1", "#6B705C"]),
    _p("classico", "marinho", N_("Marinho"), ["#0B2545", "#13315C", "#134074", "#8DA9C4", "#EEF4ED", "#B23A48"]),
    _p("classico", "bordo", N_("Bordô"), ["#273E47", "#4A0E1F", "#7D1D3F", "#A4243B", "#BD632F", "#D8973C"]),
    _p("classico", "vintage", N_("Vintage"), ["#264653", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51", "#8D6A9F"]),
    _p("classico", "nordico", N_("Nórdico"), ["#2E3440", "#4C566A", "#5E81AC", "#88C0D0", "#A3BE8C", "#D08770"]),
    _p("classico", "salvia", N_("Sálvia"), ["#3D405B", "#6D597A", "#81B29A", "#F2CC8F", "#E07A5F", "#F4F1DE"]),
    _p("classico", "escuro", N_("Escuro"), ["#1C1E24", "#FF7B72", "#FFA657", "#56D364", "#58A6FF", "#BC8CFF"]),
]
CATALOG: dict[str, Palette] = {p.id: p for p in (*COLORIDO, *CLASSICO)}
DEFAULT_PALETTE = COLORIDO[0]

# Roda do "Ramo colorido": conjuntos fixos de cores de ramo (o central não muda).
# A primeira opção ("Do tema", chave None) usa as cores do tema de cores atual; mais 8 conjuntos fixos.
BRANCH_PALETTES: dict[str, tuple[str, tuple[str, ...]]] = {
    "arco_iris": (N_("Arco-íris"), ("#E5534B", "#F0883E", "#D4A72C", "#3FA66B", "#2F80ED", "#8250DF")),
    "por_do_sol": (N_("Pôr do sol"), ("#C0395A", "#E4572E", "#F06449", "#F9A03F", "#E9B44C", "#9C3D54")),
    "oceano": (N_("Oceano"), ("#03256C", "#1768AC", "#2541B2", "#06BEE1", "#2A9D8F", "#4361EE")),
    "pastel": (N_("Pastel"), ("#E8A5A5", "#F2C49B", "#E9D985", "#A8D5BA", "#9BC1E6", "#C3B1E1")),
    "terra": (N_("Terra"), ("#8B5E3C", "#B07D4F", "#6B705C", "#A5A58D", "#CB997E", "#7F5539")),
    "neon": (N_("Neon"), ("#FF2E88", "#FF8A00", "#F5D400", "#00D68F", "#00B3FF", "#9D4EDD")),
    "floresta": (N_("Floresta"), ("#2D6A4F", "#40916C", "#52B788", "#6A994E", "#386641", "#A7C957")),
    "grafite": (N_("Grafite"), ("#2B2D42", "#4A4E69", "#5C677D", "#7D8597", "#33415C", "#6C757D")),
}

@dataclass(frozen=True)
class QuickTheme:
    key: str
    label: str
    palette_id: str
    variant: int


# Temas rápidos (1.4): paleta + variação prontas que pintam o mapa inteiro com um clique.
QUICK_THEMES: dict[str, QuickTheme] = {q.key: q for q in (
    QuickTheme("classico", N_("Clássico"), "colorido/arco_iris", 0),
    QuickTheme("noite", N_("Noite"), "colorido/aurora", 4),
    QuickTheme("oceano", N_("Oceano"), "colorido/oceano", 5),
    QuickTheme("pastel", N_("Pastel"), "colorido/pastel", 0),
    QuickTheme("executivo", N_("Executivo"), "classico/executivo", 0),
    QuickTheme("grafite", N_("Grafite"), "classico/grafite", 3),
    QuickTheme("floresta", N_("Floresta"), "colorido/floresta", 0),
    QuickTheme("por_do_sol", N_("Pôr do sol"), "colorido/por_do_sol", 1),
    QuickTheme("vibrante", N_("Vibrante"), "colorido/vibrante", 0),
    QuickTheme("terra", N_("Terra"), "classico/terra", 2),
    QuickTheme("salvia", N_("Sálvia"), "classico/salvia", 5),
    QuickTheme("neon_noturno", N_("Neon noturno"), "colorido/neon_suave", 4),
)}


def quick_theme_colors(q: QuickTheme) -> tuple[str, tuple[str, ...], str]:
    """(cor do central, cores dos ramos, fundo) — para desenhar o círculo do tema rápido."""
    th = build_theme(CATALOG[q.palette_id].colors, q.variant)
    return th.root.get("fill") or th.background, th.palette, th.background


def active_quick_theme(m) -> Optional[str]:
    """Tema rápido em uso (mesma paleta + variação, sem roda/cor estática)."""
    p = palette_from_setting(m.setting("color_theme"))
    if p is None or m.setting("branch_palette") or m.setting("static_color"):
        return None
    v = int(m.setting("color_variant") or 0)
    for q in QUICK_THEMES.values():
        if q.palette_id == p.id and q.variant == v:
            return q.key
    return None


VARIANTS: tuple[str, ...] = (
    N_("Contraste"), N_("Central colorido"), N_("Suave"), N_("Contorno"), N_("Noturno"), N_("Tom sobre tom"),
)


# ------------------------------------------------------------------ cores
def is_hex(c) -> bool:
    return isinstance(c, str) and bool(HEX_RE.match(c))


def _hsv(c: str) -> tuple[float, float, float]:
    h = c.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def _from_hls(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return "#" + "".join(f"{round(x * 255):02X}" for x in (r, g, b))


def _hls(c: str) -> tuple[float, float, float]:
    h = c.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _lum(c: str) -> float:
    from mindforge.themes import _luminance
    return _luminance(c)


def darkest(colors) -> str:
    return min(colors, key=_lum)


def most_vivid(colors) -> str:
    def score(c):
        _h, s, v = _hsv(c)
        return s * (0.4 + v)
    return max(colors, key=score)


def deep_anchor(c: str) -> str:
    """Cor escura "âncora" para o tópico central (mantém o matiz da paleta)."""
    t = 0.0
    out = c
    while _lum(out) > 0.035 and t < 1.0:
        t += 0.05
        out = mix(c, "#0B0D1A", t)
    return out


def sanitize_colors(colors) -> Optional[tuple[str, ...]]:
    if not isinstance(colors, (list, tuple)) or len(colors) != N_COLORS:
        return None
    if not all(is_hex(c) for c in colors):
        return None
    return tuple(c.upper() for c in colors)


def sanitize_setting(value) -> Optional[dict]:
    """Valida mapa.settings['color_theme'] vindo do arquivo (pode estar corrompido)."""
    if not isinstance(value, dict):
        return None
    colors = sanitize_colors(value.get("colors"))
    if colors is None:
        return None
    name = value.get("name")
    pid = value.get("id")
    return {"id": pid if isinstance(pid, str) else "custom/arquivo",
            "name": name if isinstance(name, str) and name.strip() else "—",
            "colors": list(colors)}


def palette_from_setting(value) -> Optional[Palette]:
    v = sanitize_setting(value)
    if v is None:
        return None
    group = v["id"].split("/", 1)[0] if "/" in v["id"] else "custom"
    return Palette(v["id"], v["name"], tuple(v["colors"]), group if group in ("colorido", "classico") else "custom")


def auto_complete(seeds: list[str]) -> list[str]:
    """Completa uma paleta de 6 cores em harmonia a partir de 1 ou mais cores escolhidas.

    Mantém as cores escolhidas, acrescenta uma âncora escura (para o central) e completa
    com matizes espaçados, com luminosidade e saturação parecidas com as das escolhidas.
    """
    seeds = [s.upper() for s in seeds if is_hex(s)][:N_COLORS]
    if not seeds:
        seeds = [DEFAULT_PALETTE.colors[4]]
    if len(seeds) >= N_COLORS:
        return seeds[:N_COLORS]
    hls = [_hls(s) for s in seeds]
    avg_l = sum(x[1] for x in hls) / len(hls)
    avg_s = sum(x[2] for x in hls) / len(hls)
    l = min(0.62, max(0.45, avg_l))
    s = max(0.55, min(0.85, avg_s if avg_s > 0.05 else 0.0))
    out = list(seeds)
    if all(_lum(c) > 0.06 for c in out):
        out.insert(0, _from_hls(hls[0][0], 0.16, min(0.6, s)))
    base = hls[0][0]
    # passos de matiz que evitam repetir cores já usadas
    used = [_hls(c)[0] for c in out]
    for step in (0.5, 0.17, 0.33, 0.67, 0.83, 0.08, 0.92, 0.25, 0.75):
        if len(out) >= N_COLORS:
            break
        h = (base + step) % 1.0
        if all(min(abs(h - u), 1 - abs(h - u)) > 0.06 for u in used):
            out.append(_from_hls(h, l, s if s > 0 else 0.0))
            used.append(h)
    while len(out) < N_COLORS:      # paleta cinza: varia só a luminosidade
        out.append(_from_hls(base, 0.3 + 0.1 * len(out), s))
    return out[:N_COLORS]


# ------------------------------------------------------------------ variações
def _usable(colors, bg: str, min_ratio: float, toward: str) -> list[str]:
    """Cores de ramo legíveis sobre o fundo (cores quase iguais ao fundo são ajustadas)."""
    out = []
    for c in colors:
        out.append(c if contrast_ratio(c, bg) >= min_ratio else readable(c, bg, min_ratio, toward))
    return out


def _branch_colors(colors: tuple[str, ...], bg: str, dark_bg: bool, central: str) -> tuple[str, ...]:
    pool = [c for c in colors if c != central]
    if len(pool) < 3:
        pool = list(colors)
    if dark_bg:
        pool = [c for c in pool if contrast_ratio(c, bg) >= 1.6] or pool
        pool = _usable(pool, bg, 2.2, "#FFFFFF")
    else:
        # cores quase brancas não servem como ramo: saem (se sobrarem outras) ou escurecem
        keep = [c for c in pool if contrast_ratio(c, bg) >= 1.25]
        pool = keep if len(keep) >= 3 else pool
        pool = _usable(pool, bg, 1.45, "#000000")
    # remove repetidas mantendo a ordem
    seen, out = set(), []
    for c in pool:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return tuple(out)


def _central_source(colors, central: str, anchor: str) -> str:
    """Cor da paleta que virou o central (para não repeti-la num ramo).

    Quando o central é a âncora derivada de uma cor já bem escura da paleta, essa cor sai dos ramos;
    se a âncora foi "inventada" a partir de uma cor média, todas as cores continuam nos ramos."""
    if central != anchor:
        return central
    d = darkest(colors)
    return d if _lum(d) < 0.06 else anchor


_BASE = dict(
    root=dict(shape="arredondado", font_size=26, weight=600, pad_x=26, pad_y=15, line_width=2.5,
              max_text_width=360),
    main=dict(shape="arredondado", font_size=18, weight=600, pad_x=16, pad_y=9, line_width=2.0,
              max_text_width=300),
    sub=dict(shape="arredondado", font_size=15, weight=400, pad_x=8, pad_y=4, line_width=1.5,
             max_text_width=280),
    floating=dict(shape="arredondado", font_size=15, pad_x=12, pad_y=8),
)


def _d(level: str, **kw) -> dict:
    d = dict(_BASE[level])
    d.update(kw)
    return d


@lru_cache(maxsize=256)
def build_theme(colors: tuple[str, ...], variant: int) -> Theme:
    """Monta o tema completo (formas, preenchimentos, fundo) a partir de 6 cores e de uma variação."""
    variant = variant if 0 <= variant < len(VARIANTS) else 0
    anchor = deep_anchor(darkest(colors))
    vivid = most_vivid(colors)
    key = "ct:" + hashlib.md5(("".join(colors) + str(variant)).encode()).hexdigest()[:10]
    common = dict(key=key, label=VARIANTS[variant], hidden=True, strict=True)
    if variant == 4:        # Noturno
        bg = mix(anchor, "#000000", 0.35)
        central = vivid
        if contrast_ratio(central, bg) < 3.0:      # paleta sem cor viva (ex.: Grafite): a mais clara
            central = readable(max(colors, key=_lum), bg, 3.0, "#FFFFFF")
        pal = _branch_colors(colors, bg, True, central)
        return Theme(
            background=bg, relation_color="#A7B0BE", ink="#F2F3F5", selection_color="#58A6FF",
            root=_d("root", fill=central, text_color="$auto", line_color=mix(central, "#FFFFFF", 0.15)),
            main=_d("main", fill="$branch", text_color="$auto"),
            sub=_d("sub", shape="nenhuma", text_color="$deep"),
            floating=_d("floating", fill=mix(bg, "#FFFFFF", 0.12), border=mix(bg, "#FFFFFF", 0.3),
                        border_width=1.2, text_color="#F2F3F5"),
            palette=pal, mono=pal[0] if pal else "#8B949E", tint=0.72, **common)
    if variant == 5:        # Tom sobre tom
        bg = mix(anchor, "#FFFFFF", 0.95)
        pal = _branch_colors(colors, bg, False, _central_source(colors, anchor, anchor))
        return Theme(
            background=bg, relation_color=mix(anchor, "#FFFFFF", 0.45), ink=anchor,
            root=_d("root", shape="capsula", fill=anchor, text_color="$auto", line_color=anchor, pad_x=28),
            main=_d("main", shape="capsula", fill="$branch", text_color="$auto"),
            sub=_d("sub", fill="#FFFFFF", border="$branch", border_width=1.2, text_color="$deep",
                   pad_x=9, pad_y=5),
            floating=_d("floating", fill="#FFFFFF", border=mix(anchor, "#FFFFFF", 0.5), border_width=1.2,
                        text_color=anchor),
            palette=pal, mono=pal[0] if pal else anchor, tint=0.6, **common)
    bg = "#FFFFFF"
    central = vivid if variant == 1 else anchor
    if variant == 1 and contrast_ratio(central, bg) < 1.6:
        central = anchor
    pal = _branch_colors(colors, bg, False, _central_source(colors, central, anchor))
    ink = "#1F2328"
    floating = _d("floating", fill="#EEF1F5", border="#9AA4B2", border_width=1.2)
    root = _d("root", fill=central, text_color="$auto", line_color=mix(central, "#000000", 0.1)
              if variant == 1 else central)
    if variant == 0:        # Contraste
        main = _d("main", fill="$branch", text_color="$auto")
        sub = _d("sub", fill="$tint", text_color="$deep")
    elif variant == 1:      # Central colorido
        main = _d("main", fill="$branch", text_color="$auto")
        sub = _d("sub", shape="nenhuma", text_color="$deep")
    elif variant == 2:      # Suave
        main = _d("main", fill="$tint", text_color="$deep", weight=700)
        sub = _d("sub", shape="nenhuma", text_color="$ink")
    else:                   # Contorno
        main = _d("main", fill="#FFFFFF", border="$branch", border_width=2.0, text_color="$deep")
        sub = _d("sub", shape="nenhuma", text_color="$ink")
    return Theme(background=bg, relation_color="#7C8594", ink=ink, root=root, main=main, sub=sub,
                 floating=floating, palette=pal, mono=mix(anchor, "#FFFFFF", 0.15) if variant != 1 else central,
                 tint=0.84 if variant != 2 else 0.8, **common)


# ------------------------------------------------------------------ mapa
# padrão para novos mapas (definido pelo app a partir de "Usar como padrão para novos mapas")
_DEFAULT_NEW = {"color_theme": DEFAULT_PALETTE.as_setting(), "color_variant": 0}


def set_default_for_new_maps(color_theme: Optional[dict], variant: int = 0) -> None:
    v = sanitize_setting(color_theme) if color_theme else None
    _DEFAULT_NEW["color_theme"] = v or DEFAULT_PALETTE.as_setting()
    _DEFAULT_NEW["color_variant"] = variant if v and 0 <= variant <= 5 else 0


def default_for_new_maps() -> tuple[dict, int]:
    return dict(_DEFAULT_NEW["color_theme"]), int(_DEFAULT_NEW["color_variant"])


def apply_default(m, palette_setting: Optional[dict] = None, variant: Optional[int] = None) -> None:
    """Aplica o tema de cores padrão (ou o escolhido) a um mapa novo."""
    dp, dv = default_for_new_maps()
    m.settings["color_theme"] = sanitize_setting(palette_setting) or dp
    v = dv if variant is None else variant
    if v:
        m.settings["color_variant"] = v
    else:
        m.settings.pop("color_variant", None)


def effective_theme(m) -> Theme:
    """Tema usado para desenhar o mapa: tema de cores (novo) ou tema antigo (compatibilidade)."""
    p = palette_from_setting(m.setting("color_theme"))
    if p is None:
        return get_theme(m.theme)
    try:
        v = int(m.setting("color_variant") or 0)
    except (TypeError, ValueError):
        v = 0
    return build_theme(p.colors, v)


def branch_colors_for(m, theme: Theme) -> tuple[tuple[str, ...], bool]:
    """(cores dos ramos, colorido?) conforme "Ramo colorido" / roda / cor estática."""
    if m.setting("rainbow"):
        key = m.setting("branch_palette")
        if key in BRANCH_PALETTES:
            cols = BRANCH_PALETTES[key][1]
            bg = m.setting("background") or theme.background
            from mindforge.themes import is_dark
            return _branch_colors(cols, bg, is_dark(bg), ""), True
        return theme.palette, True
    static = m.setting("static_color")
    return ((static if is_hex(static) else theme.mono),), False


def current_palette(m) -> Optional[Palette]:
    return palette_from_setting(m.setting("color_theme"))


def legacy_palette(theme_key: str) -> Palette:
    """Paleta equivalente a um tema antigo (para mostrar no seletor quando o mapa é antigo)."""
    th = THEMES.get(theme_key) or THEMES["classico"]
    cols = list(th.palette[:N_COLORS])
    while len(cols) < N_COLORS:
        cols.append(cols[-1])
    return Palette(f"legado/{th.key}", th.label, tuple(c.upper() for c in cols), "legado")
