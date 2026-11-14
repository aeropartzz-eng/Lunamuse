# Auditoria detalhada — Protótipo da Memória QG

**Arquivo:** "Protótipo da Memória QG" — https://www.figma.com/make/auRPfO4GFJtvtmGHosEf1G
**Versão:** Figma Make V3 (V1 12/11/2026 20:19 — protótipo da interface; V2 20:30 — troca de projeto e responsivo; V3 21:35 — backend de referência FastAPI/Mongo e integração verificada)
**Auditoria:** somente leitura, 2026-11-13 07:36–07:41. Nada editado, nenhuma proposta aprovada, recusada ou marcada como lida.
**Veredito em uma linha:** protótipo de interface bem estruturado, mas hoje é só uma demonstração com dados fictícios — sem backend, sem dado real, sem usuário, sem ferramenta, skill ou organograma, e sem nenhum servidor MCP dentro dele.

## 1. Estado geral

- Cabeçalho: "Demonstração · dados fictícios" e "Dados fictícios. Relógio fixo em 12/11/2026, 15:00."
- Todas as fichas do QG: "Compilada em 12/11/2026, 15:00 · revisão do projeto 18" e "Cobertura estrutural não prova verdade nem autoriza ação."
- Estrutura: 2 projetos, seletores "PROJETO" e "TAREFA", ficha da tarefa no centro, painel lateral com abas "Buscar" e "Revisar propostas".
- O prompt de IA do Figma Make estava desativado sem conta ("Crie sua conta para usar o Figma Make"). A visualização em tela cheia abre o mesmo aplicativo, sem visão de código.
- **Não há base real no arquivo:** sem código-fonte, sem endpoints, sem esquema de banco, sem documentação técnica e sem conexão viva. O único "esquema" visível é o JSON de metadados em "Detalhes técnicos" dos diálogos de origem.

## 2. Inventário das tarefas — "QG do Zero · Memória (demo)"

| Tarefa | Contrato | Estado | Cobertura |
|---|---|---|---|
| MEM-001 · Confirmar a VPS e seus recursos | Retomar | Bloqueada | 4 de 5 (missing) |
| MEM-003 · Corrigir a criação manual de memória | Implementar | Pronta | 5 de 5 (covered) |
| MEM-005 · Garantir substituição e escrita recuperáveis | Implementar | Não iniciada | 3 de 5 (conflict) |
| MEM-011 · Validar cliente gratuito e capacidade | Verificar | Não iniciada | 4 de 5 (insufficient_budget) |
| LIVRE-01 · Pergunta aberta: histórico de decisões sobre cache | — | Aberta | Não avaliada (unassessed) |

Só a MEM-003 está "Coberta". Nenhuma tarefa do QG está concluída com evidência real medida.

### MEM-001 — Confirmar a VPS e seus recursos
- Objetivo: registrar CPU, RAM livre sob carga, swap, disco, serviços e topologia do Mongo da VPS, sem segredos.
- Estado conhecido: "Inventário não iniciado. Hardware da VPS: Não medido."
- Bloqueio: "Aguardando credencial de acesso somente leitura à VPS." (Cronograma MEM-001, 12/11/2026).
- Atenção: última evidência ausente; restrição de congelamento da VPS vencida.
- Próximo passo: medir recursos livres sob carga típica e registrar o inventário datado.
- Técnicos: teto 1.600 B; contrato "retomar.v1"; obrigatório serializado 642 B; ficha serializada 1.004 B; tokens, latência p50/p95, CPU/RAM e chamadas de modelo: "Não medido".

### MEM-003 — Corrigir a criação manual de memória
- Objetivo: remover a passagem duplicada de `source` na criação de memória, sem alterar o contrato, preservando IDs e sem registrar segredos.
- Estado conhecido: o backend aceita `source` no corpo e `source` já vem preenchida em `backend/routers/memories.py`. Versões FastAPI e Mongo: "Não medido".
- Evidências: em `POST /memories`, `source` vazio produz o mesmo efeito que `source` preenchido; tipo de `source` inválido é rejeitado; teste isolado demonstra a regressão e a correção.
- Próximo passo: escrever o teste de regressão que demonstra a duplicação de `source` antes de aplicar a correção.
- "Pronta" aqui significa ficha coberta (5 de 5), não correção entregue.
- Técnicos: contrato "implementar.v1"; obrigatório 734 B; ficha 1.283 B; métricas "Não medido".

### MEM-005 — Garantir substituição e escrita recuperáveis
- Objetivo: inserir a memória substituta e marcar a antiga como substituída de forma recuperável, sem janela sem versão.
- Estado conhecido: "A topologia do Mongo ainda não foi definida para a escrita de substituição."
- Contradição (núcleo): Versão A — operação isolada em replica set, com transações multi-documento (conversa de planejamento, 08/11/2026); Versão B — operação isolada em standalone, com escrita atômica em um único documento (importação de notas antigas, 11/11/2026). Ambas com botão "Manter esta".
- Dependências: depende de MEM-001 e MEM-003; cronograma MEM-005 venceu 11/11/2026.
- Técnicos: contrato "implementar.v1"; obrigatório 749 B; ficha 1.202 B; métricas "Não medido".

### MEM-011 — Validar cliente gratuito e capacidade
- Objetivo: o cliente gratuito deve concluir uma tarefa "retomar.v1" com uma única inferência, com a resposta correta e sem ciclos de busca decididos pelo modelo.
- Estado conhecido: "A VPS ainda não foi medida (depende da MEM-001). Cliente gratuito: a definir."
- Problema: o mínimo obrigatório ocupa 1.647 B e supera o teto da ficha de 1.600 B (47 B acima); ficha serializada 2.065 B (465 B acima). A ficha oferece "Aumentar teto" ou "Dividir tarefa", sem decisão.
- Próximo passo: executar ao menos 30 consultas rotuladas no piloto, separando qualidade de latência.
- Técnicos: contrato "verificar.v1"; obrigatório 1.647 B; ficha 2.065 B; métricas "Não medido".

### LIVRE-01 — Pergunta aberta: histórico de decisões sobre cache
- Sem contrato, sem objetivo, sem estado conhecido, sem bloqueios, sem evidências e sem próximo passo. "Tarefa sem contrato: use a busca aberta. Cobertura não avaliada."
- Técnicos: contrato "—"; obrigatório 353 B; ficha 544 B; métricas "Não medido".

## 3. Aba "Buscar" — comportamento medido

- Filtros por estado: "Aprovadas", "Propostas", "Substituídas", "Todas" (padrão). No QG: Aprovadas = 28; Propostas = 3; Substituídas = 1; Todas = 32 (a conta fecha).
- Ordenação declarada: por termos e depois por data de registro. Paginação: 5 itens por vez; "Carregar mais" acrescenta 5.
- Busca testada (filtra de fato e destaca o termo): "cache" = 2; "FastAPI" = 2; "Mongo" = 8; "esquema" = 2; **"ferramenta" = 0; "habilidade" = 0** ("Nada encontrado com esses termos e filtro.").
- Cada resultado abre o diálogo "Origem da memória": tipo e escopo, texto completo, fonte, autor, "Registrada em", "Vale desde", "Vale até", escopo, "Ver versão anterior" e "Detalhes técnicos" com JSON de metadados. Sem edição nesse diálogo.
- Observação menor: ao trocar o termo, o contador do cabeçalho às vezes ficou um passo atrás do conteúdo já filtrado. Não afeta os números finais.

## 4. Aba "Revisar propostas" — as 3 propostas (fila global do projeto)

A fila é por projeto, não por tarefa: as mesmas 3 propostas aparecem em todas as tarefas.

- **p-3 — "Decisão — Projeto"** (IA "Assistente gratuito (demo)"): teto padrão de contexto, 800 tokens alvo e 1.600 como máximo. Fonte: conversa de planejamento, 12/11/2026. **Sem evidência.** Aprovação travada: checkbox "Confirmo que li o conteúdo" e botão "Aprovar" desativado.
- **p-2 — "Fato — MEM-005"**: "Mongo standalone: sem transações multi-documento." Fonte: execução de diagnóstico (demo), 12/11/2026. **Tem "Ver evidência" e "Aprovar" habilitado, sem checkbox.** A evidência é uma memória já "Aprovada": saída de `rs.status()` em cópia isolada — "NotYetInitialized" (indica standalone), registrada 12/11/2026 08:40. Ou seja, existe evidência aprovada apontando standalone, mas a MEM-005 continua "Contradição" e a proposta pendente.
- **p-1 — "Última evidência — MEM-001"**: inventário parcial, 2 vCPU e 4 GB de RAM informados pelo painel do provedor. Fonte: conversa de suporte, 12/11/2026. **Sem evidência.** Aprovação travada pelo checkbox.
- Única memória "Substituída" do QG: "Cache ligado por padrão com TTL de 300 s" (conversa de planejamento, 06/11/2026), substituída pela restrição atual de cache desligado.

## 5. "Loja exemplo (demo)"

- 1 tarefa: "LOJA-01 · Calcular frete por CEP" — "Retomar", "Em andamento", "Coberta", 5 de 5.
- Objetivo: ajustar a tabela de frete por faixa de CEP, sem alterar as regras de desconto. Estado: faixas do Nordeste revisadas; demais regiões pendentes.
- Restrição: "Não acessar dados de clientes reais." Bloqueios: nenhum. Evidência: planilha de faixas revisada (versão 3, demo). Próximo passo: revisar as faixas do Sudeste.
- Buscar: 6 resultados, todos "Aprovadas". Revisar propostas: nenhuma pendente.
- Técnicos: teto 1.600 B; contrato "retomar.v1"; obrigatório 240 B; ficha 517 B; métricas "Não medido".

## 6. Backend / FastAPI-Mongo, esquema e documentação

Nada disso existe como código ou documento dentro do arquivo visível sem login. Só referências:
- Descrição da V3: "Backend de referência FastAPI/Mongo da memória e integração verificada" (afirmação do histórico, sem código para conferência).
- Menções: "Preservar FastAPI/Mongo…", "backend/routers/memories.py", "Versões FastAPI e Mongo: Não medido", "topologia do Mongo (standalone ou replica set)".
- O mais próximo de um esquema é o JSON de metadados por memória (ex.: memória "m-r5": id, revision 12, fact_key null, validation_state "aprovada", source_ref {type "revisao_tarefa", label "Segunda revisão da proposta", ref "task-review/MEM-000"}, recorded_at "2026-11-11T16:40:00-03:00", valid_from, valid_until null, requires [], supersedes "m-old1", superseded_by null, legacy_id null, operation_id null).
- Não há: rotas/endpoints de API, modelo de dados, migração, script, repositório, credencial, URL de servidor, nem documentação de integração.

## 7. Regras e restrições visíveis

Regras do projeto (repetidas em todas as tarefas do QG):
- Preservar FastAPI/Mongo e os IDs históricos das memórias; mudanças de esquema apenas aditivas.
- Não adicionar LLM, embeddings, GPU ou serviço novo no caminho de leitura.
- Testes somente em ambiente isolado com dados sintéticos; não usar a VPS de produção.
- Congelamento de alterações na VPS durante a janela de manutenção — **vencido em 10/11/2026**.
- Cache de pacotes desligado até a MEM-015 comprovar publicação consistente por revisão.
- Teto de contexto: 800 tokens alvo e 1.600 máximo (ainda só proposta, sem evidência). Teto de ficha: 1.600 B (opções 800 / 1.600 / 3.200 B).
- Aviso recorrente: "Cobertura estrutural não prova verdade nem autoriza ação."

## 8. Lacunas, contradições, bloqueios e riscos encontrados

1. **MEM-001 bloqueada na origem.** Sem credencial de acesso somente leitura à VPS, inventário não iniciado, hardware "Não medido", última evidência ausente. Toda a cadeia depende dela: MEM-005 depende de MEM-001 e MEM-003; MEM-011 depende de MEM-001.
2. **Contradição do Mongo sem decisão.** MEM-005 opõe replica set (08/11) a standalone (11/11). A evidência aprovada de `rs.status()` (standalone) já existe e a proposta p-2 já a referencia, mas a tarefa segue "Contradição" e a escolha "Manter esta" continua pendente nas duas versões. Risco: qualquer escrita de substituição implementada antes da decisão pode usar o mecanismo errado.
3. **MEM-011 estoura o teto.** Obrigatório 1.647 B > teto 1.600 B; ficha 2.065 B. Sem decisão entre "Aumentar teto" e "Dividir tarefa". Cliente gratuito "a definir" e piloto de 30 consultas não executado.
4. **MEM-003 "Pronta" sem correção aplicada.** O bug da duplicação de `source` está descrito e o teste de regressão ainda é o próximo passo; "Pronta" = ficha coberta, não correção entregue.
5. **Referências a tarefas inexistentes.** A regra do cache depende da "MEM-015", que não existe entre as tarefas; as restrições citam "Revisão da MEM-000", que também não é uma tarefa do seletor. A regra do cache não pode ser cumprida nem verificada como está escrita.
6. **Restrições e prazos vencidos sem revalidação.** Congelamento da VPS venceu 10/11/2026; cronograma da MEM-005 venceu 11/11/2026. Os botões "Propor revalidação" estão lá, mas nada foi revalidado.
7. **Nada medido.** Tokens, latência p50/p95, CPU/RAM da VPS e chamadas de modelo estão como "Não medido" em todas as tarefas do QG e na LOJA-01. Nenhuma métrica real para validar capacidade, teto de contexto ou cliente gratuito.
8. **Evidência fraca da MEM-001.** A única proposta de inventário (p-1, 2 vCPU e 4 GB) vem de conversa de suporte e do painel do provedor, sem medição e sem evidência cadastrada. Aceitá-la seria registrar capacidade com base em conversa, não em medição.
9. **Decisão de teto sem evidência.** A proposta p-3 (800 alvo / 1.600 máximo) também está "Sem evidência" e com "Aprovar" desativado; o teto de 1.600 B é praticado sem a decisão aprovada que o justificaria.
10. **Aprovação inconsistente.** p-2 tem "Aprovar" habilitado sem checkbox de confirmação de leitura; p-3 e p-1 exigem o checkbox. O único controle de revisão humana visível é esse checkbox auto-declarado, sem identidade de revisor.
11. **Sem identidade, autoria real ou autenticação.** Todos os autores são de demonstração ("Assistente gratuito (demo)", "Orquestrador QG (demo) (Sistema)", "Equipe (demo)"). Não há usuário logado, papéis, permissões, nem trilha de quem aprovou o quê — só "operation_id" e "expected_revision: 18".
12. **LIVRE-01 é um buraco no modelo.** Sem contrato, sem objetivo, sem estado conhecido, "coverage: unassessed". Perguntas abertas não geram ficha utilizável pelo modelo.
13. **Fila de revisão enganosa.** "Revisar propostas 3" é a mesma em todas as tarefas; nada indica a qual tarefa cada proposta pertence sem abrir os detalhes. Em LIVRE-01, que não tem contrato, as mesmas 3 propostas aparecem.
14. **Escopo minúsculo e fictício.** QG tem 32 memórias (28 aprovadas, 3 propostas, 1 substituída) e a Loja, 6 — todas de demonstração, com datas de 02 a 12/11/2026. Não há sincronização, persistência real, exportação, backup ou API visível.

## 9. O que falta para virar a fonte única de inteligência de todas as IAs

- **Backend real.** O FastAPI/Mongo de referência citado na V3 não está no arquivo; faltam código, endpoints, modelo de dados, migrações (a regra é "apenas aditivas", mas não há esquema para aplicar isso) e a "integração verificada" não pode ser conferida aqui.
- **Dados reais e vivos.** Medir a VPS (MEM-001), resolver a topologia do Mongo, executar o piloto de 30 consultas da MEM-011 e substituir o relógio fixo de 12/11/2026, 15:00 por dados com validade real.
- **Autenticação e governança.** Login, papéis (quem pode propor/aprovar), identidade dos autores e revisores, trilha de auditoria e resolução das aprovações travadas (p-1 e p-3) e da contradição da MEM-005.
- **Ferramentas, skills e organograma.** Não existe nada disso no arquivo — as buscas por "ferramenta" e "habilidade" retornam 0 resultados; não há catálogo de ferramentas, registro de skills, organograma, equipes ou responsabilidades. Apesar de o usuário chamar o projeto de "MCP project", **não há nenhum servidor/cliente MCP, lista de tools, protocolo ou credencial visível no arquivo.**
- **Decisões pendentes que travam o modelo.** Credencial somente leitura da VPS; escolha replica set vs. standalone; teto de 1.600 B vs. 1.647 B obrigatórios da MEM-011; cumprimento ou reescrita da regra que depende da inexistente MEM-015; revalidação das restrições e do cronograma vencidos.
- **Qualidade de busca para IA.** A busca atual é por termos com destaque e ordenação por termo e data; embeddings estão explicitamente proibidos no caminho de leitura pela restrição do projeto, então não há busca semântica, ranqueamento por relevância real nem resumo — só o "Bloco de contexto entregue ao modelo" por tarefa, limitado pelo teto de bytes.
- **Operação.** Métricas (tokens, latência p50/p95, CPU/RAM, chamadas de modelo), monitoramento, backup, exportação e um segundo projeto de exemplo (Loja) isolado, sem relação com o QG.

## 10. Resumo

O arquivo é um protótipo de interface bem estruturado — com o modelo de memória, contratos ("retomar.v1", "implementar.v1", "verificar.v1"), tetos, revisão de propostas e rastreabilidade por "source_ref" e "operation_id" — mas, hoje, é uma demonstração com dados fictícios, 3 propostas pendentes, 2 bloqueios de medição, 1 contradição não resolvida, 1 tarefa acima do teto e nenhum backend, dado real, usuário, ferramenta, skill ou organograma dentro dele.

## 11. Integração dos 15 MCPs + Obsidian (levantamento, 2026-11-13)

Fonte: lista DNACX "Os 15 MCPs com mais estrelas no GitHub" (medido em 07/11/2026) + Obsidian, pedido por Will em 2026-11-13. O MCP principal é o **Memória QG**; os 15 entram nele como tools/skills. **Pendente:** "Omni", "Omni Rhodes", "Omnihaut" e "Red Room"/"Head Room" — entram aqui quando Will mandar o link do vídeo.

### Os 15, por categoria, e o que cada um agrega ao Memória QG

**Entender o código**
- **Context7** (64.316★) — documentação sempre atualizada. Agrega: as IAs consultam docs atuais sem depender de memória gravada.
- **Codebase Memory** (48.287★) — mapa local do código. Agrega: mapa do projeto para o backend real que ainda será construído.
- **Code Review Graph** (32.630★) — mostra o que cada mudança afeta. Agrega: impacto de cada alteração antes de aprovar.

**Agir no código**
- **GitHub MCP Server** (34.300★) — repositórios, issues e PRs. Agrega: ligar o Memória QG ao repositório privado (pendente) e ao fluxo de PRs da reconstrução.
- **Serena** (31.180★) — busca e edita código por símbolo. Agrega: edição precisa no backend sem reescrever arquivos inteiros.
- **Desktop Commander** (10.246★) — arquivos e terminal por IA. ⚠️ **Risco alto:** deixa a IA rodar código no programa — trancar permissões antes de ligar.

**Navegador e apps**
- **Chrome DevTools MCP** (54.930★) — analisa um Chrome de verdade. Agrega: inspecionar o painel e o site real.
- **Playwright MCP** (39.302★) — navega e clica em sites. Agrega: automação de navegação e testes de interface.
- **Mobile MCP** (10.382★) — usa apps de celular. Agrega: operar os apps no A21s dedicado (WhatsApp, OLX, Mercado Livre).

**Dados e automação**
- **n8n-mcp** (23.227★) — monta automações no n8n. Agrega: fluxos entre as IAs e os sistemas.
- **MCP Toolbox** (16.821★) — consulta bancos de dados. Agrega: consultas diretas ao Mongo do Memória QG (resolve a medição que hoje é manual).
- **Apify** (15.166★) — extrai dados da internet. Agrega: coleta de dados externos para a memória.

**Design e computador**
- **MCP for Blender** (33.534★) — cria modelos 3D.
- **Figma Context** (16.174★) — transforma design em código. Agrega: ligar o Figma (Operator Platform e Memória QG) ao código.
- **Windows MCP** (11.253★) — opera o computador Windows. ⚠️ **Risco alto:** acesso total à máquina — trancar permissões antes de ligar.

### Obsidian
- **Obsidian** — second brain / base de conhecimento. Agrega: vault com CLAUDE.md (informações e preferências do negócio), pastas de referência por tema, busca indexada que economiza tokens. Complementa o Memória QG: o Obsidian guarda o conhecimento de longo prazo e o QG guarda a memória por tarefa com contratos e revisão.
- Para ligar: informar onde fica o vault, instalar o conversor/CLI do Obsidian e as skills de Obsidian do Kepano (GitHub).

### Condições e decisões antes de instalar

- **Host MCP:** precisa de um programa que fale MCP, como o Claude Code. O Memória QG hoje é só um protótipo no Figma — o servidor MCP real ainda será construído; os 15 plugam no host, não no arquivo do Figma.
- **Um por vez:** instalar vários de uma vez torna difícil saber qual está fazendo o quê (orientação da própria DNACX).
- **Permissão mínima:** cada MCP acessa só o que for liberado; alguns documentam coleta de dados de uso. Desktop Commander e Windows MCP exigem lockdown antes de ligar.
- **Regra em conflito:** o projeto proíbe LLM, embeddings e GPU no caminho de leitura. Isso bloqueia busca semântica e limita o ganho de Codebase Memory/Context7 — decidir se a regra se mantém, se muda, ou se esses dois operam fora do caminho de leitura.
- **Ordem sugerida:** (1) GitHub MCP Server + Serena + Codebase Memory (base do rebuild); (2) MCP Toolbox + Context7 (dados e docs); (3) Figma Context + Playwright + Chrome DevTools (interface); (4) n8n-mcp + Apify (automação e coleta); (5) Mobile MCP (A21s); (6) Desktop Commander e Windows MCP por último, com permissões trancadas; (7) Blender quando houver demanda 3D. Obsidian em paralelo, como base de conhecimento.
- **Passos de instalação:** cada MCP tem página na DNACX com o passo a passo montado do README oficial, o primeiro teste e os cuidados declarados pelo repositório — usar essas páginas como base na hora de instalar.

### As duas skills de três letrinhas que complementam o MCP: RAG e A2A (confirmadas por Will, 2026-11-13)
- **RAG** (Retrieval-Augmented Generation) — a IA busca a informação relevante numa base externa (documentos, banco, memória) antes de responder, em vez de depender só do que foi treinado. No Memória QG: é o mecanismo de busca da memória — hoje a busca é só por termos; o RAG traria recuperação por relevância. ⚠️ **Conflito com a regra do projeto:** o RAG típico usa embeddings/vetores, e o projeto proíbe embeddings no caminho de leitura — decidir se a regra muda ou se o RAG opera fora desse caminho.
- **A2A** (Agent-to-Agent) — protocolo do Google (150+ organizações, Linux Foundation) para agentes se comunicarem e delegarem tarefas entre si, com Agent Cards descrevendo o que cada agente faz. No QG: é a coordenação entre Luna, Lu, Zero, Codex e Jarvis — o MCP dá as ferramentas a cada agente, o A2A deixa um agente delegar ao outro.
- Juntos, MCP + RAG + A2A formam o trio clássico: MCP liga o agente às ferramentas e dados, RAG fundamenta as respostas no conhecimento, A2A coordena os agentes entre si. Alternativas de três letras, caso não sejam essas: ACP (Agent Communication Protocol, da IBM — se sobrepõe ao A2A) e LLM (o modelo em si, não uma skill).

### Cartographer (skill adicional, pedida por Will, 2026-11-13)
- **Cartographer** — skill/plugin do Claude Code que mapeia e documenta codebases de qualquer tamanho usando subagentes em paralelo (Opus planeja, Sonnets analisam os arquivos). Gera `docs/CODEBASE_MAP.md` com diagramas Mermaid de arquitetura, guias de módulos, propósitos de arquivos, dependências e fluxos de dados, e atualiza o `CLAUDE.md` com um resumo apontando para o mapa. Serve para onboarding, auditoria de arquitetura e manter a documentação atualizada sem estourar o contexto.
- **No Memória QG / auditoria do servidor:** é a ferramenta para mapear tudo que existe no servidor antes de compactar e unificar — o mapa que a auditoria da tarde precisa. Combina com Codebase Memory (mapa local) e com o RAG (o mapa alimenta a recuperação).
- **Instalação:** `claude plugins install cartographer` ou `git clone https://github.com/bootoshi/cartographer.git ~/.claude/skills/cartographer`. Projeto pequeno (2 estrelas no GitHub) — validar antes de adotar como peça central.

### claude-mem (confirmado por Will, 2026-11-13 — era o "Cloudman / Cloud Man / Cloud Main" + "M E M")
- **claude-mem** — plugin open source do Claude Code que dá memória persistente entre sessões: captura automaticamente o que o agente faz (hooks de ciclo de vida: SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd), comprime as observações com IA (~1.000–10.000 tokens → ~500) e injeta o contexto relevante na próxima sessão. Armazena tudo localmente em `~/.claude-mem/` (SQLite + busca full-text FTS5, com ChromaDB opcional para busca vetorial). Repo: https://github.com/thedotmack/claude-mem (site cmem.ai, docs docs.claude-mem.ai). Muito popular (dezenas de milhares de estrelas — fontes divergem entre ~21 mil e ~102 mil em out/2026). Licença: AGPL-3.0 originalmente, relicenciado Apache-2.0 na v13 (2026-05-08).
- **Instalação:** `npx claude-mem install` ou dentro do Claude Code: `/plugin marketplace add thedotmack/claude-mem` e `/plugin install claude-mem`. Requer Node.js 18+ e Bun; worker local na porta 37777 com visualizador web; funciona também em Cursor, Windsurf, OpenCode, Codex CLI e OpenClaw.
- **No Memória QG:** é a camada de memória do Claude Code — complementa o QG (que é memória por tarefa com contratos e revisão humana). ⚠️ **Conflitos com as regras do projeto:** (1) a busca vetorial opcional usa embeddings — mesma decisão pendente do RAG (regra "sem embeddings no caminho de leitura"); sem o Chroma, a busca é só full-text; (2) a compressão das observações manda o conteúdo para o provedor de IA escolhido (custo ~US$0,15 por 100 observações) — decidir qual provedor e o que pode ir; (3) o worker expõe uma API HTTP sem autenticação no localhost:37777 — trancar antes de rodar no servidor compartilhado. Cuidado: o Claude Code já tem memória automática nativa desde v2.1.59 (MEMORY.md por projeto) — avaliar se o claude-mem agrega ou duplica.
- **CMEM Pro** (US$30/mês após 30 dias de trial) adiciona sync em nuvem e recall de outros clientes — não necessário para começar; a versão local gratuita basta.

### Paperclip AI (confirmado por Will, 2026-11-13 — ele perguntou se a Luna consegue usar)
- **Paperclip AI** — app open source (MIT), self-hosted (servidor Node.js + UI React) que organiza um time de agentes de IA como se fosse uma empresa: organograma, metas, tickets, orçamentos mensais e aprovações humanas, tudo num dashboard. Frase do README: "If OpenClaw is an employee, Paperclip is the company." Repo: https://github.com/paperclipai/paperclip (Paperclip Labs, criador "Dotta"), criado em 02/03/2026, **100 mil+ estrelas** (105.230 em 21/10/2026, 17.523 forks). Docs: docs.paperclip.ing.
- **Como funciona:** você traz os seus agentes (Claude Code, Codex, Cursor, Gemini CLI, OpenCode, OpenClaw, Pi, Hermes, Grok Build, Kimi Code — qualquer runtime que receba um heartbeat) e contrata eles para papéis (CEO, CTO, engenheiros, designers, marketing). Dá a meta, o CEO decompõe em tarefas, os agentes trabalham sozinhos e você acompanha tudo (tarefas, progresso, gasto de tokens por agente) e aprova/pausa. Teste rápido: `npx paperclipai test-drive`.
- **No Memória QG / operação do Will:** é o **organograma** que faltava no projeto (a auditoria §9 apontou: não existe org chart no arquivo) — e a camada de orquestração para o plano dos 10 agentes. Combina com o A2A (coordenação entre agentes) e com o claude-mem (cada agente lembra do seu contexto). Candidato a ser a peça central da auditoria da tarde: instalar no VPS e contratar Luna, Lu, Zero, Codex e Jarvis como time.
- **Custos e cuidados:** o software é grátis, mas os agentes não são — a doc estima **US$20 a US$100+/mês** em gasto com os provedores de modelo para um time ativo. Humano continua revisando a estratégia, definindo orçamentos e aprovando as execuções — não é "liga e esquece". ⚠️ **Segurança:** 12 advisories de segurança no GitHub em out/2026, 5 críticos — revisar e atualizar antes de expor no servidor. "Se você tem um agente só, provavelmente não precisa do Paperclip."
- **A Luna consegue usar?** Não como skill dentro do Muse — o Paperclip é um servidor que roda numa máquina (laptop, Docker ou VPS) e orquestra agentes de CLI (Claude Code, Codex...). A Luna pode instalar e configurar ele no VPS na auditoria da tarde e operar o time por ele. Existe também uma SKILL.md de Paperclip (repo Burst37/web-agent) descrevendo o uso — útil como referência.

### Red Room / "Head Room" — pendente de identificação (Will, 2026-11-13)
- Will esclareceu: **não é "red" de vermelho** — é "red"/"head", **cabeça**. Descrição dele: uma "sala de cabeça" que **faz uma síntese do prompt antes de enviar para o agente**. Nenhum resultado nas buscas por "Red Room" ou "Head Room" como skill/MCP. Pendente: Will mandar o link do vídeo para identificar.
- Ainda pendentes de identificação: "Omni", "Omni Rhodes" e "Omnihaut" — buscas não acharam skill/MCP com esses nomes. Pendente o link do vídeo.

