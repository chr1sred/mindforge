"""Modelos iniciais (esqueletos em branco e exemplos com conteúdo)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from mindforge.i18n import N_, tr
from mindforge.model.topic import MindMap, Topic


def _tree(spec) -> Topic:
    """spec = "texto" | ("texto", [filhos...])"""
    if isinstance(spec, str):
        return Topic(tr(spec))
    text, kids = spec
    t = Topic(tr(text))
    for k in kids:
        t.add_child(_tree(k))
    return t


def _blank(root: str, n: int, label: str = N_("Tópico principal")) -> Callable[[], Topic]:
    def build() -> Topic:
        t = Topic(tr(root))
        for i in range(n):
            t.add_child(Topic(f"{tr(label)} {i + 1}"))
        return t
    return build


@dataclass
class Template:
    key: str
    name: str
    layout: str
    build: Callable[[], Topic]
    description: str = ""
    sample: bool = False

    def create(self, theme: Optional[str] = None, palette: Optional[dict] = None,
               variant: Optional[int] = None) -> MindMap:
        """Mapa novo. Sem `theme`, usa o tema de cores padrão (ou `palette`/`variant`).

        `theme` com a chave de um tema antigo cria o mapa no modelo anterior (compatibilidade)."""
        m = MindMap(self.build(), self.layout, theme or "classico")
        if theme is None:
            from mindforge.colorthemes import apply_default
            apply_default(m, palette, variant)
        return m


TEMPLATES: list[Template] = [
    Template("mapa_mental", N_("Mapa mental"), "mapa_mental", _blank(N_("Tema central"), 4),
             N_("Ramos equilibrados dos dois lados. Ideal para brainstorm.")),
    Template("mapa_direita", N_("Mapa lógico"), "mapa_direita", _blank(N_("Tema central"), 4),
             N_("Hierarquia da esquerda para a direita. Ideal para planejamento.")),
    Template("mapa_esquerda", N_("Mapa lógico (esquerda)"), "mapa_esquerda", _blank(N_("Tema central"), 4),
             N_("Hierarquia crescendo para a esquerda.")),
    Template("organograma", N_("Organograma"), "organograma", _blank(N_("Organização"), 3, N_("Área")),
             N_("Estrutura de cima para baixo: equipes, sitemaps.")),
    Template("arvore", N_("Árvore"), "arvore", _blank(N_("Tema central"), 3),
             N_("Colunas com listas indentadas: decomposição de problemas.")),
    Template("linha_tempo", N_("Linha do tempo"), "linha_tempo", _blank(N_("Projeto"), 4, N_("Etapa")),
             N_("Eventos em sequência: cronogramas e roadmaps.")),
    Template("espinha_peixe", N_("Espinha de peixe"), "espinha_peixe", _blank(N_("Problema"), 4, N_("Causa")),
             N_("Diagrama de Ishikawa para análise de causa raiz.")),
    # ------------------------------------------------------------- exemplos
    Template("ex_campanha", N_("Planejamento de campanha"), "mapa_mental", lambda: _tree(
        (N_("Campanha de lançamento"), [
            (N_("Objetivo"), [N_("Leads qualificados"), N_("Meta de CPL")]),
            (N_("Público"), [N_("Persona principal"), N_("Remarketing"), N_("Lookalike")]),
            (N_("Canais"), [N_("Google Ads"), N_("Meta Ads"), N_("LinkedIn Ads")]),
            (N_("Criativos"), [N_("Vídeos curtos"), N_("Carrossel"), N_("Landing page")]),
            (N_("Mensuração"), [N_("Pixel e conversões"), N_("Relatório semanal")]),
        ])), N_("Exemplo com conteúdo para mídia paga."), True),
    Template("ex_ishikawa", N_("Causa raiz (6M)"), "espinha_peixe", lambda: _tree(
        (N_("Queda nas conversões"), [
            (N_("Método"), [N_("Processo de follow-up lento")]),
            (N_("Máquina"), [N_("Formulário com erro no mobile")]),
            (N_("Material"), [N_("Criativos saturados")]),
            (N_("Mão de obra"), [N_("Equipe comercial reduzida")]),
            (N_("Medição"), [N_("Pixel duplicado")]),
            (N_("Meio ambiente"), [N_("Sazonalidade")]),
        ])), N_("Ishikawa com as 6 categorias clássicas."), True),
    Template("ex_roadmap", N_("Roadmap trimestral"), "linha_tempo", lambda: _tree(
        (N_("Roadmap"), [
            (N_("Mês 1"), [N_("Diagnóstico"), N_("Configuração de contas")]),
            (N_("Mês 2"), [N_("Testes A/B"), N_("Ajuste de públicos")]),
            (N_("Mês 3"), [N_("Escala"), N_("Relatório final")]),
        ])), N_("Linha do tempo com entregas por mês."), True),
    Template("ex_site", N_("Estrutura de site"), "organograma", lambda: _tree(
        (N_("Site"), [
            (N_("Início"), []),
            (N_("Serviços"), [N_("Serviço A"), N_("Serviço B")]),
            (N_("Sobre"), [N_("Equipe")]),
            (N_("Contato"), []),
        ])), N_("Mapa do site em organograma."), True),
]


def get_template(key: str) -> Template:
    for t in TEMPLATES:
        if t.key == key:
            return t
    return TEMPLATES[0]
