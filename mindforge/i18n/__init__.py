"""Idiomas da interface (PT-BR e EN-US).

O português é o idioma-fonte: o texto em português é a CHAVE do catálogo
inglês (estilo gettext). Assim o código continua legível e qualquer texto
sem tradução aparece em português, nunca quebra.

    tr("Salvar")                         -> "Save" em inglês
    tr("Salvo em {path}", path=p)        -> "Saved to /x"
    ntr("{n} tópico", "{n} tópicos", n)  -> plural correto
    N_("Clássico")                       -> só marca o texto para tradução (usado
                                            em constantes); traduza ao exibir com tr()

Os testes garantem que toda chave usada no código tenha tradução.
"""
from __future__ import annotations

import os
from typing import Optional

LANGUAGES = {
    "pt_BR": "Português (PT-BR)",
    "en_US": "English (EN-US)",
}
DEFAULT = "pt_BR"
_state = {"lang": DEFAULT}


def N_(text: str) -> str:
    return text


def language() -> str:
    return _state["lang"]


def set_language(code: Optional[str]) -> str:
    _state["lang"] = code if code in LANGUAGES else DEFAULT
    return _state["lang"]


def _catalog() -> dict:
    if _state["lang"] == "en_US":
        from mindforge.i18n.en_us import EN
        return EN
    return {}


def tr(text: str, **kw) -> str:
    out = _catalog().get(text, text)
    return out.format(**kw) if kw else out


def ntr(singular: str, plural: str, n: int, **kw) -> str:
    return tr(singular if n == 1 else plural, n=n, **kw)


def system_language() -> str:
    """Idioma inicial: português se o sistema estiver em português; senão, inglês."""
    forced = os.environ.get("MINDFORGE_IDIOMA", "")
    if forced in LANGUAGES:
        return forced
    try:
        from PySide6.QtCore import QLocale
        names = [QLocale.system().name()] + list(QLocale.system().uiLanguages())
    except Exception:  # pragma: no cover
        names = []
    return "pt_BR" if any(str(n).lower().startswith("pt") for n in names) else "en_US"
