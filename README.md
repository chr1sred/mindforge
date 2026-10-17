# MindForge

🇧🇷 Português · [🇺🇸 English](README.en.md)

Editor de mapas mentais em Python + PySide6 (Qt), inspirado no XMind.

- Roda no **macOS, Windows e Linux**.
- Funciona com **7 esqueletos**, **21 temas de cores em 6 variações** (mais as suas paletas) e **7 estilos de ramo**.
- Faz **edição completa pelo teclado** e **desfazer ilimitado até 100 níveis**.
- Exporta **PNG transparente, SVG e PDF vetoriais**.
- Interface em **português (PT-BR) e inglês (EN-US)**.

---

## 1. Instalar e rodar (macOS + VS Code)

```bash
cd mindforge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m mindforge                     # ou F5 no VS Code ("MindForge")
```

> Requer Python 3.11 ou superior. No VS Code, selecione o interpretador `.venv` (Cmd+Shift+P → *Python: Select Interpreter*).

Para abrir um arquivo direto: `python -m mindforge caminho/do/mapa.mfmap`

> **Atualizando de uma versão anterior?** O `pip install -r requirements-dev.txt` não muda nesta versão; basta substituir os arquivos e rodar os testes.

## 2. Gerar o instalável (PyInstaller)

| Sistema | Comando | Resultado |
|---|---|---|
| macOS | `./build.sh` | `dist/MindForge.app` e `dist/MindForge.dmg` |
| Windows | `build.bat` | `dist\MindForge\MindForge.exe` |
| Linux | `./build.sh` | `dist/MindForge/MindForge` |

Os scripts criam o ambiente, **rodam os testes** (o build para se algum falhar) e chamam:

```bash
pyinstaller mindforge.spec --noconfirm
```

**Observações:**

- **Gere o instalador em cada sistema.** O PyInstaller não faz build cruzado: o `.exe` precisa ser gerado no Windows, e o `.app` no Mac.
- **Arquivos `.mfmap` abrem com duplo clique.** No macOS, o `.app` já registra a extensão `.mfmap`, então o arquivo abre direto no MindForge pelo Finder.
- **Distribuição para outros Macs.** Sem assinatura da Apple, o macOS mostra um aviso na primeira abertura; basta clicar com o botão direito → *Abrir*. Para distribuir sem esse aviso é preciso assinar e notarizar com uma conta Apple Developer.
- **Mac Intel e Apple Silicon.** O pacote é gerado para a arquitetura do Mac onde foi feito o build. Para atender os dois tipos de Mac, gere em cada arquitetura ou use um Python *universal2*.

## 3. Atalhos

No macOS, `Ctrl` = `⌘`. A lista completa também está em **Ajuda → Atalhos de teclado (F1)**.

| Ação | Atalho |
|---|---|
| Novo subtópico | `Tab` |
| Novo irmão abaixo / acima | `Enter` / `Shift+Enter` |
| Inserir tópico pai | `Ctrl+Enter` |
| Editar texto | `F2`, `Espaço` ou comece a digitar |
| Quebra de linha (editando) | `Shift+Enter` |
| Confirmar / cancelar edição | `Enter` / `Esc` |
| Excluir tópico | `Delete` / `Backspace` |
| Navegar | Setas |
| Mover entre irmãos | `Ctrl+↑` / `Ctrl+↓` |
| Recolher / expandir | `Ctrl+/`, ou clique no `⊖` / no número do ramo |
| Expandir o ramo inteiro | `Alt`+clique no número |
| Desfazer / refazer | `Ctrl+Z` / `Ctrl+Shift+Z` ou `Ctrl+Y` |
| Copiar / recortar / colar / duplicar | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Ctrl+D` |
| Relação | `Ctrl+R`, depois clique no destino |
| Tópico flutuante | Duplo clique no fundo |
| Salvar / exportar / buscar | `Ctrl+S` / `Ctrl+E` / `Ctrl+F` |
| Zoom | `Ctrl+=` / `Ctrl+-` / `Ctrl+0` (ajustar) / `Ctrl+1` (100%) / pinça no trackpad |
| Mover a tela | Botão direito+arrastar, rolagem do trackpad, `Espaço`+arrastar ou botão do meio |

**Dicas:**

- **Colar lista indentada.** Colar (`Ctrl+V`) um texto indentado, como uma lista do Notes, de um e-mail ou em Markdown, cria a hierarquia de tópicos automaticamente.
- **Arrastar para reorganizar.** Arrastar um tópico sobre outro o transforma em subtópico dele.

**Recolher ramos (estilo XMind).** Passe o mouse sobre um tópico com subtópicos (ou selecione-o): aparece um `⊖` na saída do ramo. Clique nele para recolher; no lugar fica um círculo com o **número de tópicos escondidos**. Clique no número para expandir só aquele nível, ou `Alt`+clique para expandir o ramo inteiro. O tópico central não recolhe.

O controle tem **hover próprio**: com o mouse em cima, ele fica preenchido na cor do ramo, um pouco maior, com a mãozinha e uma dica. Ele espera um instante antes de sumir, para dar tempo de o mouse ir do tópico até ele, e no zoom baixo a área de clique não fica menor que cerca de 16 px na tela. Clicar em qualquer ponto da caixa do tópico sempre seleciona o tópico.

**Botão direito.** Clique simples abre o menu de contexto, como antes. Clicar e **segurar arrastando** move o quadro (o cursor vira a mãozinha fechada), e o quadro cresce se você passar da borda do mapa.

## Idioma / Language

O idioma fica em **Ajustes → Idioma / Language**:

| Sistema | Onde fica |
|---|---|
| macOS | Menu **MindForge → Ajustes…** (`⌘,`), logo abaixo de *Sobre o MindForge* |
| Windows / Linux | Menu **Ajuda → Ajustes…**, logo abaixo de *Sobre o MindForge* |

- **Troca na hora.** As janelas são recriadas no novo idioma sem fechar os mapas abertos, sem perder alterações não salvas e mantendo o histórico de desfazer.
- **Primeira execução.** Segue o idioma do sistema: português se o sistema estiver em português; inglês nos demais casos.
- **O que é traduzido.** Menus, painéis, diálogos, mensagens, modelos e os textos padrão dos tópicos novos ("Tópico principal" vira "Main Topic"). **O conteúdo dos mapas não é traduzido.**
- **Forçar um idioma** (útil em testes): `MINDFORGE_IDIOMA=en_US` ou `MINDFORGE_IDIOMA=pt_BR`.

## 4. Painel lateral (estilo XMind)

| Aba | O que tem |
|---|---|
| **Estilo** | Seções recolhíveis: **Forma** (9 formas, preenchimento, largura fixa), **Limite** (estilo, espessura e cor da borda), **Texto** (fonte, peso, tamanho, cor, negrito, itálico, riscado, maiúsculas, alinhamento), **Ramo** (estilo, linha, ponta, espessura, cor), Marcadores e Nota. Botões **Aplicar ao nível** e **Repor estilo** |
| **Mapa** | Esqueleto (galeria com miniaturas), tema de cores (paleta + 6 variações), cor de fundo, tipo de letra global, estilo de ramo padrão, largura da linha, ramo colorido, compactar mapa e (na espinha de peixe) alinhar tópicos principais |

### Tema de cores (estilo XMind)

Em **Mapa → Tema de cores**, o botão com a faixa de cores abre o seletor com três abas:

| Aba | O que tem |
|---|---|
| **A Minha Cor** | Suas paletas. O botão **+** (ou "Criar paleta…") abre **Criar novo tema de cores**: 6 cores, nome e pré-visualização ao vivo. **Completar automaticamente** sugere as cores que faltam, em harmonia com 1 ou 2 escolhidas. Clique direito numa paleta: Editar, Duplicar, Renomear, Excluir |
| **Colorido** | 12 paletas: Arco-íris (padrão), Aurora, Tropical, Neon suave, Pôr do sol, Oceano, Primavera, Doces, Vibrante, Floresta, Cítrico, Pastel |
| **Clássico** | 9 paletas: Executivo, Grafite, Terra, Marinho, Bordô, Vintage, Nórdico, Sálvia, Escuro |

Abaixo do botão, as **6 variações** aplicam a mesma paleta de jeitos diferentes:

| Variação | Como fica |
|---|---|
| Contraste | Central escuro, principais preenchidos, subtópicos em caixas claras |
| Central colorido | Central na cor mais viva, subtópicos só com texto |
| Suave | Principais em tons claros com texto na cor do ramo |
| Contorno | Principais com borda colorida e fundo branco |
| Noturno | Fundo escuro, textos claros |
| Tom sobre tom | Fundo levemente tingido, formas em cápsula, subtópicos contornados |

**Detalhes:**

- **Contraste garantido.** Textos e linhas são ajustados automaticamente para continuarem legíveis em qualquer paleta, inclusive nas muito claras.
- **Fundo.** Trocar de tema ou variação volta a cor de fundo para a do tema (a variação Noturno tem fundo escuro).
- **Estilo manual vence.** O que você formatou à mão num tópico continua igual ao trocar de tema; **Repor estilo** volta ao tema.
- **Paletas suas no arquivo.** As cores ficam gravadas dentro do `.mfmap`: o mapa abre igual em outro computador, mesmo que a paleta não exista lá ou tenha sido excluída.
- **Padrão para novos mapas.** No seletor, **Usar como padrão para novos mapas** guarda o tema e a variação atuais. As paletas e o padrão ficam em `temas.json`, na pasta de dados do app.
- **Mapas antigos.** Mapas criados com os temas da 1.2 (Clássico, Escuro, Oceano, Minimalista, Pastel) abrem idênticos; ao escolher uma variação ou paleta, passam para o sistema novo.
- **Aviso na exportação.** Com fundo escuro e "Fundo transparente" marcado, o diálogo avisa que os textos claros podem sumir num documento branco.

**Ramo colorido.** Ligado, o botão ao lado abre uma roda com 9 conjuntos de cores para os ramos (o primeiro, **Do tema**, usa a paleta atual). A roda muda principais, subtópicos e linhas, nunca o tópico central. Desligado, o botão vira uma **cor estática** única para todos os ramos.

**Ramos.** As opções de Ramo de um tópico valem para as linhas que saem dele para os subtópicos. Marque **Aplicar também aos descendentes** para estender a escolha ao ramo inteiro.

| Estilo de ramo | Desenho |
|---|---|
| Colchete curvo (⊂) | Padrão do mapa lógico e da árvore |
| Colchete reto (⊏) | Padrão do organograma |
| Chave ({) | Padrão do mapa mental e das costelas da espinha de peixe |
| Leque reto, Arco, Diagonal, Leque curvo | Variações disponíveis em qualquer esqueleto horizontal ou vertical |

**Seleção múltipla.** Com vários tópicos selecionados, valores diferentes aparecem como "—" e qualquer alteração vale para todos.

**Fonte.** O app traz a fonte **Inter** embutida (licença SIL OFL, em `assets/fonts/OFL.txt`), então o mapa fica igual no Mac e no Windows. Se um mapa usar uma fonte que não existe no computador, o painel avisa e o app usa uma substituta.

A barra superior traz Tópico (com menu de opções), Subtópico, Relação, Marcador, Nota, Desfazer/Refazer, Buscar, Exportar, Tela cheia e Painel. O zoom fica no canto inferior direito.

A interface acompanha o modo claro/escuro do sistema. Para forçar um modo, defina a variável `MINDFORGE_APARENCIA=claro` ou `MINDFORGE_APARENCIA=escuro`.

A **espinha de peixe** cresce da esquerda para a direita. As espinhas de cima e de baixo formam pares que saem do mesmo ponto da coluna, cada uma com o comprimento do seu conteúdo, e nenhum texto cruza uma linha.

## 5. Exportação

| Formato | Opções |
|---|---|
| PNG | Fundo transparente (padrão), escala 1x–4x, margem |
| SVG | Fundo transparente, textos editáveis ou convertidos em curvas |
| PDF | Página do tamanho do mapa, A4/A3; fontes embutidas e texto selecionável |

**Regras que valem para os três formatos:**

- **Escopo.** Pode exportar o mapa inteiro ou só o ramo selecionado.
- **Sem elementos de interface.** Seleção e cursor nunca aparecem no arquivo exportado.
- **Ramos recolhidos.** Saem recolhidos, exatamente como estão na tela, com o círculo do número de tópicos escondidos. O botão `⊖` nunca é exportado.

## 6. Arquitetura

```
mindforge/
├── model/      Árvore de tópicos e operações (Python puro, sem Qt)
├── layouts/    Um algoritmo por esqueleto (Python puro, testável); gera "grupos de ramos"
├── document.py Undo/redo por snapshot (100 níveis)
├── storage/    .mfmap (JSON versionado, gravação atômica) + recuperação + paletas do usuário
├── themes.py   Temas e resolução de estilo (com contraste mínimo)
├── colorthemes.py Temas de cores: paletas, 6 variações, roda do Ramo colorido
├── templates.py Modelos iniciais
├── export/     PNG / SVG / PDF
├── i18n/       Idiomas: tr()/ntr()/N_() e catálogo inglês (en_us.py)
└── view/       Cena, itens gráficos, ramos (branches.py), canvas (atalhos), janela, painel, diálogos
```

**Decisões de robustez:**

- **Desfazer por snapshot.** Toda alteração passa por `Document.apply()`, que guarda o estado antes e depois. Assim, qualquer funcionalidade nova já nasce desfazível.
- **Criar e nomear viram um único desfazer.** "Criar tópico + digitar o nome" é mesclado em um único `Ctrl+Z`.
- **Edição de texto protegida.** Durante a edição, `Delete`, `Ctrl+C` e `Ctrl+Z` agem sobre o texto, não sobre o mapa. `Ctrl+S` confirma a edição e salva.
- **Gravação atômica.** O arquivo é gravado num temporário, recebe `fsync` e só então substitui o original.
- **Recuperação automática.** O autosave a cada 60 s vai para uma pasta de recuperação. Se o app fechar inesperadamente, os mapas são oferecidos na próxima abertura.
- **Fontes em pixels.** Isso garante o mesmo tamanho na tela, no PNG, no SVG e no PDF, independentemente do DPI de cada sistema.
- **Tronco único.** Cada pai desenha as linhas para os filhos como um grupo: o tronco compartilhado é traçado uma vez só, sem sobreposições que deixem a linha irregular.
- **Desenho em código.** Ícones e marcadores são desenhados com `QPainter` e saem vetoriais nas exportações.
- **Português como chave de tradução.** O texto em português no código é a chave do catálogo inglês (estilo gettext). Um texto sem tradução aparece em português, nunca quebra, e um teste falha se faltar alguma tradução.

**Formato do arquivo:** JSON legível, com `schema_version` para migrações futuras.

## 7. Testes

```bash
QT_QPA_PLATFORM=offscreen python -m pytest
```

Os 205 testes cobrem:

- **Modelo:** operações e serialização.
- **Desfazer/refazer:** todas as operações e o limite de 100 níveis.
- **Layouts:** ausência de sobreposição de caixas em 60 árvores aleatórias por esqueleto, e desempenho com 1.000 tópicos.
- **Arquivos:** gravação atômica, arquivos corrompidos e recuperação.
- **Exportação:** transparência real do PNG, SVG válido, PDF com fontes embutidas e exportação de ramo.
- **Atalhos:** os de teclado, incluindo os conflitos durante a edição.
- **Recolher e botão direito (1.3):** contagem de escondidos, círculo sem colidir com tópicos em todos os esqueletos, `⊖` fora da exportação, clique em toda a caixa do tópico em todos os esqueletos e zooms, hover próprio do controle, duplo clique no controle, clique simples × arrasto.
- **Idiomas (1.3):** toda chave com tradução, marcadores e atalhos preservados, nenhuma palavra em português na interface inglesa, troca de idioma preservando documento, seleção e desfazer.
- **Temas de cores (1.3):** contraste mínimo de texto e linhas em todas as paletas e variações, mapas antigos idênticos, roda sem alterar o central, cor estática, paleta dentro do arquivo, paletas do usuário (criar, editar, duplicar, excluir, limite, arquivo corrompido), completar automaticamente, padrão para novos mapas, painel, menu e aviso de exportação.
- **Ramos e estilo (1.2):** os 7 estilos em todas as direções, pontas, padrões de linha, tronco único, espinha de peixe sem nenhuma linha cruzando texto, formas, riscado no SVG, compatibilidade com mapas antigos e o painel.

## 8. Próximas versões

Ficaram para versões futuras:

- Importar arquivos `.xmind`.
- Exportar e importar Markdown e OPML.
- Imagens dentro dos tópicos.
- Modo apresentação.
- Estrutura por tópico (cada ramo com esqueleto próprio).
- Linhas "à mão livre" e ramos afunilados.
- Estilos salvos (presets próprios).
