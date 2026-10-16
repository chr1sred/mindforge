# MindForge

Editor de mapas mentais em Python + PySide6 (Qt), inspirado no XMind.

<img width="1657" height="1116" alt="screenshot-01" src="https://github.com/user-attachments/assets/34776931-dc52-46c2-99ec-9a002c4a9019" />

- Roda no **macOS, Windows e Linux**.
- Funciona com **7 esqueletos**, **5 temas** e **7 estilos de ramo**.
- Faz **edição completa pelo teclado** e **desfazer ilimitado até 100 níveis**.
- Exporta **PNG transparente, SVG e PDF vetoriais**.

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
| Recolher / expandir | `Ctrl+/` |
| Desfazer / refazer | `Ctrl+Z` / `Ctrl+Shift+Z` ou `Ctrl+Y` |
| Copiar / recortar / colar / duplicar | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Ctrl+D` |
| Relação | `Ctrl+R`, depois clique no destino |
| Tópico flutuante | Duplo clique no fundo |
| Salvar / exportar / buscar | `Ctrl+S` / `Ctrl+E` / `Ctrl+F` |
| Zoom | `Ctrl+=` / `Ctrl+-` / `Ctrl+0` (ajustar) / `Ctrl+1` (100%) / pinça no trackpad |
| Mover a tela | Rolagem do trackpad, `Espaço`+arrastar ou botão do meio |

**Dicas:**

- **Colar lista indentada.** Colar (`Ctrl+V`) um texto indentado, como uma lista do Notes, de um e-mail ou em Markdown, cria a hierarquia de tópicos automaticamente.
- **Arrastar para reorganizar.** Arrastar um tópico sobre outro o transforma em subtópico dele.

## 4. Painel lateral (estilo XMind)

| Aba | O que tem |
|---|---|
| **Estilo** | Seções recolhíveis: **Forma** (9 formas, preenchimento, largura fixa), **Limite** (estilo, espessura e cor da borda), **Texto** (fonte, peso, tamanho, cor, negrito, itálico, riscado, maiúsculas, alinhamento), **Ramo** (estilo, linha, ponta, espessura, cor), Marcadores e Nota. Botões **Aplicar ao nível** e **Repor estilo** |
| **Mapa** | Esqueleto (galeria com miniaturas), tema de cores, cor de fundo, tipo de letra global, estilo de ramo padrão, largura da linha, ramo colorido, compactar mapa e (na espinha de peixe) alinhar tópicos principais |

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
- **Ramos recolhidos.** Saem recolhidos, exatamente como estão na tela.

## 6. Arquitetura

```
mindforge/
├── model/      Árvore de tópicos e operações (Python puro, sem Qt)
├── layouts/    Um algoritmo por esqueleto (Python puro, testável); gera "grupos de ramos"
├── document.py Undo/redo por snapshot (100 níveis)
├── storage/    .mfmap (JSON versionado, gravação atômica) + recuperação
├── themes.py   Temas e resolução de estilo
├── templates.py Modelos iniciais
├── export/     PNG / SVG / PDF
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

**Formato do arquivo:** JSON legível, com `schema_version` para migrações futuras.

## 7. Testes

```bash
QT_QPA_PLATFORM=offscreen python -m pytest
```

Os 156 testes cobrem:

- **Modelo:** operações e serialização.
- **Desfazer/refazer:** todas as operações e o limite de 100 níveis.
- **Layouts:** ausência de sobreposição de caixas em 60 árvores aleatórias por esqueleto, e desempenho com 1.000 tópicos.
- **Arquivos:** gravação atômica, arquivos corrompidos e recuperação.
- **Exportação:** transparência real do PNG, SVG válido, PDF com fontes embutidas e exportação de ramo.
- **Atalhos:** os de teclado, incluindo os conflitos durante a edição.
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
