"""Limpeza de texto que entra no mapa vindo de fora (1.4.3).

Texto copiado de navegadores, Word, Notion, e-mails etc. costuma trazer espaços especiais,
caracteres invisíveis e quebras de parágrafo que não aparecem na tela mas ficam no tópico.
Aqui só se mexe em espaços, quebras e invisíveis: todo caractere visível (letras, números,
pontuação, símbolos como • ◘ ♦ ☺ →) é mantido exatamente como veio.
"""
from __future__ import annotations

import re

# quebras de linha/parágrafo de todos os sistemas e editores → "\n"
_NEWLINES = re.compile(r"\r\n|[\r  \x0b\x0c\x85]")

# invisíveis: largura zero, BOM, hífen suave, marcas e isolamentos de direção, controles C0/C1
_INVISIBLE = re.compile(
    "[​‌‍⁠﻿­‎‏‪-‮⁦-⁩"
    "\x00-\x08\x0e-\x1f\x7f-\x84\x86-\x9f]")

# espaços "especiais" (não separável, finos, ideográfico...) e tab → espaço comum
_SPACES = re.compile("[\t   -   　]")
_MULTI_SPACE = re.compile(" {2,}")


def normalize_newlines(text: str) -> str:
    return _NEWLINES.sub("\n", text or "")


def remove_invisible(text: str) -> str:
    return _INVISIBLE.sub("", text or "")


def clean_line(line: str) -> str:
    """Uma linha: invisíveis fora, espaços especiais viram um espaço simples, sem pontas."""
    line = _SPACES.sub(" ", remove_invisible(line))
    return _MULTI_SPACE.sub(" ", line).strip()


def clean_lines(text: str) -> list[str]:
    """Linhas limpas e sem as vazias."""
    lines = (clean_line(ln) for ln in normalize_newlines(text).split("\n"))
    return [ln for ln in lines if ln]


def clean_paste(text: str, keep_lines: bool = False) -> str:
    """Texto colado durante a edição de um tópico.

    Padrão: tudo numa linha só (as quebras viram espaço).  ``keep_lines``: mantém uma quebra
    entre as linhas com conteúdo (linhas vazias saem)."""
    return ("\n" if keep_lines else " ").join(clean_lines(text))


def clean_committed(text: str) -> str:
    """Limpeza leve ao confirmar a edição: invisíveis, quebras padronizadas, sem espaço sobrando
    no fim de cada linha nem linhas vazias nas pontas. Espaços digitados no meio ficam."""
    text = remove_invisible(normalize_newlines(text))
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).strip()


def prepare_outline(text: str) -> str:
    """Prepara texto para virar tópicos (colar fora da edição): mantém a indentação do começo
    de cada linha (ela define a hierarquia), limpa o resto."""
    out = []
    for ln in normalize_newlines(remove_invisible(text)).split("\n"):
        ln = _SPACES.sub(lambda m: "\t" if m.group(0) == "\t" else " ", ln)
        indent = len(ln) - len(ln.lstrip(" \t"))
        body = _MULTI_SPACE.sub(" ", ln[indent:]).strip()
        out.append(ln[:indent] + body)
    return "\n".join(out)
