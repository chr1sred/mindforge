"""Modelos iniciais (esqueletos em branco e exemplos com conteúdo)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mindforge.model.topic import MindMap, Topic


def _tree(spec) -> Topic:
    """spec = "texto" | ("texto", [filhos...])"""
    if isinstance(spec, str):
        return Topic(spec)
    text, kids = spec
    t = Topic(text)
    for k in kids:
        t.add_child(_tree(k))
    return t


def _blank(root: str, n: int, label: str = "Tópico principal") -> Callable[[], Topic]:
    return lambda: _tree((root, [f"{label} {i + 1}" for i in range(n)]))


@dataclass
class Template:
    key: str
    name: str
    layout: str
    build: Callable[[], Topic]
    description: str = ""
    sample: bool = False

    def create(self, theme: str = "classico") -> MindMap:
        return MindMap(self.build(), self.layout, theme)


TEMPLATES: list[Template] = [
    Template("mapa_mental", "Mapa mental", "mapa_mental", _blank("Tema central", 4),
             "Ramos equilibrados dos dois lados. Ideal para brainstorm."),
    Template("mapa_direita", "Mapa lógico", "mapa_direita", _blank("Tema central", 4),
             "Hierarquia da esquerda para a direita. Ideal para planejamento."),
    Template("mapa_esquerda", "Mapa lógico (esquerda)", "mapa_esquerda", _blank("Tema central", 4),
             "Hierarquia crescendo para a esquerda."),
    Template("organograma", "Organograma", "organograma", _blank("Organização", 3, "Área"),
             "Estrutura de cima para baixo: equipes, sitemaps."),
    Template("arvore", "Árvore", "arvore", _blank("Tema central", 3),
             "Colunas com listas indentadas: decomposição de problemas."),
    Template("linha_tempo", "Linha do tempo", "linha_tempo", _blank("Projeto", 4, "Etapa"),
             "Eventos em sequência: cronogramas e roadmaps."),
    Template("espinha_peixe", "Espinha de peixe", "espinha_peixe", _blank("Problema", 4, "Causa"),
             "Diagrama de Ishikawa para análise de causa raiz."),
    # ------------------------------------------------------------- exemplos
    Template("ex_campanha", "Planejamento de campanha", "mapa_mental", lambda: _tree(
        ("Campanha de lançamento", [
            ("Objetivo", ["Leads qualificados", "Meta de CPL"]),
            ("Público", ["Persona principal", "Remarketing", "Lookalike"]),
            ("Canais", ["Google Ads", "Meta Ads", "LinkedIn Ads"]),
            ("Criativos", ["Vídeos curtos", "Carrossel", "Landing page"]),
            ("Mensuração", ["Pixel e conversões", "Relatório semanal"]),
        ])), "Exemplo com conteúdo para mídia paga.", True),
    Template("ex_ishikawa", "Causa raiz (6M)", "espinha_peixe", lambda: _tree(
        ("Queda nas conversões", [
            ("Método", ["Processo de follow-up lento"]),
            ("Máquina", ["Formulário com erro no mobile"]),
            ("Material", ["Criativos saturados"]),
            ("Mão de obra", ["Equipe comercial reduzida"]),
            ("Medição", ["Pixel duplicado"]),
            ("Meio ambiente", ["Sazonalidade"]),
        ])), "Ishikawa com as 6 categorias clássicas.", True),
    Template("ex_roadmap", "Roadmap trimestral", "linha_tempo", lambda: _tree(
        ("Roadmap", [
            ("Mês 1", ["Diagnóstico", "Configuração de contas"]),
            ("Mês 2", ["Testes A/B", "Ajuste de públicos"]),
            ("Mês 3", ["Escala", "Relatório final"]),
        ])), "Linha do tempo com entregas por mês.", True),
    Template("ex_site", "Estrutura de site", "organograma", lambda: _tree(
        ("Site", [
            ("Início", []),
            ("Serviços", ["Serviço A", "Serviço B"]),
            ("Sobre", ["Equipe"]),
            ("Contato", []),
        ])), "Mapa do site em organograma.", True),
]


def get_template(key: str) -> Template:
    for t in TEMPLATES:
        if t.key == key:
            return t
    return TEMPLATES[0]
